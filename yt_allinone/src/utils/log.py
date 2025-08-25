from __future__ import annotations

import os
import sys
import datetime as _dt
import logging
from typing import Any, Dict

from loguru import logger
from rich.logging import RichHandler


def _ensure_logs_dir() -> str:
    logs_dir = os.path.join(os.getcwd(), "logs")
    os.makedirs(logs_dir, exist_ok=True)
    return logs_dir


def setup_logging(level: str = "INFO") -> None:
    logger.remove()

    # File sink with rotation 10MB and retention 5 files
    logs_dir = _ensure_logs_dir()
    date = _dt.datetime.now().strftime("%Y-%m-%d")
    file_path = os.path.join(logs_dir, f"yttool_{date}.log")
    logger.add(
        file_path,
        rotation="10 MB",
        retention=5,
        enqueue=True,
        encoding="utf-8",
        level=level,
        backtrace=False,
        diagnose=False,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
    )

    # Stdlib logging with RichHandler for pretty console logs
    root_logger = logging.getLogger("yttool")
    root_logger.handlers = []
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    rich_handler = RichHandler(rich_tracebacks=False, show_time=True, show_level=True, show_path=False)
    rich_handler.setLevel(getattr(logging, level.upper(), logging.INFO))
    root_logger.addHandler(rich_handler)

    # Bridge loguru -> stdlib (which uses RichHandler)
    def _to_stdlib_sink(message):  # type: ignore[no-untyped-def]
        record = message.record
        lvl_name = record["level"].name
        lvl = getattr(logging, lvl_name, logging.INFO)
        root_logger.log(lvl, record["message"])  # pragma: no cover (formatting handled by Rich)

    logger.add(_to_stdlib_sink, level=level)


# Initialize on import
setup_logging()


def log_task_start(url: str, quality: str, only_audio: bool, filter_hint: str) -> None:
    logger.info(f"Start task url={url} quality={quality} only_audio={only_audio} filter={filter_hint}")


def log_task_end(url: str, success: bool, reason: str | None = None) -> None:
    if success:
        logger.info(f"Done task url={url} result=SUCCESS")
    else:
        logger.error(f"Done task url={url} result=FAIL reason={reason or ''}")

