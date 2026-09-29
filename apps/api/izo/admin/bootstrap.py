"""Explicit local-staging operator enrollment, never executed on startup or via HTTP."""
import argparse
import os
from uuid import UUID
from ..config import Settings
from ..accounts.repository import create_auth_engine
from ..accounts.settings import AuthSettings
from ..accounts.service import AuthService
from .service import AdminService


def main():
    parser = argparse.ArgumentParser(description="Enroll one existing verified account on an isolated dev/test stack")
    parser.add_argument("--account", required=True, type=UUID)
    parser.add_argument("--grant-limit", required=True, type=int)
    args = parser.parse_args()
    config = Settings()
    if config.environment not in {"development", "test"} or os.getenv("IZO_ADMIN_BOOTSTRAP") != "isolated":
        raise SystemExit("Only explicit isolated local enrollment is allowed")
    engine = create_auth_engine(config)
    try:
        AdminService(AuthService(engine, AuthSettings())).enroll_local_operator(args.account, args.grant_limit)
        print("LOCAL_OPERATOR_ENROLLED: scoped permissions and finite per-grant cap; no credits issued")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
