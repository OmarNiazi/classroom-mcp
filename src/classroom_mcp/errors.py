"""Failures rendered as text the model can relay to the student (ADR-006)."""


def api_error_text(action, error):
    """Turn an HttpError into something the student can act on."""
    status = getattr(getattr(error, "resp", None), "status", None)
    if status == 404:
        return f"Error {action}: course not found. Check the course ID (use get_all_courses)."
    if status == 403:
        return (
            f"Error {action}: access denied by Google ({error}). "
            "This usually means the granted OAuth scopes do not cover this call."
        )
    return f"Error {action}: {error}"


def sign_in_text(url, reason=None):
    """Instructions for connecting a Google account, addressed to the student."""
    if url is None:
        return (
            f"Google Classroom sign-in didn't complete: {reason or 'unknown error.'} "
            "Ask again to get a new sign-in window."
        )

    lines = []
    if reason:
        lines.append(f"The last sign-in attempt didn't work: {reason}")
        lines.append("")
    lines += [
        "Google Classroom isn't connected yet. A browser window should have opened to sign in with Google.",
        f"If it didn't, open this link: {url}",
        "",
        "- Google may say it hasn't verified this app. Click 'Advanced', then the "
        "'Go to ... (unsafe)' link to continue.",
        "- Leave every permission box ticked. Access is read-only.",
        "- When the page says 'Connected to Google Classroom', ask your question again.",
        "- If Google says your school or organisation blocks this app, only your "
        "school's IT admin can allow it.",
    ]
    return "\n".join(lines)
