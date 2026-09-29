"""Specific web boundaries; do not claim protection of all future modules."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "apps/web/src"


def imports(path):
    return re.findall(r"(?:from\s+|import\s*\()['\"]([^'\"]+)", path.read_text(encoding="utf-8"))


def test_shared_ui_has_no_product_or_demo_dependencies():
    for path in (WEB / "shared/ui").rglob("*.tsx"):
        for name in imports(path):
            assert not any(part in name for part in ("features", "shell", "prototype")), path


def test_gallery_and_studio_are_sibling_features_not_a_dependency_cycle():
    for feature, other in (("gallery", "studio"), ("studio", "gallery")):
        for path in (WEB / "features" / feature).rglob("*.tsx"):
            assert not any(other in name for name in imports(path)), path


def test_browser_demo_is_retired_not_a_fallback_for_missing_server_data():
    assert not list((WEB / "features/prototype").glob("*.ts*"))
    for path in (WEB / "features").rglob("*.ts*"):
        assert not any("prototype" in name for name in imports(path)), path
    assert 'DemoProvider' not in (WEB / 'shell/App.tsx').read_text(encoding="utf-8")


def test_features_do_not_bypass_shared_transport():
    for path in (WEB / "features").rglob("*.ts*"):
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"\b(?:fetch|XMLHttpRequest|WebSocket)\s*\(", text), path
        assert "import.meta.env" not in text, path


def test_high_density_profiles_are_explicit():
    text = (ROOT / "apps/web/playwright.config.ts").read_text(encoding="utf-8")
    for profile in ("qhd", "uhd", "hidpi-150", "hidpi-200"):
        assert f"name: '{profile}'" in text
    assert "width: 3840, height: 2160" in text
    assert "deviceScaleFactor: 1.5" in text
    assert "deviceScaleFactor: 2" in text
