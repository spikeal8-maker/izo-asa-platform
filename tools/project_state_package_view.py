"""Read-only projection of one package and its direct dependencies."""
from __future__ import annotations

def show_package(plan: dict, package_id: str) -> dict:
    packages = plan["packages"]
    item = packages.get(package_id)
    if item is None:
        raise ValueError(f"unknown package {package_id}")
    dependencies = {
        dep: {
            key: value for key, value in packages[dep].items()
            if key in {"status", "checkpoint", "goal"}
        }
        for dep in item.get("depends_on", [])
    }
    return {"package_id": package_id, "package": item, "dependencies": dependencies}
