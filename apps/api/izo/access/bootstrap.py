"""Explicit isolated initial ACCESS owner provisioning; never executed on startup or HTTP."""
import argparse
import os
from uuid import UUID

from ..accounts.repository import create_auth_engine
from ..accounts.service import AuthService
from ..accounts.settings import AuthSettings
from ..config import Settings
from .permissions import GLOBAL_DELEGABLE
from .service import AccessService


def main():
    parser = argparse.ArgumentParser(description="Enroll one existing verified initial access owner")
    parser.add_argument("--account", required=True, type=UUID)
    parser.add_argument("--permission", action="append", choices=GLOBAL_DELEGABLE)
    args = parser.parse_args()
    config = Settings()
    if config.environment not in {"development", "test"} or os.getenv("IZO_ACCESS_BOOTSTRAP") != "isolated":
        raise SystemExit("Only explicit isolated access-owner enrollment is allowed")
    engine = create_auth_engine(config)
    try:
        selected = tuple(args.permission) if args.permission else GLOBAL_DELEGABLE
        AccessService(AuthService(engine, AuthSettings())).enroll_local_owner(args.account, selected)
        print("LOCAL_ACCESS_OWNER_ENROLLED: known global permissions and matching delegation ceilings")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
