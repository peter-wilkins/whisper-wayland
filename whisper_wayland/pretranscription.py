"""Shared configuration for experimental pre-transcription chunking."""

from __future__ import annotations

import typing
from dataclasses import dataclass


@dataclass(frozen=True)
class ChunkTranscriptionConfig:
    """Config proxy that overrides only chunk transcription provider settings."""

    base_config: typing.Any
    whisper_model: str
    transcription_race_models: list[str]

    def __getattr__(self, name: str) -> object:
        """Delegate all unrelated settings to the normal configuration."""
        return getattr(self.base_config, name)


def chunk_transcription_config(
    base_config: typing.Any,
    *,
    whisper_model: str | None = None,
    race_models: list[str] | None = None,
) -> ChunkTranscriptionConfig:
    """Build the chunk-only provider configuration from normal app config."""
    return ChunkTranscriptionConfig(
        base_config=base_config,
        whisper_model=(whisper_model or base_config.pretranscription_chunk_whisper_model),
        transcription_race_models=(
            race_models
            if race_models is not None
            else base_config.pretranscription_chunk_race_models
        ),
    )
