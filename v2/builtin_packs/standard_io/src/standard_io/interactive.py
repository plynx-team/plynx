"""Interactive operations in the built-in ``standard_io`` pack."""

from __future__ import annotations

import sys
from typing import TypedDict

from plynx_sdk import Op


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


class MultiStepQuestionnaire(Op):
    """Multi-step questionnaire exercising sequential checkpoints and idempotent replay.

    Args:
        intro_prompt: Introductory banner message logged to standard output at start.
    """

    TITLE = "Multi-Step Questionnaire"
    CATEGORY = "Core / Interactive"
    CACHEABLE = False

    class Outputs(TypedDict):
        step1_answer: str
        step2_answer: str
        step3_answer: str
        summary: str

    def run(
        self,
        intro_prompt: str = "Starting 3-step interactive questionnaire.",
    ) -> Outputs:
        print(f"[STDOUT] {intro_prompt}", flush=True)
        print(
            "[STDERR] [MultiStepQuestionnaire] Commencing step 1: Role Selection",
            file=sys.stderr,
            flush=True,
        )

        # Step 1: cp_0 - Choice selection from options
        step1 = self.checkpoint(
            "Step 1/3: What is your primary role?",
            options=["Data Scientist", "Software Engineer", "DevOps Engineer", "Researcher"],
            allow_freeform=False,
        )
        print(f"[STDOUT] Step 1 completed. Selected role: {step1}", flush=True)
        print(
            "[STDERR] [MultiStepQuestionnaire] Step 1 passed. Commencing step 2: Goal Input",
            file=sys.stderr,
            flush=True,
        )

        # Step 2: cp_1 - Freeform string input
        step2 = self.checkpoint(
            "Step 2/3: Briefly describe your pipeline goal:",
            options=None,
            allow_freeform=True,
        )
        print(f"[STDOUT] Step 2 completed. Pipeline goal: {step2}", flush=True)
        print(
            "[STDERR] [MultiStepQuestionnaire] Step 2 passed. Commencing step 3: Target Env",
            file=sys.stderr,
            flush=True,
        )

        # Step 3: cp_2 - Choice selection from options
        step3 = self.checkpoint(
            "Step 3/3: Choose execution target environment:",
            options=["Local Machine", "Staging Cluster", "Production Cloud"],
            allow_freeform=False,
        )
        print(f"[STDOUT] Step 3 completed. Target environment: {step3}", flush=True)
        print(
            "[STDERR] [MultiStepQuestionnaire] All 3 steps complete. Returning summary.",
            file=sys.stderr,
            flush=True,
        )

        summary = f"Role: {step1} | Goal: {step2} | Environment: {step3}"
        return {
            "step1_answer": step1,
            "step2_answer": step2,
            "step3_answer": step3,
            "summary": summary,
        }


__all__ = [
    "AskChoice",
    "MultiStepQuestionnaire",
]
