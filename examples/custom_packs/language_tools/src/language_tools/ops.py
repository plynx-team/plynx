"""General-purpose statistical language detection and agentic translation operations."""

from __future__ import annotations

from typing import Any, TypedDict

from langdetect import DetectorFactory, LangDetectException, detect_langs  # type: ignore[import-untyped]
from plynx_sdk import (
    AgentOp,
    AgentProviderLiteral,
    MarkdownFile,
    Op,
)

# Seed langdetect's n-gram sampler once so language detection is 100% deterministic.
DetectorFactory.seed = 0


class DetectLanguage(Op):
    """Detect the ISO 639-1 language code of input text using statistical n-gram profiles.

    Uses ``langdetect`` (55 languages). When ``expected_language`` is non-empty and does
    not match the detected language code, emits a non-fatal warning via ``self.warn()``.

    Args:
        text: Input text to analyze.
        expected_language: Expected ISO 639-1 code (e.g. ``"en"``). Pass ``""`` to disable
            mismatch warnings.
    """

    TITLE = "Detect Language"
    CATEGORY = "Text & Language"
    CACHEABLE = True

    class Outputs(TypedDict):
        text: str
        language: str
        confidence: float
        word_count: int

    def run(self, text: str, expected_language: str = "en") -> Outputs:
        stripped = text.strip()
        expected = expected_language.strip().lower()

        if not stripped:
            language = "unknown"
            confidence = 0.0
        else:
            try:
                candidates = detect_langs(stripped)
            except LangDetectException:
                language = "unknown"
                confidence = 0.0
            else:
                if candidates:
                    top = candidates[0]
                    raw_code = str(top.lang).lower()
                    language = raw_code if "-" in expected else raw_code.split("-")[0]
                    confidence = round(float(top.prob), 4)
                else:
                    language = "unknown"
                    confidence = 0.0

        if expected and language != expected:
            self.warn(
                f"Detected language '{language}' (confidence={confidence:.2f}) "
                f"differs from expected '{expected}'"
            )

        word_count = len(stripped.split()) if stripped else 0
        print(
            f"Detected language: {language} (confidence={confidence:.2f}, words={word_count})",
            flush=True,
        )
        return {
            "text": text,
            "language": language,
            "confidence": confidence,
            "word_count": word_count,
        }


class TranslateText(AgentOp):
    """Translate input text into ``target_language`` using the configured coding agent.

    Args:
        text: Source text in any language.
        target_language: Target language name or ISO code (e.g. ``"English"``, ``"Spanish"``).
        prompt_file: Optional Markdown file with domain glossary or style instructions.
        prompt: Optional inline style or terminology instructions.
        provider: Coding-agent CLI provider override.
        model: Model identifier override.
    """

    TITLE = "Translate Text"
    CATEGORY = "Text & Language"
    CACHEABLE = True

    class Outputs(TypedDict):
        text: str
        source_language: str

    def run(
        self,
        text: str,
        target_language: str = "English",
        prompt_file: MarkdownFile | None = None,
        prompt: str = "",
        provider: AgentProviderLiteral = "default",
        model: str = "",
        **extra: Any,
    ) -> Outputs:
        base_instruction = (
            f"Translate the provided `text` accurately into {target_language}, preserving "
            "meaning, paragraph structure, Markdown formatting, and tone. Do not summarize "
            "or omit details. Return the translated text in `text` and the detected ISO 639-1 "
            "language code of the original input in `source_language`."
        )
        combined_prompt = (
            f"{base_instruction}\n\n{prompt.strip()}" if prompt.strip() else base_instruction
        )
        res = self.run_agent(
            prompt_file=prompt_file,
            prompt=combined_prompt,
            provider=provider,
            model=model,
            text=text,
            target_language=target_language,
            **extra,
        )
        return res  # type: ignore[return-value]


__all__ = [
    "DetectLanguage",
    "TranslateText",
]
