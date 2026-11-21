"""Tests for the interactive SecretCodeChallenge checkpoint operation."""

from __future__ import annotations

import io
from contextlib import redirect_stderr, redirect_stdout

import pytest
from plynx_sdk.checkpoint import CheckpointInterrupt, checkpoint_context
from standard_io.demo import SecretCodeChallenge


def test_secret_code_challenge_loop_and_logging() -> None:
    """Verify SecretCodeChallenge restarts on wrong answers and succeeds on 42."""
    op = SecretCodeChallenge()
    prompt = "Clearance Verification"

    # Attempt 1: No answers yet -> raises cp_0 checkpoint
    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
        with pytest.raises(CheckpointInterrupt) as excinfo:
            with checkpoint_context(answers={}):
                op.run(prompt)

    cp_0 = excinfo.value.manifest
    assert cp_0.checkpoint_id == "cp_0"
    assert cp_0.options == ["007", "42", "404", "90210"]
    assert "Attempt 1" in cp_0.question
    assert "[STDOUT] Starting Secret Code Challenge..." in stdout_buf.getvalue()
    assert "[STDERR] Security checkpoint active." in stderr_buf.getvalue()

    # Attempt 2: User answers '007' -> wrong answer, prints error, raises cp_1
    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
        with pytest.raises(CheckpointInterrupt) as excinfo:
            with checkpoint_context(answers={"cp_0": "007"}):
                op.run(prompt)

    cp_1 = excinfo.value.manifest
    assert cp_1.checkpoint_id == "cp_1"
    assert cp_1.options == ["007", "42", "404", "90210"]
    assert "Attempt 2" in cp_1.question
    assert "Received user response: '007'" in stdout_buf.getvalue()
    assert "[STDERR] [ACCESS DENIED] Code '007' is incorrect!" in stderr_buf.getvalue()
    assert "Clearance failed for '007'. Restarting verification challenge..." in stdout_buf.getvalue()

    # Attempt 3: User answers '007' then '404' -> wrong answer again, raises cp_2
    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
        with pytest.raises(CheckpointInterrupt) as excinfo:
            with checkpoint_context(answers={"cp_0": "007", "cp_1": "404"}):
                op.run(prompt)

    cp_2 = excinfo.value.manifest
    assert cp_2.checkpoint_id == "cp_2"
    assert cp_2.options == ["007", "42", "404", "90210"]
    assert "Attempt 3" in cp_2.question
    assert "[STDERR] [ACCESS DENIED] Code '404' is incorrect!" in stderr_buf.getvalue()

    # Attempt 4: User finally enters '42' -> succeeds!
    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
        with checkpoint_context(answers={"cp_0": "007", "cp_1": "404", "cp_2": "42"}):
            result = op.run(prompt)

    assert result["code"] == "42"
    assert "42 is the ultimate answer" in result["message"]
    assert "ACCESS GRANTED: 42 is the Answer" in stdout_buf.getvalue()
    assert "Clearance code 42 verified. Security gate opened." in stderr_buf.getvalue()
