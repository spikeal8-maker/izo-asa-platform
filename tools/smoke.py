"""Read-only loopback smoke; never takes an arbitrary production URL."""
import json
from urllib.request import urlopen


def main() -> None:
    for path in ["/", "/studio/video", "/gallery", "/api/health/live", "/api/health/ready"]:
        with urlopen("http://127.0.0.1:8080" + path, timeout=10) as r:
            assert r.status == 200, path
    with urlopen("http://127.0.0.1:8080/api/v1/foundation", timeout=10) as r:
        data = json.load(r)
    assert data["stage"] == "foundation"
    assert len(data["capabilities"]) == 5
    assert all(not c["available"] for c in data["capabilities"])
    print("SMOKE_OK: shell, deep links, API, PostgreSQL and S3 readiness")


if __name__ == "__main__":
    main()
