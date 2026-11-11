"""Testes unitarios: logica pura, sem ffmpeg, sem GPU, sem Ollama."""

from __future__ import annotations

import io
import json
import urllib.error

import pytest

from luismedia.adapters.ollama import OllamaClient
from luismedia.core import subtitles
from luismedia.core.config import AutoCutConfig, LLMConfig, Settings
from luismedia.core.errors import LLMOutputInvalid, ServiceUnavailable
from luismedia.core.models import ClipPlan, Segment, Span
from luismedia.core.retry import with_retry
from luismedia.stages.media import autocut_filter, parse_silences, speech_spans


# ---------------------------------------------------------------- timecodes
@pytest.mark.parametrize("sec,expected", [
    (0, "00:00:00,000"),
    (59.9996, "00:01:00,000"),      # antigo: "00:00:60,000" (invalido)
    (3599.9999, "01:00:00,000"),
    (3725.5, "01:02:05,500"),
    (-0.2, "00:00:00,000"),
])
def test_srt_time_never_overflows(sec, expected):
    assert subtitles.srt_time(sec) == expected


def test_ass_time_rounding():
    assert subtitles.ass_time(3599.999) == "1:00:00.00"  # antigo: "0:59:60.00"


def test_ass_escapes_override_braces(tmp_path):
    p = subtitles.write_ass([Segment(start=0, end=1, text="use {chaves}")], tmp_path / "x.ass")
    assert "{chaves}" not in p.read_text(encoding="utf-8")


def test_srt_skips_empty_segments(tmp_path):
    segs = [Segment(start=0, end=1, text="  "), Segment(start=1, end=2, text="ola\nmundo")]
    text = subtitles.write_srt(segs, tmp_path / "x.srt").read_text(encoding="utf-8")
    # a quebra de linha feita pela segmentacao e preservada
    assert text.startswith("1\n00:00:01,000 --> 00:00:02,000\nola\nmundo")


# ---------------------------------------------------------------- autocut
STDERR = """
[silencedetect @ 0x1] silence_start: 3.02
[silencedetect @ 0x1] silence_end: 4.49 | silence_duration: 1.47
[silencedetect @ 0x1] silence_start: 7.01
[silencedetect @ 0x1] silence_end: 11.0 | silence_duration: 3.99
[silencedetect @ 0x1] silence_start: 11.8
"""


def test_parse_silences_includes_trailing_silence():
    spans = parse_silences(STDERR, duration=12.0)
    assert [(s.start, s.end) for s in spans] == [(3.02, 4.49), (7.01, 11.0), (11.8, 12.0)]


def test_speech_spans_cuts_short_and_keeps_long_pauses():
    cfg = AutoCutConfig(keep_pauses_longer_than_s=2.5, margin_s=0.25)
    keep = speech_spans(parse_silences(STDERR, 12.0), 12.0, cfg)
    # pausa de 1.47 s cortada; pausa de 3.99 s preservada (didatica)
    assert [(round(s.start, 2), round(s.end, 2)) for s in keep] == [(0.0, 3.27), (4.24, 12.0)]


def test_speech_spans_without_silence_returns_whole_file():
    assert [(s.start, s.end) for s in speech_spans([], 10.0, AutoCutConfig())] == [(0.0, 10.0)]


def test_autocut_filter_is_single_graph():
    g = autocut_filter([Span(start=0, end=1), Span(start=2, end=3)])
    assert g.count("trim=") == 4 and g.endswith("concat=n=2:v=1:a=1[vout][aout]")


# ---------------------------------------------------------------- config
def test_settings_reject_unknown_keys():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Settings.model_validate({"autocutt": {}})  # erro de digitacao vira erro, nao silencio


def test_settings_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("LUISMEDIA_LLM__MODEL", "qwen2.5:3b")
    prof = tmp_path / "p.json"
    prof.write_text("﻿" + json.dumps({"audio": {"target_lufs": -16}}), encoding="utf-8")
    s = Settings.load(prof)
    assert s.llm.model == "qwen2.5:3b" and s.audio.target_lufs == -16


def test_defaults_are_safe():
    s = Settings()
    assert s.move_source_files is False and s.audio.target_lufs == -14


# ---------------------------------------------------------------- retry
def test_retry_only_retryable():
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise ServiceUnavailable("fora")
        return "ok"

    assert with_retry(flaky, attempts=3, sleep=lambda _: None) == "ok" and len(calls) == 3


# ---------------------------------------------------------------- ollama
class FakeResp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def fake_opener(responses):
    it = iter(responses)

    def _open(req, timeout=None):
        assert timeout is not None, "toda chamada precisa de timeout"
        r = next(it)
        if isinstance(r, Exception):
            raise r
        return FakeResp(json.dumps({"response": r}).encode())

    return _open


def test_llm_invalid_clip_is_rejected_then_corrected():
    bad = json.dumps({"clips": [{"title": "x", "start": 40, "end": 35}]})       # fim < inicio
    good = json.dumps({"clips": [{"title": "Gancho", "start": 10, "end": 45}]})
    client = OllamaClient(LLMConfig(), opener=fake_opener([bad, good]))
    plan = client.generate_model("escolha cortes", ClipPlan)
    assert plan.clips[0].start == 10


def test_llm_gives_up_with_typed_error():
    client = OllamaClient(LLMConfig(), opener=fake_opener(["nao e json"] * 3))
    with pytest.raises(LLMOutputInvalid):
        client.generate_model("x", ClipPlan)


def test_ollama_down_is_service_unavailable(monkeypatch):
    monkeypatch.setattr("luismedia.core.retry.time.sleep", lambda _: None)
    err = urllib.error.URLError("connection refused")
    client = OllamaClient(LLMConfig(), opener=fake_opener([err] * 3))
    with pytest.raises(ServiceUnavailable):
        client.generate("oi")
