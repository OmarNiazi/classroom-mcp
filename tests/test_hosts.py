import json
import subprocess

import pytest

from classroom_mcp import __main__ as cli
from classroom_mcp import hosts

CMD = r"C:\Users\Student\.local\bin\uvx.exe"
ARGS = ["--managed-python", "classroom-mcp"]


def host(tmp_path, name="claude_desktop_config.json"):
    return hosts.JsonHost(hosts.CLAUDE_DESKTOP, "Claude Desktop", tmp_path / name)


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


# --- finding apps ------------------------------------------------------------


def test_windows_finds_regular_and_store_claude_desktop(tmp_path):
    appdata, local = tmp_path / "Roaming", tmp_path / "Local"
    (appdata / "Claude").mkdir(parents=True)
    store = local / "Packages" / "Claude_abc123" / "LocalCache" / "Roaming" / "Claude"
    store.mkdir(parents=True)
    (local / "Packages" / "Claude_unused").mkdir()  # Store package with no config dir

    found = hosts.json_hosts("win32", {"APPDATA": str(appdata), "LOCALAPPDATA": str(local)}, tmp_path)
    assert [(h.label, h.path) for h in found] == [
        ("Claude Desktop", appdata / "Claude" / "claude_desktop_config.json"),
        ("Claude Desktop (Store)", store / "claude_desktop_config.json"),
    ]


def test_macos_and_linux_paths(tmp_path):
    (tmp_path / "Library" / "Application Support" / "Claude").mkdir(parents=True)
    (tmp_path / ".config" / "Claude").mkdir(parents=True)
    (tmp_path / ".cursor").mkdir()

    mac = hosts.json_hosts("darwin", {}, tmp_path)
    assert [h.path for h in mac] == [
        tmp_path / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json",
        tmp_path / ".cursor" / "mcp.json",
    ]
    linux = hosts.json_hosts("linux", {}, tmp_path)
    assert linux[0].path == tmp_path / ".config" / "Claude" / "claude_desktop_config.json"


def test_apps_that_are_not_installed_are_skipped(tmp_path):
    assert hosts.json_hosts("win32", {"APPDATA": str(tmp_path)}, tmp_path) == []


# --- registering -------------------------------------------------------------


def test_creates_config_when_missing(tmp_path):
    h = host(tmp_path)
    result = hosts.register_json(h, CMD, ARGS)
    assert result.status == "added"
    assert read(h.path) == {"mcpServers": {"google-classroom": {"command": CMD, "args": ARGS}}}
    assert not h.path.with_name(h.path.name + hosts.BACKUP_SUFFIX).exists()


def test_merges_without_touching_other_servers_or_settings(tmp_path):
    h = host(tmp_path)
    original = {
        "mcpServers": {"other": {"command": "node", "args": ["x.js"], "env": {"KEY": "v"}}},
        "preferences": {"theme": "dark", "caf\u00e9": True},
    }
    h.path.write_text(json.dumps(original), encoding="utf-8")

    assert hosts.register_json(h, CMD, ARGS).status == "added"
    config = read(h.path)
    assert config["preferences"] == original["preferences"]
    assert config["mcpServers"]["other"] == original["mcpServers"]["other"]
    assert config["mcpServers"]["google-classroom"] == {"command": CMD, "args": ARGS}
    # The original was backed up byte for byte.
    assert read(h.path.with_name(h.path.name + hosts.BACKUP_SUFFIX)) == original


def test_replaces_an_old_registration(tmp_path):
    h = host(tmp_path)
    old = {"mcpServers": {"google-classroom": {"command": "C:\\Python313\\python.exe", "args": ["server.py"]}}}
    h.path.write_text(json.dumps(old), encoding="utf-8")
    assert hosts.register_json(h, CMD, ARGS).status == "updated"
    assert read(h.path)["mcpServers"]["google-classroom"] == {"command": CMD, "args": ARGS}


def test_running_twice_changes_nothing(tmp_path):
    h = host(tmp_path)
    hosts.register_json(h, CMD, ARGS)
    before = h.path.read_bytes()
    assert hosts.register_json(h, CMD, ARGS).status == "unchanged"
    assert h.path.read_bytes() == before


def test_tolerates_bom_and_empty_files(tmp_path):
    h = host(tmp_path)
    h.path.write_bytes(b"\xef\xbb\xbf" + json.dumps({"mcpServers": {}}).encode())
    assert hosts.register_json(h, CMD, ARGS).status == "added"
    assert not h.path.read_bytes().startswith(b"\xef\xbb\xbf")

    h2 = host(tmp_path, "empty.json")
    h2.path.write_text("   \n", encoding="utf-8")
    assert hosts.register_json(h2, CMD, ARGS).status == "added"


@pytest.mark.parametrize("content", ["{not json", "[1, 2]", '{"mcpServers": []}'])
def test_never_rewrites_a_file_it_does_not_understand(tmp_path, content):
    h = host(tmp_path)
    h.path.write_text(content, encoding="utf-8")
    result = hosts.register_json(h, CMD, ARGS)
    assert result.status == "skipped"
    assert h.path.read_text(encoding="utf-8") == content


def test_remove_takes_out_only_this_server(tmp_path):
    h = host(tmp_path)
    h.path.write_text(json.dumps({"mcpServers": {"other": {"command": "x"}}, "preferences": {}}), encoding="utf-8")
    hosts.register_json(h, CMD, ARGS)

    assert hosts.unregister_json(h).status == "removed"
    assert read(h.path) == {"mcpServers": {"other": {"command": "x"}}, "preferences": {}}
    assert hosts.unregister_json(h).status == "not-present"


def test_remove_when_config_missing(tmp_path):
    assert hosts.unregister_json(host(tmp_path)).status == "not-present"


# --- Claude Code ---------------------------------------------------------------


@pytest.fixture
def fake_claude(monkeypatch):
    calls = []
    outcome = {"add": 0}

    def run(cmd, **kwargs):
        calls.append(cmd[1:])
        code = outcome["add"] if cmd[2] == "add" else 0
        return subprocess.CompletedProcess(cmd, code, stdout="", stderr="boom" if code else "")

    monkeypatch.setattr(hosts.shutil, "which", lambda name: f"/bin/{name}")
    monkeypatch.setattr(hosts.subprocess, "run", run)
    return calls, outcome


def test_claude_code_registration_replaces_previous(fake_claude):
    calls, _ = fake_claude
    result = hosts.register_claude_code(CMD, ARGS)
    assert result.status == "added"
    assert calls == [
        ["mcp", "remove", "--scope", "user", "google-classroom"],
        ["mcp", "add", "--scope", "user", "google-classroom", "--", CMD, *ARGS],
    ]


def test_claude_code_failure_is_reported(fake_claude):
    _, outcome = fake_claude
    outcome["add"] = 1
    result = hosts.register_claude_code(CMD, ARGS)
    assert result.status == "failed" and result.detail == "boom"


# --- CLI -----------------------------------------------------------------------


def test_setup_with_no_apps_prints_manual_instructions(monkeypatch, capsys):
    monkeypatch.setattr(hosts, "json_hosts", lambda: [])
    monkeypatch.setattr(hosts, "claude_code_installed", lambda: False)
    assert cli.main(["setup"]) == 1
    out = capsys.readouterr().out
    assert "No supported apps found" in out
    assert "--managed-python classroom-mcp" in out


def test_setup_registers_then_signs_in(tmp_path, monkeypatch, capsys):
    h = host(tmp_path)
    monkeypatch.setattr(hosts, "json_hosts", lambda: [h])
    monkeypatch.setattr(hosts, "claude_code_installed", lambda: False)
    monkeypatch.setattr(cli, "_login", lambda: print("[sign-in ran]") or 0)

    assert cli.main(["setup"]) == 0
    out = capsys.readouterr().out
    assert "Claude Desktop  set up" in out
    assert "[sign-in ran]" in out
    assert "Fully quit and reopen Claude Desktop" in out
    assert "google-classroom" in read(h.path)["mcpServers"]


def test_client_filter(tmp_path, monkeypatch):
    desktop = host(tmp_path)
    cursor = hosts.JsonHost(hosts.CURSOR, "Cursor", tmp_path / "mcp.json")
    monkeypatch.setattr(hosts, "json_hosts", lambda: [desktop, cursor])
    monkeypatch.setattr(hosts, "claude_code_installed", lambda: pytest.fail("not requested"))

    results = hosts.setup((hosts.CURSOR,))
    assert [r.label for r in results] == ["Cursor"]
    assert not desktop.path.exists()
