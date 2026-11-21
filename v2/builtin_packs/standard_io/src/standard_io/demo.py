"""Demo operations in the built-in ``standard_io`` pack (PROTOCOL.md sections 2 & 3)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TypedDict

from plynx_sdk import Op, TextFile


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
        print("[STDERR] Security checkpoint active. Clearance verification required.", file=sys.stderr, flush=True)

        attempt = 1
        while True:
            print(f"[STDOUT] [Attempt {attempt}] Presenting checkpoint challenge to user...", flush=True)
            print(f"[STDERR] [Security Guard] Halting execution. Awaiting clearance code (attempt {attempt})...", file=sys.stderr, flush=True)

            answer = self.checkpoint(
                f"{prompt} (Attempt {attempt})",
                options=["007", "42", "404", "90210"],
                allow_freeform=False,
            )

            print(f"[STDOUT] Received user response: '{answer}'", flush=True)

            if answer == "42":
                print("[STDOUT] >>> ACCESS GRANTED: 42 is the Answer to the Ultimate Question of Life, the Universe, and Everything!", flush=True)
                print("[STDERR] [Security Guard] Clearance code 42 verified. Security gate opened.", file=sys.stderr, flush=True)
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


class Echo(Op):
    """Echo an input string to its output."""

    TITLE = "Echo text"
    CATEGORY = "Core / Text & Data"
    CACHEABLE = True

    class Outputs(TypedDict):
        text: str

    def run(self, text: str) -> Outputs:
        return {"text": text}


class ReadText(Op):
    """Read UTF-8 text from a file."""

    TITLE = "Read text file"
    CATEGORY = "Core / Files"
    CACHEABLE = True

    class Outputs(TypedDict):
        text: str

    def run(self, path: Path) -> Outputs:
        return {"text": path.read_text(encoding="utf-8")}


class WriteText(Op):
    """Write UTF-8 text to a file."""

    TITLE = "Write text file"
    CATEGORY = "Core / Files"
    CACHEABLE = True

    class Outputs(TypedDict):
        file: TextFile

    def run(self, text: str, filename: str = "out.txt") -> Outputs:
        out_path = Path(filename)
        if out_path.is_absolute() or ".." in out_path.parts or len(out_path.parts) != 1:
            raise ValueError(f"filename must be a single relative file name, got {filename!r}")
        out_path.write_text(text, encoding="utf-8")
        return {"file": out_path}


__all__ = [
    "AskFooOrWoo",
    "Echo",
    "ReadText",
    "SecretCodeChallenge",
    "WriteText",
]
