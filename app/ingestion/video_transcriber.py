from __future__ import annotations

from pathlib import Path


class WhisperTranscriber:
    def __init__(self, model_name: str = "base", language: str = "vi"):
        self.model_name = model_name
        self.language = language
        self._model = None

    def _load_model(self):
        if self._model is not None:
            return self._model
        try:
            import whisper  # type: ignore
        except ImportError:
            raise ImportError(
                "openai-whisper is not installed. Run: pip install openai-whisper"
            )
        self._model = whisper.load_model(self.model_name)
        return self._model

    def transcribe(self, path: str | Path) -> dict:
        model = self._load_model()
        result = model.transcribe(
            str(path),
            verbose=False,
            language=self.language,
            initial_prompt=(
                "Đây là video tiếng Việt có dấu đầy đủ. "
                "Vui lòng ghi chính xác dấu thanh và dấu mũ tiếng Việt."
            ),
            condition_on_previous_text=True,
            temperature=0.0,
            beam_size=5,
            best_of=5,
        )
        segments = [
            {
                "start": round(float(s["start"]), 3),
                "end": round(float(s["end"]), 3),
                "text": s["text"].strip(),
            }
            for s in result["segments"]
        ]
        duration = float(result.get("duration", 0.0))
        if not duration and segments:
            duration = segments[-1]["end"]
        return {
            "segments": segments,
            "language": result.get("language", self.language),
            "duration": duration,
        }
