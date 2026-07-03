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
    if not operator_user_ids:
        return True
    return user_id in operator_user_ids
