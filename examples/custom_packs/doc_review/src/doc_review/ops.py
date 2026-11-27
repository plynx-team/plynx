"""Document inspection, translation adapter, and batch-checkpoint review operations."""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict

from plynx_sdk import CheckpointQuestion, MarkdownFile, Op

_FRENCH_MARKERS = frozenset({"bonjour", "rapport", "merci", "trimestriel", "revenus", "equipe"})

_FR_TO_EN_PHRASES: tuple[tuple[str, str], ...] = (
    ("Bonjour equipe.", "Hello team."),
    ("Rapport trimestriel:", "Quarterly report:"),
    ("les revenus ont augmente de", "revenue increased by"),
    ("pour cent grace aux renouvellements entreprises.", "percent driven by enterprise renewals."),
    ("Merci.", "Thank you."),
    ("Bonjour", "Hello"),
    ("Merci", "Thank you"),
)


class InspectDocument(Op):
    """Inspect a document and emit a warning when non-English text is detected.

    Args:
        document_text: Raw text content to inspect.
    """

    TITLE = "Inspect Document"
    CATEGORY = "Examples / Document Review"
    CACHEABLE = True

    class Outputs(TypedDict):
        text: str
        language: str
        word_count: int

    def run(self, document_text: str) -> Outputs:
        tokens = {word.strip(".,:;!?").lower() for word in document_text.split()}
        if tokens & _FRENCH_MARKERS:
            language = "fr"
            self.warn("Detected non-English document (lang=fr)")
        else:
            language = "en"
        return {
            "text": document_text,
            "language": language,
            "word_count": len(document_text.split()),
        }


class TranslateToEnglish(Op):
    """Translate detected French document text into English for downstream review.

    Args:
        text: Source text to translate.
    """

    TITLE = "Translate to English"
    CATEGORY = "Examples / Document Review"
    CACHEABLE = True

    class Outputs(TypedDict):
        text: str

    def run(self, text: str) -> Outputs:
        translated = text
        for src, dst in _FR_TO_EN_PHRASES:
            translated = translated.replace(src, dst)
        return {"text": translated}


class CompileReviewBrief(Op):
    """Collect reviewer preferences in a single batch checkpoint and write a Markdown brief.

    Args:
        text: Document text to summarize in the brief.
        title: Heading for the generated Markdown report.
    """

    TITLE = "Compile Review Brief"
    CATEGORY = "Examples / Document Review"
    CACHEABLE = True

    class Outputs(TypedDict):
        report: MarkdownFile
        summary: str

    def run(
        self,
        text: str,
        title: str = "Document Review Brief",
    ) -> Outputs:
        answers = self.checkpoint_batch(
            [
                CheckpointQuestion(
                    id="audience",
                    header="Target Audience",
                    question="Who is the primary audience for this review?",
                    options=["Executive", "Engineering", "Legal"],
                    multi_select=False,
                    allow_freeform=True,
                ),
                CheckpointQuestion(
                    id="focus",
                    header="Focus Areas",
                    question="Which focus areas should be highlighted?",
                    options=["Metrics", "Risks", "Action Items"],
                    multi_select=True,
                    allow_freeform=False,
                ),
            ]
        )
        audience_val = answers.get("audience", "Executive")
        audience = audience_val if isinstance(audience_val, str) else ", ".join(audience_val)
        focus_val = answers.get("focus", [])
        focus_list = focus_val if isinstance(focus_val, list) else [focus_val]
        focus_display = ", ".join(focus_list) if focus_list else "General"

        lines = [
            f"# {title}",
            "",
            f"- **Audience**: {audience}",
            f"- **Focus Areas**: {focus_display}",
            "",
            "## Document Content",
            "",
            text.strip(),
            "",
        ]
        out_path = Path("review_brief.md")
        out_path.write_text("\n".join(lines), encoding="utf-8")
        summary = f"{title} ({audience}; {focus_display})"
        return {"report": out_path, "summary": summary}


__all__ = [
    "CompileReviewBrief",
    "InspectDocument",
    "TranslateToEnglish",
]
