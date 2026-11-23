"""Inicio: o caminho de um passo. Solta o video, escolhe o estilo, clica em Gerar.

Usa as opcoes salvas da tela de lote (avancado) e so troca o que esta na tela: estilo da
legenda, corte de pausas/vicios e revisao antes de gerar. O processamento e o mesmo da
tela de lote (mesmo pipeline, mesmo checkpoint).
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from PySide6.QtCore import QStandardPaths, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..adapters import ffmpeg as ff
from ..cli import VIDEO_EXT
from ..core.style import PRESETS_H
from . import state
from .process_page import STAGE_NAMES, STAGE_ORDER, DropFrame, ProcessPage, fmt_duration
from .style_page import load_user_presets
from .tasks import run_task
from .widgets import banner, toggle

MY_STYLE = "Meu estilo (tela Estilo)"
NO_SUBS = "Sem legenda no vídeo (só os arquivos .srt)"


def grab_thumbnail(video: Path, out: Path, duration: float) -> Path:
    ff.run_ffmpeg(["-ss", f"{max(0.0, duration * 0.15):.2f}", "-i", str(video), "-frames:v", "1",
                   "-vf", "scale=480:-2", str(out)], timeout_s=30, stall_timeout_s=30)
    return out


class HomePage(QWidget):
    review_requested = Signal(str, str)  # pasta do lote, nome do video
    advanced_requested = Signal()

    def __init__(self, process: ProcessPage) -> None:
        super().__init__()
        self.setObjectName("page")
        self.process = process
        self.video: Path | None = None
        self.duration = 0.0
        self._job = None
        self._tmp = Path(tempfile.mkdtemp(prefix="lmt_home_"))
        self._result: dict | None = None
        self._build()
        process.job_started.connect(self._watch)
        process.busy_changed.connect(lambda busy: self.btn_go.setEnabled(not busy and self.video is not None))

    # ------------------------------------------------------------------ layout
    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 22, 28, 18)
        outer.addStretch(1)
        center = QHBoxLayout()
        center.addStretch(1)
        col = QVBoxLayout()
        col.setSpacing(18)
        center.addLayout(col)
        center.addStretch(1)
        outer.addLayout(center)
        outer.addStretch(2)

        title = QLabel("O que vamos editar hoje?")
        title.setObjectName("heroTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub = QLabel("Solte a aula e receba o vídeo sem pausas, com legenda, cortes e material, "
                     "tudo no seu computador.")
        sub.setObjectName("pageSubtitle")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        col.addWidget(title)
        col.addWidget(sub)

        self.steps = QStackedWidget()
        self.steps.setFixedWidth(640)
        col.addWidget(self.steps, 0, Qt.AlignmentFlag.AlignHCenter)

        # ---- 0: soltar o video
        self.drop = DropFrame()
        self.drop.setMinimumHeight(260)
        dl = QVBoxLayout(self.drop)
        dl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dl.setSpacing(10)
        icon = QLabel("⬆")
        icon.setObjectName("dropIcon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        big = QLabel("Arraste o vídeo da aula aqui")
        big.setObjectName("cardTitle")
        big.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.btn_pick = QPushButton("Escolher vídeo…")
        self.btn_pick.setObjectName("primary")
        self.btn_pick.setCursor(Qt.CursorShape.PointingHandCursor)
        small = QLabel("MP4, MOV, MKV ou WEBM · o arquivo original nunca é alterado")
        small.setObjectName("muted")
        small.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dl.addWidget(icon)
        dl.addWidget(big)
        dl.addWidget(self.btn_pick, 0, Qt.AlignmentFlag.AlignHCenter)
        dl.addWidget(small)
        self.steps.addWidget(self.drop)

        # ---- 1: escolher e gerar
        ready = QFrame()
        ready.setObjectName("card")
        rl = QVBoxLayout(ready)
        rl.setContentsMargins(20, 18, 20, 18)
        rl.setSpacing(14)
        top = QHBoxLayout()
        top.setSpacing(16)
        self.thumb = QLabel()
        self.thumb.setObjectName("thumb")
        self.thumb.setFixedSize(192, 108)
        self.thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info = QVBoxLayout()
        info.setSpacing(4)
        self.v_name = QLabel()
        self.v_name.setObjectName("cardTitle")
        self.v_name.setWordWrap(True)
        self.v_meta = QLabel()
        self.v_meta.setObjectName("muted")
        self.btn_swap = QPushButton("Trocar vídeo")
        self.btn_swap.setObjectName("link")
        info.addWidget(self.v_name)
        info.addWidget(self.v_meta)
        info.addStretch(1)
        info.addWidget(self.btn_swap, 0, Qt.AlignmentFlag.AlignLeft)
        top.addWidget(self.thumb)
        top.addLayout(info, 1)
        rl.addLayout(top)

        line = QFrame()
        line.setObjectName("divider")
        line.setFixedHeight(1)
        rl.addWidget(line)

        srow = QHBoxLayout()
        lab = QLabel("Estilo da legenda")
        self.style_box = QComboBox()
        self.style_box.setMinimumWidth(260)
        srow.addWidget(lab)
        srow.addStretch(1)
        srow.addWidget(self.style_box)
        rl.addLayout(srow)
        self.o_clean = toggle("Cortar pausas e vícios (é…, ãh, hum)",
                              "Encurta silêncios e tira hesitações. Você confere tudo antes, se a revisão estiver ligada.")
        self.o_review = toggle("Revisar antes de gerar o vídeo",
                               "Para depois da transcrição e abre a linha do tempo para conferir texto e cortes")
        rl.addWidget(self.o_clean)
        rl.addWidget(self.o_review)

        go = QHBoxLayout()
        self.btn_more = QPushButton("Mais opções")
        self.btn_more.setObjectName("link")
        self.btn_more.setToolTip("Apostila, quiz, cortes 9:16, pasta de saída e aceleração: tela Processar em lote")
        self.btn_go = QPushButton("Gerar")
        self.btn_go.setObjectName("hero")
        self.btn_go.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_go.setMinimumWidth(180)
        go.addWidget(self.btn_more)
        go.addStretch(1)
        go.addWidget(self.btn_go)
        rl.addLayout(go)
        self.steps.addWidget(ready)

        # ---- 2: processando / pronto
        run = QFrame()
        run.setObjectName("card")
        ul = QVBoxLayout(run)
        ul.setContentsMargins(22, 20, 22, 20)
        ul.setSpacing(12)
        self.r_title = QLabel()
        self.r_title.setObjectName("cardTitle")
        self.r_stage = QLabel()
        self.r_stage.setObjectName("muted")
        self.r_stage.setWordWrap(True)
        self.r_bar = QProgressBar()
        self.r_bar.setRange(0, 1000)
        self.r_bar.setFixedHeight(10)
        self.r_bar.setTextVisible(False)
        self.r_msg = QLabel()
        self.r_msg.setObjectName("banner")
        self.r_msg.setWordWrap(True)
        self.r_msg.setVisible(False)
        acts = QHBoxLayout()
        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.setObjectName("danger")
        self.btn_new = QPushButton("Editar outro vídeo")
        self.btn_folder = QPushButton("Abrir pasta")
        self.btn_review = QPushButton("Revisar agora")
        self.btn_review.setObjectName("primary")
        self.btn_open = QPushButton("Abrir vídeo final")
        self.btn_open.setObjectName("primary")
        acts.addWidget(self.btn_new)
        acts.addStretch(1)
        for b in (self.btn_cancel, self.btn_folder, self.btn_review, self.btn_open):
            acts.addWidget(b)
        ul.addWidget(self.r_title)
        ul.addWidget(self.r_stage)
        ul.addWidget(self.r_bar)
        ul.addWidget(self.r_msg)
        ul.addStretch(1)
        ul.addLayout(acts)
        self.steps.addWidget(run)

        self.drop.dropped.connect(self._dropped)
        self.btn_pick.clicked.connect(lambda _c=False: self._pick())
        self.btn_swap.clicked.connect(lambda _c=False: self._pick())
        self.btn_go.clicked.connect(lambda _c=False: self.generate())
        self.btn_more.clicked.connect(lambda _c=False: self.advanced_requested.emit())
        self.btn_cancel.clicked.connect(lambda _c=False: self.process.cancel())
        self.btn_new.clicked.connect(lambda _c=False: self.reset())
        self.btn_folder.clicked.connect(lambda _c=False: QDesktopServices.openUrl(QUrl.fromLocalFile(self._out_dir())))
        self.btn_open.clicked.connect(lambda _c=False: self._open_final())
        self.btn_review.clicked.connect(lambda _c=False: self.review_requested.emit(
            str(self._out_root()), self.video.stem if self.video else ""))
        self.reset()

    # ------------------------------------------------------------------ estados
    def reset(self) -> None:
        self.video, self._result = None, None
        self.steps.setCurrentIndex(0)

    def _fill_styles(self) -> None:
        self.style_box.clear()
        self.style_box.addItem(MY_STYLE)
        self.style_box.addItems(list(PRESETS_H))
        self.style_box.addItems(["★ " + n for n in load_user_presets()["h"]])
        self.style_box.addItem(NO_SUBS)

    def _pick(self) -> None:
        start = str(self.video.parent) if self.video else \
            QStandardPaths.writableLocation(QStandardPaths.StandardLocation.MoviesLocation)
        f, _ = QFileDialog.getOpenFileName(self, "Escolher vídeo", start, "Vídeos (*.mp4 *.mkv *.mov *.m4v *.webm)")
        if f:
            self.set_video(Path(f))

    def _dropped(self, paths: list[Path]) -> None:
        vids = [p for p in paths if p.suffix.lower() in VIDEO_EXT]
        if vids:
            self.set_video(vids[0])

    def set_video(self, video: Path) -> None:
        self.video = video.resolve()
        self._fill_styles()
        s = state.load_base_settings()
        ui = state.load_ui()
        self.o_clean.setChecked(ui.get("home_clean", s.cleanup.enabled))
        self.o_review.setChecked(ui.get("home_review", True))
        if ui.get("home_style") and self.style_box.findText(ui["home_style"]) >= 0:
            self.style_box.setCurrentText(ui["home_style"])
        self.v_name.setText(self.video.name)
        self.v_meta.setText("Lendo o vídeo…")
        self.thumb.setText("🎬")
        self.thumb.setPixmap(QPixmap())
        self.btn_go.setEnabled(self.process.job is None)
        self.steps.setCurrentIndex(1)
        v = self.video
        run_task(lambda _p: ff.probe(v), on_done=lambda info, v=v: self._probed(v, info),
                 on_error=lambda e: self.v_meta.setText(f"Não consegui ler este vídeo: {e}"))

    def _probed(self, v: Path, info) -> None:
        if v != self.video:
            return
        self.duration = info.duration
        size = f"{info.width}×{info.height} · " if info.width else ""
        self.v_meta.setText(f"{size}{fmt_duration(info.duration)}")
        out = self._tmp / f"{abs(hash(str(v)))}.jpg"
        run_task(lambda _p: grab_thumbnail(v, out, info.duration),
                 on_done=lambda p, v=v: self._thumb(v, p), on_error=lambda _e: None)

    def _thumb(self, v: Path, p: Path) -> None:
        if v == self.video:
            self.thumb.setPixmap(QPixmap(str(p)).scaled(self.thumb.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                                        Qt.TransformationMode.SmoothTransformation))

    # ------------------------------------------------------------------ gerar
    def overrides(self) -> dict:
        clean = self.o_clean.isChecked()
        ov: dict = {"cleanup": {"enabled": clean, "pauses": clean, "fillers": clean},
                    "autocut": {"enabled": False},
                    "subtitles": {"review": self.o_review.isChecked()}}
        name = self.style_box.currentText()
        ov["render"] = {"hardsub": name != NO_SUBS}
        style = PRESETS_H.get(name) or load_user_presets()["h"].get(name.removeprefix("★ "))
        if style is not None:
            ov["subtitles"]["style_h"] = style.model_dump()
        return ov

    def _out_root(self) -> Path:
        txt = self.process.out_edit.text().strip()
        if txt:
            return Path(txt)
        assert self.video is not None
        return self.video.parent / "LUIS MEDIA - resultado"

    def _out_dir(self) -> str:
        return str(self._out_root() / self.video.stem) if self.video else str(self._out_root())

    def generate(self) -> None:
        if self.video is None or self.process.job is not None:
            return
        ui = state.load_ui()
        ui.update({"home_clean": self.o_clean.isChecked(), "home_review": self.o_review.isChecked(),
                   "home_style": self.style_box.currentText()})
        state.save_ui(ui)
        if not self.process.out_edit.text().strip():
            self.process.out_edit.setText(str(self._out_root()))
        self.process.add_paths([self.video])
        self.process.start(only=[self.video], overrides=self.overrides())

    def _watch(self, job) -> None:
        if self.video is None or self.video not in job.videos:
            return
        self._job = job
        self._result = None
        self.steps.setCurrentIndex(2)
        self.r_title.setText(f"Editando {self.video.name}")
        self.r_stage.setText("Preparando…")
        self.r_bar.setValue(0)
        banner(self.r_msg, "info", "")
        for b in (self.btn_folder, self.btn_review, self.btn_open, self.btn_new):
            b.setVisible(False)
        self.btn_cancel.setVisible(True)
        job.signals.event.connect(self._on_event)
        job.signals.finished.connect(self._on_finished)
        job.signals.failed.connect(self._on_failed)

    def _on_event(self, e: dict) -> None:
        if self.video is None or e.get("video") != self.video.stem:
            return
        stage = e["stage"]
        pos = STAGE_ORDER.index(stage) if stage in STAGE_ORDER else 0
        frac = (pos + min(1.0, float(e.get("progress") or 0))) / len(STAGE_ORDER)
        self.r_bar.setValue(max(self.r_bar.value(), int(1000 * frac)))
        pct = f" {float(e['progress']):.0%}" if e["status"] == "running" and e.get("progress") else ""
        self.r_stage.setText(STAGE_NAMES.get(stage, stage) + pct)

    def _on_finished(self, results: list[dict]) -> None:
        self.btn_cancel.setVisible(False)
        self.btn_new.setVisible(True)
        self.btn_folder.setVisible(True)
        r = next((x for x in results if self.video and Path(x["source"]) == self.video), None)
        self._result = r
        if r is None:
            self.r_title.setText("Processamento cancelado")
            self.r_stage.setText("O que já ficou pronto foi mantido.")
            return
        if not r["ok"]:
            self.r_title.setText("Não deu certo desta vez")
            self.r_stage.setText("")
            banner(self.r_msg, "error", r.get("error") or "erro desconhecido")
            return
        self.r_bar.setValue(1000)
        if r.get("needs_review"):
            self.r_title.setText("Transcrição pronta. Confira antes de gerar")
            cuts = self._cut_summary()
            self.r_stage.setText("Revise o texto e os cortes na linha do tempo; depois clique em "
                                 "“Aprovar e gerar vídeos”." + (f"\n{cuts}" if cuts else ""))
            self.btn_review.setVisible(True)
            return
        self.r_title.setText("Pronto! ✓")
        warn = r.get("warnings") or []
        self.r_stage.setText(f"Vídeo final: {fmt_duration(r.get('duration') or 0)}"
                             + (f" · {len(warn)} aviso(s)" if warn else ""))
        if warn:
            banner(self.r_msg, "warn", "\n".join(warn))
        self.btn_open.setVisible(bool(self._final_video()))

    def _cut_summary(self) -> str:
        import json

        if not self.video:
            return ""
        p = self._out_root() / self.video.stem / "legendas" / f"{self.video.stem}.cortes.json"
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return ""
        return f"Encontrei {d['sugeridos']} pausas/vícios; {d['marcados']} já marcados para corte (−{d['segundos']:.0f} s)."

    def _on_failed(self, msg: str) -> None:
        self.btn_cancel.setVisible(False)
        self.btn_new.setVisible(True)
        self.r_title.setText("O processamento parou")
        banner(self.r_msg, "error", msg)

    def _final_video(self) -> str | None:
        out = (self._result or {}).get("outputs") or {}
        for k in ("video_legendado", "video_editado", "video_base"):
            if out.get(k) and Path(out[k]).exists():
                return out[k]
        return None

    def _open_final(self) -> None:
        f = self._final_video()
        if f:
            QDesktopServices.openUrl(QUrl.fromLocalFile(f))
