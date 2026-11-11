"""Retry com backoff exponencial + jitter, so para erros marcados como retryable."""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from typing import TypeVar

from .errors import LuisMediaError
from .logging import get_logger

T = TypeVar("T")
log = get_logger("retry")


def with_retry(
    fn: Callable[[], T],
    *,
    attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 20.0,
    op_name: str = "operacao",
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    last: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except LuisMediaError as exc:
            last = exc
            if not exc.retryable or attempt == attempts:
                raise
            delay = min(max_delay, base_delay * 2 ** (attempt - 1)) * (0.5 + random.random() / 2)
            log.warning(
                "%s falhou, tentando de novo",
                op_name,
                extra={"attempt": attempt, "delay_s": round(delay, 2), "error": str(exc)},
            )
            sleep(delay)
    raise AssertionError("inalcancavel") from last
