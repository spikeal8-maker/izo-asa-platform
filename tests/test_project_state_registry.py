from __future__ import annotations
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))

from project_state import load_plan,serialize_plan,show_package
from project_state_decision import decided_transition


def test_machine_plan_stays_compact_enough_for_agent_context():
    source=load_plan(ROOT)
    text=serialize_plan(source)
    live=json.loads(text)
    assert "packages" not in live
    assert "status_meaning" not in live
    assert live["packages_ref"]=="PACKAGES.json"
    assert (ROOT/"docs/PLAN.json").read_text(encoding="utf-8")==text
    assert len(text.encode("utf-8"))<=4_000
    assert len(text.encode("utf-8"))<6_000


def test_live_plan_growth_is_bounded_across_multiple_successor_transitions():
    source=load_plan(ROOT)
    sizes=[len(serialize_plan(source).encode("utf-8"))]
    for index in range(6):
        package_id=f"TEST-GROW-{index:03d}"
        head=f"{index + 1:040x}"
        source=decided_transition(
            source,
            candidate={"id":package_id,"goal":"growth fixture",
                       "depends_on":[source["active_package"]],"decides_next":True},
            new_branch=f"test/grow-{index:03d}",source_head=head,
            evidence={"source_head":head},
        )
        sizes.append(len(serialize_plan(source).encode("utf-8")))
    assert max(sizes)<6_000
    assert max(sizes)-min(sizes)<256


def test_show_package_returns_bounded_direct_dependency_slice():
    source=load_plan(ROOT)
    result=show_package(source,source["active_package"])
    assert result["package_id"]==source["active_package"]
    assert set(result)=={"package_id","package","dependencies"}
    assert set(result["dependencies"])==set(result["package"].get("depends_on",[]))
    assert "DOC-001" not in result["dependencies"]
