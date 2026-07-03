from __future__ import annotations


def forwarded_public_post_url(message: object) -> str | None:
    origin = getattr(message, "forward_origin", None)
    if origin is None:
        return None

    chat = getattr(origin, "chat", None)
    username = getattr(chat, "username", None)
    message_id = getattr(origin, "message_id", None)
    if username and message_id:
        return f"https://t.me/{username}/{message_id}"

    return None
