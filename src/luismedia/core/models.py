"""Schemas que trafegam entre as etapas (contrato unico, sem 'pastas magicas')."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field, model_validator


class Span(BaseModel):
    start: float = Field(ge=0)
    end: float = Field(ge=0)

    @model_validator(mode="after")
    def _ordered(self) -> Span:
        if self.end < self.start:
            raise ValueError(f"end ({self.end}) < start ({self.start})")
        return self

    @property
    def duration(self) -> float:
        return self.end - self.start


class Word(Span):
    text: str
    probability: float | None = None


class Segment(Span):
    text: str
    words: list[Word] = []


class Transcript(BaseModel):
    language: str
    duration: float
    segments: list[Segment]
    model: str
    device: str

    def plain_text(self) -> str:
        return " ".join(s.text.strip() for s in self.segments if s.text.strip())


class MediaInfo(BaseModel):
    path: Path
    duration: float = Field(gt=0)
    has_audio: bool
    has_video: bool
    width: int | None = None
    height: int | None = None
    fps: float | None = None


class SlideFrame(BaseModel):
    path: Path
    timestamp: float = Field(ge=0)  # sai do ffmpeg (showinfo), nao do nome do arquivo


class ClipSuggestion(BaseModel):
    """Saida do LLM para cortes 9:16, validada antes de chegar no ffmpeg."""

    title: str = Field(min_length=1, max_length=120)
    start: float = Field(ge=0)
    end: float = Field(gt=0)

    @model_validator(mode="after")
    def _sane(self) -> ClipSuggestion:
        if not 5 <= self.end - self.start <= 180:
            raise ValueError("corte precisa ter entre 5 e 180 segundos")
        return self


class ClipPlan(BaseModel):
    clips: list[ClipSuggestion]


class QuizQuestion(BaseModel):
    question: str = Field(min_length=5)
    correct: str = Field(min_length=1)
    wrong: list[str] = Field(min_length=3, max_length=3)


class Quiz(BaseModel):
    questions: list[QuizQuestion] = Field(min_length=1, max_length=20)
