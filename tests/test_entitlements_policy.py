"""Entitlements demand/runtime/usage policy boundary tests."""
from uuid import uuid4

import pytest
from pydantic import ValidationError

from izo.credits.schemas import Reserve, Release
from izo.entitlements.schemas import ImageSize, PublishPlan
from test_entitlements_support import env, policy, publish, default, demand, usage, runtime, setup


@pytest.mark.parametrize('data,code', [
    ({'capability_id':'image.other'},'plan_restricted'),
    ({'size':ImageSize(width=1024,height=1024)},'image_size_restricted'),
    ({'input_count':3,'largest_input_bytes':50},'input_limit'),
    ({'input_count':1,'largest_input_bytes':101},'input_limit'),
    ({'input_count':0,'largest_input_bytes':1},'invalid_input_usage'),
    ({'reserve_credits':101},'action_budget_exceeded'),
])
def test_demand_limits(env, data, code):
    engine, svc, owner, *_ = env
    with engine.begin() as conn:
        setup(conn, env)
        assert svc.assess_image(conn, owner, demand(**data), runtime(), usage(owner)).code == code


@pytest.mark.parametrize('data,code', [
    ({'active_jobs':2},'concurrency_limit'), ({'submissions':10},'rate_limited'),
    ({'committed_bytes':900,'reserved_bytes':1},'storage_quota_exceeded'),
    ({'as_of':1999},'usage_unavailable'), ({'as_of':2001},'usage_unavailable'),
    ({'window_seconds':61},'usage_unavailable'), ({'account_id':uuid4()},'usage_unavailable'),
])
def test_usage_limits_and_owner(env, data, code):
    engine, svc, owner, *_ = env
    with engine.begin() as conn:
        setup(conn, env)
        assert svc.assess_image(conn, owner, demand(), runtime(), usage(owner, **data)).code == code


def test_missing_usage_is_not_zero(env):
    engine, svc, owner, *_ = env
    with engine.begin() as conn:
        setup(conn, env)
        assert svc.assess_image(conn, owner, demand(), runtime()).code == 'usage_unavailable'


@pytest.mark.parametrize('data,code', [
    ({'feature_enabled':False},'feature_unavailable'),
    ({'capability_supported':False},'capability_unsupported'),
    ({'provider_available':False},'provider_unavailable'),
])
def test_provider_or_feature_not_replaced_with_silent_fallback(env, data, code):
    engine, svc, owner, *_ = env
    with engine.begin() as conn:
        setup(conn, env)
        assert svc.assess_image(conn, owner, demand(), runtime(**data), usage(owner)).code == code
        assert svc.assess_image(conn, owner, demand(executor='local'), runtime(), usage(owner)).allowed


def test_balance_reserve_is_read_from_real_credit_module(env):
    engine, svc, owner, _, staff, _, credits = env
    with engine.begin() as conn:
        setup(conn, env)
        hold = Reserve(operation_id=uuid4(), reservation_id=uuid4(), request_id=uuid4(), amount=95)
        credits.reserve(conn, owner, hold)
        assert svc.assess_image(conn, owner, demand(), runtime(), usage(owner)).code == 'insufficient_credits'
        credits.release(conn, owner, Release(operation_id=uuid4(), reservation_id=hold.reservation_id))
        assert svc.assess_image(conn, owner, demand(), runtime(), usage(owner)).allowed


@pytest.mark.parametrize('data', [
    {'active_jobs':True}, {'submissions':-1}, {'storage_bytes':None},
    {'upload_bytes':1001,'storage_bytes':1000}, {'max_action_credits':1.5},
    {'active_jobs':'2'}, {'role':'admin'}, {'executors':('other',)},
    {'capability_ids':('image.test','image.test')}, {'can_publish':'yes'},
    {'image_sizes':(ImageSize(width=1,height=1),)*2}, {'window_seconds':0},
])
def test_malformed_policy_rejected(data):
    with pytest.raises(ValidationError): policy(**data)


def test_frozen_policy_revalidates_forged_copy(env):
    bad = policy().model_copy(update={'active_jobs':-1})
    with pytest.raises(ValidationError):
        PublishPlan(operation_id=uuid4(), reason='test', revision_id=uuid4(),
                    plan_code='basic', revision=1, policy=bad)
