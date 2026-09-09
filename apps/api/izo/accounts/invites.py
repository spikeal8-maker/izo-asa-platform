"""Trusted local operator command, not an API route. Prints a one-use invite once."""
import argparse

from izo.config import Settings
from .repository import create_auth_engine
from .service import AuthService
from .settings import AuthSettings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hours", type=int, default=24, choices=range(1, 169), metavar="1..168")
    args = parser.parse_args()
    settings = Settings()  # Only development/test are currently accepted.
    policy = AuthSettings()
    policy.require_configured()
    engine = create_auth_engine(settings)
    try:
        print(AuthService(engine, policy).issue_invite(args.hours * 3600))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
