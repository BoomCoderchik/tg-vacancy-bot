from __future__ import annotations


def parse_operator_user_ids(raw_value: str) -> tuple[int, ...]:
    ids: list[int] = []
    for item in raw_value.replace(";", ",").split(","):
        value = item.strip()
        if not value:
            continue
        try:
            ids.append(int(value))
        except ValueError as exc:
            raise RuntimeError(f"Invalid OPERATOR_USER_IDS value: {value}") from exc
    return tuple(dict.fromkeys(ids))


def is_authorized_user(user_id: int | None, operator_user_ids: tuple[int, ...]) -> bool:
    """Return whether ``user_id`` may publish through the bot.

    Access is closed by default: an empty ``OPERATOR_USER_IDS`` allowlist means
    nobody can publish or manage filters. Otherwise any Telegram user who can
    write to the bot could push messages into the target channel. Operators
    discover their ID with ``/whoami`` (which stays public) and add it to
    ``OPERATOR_USER_IDS`` before the bot accepts commands from them.
    """
    if user_id is None or not operator_user_ids:
        return False
    return user_id in operator_user_ids


def unauthorized_reply_text(operator_user_ids: tuple[int, ...]) -> str:
    """Explain a denied request without revealing the allowlist itself."""
    if not operator_user_ids:
        return (
            "Not authorized: OPERATOR_USER_IDS is empty, so publishing is locked. "
            "Send /whoami, put your ID into OPERATOR_USER_IDS and restart the bot."
        )
    return "Not authorized."
