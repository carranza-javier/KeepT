import io
import json
import time
from types import SimpleNamespace

from keept import updates


class Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


def opener_for(payload, seen=None):
    def opener(req, timeout=0):
        if seen is not None:
            seen.append(req)
        return Resp(json.dumps(payload).encode())

    return opener


def test_version_comparison():
    assert updates.is_newer("v1.0.1", "1.0.0")
    assert updates.is_newer("2.0.0", "1.9.9")
    assert not updates.is_newer("v1.0.0", "1.0.0")
    assert not updates.is_newer("v0.9.0", "1.0.0")
    assert updates.is_newer("v0.10.0", "0.9.0")
    assert not updates.is_newer("models-v1", "1.0.0")


def test_fetch_latest_reads_tag_and_installer():
    seen = []
    payload = [
        {"tag_name": "models-v1", "prerelease": True, "assets": []},
        {"tag_name": "v0.9.0", "prerelease": True, "html_url": "old", "assets": []},
        {"tag_name": "v0.10.0", "prerelease": True, "html_url": "https://github.com/x/releases/tag/v0.10.0",
         "assets": [{"name": "KeepT-Setup-0.10.0.exe.sha256", "browser_download_url": "a"},
                    {"name": "KeepT-Setup-0.10.0.exe", "browser_download_url": "https://dl/setup.exe"}]},
        {"tag_name": "v0.11.0", "draft": True, "assets": []},
    ]
    rel = updates.fetch_latest(opener_for(payload, seen))
    # pre-releases count (KeepT 0.x is only published as pre-release); drafts and models-v1 do not
    assert (rel.version, rel.installer_url) == ("0.10.0", "https://dl/setup.exe")
    assert seen[0].full_url == updates.RELEASES_API
    # nothing identifying is sent
    assert set(k.lower() for k in seen[0].headers) <= {"accept", "user-agent"}
    assert updates.fetch_latest(opener_for([{"tag_name": "models-v1", "assets": []}])) is None


def make_checker(payload, check_updates=True, last=0.0):
    cfg = SimpleNamespace(check_updates=check_updates, last_update_check=last)
    saved = []
    return updates.UpdateChecker(cfg, lambda: saved.append(True), opener=opener_for(payload)), cfg, saved


def test_checker_finds_newer_release_once_a_day():
    checker, cfg, saved = make_checker([{"tag_name": "v9.0.0", "prerelease": True, "html_url": "u", "assets": []}])
    assert checker.due()
    checker._run()
    assert checker.available.version == "9.0.0" and saved
    assert not checker.due()  # checked just now: not again for 24 h


def test_checker_respects_setting_and_ignores_older():
    checker, cfg, _ = make_checker([{"tag_name": "v9.0.0", "assets": []}], check_updates=False)
    assert not checker.due()
    checker, cfg, _ = make_checker([{"tag_name": "v0.1.0", "assets": []}])
    checker._run()
    assert checker.available is None
    recent, _, _ = make_checker([], last=time.time() - 3600)
    assert not recent.due()
