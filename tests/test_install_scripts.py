"""Guards for the one-line installers, which are served raw from GitHub."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_install_ps1_survives_line_by_line_iex():
    # Some Windows PowerShell 5.1 setups make `irm ... | iex` run the script one
    # line at a time: a blank line fails ("empty string"), and a block split
    # across lines fails to parse. So: one complete statement per line.
    raw = (ROOT / "install.ps1").read_bytes()
    assert b"\r" not in raw
    assert not raw.startswith(b"\xef\xbb\xbf")
    assert not raw.endswith(b"\n"), "a trailing newline becomes an empty iex call"

    for number, line in enumerate(raw.decode("utf-8").split("\n"), 1):
        assert line.strip(), f"line {number} is blank"
        if line.lstrip().startswith("#"):
            continue
        assert line.count("{") == line.count("}"), f"line {number} splits a block"
        assert line.count("(") == line.count(")"), f"line {number} splits an expression"
        assert line.count('"') % 2 == 0, f"line {number} splits a string"


def test_install_scripts_install_the_published_package():
    for name in ("install.ps1", "install.sh"):
        text = (ROOT / name).read_text(encoding="utf-8")
        assert "uvx --managed-python classroom-mcp@latest setup" in text


def test_install_sh_is_posix_with_lf():
    raw = (ROOT / "install.sh").read_bytes()
    assert raw.startswith(b"#!/bin/sh\n")
    assert b"\r" not in raw
