"""Interactive operations in the built-in ``standard_io`` pack."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypedDict

from plynx_sdk import CheckpointQuestion, Op


class AskChoice(Op):
    """Prompt the user with a question and configurable choices or optional freeform entry.

    Args:
        question: Question or prompt presented to the user at the checkpoint.
        options_csv: Comma-separated list of candidate options to select from.
        allow_freeform: Whether the user is permitted to enter freeform text.
    """

    TITLE = "Ask Choice"
    CATEGORY = "Core / Interactive"
    CACHEABLE = False

    class Outputs(TypedDict):
        choice: str

    def run(
        self,
        question: str = "Please choose an option:",
        options_csv: str = "Option A, Option B, Option C",
        allow_freeform: bool = False,
    ) -> Outputs:
        opts = [opt.strip() for opt in options_csv.split(",") if opt.strip()]
        choice = self.checkpoint(
            question,
            options=opts if opts else None,
            allow_freeform=allow_freeform,
        )
        return {"choice": choice}


class AskQuestions(Op):
    """Prompt the user with a configurable list of checkpoint questions in a single pause.

    Args:
        questions: Non-empty list of question specification dictionaries (id, question,
            optional header, options, multi_select, allow_freeform).
    """

    TITLE = "Ask Questions"
    CATEGORY = "Core / Interactive"
    CACHEABLE = False

    class Outputs(TypedDict):
        answers: dict[str, Any]
        summary_markdown: str

    def run(self, questions: list[Any]) -> Outputs:
        if not questions:
            raise ValueError("questions must be a non-empty list of question definitions")

        parsed_questions: list[CheckpointQuestion] = []
        for idx, item in enumerate(questions):
            if not isinstance(item, Mapping):
                raise ValueError(f"questions[{idx}] must be a mapping, got {type(item).__name__}")
            parsed_questions.append(CheckpointQuestion.from_dict(item))

        raw_answers = self.checkpoint_batch(parsed_questions)
        answers: dict[str, Any] = dict(raw_answers)

        bullet_lines: list[str] = []
        for q in parsed_questions:
            label = q.header.strip() if q.header.strip() else q.question.strip()
            ans = answers.get(q.id, "")
            rendered = ", ".join(str(v) for v in ans) if isinstance(ans, list) else str(ans)
            bullet_lines.append(f"- **{label}**: {rendered}")

        return {
            "answers": answers,
            "summary_markdown": "\n".join(bullet_lines),
        }


__all__ = [
    "AskChoice",
    "AskQuestions",
]
