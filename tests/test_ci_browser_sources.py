"""Execute the CI helper against temporary files only; never touch /etc."""
from pathlib import Path
import runpy
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "tools/ci_browser_sources.py"


def chrome_cleanup():
    return runpy.run_path(str(HELPER))["disable_unused_chrome"]


@pytest.mark.parametrize('entry', [
    'deb [arch=amd64] https://dl.google.com/linux/chrome/deb/ stable main',
    'deb https://dl.google.com/linux/chrome-stable/deb stable main',
    'deb [arch=amd64 signed-by=/usr/share/keyrings/google.gpg] http://dl.google.com/linux/chrome/deb/ stable main',
])
def test_ci_disables_only_the_dedicated_unused_chrome_feed(tmp_path, entry):
    source = tmp_path/'google-chrome.list'
    contents = '# Installed by Chrome package\n' + entry + '\n'
    source.write_text(contents)
    ubuntu = tmp_path/'ubuntu.sources'
    ubuntu.write_text('Signed Ubuntu repositories must remain unchanged')
    chrome_cleanup()(tmp_path)
    assert not source.exists()
    assert (tmp_path/'google-chrome.list.izo-disabled').read_text() == contents
    assert ubuntu.read_text() == 'Signed Ubuntu repositories must remain unchanged'


@pytest.mark.parametrize('entry', [
    '',
    'deb https://archive.ubuntu.com/ubuntu noble main',
    'deb https://dl.google.com/linux/chrome/deb stable main\ndeb https://archive.ubuntu.com/ubuntu noble main',
    'deb https://dl.google.com.example.invalid/linux/chrome/deb stable main',
])
def test_ci_source_cleanup_fails_closed_for_unexpected_contents(tmp_path, entry):
    source = tmp_path/'google-chrome.list'
    source.write_text(entry)
    with pytest.raises(RuntimeError, match='Unexpected Chrome source contents'):
        chrome_cleanup()(tmp_path)
    assert source.read_text() == entry


def test_ci_source_cleanup_accepts_absent_feed_but_rejects_symlink(tmp_path):
    cleanup = chrome_cleanup()
    cleanup(tmp_path)
    other = tmp_path/'untouched.list'
    other.write_text('Do not change')
    (tmp_path/'google-chrome.list').symlink_to(other)
    with pytest.raises(RuntimeError, match='symlink'):
        cleanup(tmp_path)
    assert other.read_text() == 'Do not change'


def test_ci_source_cleanup_refuses_to_overwrite_backup(tmp_path):
    (tmp_path/'google-chrome.list').write_text('deb https://dl.google.com/linux/chrome/deb stable main')
    backup = tmp_path/'google-chrome.list.izo-disabled'
    backup.write_text('Existing backup')
    with pytest.raises(RuntimeError, match='backup already exists'):
        chrome_cleanup()(tmp_path)
    assert backup.read_text() == 'Existing backup'


def test_ci_retains_browser_checks_and_package_integrity():
    workflow = (ROOT/'.github/workflows/ci.yml').read_text()
    assert workflow.index('ci_browser_sources.py') < workflow.index('npx playwright install --with-deps chromium')
    assert 'IZO_CI_BROWSER_SETUP=isolated' in workflow
    assert 'npm run test:e2e' in workflow and 'admin-live.mjs' in workflow
    for forbidden in ('--allow-unauthenticated', 'AllowInsecureRepositories', 'trusted=yes',
                      'Verify-Peer=false', 'Check-Valid-Until=false', 'apt-get update || true'):
        assert forbidden not in workflow


DEB822 = '''Types: deb
URIs: https://dl.google.com/linux/chrome-stable/deb/
Suites: stable
Components: main
Architectures: amd64
Signed-By: /usr/share/keyrings/google-chrome.gpg
'''


@pytest.mark.parametrize('name', ['google-chrome.sources', 'google-chrome-stable.sources', 'vendor.sources'])
def test_deb822_discovered_by_content_not_fixed_filename(tmp_path, name):
    source = tmp_path/name
    source.write_text(DEB822)
    ubuntu = tmp_path/'ubuntu.sources'
    ubuntu.write_text('Types: deb\nURIs: https://archive.ubuntu.com/ubuntu\nSuites: noble\nComponents: main\n')
    before = ubuntu.read_bytes()
    assert chrome_cleanup()(tmp_path) == (name,)
    assert source.with_suffix('.sources.izo-disabled').read_bytes() == DEB822.encode()
    assert ubuntu.read_bytes() == before
    assert chrome_cleanup()(tmp_path) == ()


@pytest.mark.parametrize('name', ['google-chrome-stable.list', 'vendor.list'])
def test_alternative_list_name_is_discovered(tmp_path, name):
    (tmp_path/name).write_text('deb https://dl.google.com/linux/chrome-stable/deb/ stable main')
    assert chrome_cleanup()(tmp_path) == (name,)


@pytest.mark.parametrize('text', [
    DEB822 + '\nTypes: deb\nURIs: https://archive.ubuntu.com/ubuntu\nSuites: noble\nComponents: main\n',
    DEB822.replace('URIs: ', 'URIs: https://archive.ubuntu.com/ubuntu '),
    DEB822.replace('dl.google.com/', 'dl.google.com.evil.invalid/'),
    DEB822.replace('Suites: stable', 'Suites: stable testing'),
    DEB822.replace('Types: deb', 'Types: rpm'),
    DEB822 + 'URIs: https://dl.google.com/linux/chrome/deb\n',
    DEB822.replace('Components: main', 'Malformed field'),
])
def test_deb822_mixed_or_ambiguous_file_is_never_disabled(tmp_path, text):
    source = tmp_path/'google-chrome.sources'
    source.write_text(text)
    with pytest.raises(RuntimeError, match='contents'):
        chrome_cleanup()(tmp_path)
    assert source.read_text() == text
    assert not source.with_suffix('.sources.izo-disabled').exists()


def test_all_candidates_validated_before_first_change(tmp_path):
    valid = tmp_path/'a-chrome.sources'
    valid.write_text(DEB822)
    invalid = tmp_path/'z-chrome.list'
    invalid.write_text('Not a dedicated Chrome feed')
    with pytest.raises(RuntimeError):
        chrome_cleanup()(tmp_path)
    assert valid.read_text() == DEB822
    assert invalid.exists()


def test_deb822_continuations_comments_and_two_stanzas(tmp_path):
    contents = '# Header\n' + DEB822.replace('URIs: ', 'URIs:\n ').replace(
        'Signed-By: /usr/share/keyrings/google-chrome.gpg',
        'Signed-By:\n -----BEGIN PGP PUBLIC KEY BLOCK-----\n .\n public-test-data\n -----END PGP PUBLIC KEY BLOCK-----')
    contents += '\n' + DEB822 + 'Enabled: no\n'
    source = tmp_path/'google-chrome.sources'
    source.write_text(contents)
    chrome_cleanup()(tmp_path)
    assert source.with_suffix('.sources.izo-disabled').read_text() == contents


def test_main_requires_explicit_isolated_opt_in(monkeypatch):
    monkeypatch.delenv('IZO_CI_BROWSER_SETUP', raising=False)
    result = subprocess.run([sys.executable, str(HELPER)], capture_output=True, text=True, timeout=5)
    assert result.returncode != 0
    assert 'Explicit isolated CI setup is required' in result.stderr
