"""Execucao em segundo plano para a interface nunca congelar."""

from __future__ import annotations

import threading
import traceback
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

from ..core.config import Settings
from ..core.logging import get_logger

log = get_logger("gui")


class _Signals(QObject):
    done = Signal(object)
    failed = Signal(str)
    progress = Signal(float)


class Task(QRunnable):
    """Roda ``fn(progress_callback)`` numa thread do pool e devolve o resultado por sinal."""

    def __init__(self, fn: Callable[[Callable[[float], None]], Any]) -> None:
        super().__init__()
        self.fn = fn
        self.signals = _Signals()

    @Slot()
    def run(self) -> None:
        try:
            result = self.fn(self.signals.progress.emit)
        except Exception as exc:  # noqa: BLE001 - qualquer erro vira mensagem na tela
            log.error("tarefa falhou", extra={"error": str(exc), "trace": traceback.format_exc()})
            self.signals.failed.emit(str(exc) or exc.__class__.__name__)
        else:
            self.signals.done.emit(result)


_alive: set[Task] = set()  # evita o coletor de lixo apagar a tarefa antes do sinal chegar


def run_task(fn, on_done=None, on_error=None, on_progress=None) -> Task:
    task = Task(fn)
    task.setAutoDelete(False)
    _alive.add(task)
    task.signals.done.connect(lambda _r: _alive.discard(task))
    task.signals.failed.connect(lambda _e: _alive.discard(task))
    if on_done:
        task.signals.done.connect(on_done)
    if on_error:
        task.signals.failed.connect(on_error)
    if on_progress:
        task.signals.progress.connect(on_progress)
    QThreadPool.globalInstance().start(task)
    return task


class JobSignals(QObject):
    event = Signal(dict)       # ProgressEvent em dict
    finished = Signal(list)    # lista de VideoResult em dict
    failed = Signal(str)


class PipelineJob(QRunnable):
    """Roda o Pipeline inteiro. ``cancel()`` interrompe ate o ffmpeg em andamento."""

    def __init__(self, settings: Settings, videos: list[Path], out: Path) -> None:
        super().__init__()
        self.settings, self.videos, self.out = settings, videos, out
        self.signals = JobSignals()
        self._cancel = threading.Event()

    def cancel(self) -> None:
        self._cancel.set()

    @property
    def cancelled(self) -> bool:
        return self._cancel.is_set()

    @Slot()
    def run(self) -> None:
        from ..core.logging import setup_logging
        from ..pipeline.runner import Pipeline

        try:
            self.out.mkdir(parents=True, exist_ok=True)
            setup_logging(self.out / "job.log.jsonl")
            pipeline = Pipeline(self.settings, listeners=[lambda e: self.signals.event.emit(asdict(e))],
                                cancel=self._cancel)
            results = pipeline.run(self.videos, self.out)
            self.signals.finished.emit([{**asdict(r), "source": str(r.source), "ok": r.ok} for r in results])
        except Exception as exc:  # noqa: BLE001
            log.error("job falhou", extra={"error": str(exc), "trace": traceback.format_exc()})
            self.signals.failed.emit(str(exc) or exc.__class__.__name__)


def start_job(job: PipelineJob) -> None:
    QThreadPool.globalInstance().start(job)
