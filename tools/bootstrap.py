"""Create local development credentials once, never overwrite or print them."""
import os
import secrets
from pathlib import Path


def bootstrap(path: Path = Path(".env")) -> bool:
    values = {"IZO_ENVIRONMENT": "development", "IZO_PG_PASSWORD": secrets.token_hex(24),
              "IZO_S3_ACCESS_KEY": "izo" + secrets.token_hex(8),
              "IZO_S3_SECRET_KEY": secrets.token_hex(32), "IZO_HTTP_PORT": "8080"}
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return False
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as out:
        out.write("# Local development only. Never commit or publish this file.\n")
        out.write("".join(f"{key}={value}\n" for key, value in values.items()))
    return True


if __name__ == "__main__":
    print("Created .env for local development" if bootstrap() else "Existing .env preserved")
