"""Register this server with the MCP host apps on this computer (ADR-010).

Students shouldn't have to find and hand-edit JSON config files. `setup` finds
the supported apps, merges a `google-classroom` entry into each one's config
(other servers and settings are left alone, a backup is saved first), and
`remove` takes it out again.
"""

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

SERVER_NAME = "google-classroom"
PACKAGE = "classroom-mcp"

CLAUDE_DESKTOP = "claude-desktop"
CLAUDE_CODE = "claude-code"
CURSOR = "cursor"
CLIENTS = (CLAUDE_DESKTOP, CLAUDE_CODE, CURSOR)

BACKUP_SUFFIX = ".classroom-mcp.bak"


@dataclass
class JsonHost:
    client: str
    label: str
    path: Path
    key: str = "mcpServers"


@dataclass
class Result:
    label: str
    status: str  # added | updated | unchanged | removed | not-present | skipped | failed
    detail: str = ""


def launch_command():
    """What hosts should run. uvx by absolute path: apps opened from the Start
    menu or Dock often don't see the PATH that uv's installer set up.
    --managed-python keeps broken system Pythons out of it (ADR-008)."""
    uvx = shutil.which("uvx") or "uvx"
    return uvx, ["--managed-python", PACKAGE]


def json_hosts(platform=None, env=None, home=None):
    """Config files of supported JSON-configured apps that are installed."""
    platform = platform or sys.platform
    env = os.environ if env is None else env
    home = Path.home() if home is None else Path(home)

    claude_dirs = []
    if platform == "win32":
        if env.get("APPDATA"):
            claude_dirs.append(("Claude Desktop", Path(env["APPDATA"]) / "Claude"))
        if env.get("LOCALAPPDATA"):
            # The Microsoft Store build keeps its config in the package's
            # virtualised AppData instead.
            packages = Path(env["LOCALAPPDATA"]) / "Packages"
            for store_dir in sorted(packages.glob("Claude_*/LocalCache/Roaming/Claude")):
                claude_dirs.append(("Claude Desktop (Store)", store_dir))
    elif platform == "darwin":
        claude_dirs.append(("Claude Desktop", home / "Library" / "Application Support" / "Claude"))
    else:
        config_home = Path(env.get("XDG_CONFIG_HOME") or home / ".config")
        claude_dirs.append(("Claude Desktop", config_home / "Claude"))

    hosts = [
        JsonHost(CLAUDE_DESKTOP, label, directory / "claude_desktop_config.json")
        for label, directory in claude_dirs
        if directory.is_dir()
    ]
    if (home / ".cursor").is_dir():
        hosts.append(JsonHost(CURSOR, "Cursor", home / ".cursor" / "mcp.json"))
    return hosts


def _read_config(path):
    """(config, problem). A missing or empty file is an empty config."""
    if not path.exists():
        return {}, None
    try:
        raw = path.read_text(encoding="utf-8-sig")
        config = json.loads(raw) if raw.strip() else {}
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
        return None, f"couldn't read {path} ({e}); left untouched"
    if not isinstance(config, dict):
        return None, f"{path} isn't a JSON object; left untouched"
    return config, None


def _write_config(path, config):
    if path.exists():
        shutil.copy2(path, path.with_name(path.name + BACKUP_SUFFIX))
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def register_json(host, command, args):
    config, problem = _read_config(host.path)
    if problem:
        return Result(host.label, "skipped", problem)
    servers = config.setdefault(host.key, {})
    if not isinstance(servers, dict):
        return Result(host.label, "skipped", f"'{host.key}' in {host.path} isn't an object; left untouched")

    entry = {"command": command, "args": list(args)}
    if servers.get(SERVER_NAME) == entry:
        return Result(host.label, "unchanged", str(host.path))
    status = "updated" if SERVER_NAME in servers else "added"
    servers[SERVER_NAME] = entry
    try:
        _write_config(host.path, config)
    except OSError as e:
        return Result(host.label, "failed", f"couldn't write {host.path} ({e})")
    return Result(host.label, status, str(host.path))


def unregister_json(host):
    if not host.path.exists():
        return Result(host.label, "not-present")
    config, problem = _read_config(host.path)
    if problem:
        return Result(host.label, "skipped", problem)
    servers = config.get(host.key)
    if not isinstance(servers, dict) or SERVER_NAME not in servers:
        return Result(host.label, "not-present")
    del servers[SERVER_NAME]
    try:
        _write_config(host.path, config)
    except OSError as e:
        return Result(host.label, "failed", f"couldn't write {host.path} ({e})")
    return Result(host.label, "removed", str(host.path))


def _claude(*args):
    claude = shutil.which("claude")
    return subprocess.run(
        [claude, *args],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=120,
    )


def claude_code_installed():
    return shutil.which("claude") is not None


def register_claude_code(command, args):
    try:
        # `mcp add` refuses to overwrite, so replace any earlier registration.
        _claude("mcp", "remove", "--scope", "user", SERVER_NAME)
        done = _claude("mcp", "add", "--scope", "user", SERVER_NAME, "--", command, *args)
    except (OSError, subprocess.SubprocessError) as e:
        return Result("Claude Code", "failed", str(e))
    if done.returncode != 0:
        return Result("Claude Code", "failed", (done.stderr or done.stdout).strip())
    return Result("Claude Code", "added", "user scope")


def unregister_claude_code():
    try:
        done = _claude("mcp", "remove", "--scope", "user", SERVER_NAME)
    except (OSError, subprocess.SubprocessError) as e:
        return Result("Claude Code", "failed", str(e))
    if done.returncode != 0:
        return Result("Claude Code", "not-present")
    return Result("Claude Code", "removed")


def setup(clients=CLIENTS):
    command, args = launch_command()
    results = [register_json(h, command, args) for h in json_hosts() if h.client in clients]
    if CLAUDE_CODE in clients and claude_code_installed():
        results.append(register_claude_code(command, args))
    return results


def remove(clients=CLIENTS):
    results = [unregister_json(h) for h in json_hosts() if h.client in clients]
    if CLAUDE_CODE in clients and claude_code_installed():
        results.append(unregister_claude_code())
    return results
