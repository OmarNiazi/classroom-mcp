"""Command line entry point: `classroom-mcp [serve|login|logout|status]`."""

import argparse
import asyncio
import logging
import sys

from . import __version__


def _force_utf8_stdio():
    # On Windows Python gives stdio the console codepage (cp1252 here), and one
    # non-Latin-1 character -- an arrow, a curly quote, an emoji -- raises
    # UnicodeEncodeError on write. In mcp 1.0 that killed the whole server from
    # inside the stdio transport (ADR-005). mcp >= 1.30 wraps the protocol streams
    # in UTF-8 itself; this still covers stderr logging and the CLI's own output.
    # Must run before anything touches the streams.
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8")
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def _login():
    from . import auth

    if auth.current_credentials() is not None:
        print(f"Already signed in (saved at {auth.token_path()}).")
        print("To switch accounts, run `classroom-mcp logout` first.")
        return 0

    attempt, _ = auth.start_sign_in()
    print("Opening your browser to sign in with Google...")
    print(f"If it doesn't open, visit this link:\n\n  {attempt.url}\n")
    print("If Google says it hasn't verified this app, click 'Advanced', then 'Go to ... (unsafe)'.")
    print("Leave every permission box ticked. Waiting for you to finish (Ctrl+C to cancel)...")

    attempt.wait(auth.SIGN_IN_TIMEOUT_SECONDS + 5)
    if attempt.creds is not None:
        print(f"\nSigned in. Saved to {auth.token_path()}")
        return 0
    print(f"\nSign-in didn't complete: {attempt.error}", file=sys.stderr)
    return 1


def _logout():
    from . import auth

    had_token, revoked = auth.sign_out()
    if not had_token:
        print("Not signed in; nothing to do.")
    elif revoked:
        print("Signed out. Access was revoked with Google and the saved sign-in deleted.")
    else:
        print("Saved sign-in deleted. Google couldn't be reached to revoke access; you can")
        print("remove it at https://myaccount.google.com/permissions")
    return 0


_STATUS_TEXT = {
    "added": "set up",
    "updated": "updated",
    "unchanged": "already set up",
    "removed": "removed",
    "not-present": "wasn't set up",
    "skipped": "SKIPPED",
    "failed": "FAILED",
}


def _print_results(results):
    width = max(len(r.label) for r in results)
    for r in results:
        line = f"  {r.label.ljust(width)}  {_STATUS_TEXT[r.status]}"
        if r.detail and r.status in ("skipped", "failed"):
            line += f": {r.detail}"
        print(line)


def _manual_instructions():
    from . import hosts

    command, args = hosts.launch_command()
    print("For other apps that support MCP servers, add a server with:")
    print(f"  command: {command}")
    print(f"  args:    {' '.join(args)}")


def _setup(clients):
    from . import hosts

    print("Adding classroom-mcp to the AI apps on this computer...\n")
    results = hosts.setup(clients)
    if not results:
        print("No supported apps found (Claude Desktop, Claude Code, Cursor).")
        _manual_instructions()
        return 1
    _print_results(results)
    print()

    ok = [r for r in results if r.status in ("added", "updated", "unchanged")]
    if len(ok) < len(results):
        _manual_instructions()
        print()

    code = _login()
    if ok:
        apps = sorted({r.label.split(" (")[0] for r in ok if r.label != "Claude Code"})
        print("\nAll done.", end=" ")
        if apps:
            print(f"Fully quit and reopen {' and '.join(apps)}, then", end=" ")
        print('ask: "What do I still have to hand in this week?"')
    return code if ok else 1


def _remove(clients):
    from . import hosts

    results = hosts.remove(clients)
    if not results:
        print("No supported apps found.")
        return 0
    _print_results(results)
    print("\nTo also revoke Google access and delete your sign-in, run `classroom-mcp logout`.")
    return 0 if all(r.status not in ("failed", "skipped") for r in results) else 1


def _status():
    from . import auth

    print(f"Sign-in file: {auth.token_path()}")
    creds = auth.current_credentials()
    if creds is None:
        print("Status: not signed in (run `classroom-mcp login`, or just ask your assistant).")
        return 1
    print("Status: signed in")
    print("Access: " + ", ".join(sorted(s.rsplit("/", 1)[-1] for s in creds.scopes or [])))
    return 0


def main(argv=None):
    _force_utf8_stdio()

    parser = argparse.ArgumentParser(
        prog="classroom-mcp",
        description="Google Classroom MCP server for students. With no command, serves MCP over stdio.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", metavar="command")
    commands.add_parser("serve", help="run the MCP server over stdio (the default)")
    for name, help_text in (
        ("setup", "add this server to your AI apps, then sign in"),
        ("remove", "take this server out of your AI apps"),
    ):
        sub = commands.add_parser(name, help=help_text)
        sub.add_argument(
            "--client",
            action="append",
            choices=["claude-desktop", "claude-code", "cursor"],
            help="only this app (repeatable); default: every supported app found",
        )
    commands.add_parser("login", help="sign in to Google now instead of on first use")
    commands.add_parser("logout", help="revoke access and delete the saved sign-in")
    commands.add_parser("status", help="show whether you're signed in and where it's saved")
    args = parser.parse_args(argv)

    # Logs always go to stderr: stdout carries the MCP protocol when serving.
    logging.basicConfig(stream=sys.stderr, level=logging.INFO)

    if args.command in (None, "serve"):
        from .server import serve

        asyncio.run(serve())
        return 0
    if args.command in ("setup", "remove"):
        from .hosts import CLIENTS

        clients = tuple(args.client) if args.client else CLIENTS
        return _setup(clients) if args.command == "setup" else _remove(clients)
    if args.command == "login":
        return _login()
    if args.command == "logout":
        return _logout()
    return _status()


if __name__ == "__main__":
    sys.exit(main())
