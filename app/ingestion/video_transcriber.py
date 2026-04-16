from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def _detect_device() -> str:
    try:
        import torch
        if torch.cuda.is_available():
            logger.info("Whisper sử dụng CUDA GPU")
            return "cuda"
        # MPS (Apple Silicon) gây hallucination/lặp với Whisper, không dùng
    except Exception:
        pass
    logger.info("Whisper sử dụng CPU")
    return "cpu"


class WhisperTranscriber:
    def __init__(self, model_name: str = "medium", language: str = "vi"):
        self.model_name = model_name
        self.language = language
        self._model = None
        self._device = _detect_device()

    def _load_model(self):
        if self._model is not None:
            return self._model
        try:
            import whisper  # type: ignore
        except ImportError:
            raise ImportError(
                "openai-whisper is not installed. Run: pip install openai-whisper"
            )
        self._model = whisper.load_model(self.model_name, device=self._device)
        logger.info("Loaded Whisper model '%s' on %s", self.model_name, self._device)
        return self._model

    def transcribe(self, path: str | Path) -> dict:
        model = self._load_model()
        # MPS với fp16 gây lặp/hallucination, chỉ dùng fp16 cho CUDA
        fp16 = self._device == "cuda"
        result = model.transcribe(
            str(path),
            verbose=False,
            language=self.language,
            fp16=fp16,
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
