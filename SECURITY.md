# Security

## Reporting a vulnerability
Please **don't** open a public issue for security problems. Use GitHub's private reporting
instead: **Security** tab → **Report a vulnerability** on
<https://github.com/OmarNiazi/classroom-mcp>. You'll get a response as soon as possible.

Especially relevant: anything that could leak a user's saved Google sign-in, let another
process or site complete or hijack the sign-in, or expose data from one Google account to
another.

## Things that are intentional
- **The OAuth client secret in `src/classroom_mcp/client_config.json` is public by design.**
  It's a Desktop-app client. Google treats these secrets as non-confidential because every
  installed copy of any desktop app has to carry one. User data is protected by each user's
  own sign-in and token, not by that secret.
- The sign-in briefly runs a web listener on `127.0.0.1` (loopback only, random port, PKCE and
  state-checked) to receive Google's redirect. It closes after sign-in or 5 minutes.
- Saved sign-ins live in the user's config directory (file mode 0600 on macOS/Linux).
