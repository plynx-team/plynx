"""Hardcoded test toy operations for interactive checkpoints and replay tests."""

from __future__ import annotations

import sys
from typing import TypedDict

from plynx_sdk import Op


class AskFooOrWoo(Op):
    """Ask the user to pick foo or woo."""

    TITLE = "Ask foo or woo"
    CATEGORY = "Core / Interactive"
    CACHEABLE = False

    class Outputs(TypedDict):
        choice: str

    def run(self, prompt: str = "foo or woo?") -> Outputs:
        choice = self.checkpoint(
            prompt,
            options=["foo", "woo"],
            allow_freeform=False,
        )
        return {"choice": choice}


class SecretCodeChallenge(Op):
    """Challenge the user to enter the secret clearance code with interactive checkpoints."""

    TITLE = "Secret Code Challenge"
    CATEGORY = "Core / Interactive"
    CACHEABLE = False

    class Outputs(TypedDict):
        code: str
        message: str

    def run(self, prompt: str = "Select the secret clearance code to proceed:") -> Outputs:
        print("[STDOUT] Starting Secret Code Challenge...", flush=True)
        print(
            "[STDERR] Security checkpoint active. Clearance verification required.",
            file=sys.stderr,
            flush=True,
        )

        attempt = 1
        while True:
            print(
                f"[STDOUT] [Attempt {attempt}] Presenting checkpoint challenge to user...",
                flush=True,
            )
            print(
                f"[STDERR] [Security Guard] Halting execution. Awaiting clearance code (attempt {attempt})...",
                file=sys.stderr,
                flush=True,
            )

            answer = self.checkpoint(
                f"{prompt} (Attempt {attempt})",
                options=["007", "42", "404", "90210"],
                allow_freeform=False,
            )

            print(f"[STDOUT] Received user response: '{answer}'", flush=True)

            if answer == "42":
                print(
                    "[STDOUT] >>> ACCESS GRANTED: 42 is the Answer to the Ultimate Question of Life, the Universe, and Everything!",
                    flush=True,
                )
                print(
                    "[STDERR] [Security Guard] Clearance code 42 verified. Security gate opened.",
                    file=sys.stderr,
                    flush=True,
                )
                return {
                    "code": answer,
                    "message": "Access granted: 42 is the ultimate answer!",
                }

            print(
                f"[STDERR] [ACCESS DENIED] Code '{answer}' is incorrect! Clearance rejected.",
                file=sys.stderr,
                flush=True,
            )
            print(
                f"[STDOUT] Clearance failed for '{answer}'. Restarting verification challenge...",
                flush=True,
            )
            attempt += 1


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
    "AskFooOrWoo",
    "MultiStepQuestionnaire",
    "SecretCodeChallenge",
]
