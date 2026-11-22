"""Testes de integracao com ffmpeg real e midia sintetica."""

from __future__ import annotations

import re
import subprocess
import time
from pathlib import Path

import pytest

from luismedia.adapters import ffmpeg as ff
from luismedia.core import subtitles
from luismedia.core.config import AudioConfig, AutoCutConfig, Encoder, Settings
from luismedia.core.errors import InvalidMedia, ProcessFailed, ProcessTimeout
from luismedia.core.models import Segment, Transcript
from luismedia.stages import media

from .conftest import needs_ffmpeg, needs_libass

pytestmark = [pytest.mark.integration, needs_ffmpeg]


def test_probe_reads_synthetic_lesson(lesson_video):
    info = ff.probe(lesson_video)
    assert info.has_audio and info.has_video and 11.5 < info.duration < 12.5


def test_probe_rejects_corrupt_file(corrupt_video):
    with pytest.raises(InvalidMedia):
        ff.probe(corrupt_video)


def test_ffmpeg_error_is_raised_with_stderr(tmp_path):
    with pytest.raises(ProcessFailed) as exc:
        ff.run_ffmpeg(["-i", str(tmp_path / "nao_existe.mp4"), str(tmp_path / "x.mp4")])
    assert "No such file" in (exc.value.detail or "")


def test_stalled_ffmpeg_is_killed():
    # -re + -t longo: ffmpeg fica vivo; watchdog de timeout total precisa matar rapido
    t0 = time.monotonic()
    with pytest.raises(ProcessTimeout):
        ff.run_ffmpeg(["-re", "-f", "lavfi", "-i", "sine=d=600", "-f", "null", "-"], timeout_s=2)
    assert time.monotonic() - t0 < 10


def test_failed_render_leaves_no_partial_file(tmp_path, lesson_video):
    out = tmp_path / "saida.mp4"
    with pytest.raises(ProcessFailed):
        ff.run_to_file(out, lambda tmp: ["-i", str(lesson_video), "-c:v", "codec_inexistente", str(tmp)])
    assert not out.exists() and not list(tmp_path.glob("*.part*"))


def test_autocut_end_to_end(tmp_path, lesson_video):
    info = ff.probe(lesson_video)
    wav = media.extract_audio(info, tmp_path / "a.wav")
    cfg = AutoCutConfig(keep_pauses_longer_than_s=2.5)
    sil = media.detect_silences(wav, info.duration, cfg)
    spans = media.speech_spans(sil, info.duration, cfg)
    out = media.render_autocut(info, spans, tmp_path / "cut.mp4", encoder=Encoder.CPU, crf=30, work=tmp_path)
    cut = ff.probe(out)
    # tirou ~1 s do silencio curto (1.5 s - 2 x 0.25 de margem), manteve a pausa de 4 s
    assert 10.5 < cut.duration < 11.5
    assert cut.has_audio and abs(cut.duration - sum(s.duration for s in spans)) < 0.15


def test_master_audio_hits_target_lufs(tmp_path, lesson_video):
    info = ff.probe(lesson_video)
    wav = media.extract_audio(info, tmp_path / "a.wav", sample_rate=48_000)
    out = media.master_audio(wav, tmp_path / "m.wav", info.duration, AudioConfig(target_lufs=-14))
    res = subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", "-i", str(out), "-af",
                          "ebur128", "-f", "null", "-"], capture_output=True, text=True)
    integrated = float(re.findall(r"I:\s+(-?\d+\.\d) LUFS", res.stderr)[-1])
    assert abs(integrated - (-14)) <= 1.0


def test_slides_have_real_timestamps(tmp_path, lesson_video):
    frames = media.extract_slides(ff.probe(lesson_video), tmp_path / "slides", threshold=0.25)
    times = [round(f.timestamp) for f in frames]
    assert times == [0, 4, 8]  # abertura + trocas de cor em 4 s e 8 s


@needs_libass
def test_hardsub_with_hostile_path(tmp_path, lesson_video):
    # pasta com espaco, apostrofo e colchete: quebrava o escape manual do script antigo
    d = tmp_path / "Aula d'Ouro [final]"
    d.mkdir()
    ass = subtitles.write_ass([Segment(start=0.5, end=3, text="Ola, turma!")], d / "leg.ass",
                              width=320, height=240)
    info = ff.probe(lesson_video)
    out = media.burn_subtitles(info, ass, d / "leg.mp4", encoder=Encoder.CPU, crf=30, work=d)
    assert ff.probe(out).duration > 11


class FakeWhisper:
    def transcribe(self, audio, duration, on_progress=None):
        return Transcript(language="pt", duration=duration, model="fake", device="cpu",
                          segments=[Segment(start=0, end=2.5, text="Bem-vindos a aula.")])


@needs_libass
def test_pipeline_end_to_end_with_checkpoint(tmp_path, lesson_video, monkeypatch):
    from luismedia.pipeline.runner import Pipeline

    s = Settings(render={"encoder": "libx264", "crf": 30}, llm={"enabled": False},
                 slides={"handout_pdf": False})
    events = []
    p = Pipeline(s, listeners=[events.append])
    p.whisper = FakeWhisper()
    [r] = p.run([lesson_video], tmp_path / "saida")
    assert r.ok, r.error
    for key in ("video_dinamico", "edl", "srt", "srt_shorts", "ass", "audio_master",
                "video_legendado", "slides_index", "apostila_html"):
        assert key in r.outputs, key
    assert lesson_video.exists()  # original intocado
    out = tmp_path / "saida"
    assert (out / "capitulos-youtube.txt").read_text(encoding="utf-8").startswith("00:00 - aula 01")
    assert (out / "Entregavel.zip").exists() and (out / "relatorio.json").exists()
    apostila = Path(r.outputs["apostila_html"]).read_text(encoding="utf-8")
    assert "Bem-vindos" in apostila and "../slides/slide_0001.jpg" in apostila

    # segunda execucao: tudo vem do checkpoint, nada e reprocessado
    events.clear()
    p.run([lesson_video], tmp_path / "saida")
    assert {e.status for e in events} == {"skipped"}


class FakeOllama:
    """Servidor Ollama falso: responde conforme o que o prompt pede."""

    def __init__(self):
        self.prompts = []

    def __call__(self, req, timeout=None):
        import io
        import json as _json

        class R(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        url = req if isinstance(req, str) else req.full_url
        if url.endswith("/api/version"):
            return R(b'{"version":"0.0.0"}')
        if url.endswith("/api/tags"):
            return R(b'{"models":[{"name":"llama3.2:3b"}]}')
        prompt = _json.loads(req.data)["prompt"]
        self.prompts.append(prompt)
        if "Resumo Executivo" in prompt:
            out = "## Objetivo da aula\n- Apresentar o curso"
        elif "perguntas" in prompt:
            out = _json.dumps({"questions": [{"question": "Qual o tema da aula?", "correct": "Boas-vindas",
                                              "wrong": ["Calculo", "Fisica", "Quimica"]}]})
        else:
            out = _json.dumps({"clips": [{"title": "Abertura da aula", "start": 0.5, "end": 8.0}]})
        return R(_json.dumps({"response": out}).encode())


@needs_libass
def test_pipeline_with_ai_and_vertical_clip(tmp_path, lesson_video):
    from luismedia.adapters.ollama import OllamaClient
    from luismedia.pipeline.runner import Pipeline

    s = Settings(render={"encoder": "libx264", "crf": 32}, autocut={"enabled": False},
                 slides={"enabled": False, "handout_pdf": False}, audio={"master": False},
                 llm={"clips": True, "clips_count": 1})
    p = Pipeline(s)
    p.whisper = FakeWhisper()
    p.llm = OllamaClient(s.llm, opener=FakeOllama())
    [r] = p.run([lesson_video], tmp_path / "out")
    assert r.ok and not r.warnings, r.warnings
    clip = ff.probe(Path(r.outputs["corte_1"]))
    assert (clip.width, clip.height) == (1080, 1920) and 7 < clip.duration < 8.2
    assert "Apresentar o curso" in Path(r.outputs["apostila_html"]).read_text(encoding="utf-8")
    assert "Qual o tema" in Path(r.outputs["quiz"]).read_text(encoding="utf-8")


def test_pipeline_without_ollama_warns_and_finishes(tmp_path, lesson_video):
    from luismedia.pipeline.runner import Pipeline

    s = Settings(render={"encoder": "libx264", "hardsub": False}, autocut={"enabled": False},
                 slides={"enabled": False, "handout": False}, audio={"master": False},
                 llm={"base_url": "http://127.0.0.1:9"})
    p = Pipeline(s)
    p.whisper = FakeWhisper()
    [r] = p.run([lesson_video], tmp_path / "out")
    assert r.ok and any(w.startswith("ia:") for w in r.warnings)


class ExplodingWhisper:
    def transcribe(self, audio, duration, on_progress=None):
        raise RuntimeError("403 Forbidden")  # erro que nao e da hierarquia do projeto


def test_unexpected_error_fails_only_that_video(tmp_path, lesson_video):
    from luismedia.pipeline.runner import Pipeline

    s = Settings(render={"encoder": "libx264", "hardsub": False}, autocut={"enabled": False},
                 llm={"enabled": False}, slides={"enabled": False, "handout": False})
    p = Pipeline(s)
    p.whisper = ExplodingWhisper()
    results = p.run([lesson_video, lesson_video], tmp_path / "out")
    assert len(results) == 2 and all(r.failed_stage == "transcricao" for r in results)
    assert "403" in results[0].error


def test_missing_subtitles_filter_is_clear_warning(tmp_path, lesson_video, monkeypatch):
    from luismedia.pipeline.runner import Pipeline

    monkeypatch.setattr(ff, "has_filter", lambda name: False)
    s = Settings(render={"encoder": "libx264"}, autocut={"enabled": False}, llm={"enabled": False},
                 slides={"enabled": False, "handout": False}, audio={"master": False})
    p = Pipeline(s)
    p.whisper = FakeWhisper()
    [r] = p.run([lesson_video], tmp_path / "out")
    assert r.ok and any("filtro 'subtitles'" in w for w in r.warnings)


def test_whisper_receives_decoded_audio_not_a_path(tmp_path, lesson_video):
    """Regressao: o faster-whisper decodifica com PyAV e quebra no PyAV 14+
    ("metadata_errors"). O adapter precisa entregar o audio ja decodificado."""
    import numpy as np

    from luismedia.adapters import whisper as wh
    from luismedia.core.config import WhisperConfig

    info = ff.probe(lesson_video)
    wav = media.extract_audio(info, tmp_path / "a.wav")
    arr = wh.load_audio(wav)
    assert arr.dtype == np.float32 and abs(len(arr) / 16000 - info.duration) < 0.2

    seen = {}

    class FakeModel:
        def transcribe(self, audio, **kw):
            seen["audio"] = audio
            return iter([]), type("I", (), {"language": "pt"})()

    eng = wh.WhisperEngine(WhisperConfig(device="cpu", fallback_models=[]))
    eng._load = lambda *a: FakeModel()
    eng.transcribe(wav, info.duration)
    assert isinstance(seen["audio"], np.ndarray)
