from __future__ import annotations

import sys

from typing import (
    Any,
)

DEBUG = 10
INFO = 20
WARNING = 30
ERROR = 40
CRITICAL = 50

_level_to_name = {
    DEBUG: "DEBUG",
    INFO: "INFO",
    WARNING: "WARNING",
    ERROR: "ERROR",
    CRITICAL: "CRITICAL",
}

min_log_level = CRITICAL + 1


def basicConfig(*, level: int = INFO) -> None:
    global min_log_level
    min_log_level = level


def log(level: int, msg: str, args: dict[str, Any] = {}) -> None:
    if level < min_log_level:
        return

    level_name = _level_to_name[level]
    sys.stderr.write(f"{level_name}:root:{msg % args}\n")


def debug(msg: str, args: dict[str, Any] = {}) -> None:
    log(DEBUG, msg, args)


def info(msg: str, args: dict[str, Any] = {}) -> None:
    log(INFO, msg, args)


def warning(msg: str, args: dict[str, Any] = {}) -> None:
    log(WARNING, msg, args)


def error(msg: str, args: dict[str, Any] = {}) -> None:
    log(ERROR, msg, args)


def critical(msg: str, args: dict[str, Any] = {}) -> None:
    log(CRITICAL, msg, args)
