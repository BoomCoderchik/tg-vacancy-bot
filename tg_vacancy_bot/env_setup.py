from __future__ import annotations

from pathlib import Path


def init_env_file(example_path: str = ".env.example", env_path: str = ".env") -> str:
    source = Path(example_path)
    target = Path(env_path)
    if not source.exists():
        raise RuntimeError(f"Missing {example_path}; cannot create {env_path}.")
    if target.exists():
        raise RuntimeError(f"{env_path} already exists; refusing to overwrite it.")

    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    return f"Created {env_path}. Fill TELEGRAM_BOT_TOKEN and TARGET_CHAT_ID before running the bot."
