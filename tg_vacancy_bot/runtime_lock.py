from __future__ import annotations

import ctypes
import hashlib
import os
import sys
from pathlib import Path


class SingleInstanceLock:
    def __init__(self, lock_path: Path) -> None:
        self.lock_path = lock_path
        self._acquired = False

    def __enter__(self) -> SingleInstanceLock:
        self.acquire()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.release()

    def acquire(self) -> None:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        while True:
            try:
                fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                if self._remove_stale_lock():
                    continue
                pid = _read_lock_pid(self.lock_path)
                detail = f" PID {pid}" if pid is not None else ""
                raise RuntimeError(
                    "Another tg-vacancy-bot run process is already active"
                    f"{detail}. Stop it before starting a second polling instance."
                )

            with os.fdopen(fd, "w", encoding="utf-8") as lock_file:
                lock_file.write(f"{os.getpid()}\n")
            self._acquired = True
            return

    def release(self) -> None:
        if not self._acquired:
            return
        if _read_lock_pid(self.lock_path) == os.getpid():
            self.lock_path.unlink(missing_ok=True)
        self._acquired = False

    def _remove_stale_lock(self) -> bool:
        pid = _read_lock_pid(self.lock_path)
        if pid is not None and _pid_is_running(pid):
            return False
        self.lock_path.unlink(missing_ok=True)
        return True


def bot_run_lock_path(database_path: str, telegram_bot_token: str) -> Path:
    token_hash = hashlib.sha256(telegram_bot_token.encode("utf-8")).hexdigest()[:12]
    return Path(database_path).parent / f"tg-vacancy-bot-{token_hash}.lock"


def _read_lock_pid(lock_path: Path) -> int | None:
    try:
        first_line = lock_path.read_text(encoding="utf-8").splitlines()[0]
        return int(first_line)
    except (FileNotFoundError, IndexError, ValueError):
        return None


def _pid_is_running(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        return _windows_pid_is_running(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _windows_pid_is_running(pid: int) -> bool:
    process_query_limited_information = 0x1000
    still_active = 259
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
    if not handle:
        return False
    try:
        exit_code = ctypes.c_ulong()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            return False
        return exit_code.value == still_active
    finally:
        kernel32.CloseHandle(handle)
