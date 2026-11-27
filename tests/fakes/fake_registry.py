"""In-memory FakeRegistry and default_fake_ops for testing."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from plynx.api_models import InputPortSpec, OpEntry, OutputPortSpec


def default_fake_ops() -> list[OpEntry]:
    """Return the built-in ``standard_io`` fake op entries used in Phase 0."""
    return [
        OpEntry(
            id="standard_io/demo:AskFooOrWoo",
            pack="standard_io",
            module="toy_ops",
            name="AskFooOrWoo",
            kind="class",
            title="Ask foo or woo",
            category="Core / Interactive",
            cacheable=False,
            description="Ask the user to pick foo or woo.",
            inputs=[
                InputPortSpec(
                    name="prompt",
                    type="str",
                    required=False,
                    default="foo or woo?",
                ),
            ],
            outputs=[
                OutputPortSpec(name="choice", type="str"),
            ],
            source="tests/fixtures/toy_ops.py",
        ),
        OpEntry(
            id="standard_io/demo:SecretCodeChallenge",
            pack="standard_io",
            module="toy_ops",
            name="SecretCodeChallenge",
            kind="class",
            title="Secret Code Challenge",
            category="Core / Interactive",
            cacheable=False,
            description="Challenge the user to enter the secret clearance code with interactive checkpoints.",
            inputs=[
                InputPortSpec(
                    name="prompt",
                    type="str",
                    required=False,
                    default="Select the secret clearance code to proceed:",
                ),
            ],
            outputs=[
                OutputPortSpec(name="code", type="str"),
                OutputPortSpec(name="message", type="str"),
            ],
            source="tests/fixtures/toy_ops.py",
        ),
        OpEntry(
            id="standard_io/demo:Echo",
            pack="standard_io",
            module="demo",
            name="Echo",
            kind="class",
            title="Echo text",
            category="Core / Text & Data",
            cacheable=True,
            description="Echo an input string to its output.",
            inputs=[
                InputPortSpec(name="text", type="str", required=True),
            ],
            outputs=[
                OutputPortSpec(name="text", type="str"),
            ],
            source="builtin_packs/standard_io/src/standard_io/demo.py",
        ),
        OpEntry(
            id="standard_io/text:Concat",
            pack="standard_io",
            module="text",
            name="Concat",
            kind="class",
            title="Concat text",
            category="Core / Text & Data",
            cacheable=True,
            description="Join two strings.",
            inputs=[
                InputPortSpec(name="a", type="str", required=True),
                InputPortSpec(name="b", type="str", required=False, default=" "),
            ],
            outputs=[
                OutputPortSpec(name="text", type="str"),
            ],
            source="builtin_packs/standard_io/src/standard_io/text.py",
        ),
        OpEntry(
            id="standard_io/demo:ReadText",
            pack="standard_io",
            module="demo",
            name="ReadText",
            kind="class",
            title="Read text file",
            category="Core / Files",
            cacheable=True,
            description="Read UTF-8 text from a file.",
            inputs=[
                InputPortSpec(name="path", type="file", required=True),
            ],
            outputs=[
                OutputPortSpec(name="text", type="str"),
            ],
            source="builtin_packs/standard_io/src/standard_io/demo.py",
        ),
        OpEntry(
            id="standard_io/demo:WriteText",
            pack="standard_io",
            module="demo",
            name="WriteText",
            kind="class",
            title="Write text file",
            category="Core / Files",
            cacheable=True,
            description="Write UTF-8 text to a file.",
            inputs=[
                InputPortSpec(name="text", type="str", required=True),
                InputPortSpec(
                    name="filename",
                    type="str",
                    required=False,
                    default="out.txt",
                ),
            ],
            outputs=[
                OutputPortSpec(name="file", type="file", media="text/plain"),
            ],
            source="builtin_packs/standard_io/src/standard_io/demo.py",
        ),
        OpEntry(
            id="standard_io/data:TemplateFormat",
            pack="standard_io",
            module="data",
            name="TemplateFormat",
            kind="class",
            title="Template Format",
            category="Core / Text & Data",
            cacheable=True,
            description="Format a template string using scalar parameters and optional dictionary values.\n\nArgs:\n    template: Python format string containing replacement fields like '{a}', '{b}'.\n    values: Optional dictionary mapping field names to values.",
            inputs=[
                InputPortSpec(
                    name="template",
                    type="str",
                    required=True,
                    description="Python format string containing replacement fields like '{a}', '{b}'.",
                ),
                InputPortSpec(
                    name="values",
                    type="json",
                    required=False,
                    default=None,
                    description="Optional dictionary mapping field names to values.",
                ),
            ],
            outputs=[
                OutputPortSpec(name="text", type="str"),
            ],
            allow_extra_inputs=True,
            extra_inputs_type=None,
            source="builtin_packs/standard_io/src/standard_io/data.py",
        ),
        OpEntry(
            id="standard_io/data:MathOp",
            pack="standard_io",
            module="data",
            name="MathOp",
            kind="class",
            title="Math Operation",
            category="Core / Text & Data",
            cacheable=True,
            description="Perform basic arithmetic operations on numeric operands.\n\nArgs:\n    a: First numeric operand.\n    b: Second numeric operand.\n    operation: Arithmetic operation: 'add', 'sub', 'mul', 'div', 'pow', or 'mod'.",
            inputs=[
                InputPortSpec(
                    name="a",
                    type="float",
                    required=True,
                    description="First numeric operand.",
                ),
                InputPortSpec(
                    name="b",
                    type="float",
                    required=False,
                    default=0.0,
                    description="Second numeric operand.",
                ),
                InputPortSpec(
                    name="operation",
                    type="str",
                    options=["add", "sub", "mul", "div", "pow", "mod"],
                    required=False,
                    default="add",
                    description="Arithmetic operation: 'add', 'sub', 'mul', 'div', 'pow', or 'mod'.",
                ),
            ],
            outputs=[
                OutputPortSpec(name="result", type="float"),
                OutputPortSpec(name="is_positive", type="bool"),
                OutputPortSpec(name="rounded", type="int"),
            ],
            source="builtin_packs/standard_io/src/standard_io/data.py",
        ),
        OpEntry(
            id="standard_io/data:JsonExtract",
            pack="standard_io",
            module="data",
            name="JsonExtract",
            kind="class",
            title="JSON Extract",
            category="Core / Text & Data",
            cacheable=True,
            description="Extract a value or sub-tree from a JSON object or JSON file.\n\nArgs:\n    json_data: In-memory JSON dictionary.\n    json_file: Path to a JSON file on disk.\n    key: Dot-separated path to the key to extract (e.g. 'user.profile.name').\n        Empty string targets root.\n    default: Fallback string value if the specified key path is not found.",
            inputs=[
                InputPortSpec(
                    name="json_data",
                    type="json",
                    required=False,
                    default=None,
                    description="In-memory JSON dictionary.",
                ),
                InputPortSpec(
                    name="json_file",
                    type="file",
                    media="application/json",
                    required=False,
                    default=None,
                    description="Path to a JSON file on disk.",
                ),
                InputPortSpec(
                    name="key",
                    type="str",
                    required=False,
                    default="",
                    description="Dot-separated path to the key to extract (e.g. 'user.profile.name'). Empty string targets root.",
                ),
                InputPortSpec(
                    name="default",
                    type="str",
                    required=False,
                    default="",
                    description="Fallback string value if the specified key path is not found.",
                ),
            ],
            outputs=[
                OutputPortSpec(name="value_str", type="str"),
                OutputPortSpec(name="value_json", type="json"),
                OutputPortSpec(name="found", type="bool"),
            ],
            source="builtin_packs/standard_io/src/standard_io/data.py",
        ),
        OpEntry(
            id="standard_io/data:JsonMerge",
            pack="standard_io",
            module="data",
            name="JsonMerge",
            kind="class",
            title="JSON Merge",
            category="Core / Text & Data",
            cacheable=True,
            description="Merge two JSON objects and write the combined dictionary to a JSON file.\n\nArgs:\n    a: Primary JSON dictionary.\n    b: Secondary JSON dictionary whose keys take precedence on conflict.\n    output_filename: Relative destination filename for the merged JSON artifact.",
            inputs=[
                InputPortSpec(
                    name="a",
                    type="json",
                    required=True,
                    description="Primary JSON dictionary.",
                ),
                InputPortSpec(
                    name="b",
                    type="json",
                    required=True,
                    description="Secondary JSON dictionary whose keys take precedence on conflict.",
                ),
                InputPortSpec(
                    name="output_filename",
                    type="str",
                    required=False,
                    default="merged.json",
                    description="Relative destination filename for the merged JSON artifact.",
                ),
            ],
            outputs=[
                OutputPortSpec(name="merged", type="json"),
                OutputPortSpec(name="file", type="file", media="application/json"),
            ],
            source="builtin_packs/standard_io/src/standard_io/data.py",
        ),
        OpEntry(
            id="standard_io/data:CsvSummary",
            pack="standard_io",
            module="data",
            name="CsvSummary",
            kind="class",
            title="CSV Summary",
            category="Core / Text & Data",
            cacheable=True,
            description="Parse a CSV file and output summary metrics, stats JSON, and summary Markdown.\n\nArgs:\n    csv_file: Path to the input CSV file.\n    delimiter: Column delimiter character used in the CSV.",
            inputs=[
                InputPortSpec(
                    name="csv_file",
                    type="file",
                    media="text/csv",
                    required=True,
                    description="Path to the input CSV file.",
                ),
                InputPortSpec(
                    name="delimiter",
                    type="str",
                    required=False,
                    default=",",
                    description="Column delimiter character used in the CSV.",
                ),
            ],
            outputs=[
                OutputPortSpec(name="row_count", type="int"),
                OutputPortSpec(name="column_count", type="int"),
                OutputPortSpec(name="column_names", type="json"),
                OutputPortSpec(name="stats_json", type="file", media="application/json"),
                OutputPortSpec(name="summary_md", type="file", media="text/markdown"),
            ],
            source="builtin_packs/standard_io/src/standard_io/data.py",
        ),
        OpEntry(
            id="standard_io/files:ListDirectory",
            pack="standard_io",
            module="files",
            name="ListDirectory",
            kind="class",
            title="List Directory",
            category="Core / Files",
            cacheable=True,
            description="List the contents of an input directory and produce file statistics and a manifest.\n\nArgs:\n    directory: Directory path to inspect and list.\n    recursive: Whether to traverse subdirectories recursively.\n    pattern: Glob pattern to filter matching file paths.",
            inputs=[
                InputPortSpec(
                    name="directory",
                    type="directory",
                    required=True,
                    description="Directory path to inspect and list.",
                ),
                InputPortSpec(
                    name="recursive",
                    type="bool",
                    required=False,
                    default=True,
                    description="Whether to traverse subdirectories recursively.",
                ),
                InputPortSpec(
                    name="pattern",
                    type="str",
                    required=False,
                    default="*",
                    description="Glob pattern to filter matching file paths.",
                ),
            ],
            outputs=[
                OutputPortSpec(name="file_count", type="int"),
                OutputPortSpec(name="filenames", type="json"),
                OutputPortSpec(name="manifest", type="file", media="application/json"),
            ],
            source="builtin_packs/standard_io/src/standard_io/files.py",
        ),
        OpEntry(
            id="standard_io/files:BundleDirectory",
            pack="standard_io",
            module="files",
            name="BundleDirectory",
            kind="class",
            title="Bundle Directory",
            category="Core / Files",
            cacheable=True,
            description="Bundle arbitrary files or sub-directories into a single structured output directory.\n\nArgs:\n    bundle_name: Name of the output destination folder in the working directory.",
            inputs=[
                InputPortSpec(
                    name="bundle_name",
                    type="str",
                    required=False,
                    default="bundle",
                    description="Name of the output destination folder in the working directory.",
                ),
            ],
            outputs=[
                OutputPortSpec(name="bundle", type="directory"),
                OutputPortSpec(name="file_count", type="int"),
            ],
            allow_extra_inputs=True,
            extra_inputs_type=InputPortSpec(name="files", type="file", required=False),
            source="builtin_packs/standard_io/src/standard_io/files.py",
        ),
        OpEntry(
            id="standard_io/files:MarkdownReport",
            pack="standard_io",
            module="files",
            name="MarkdownReport",
            kind="class",
            title="Markdown Report",
            category="Core / Files",
            cacheable=True,
            description="Generate a clean Markdown document report from a title, body, and metrics.\n\nArgs:\n    title: Title displayed as the primary H1 header.\n    body: Descriptive Markdown body content for the report.\n    metrics: Optional key-value metrics dictionary to render as a list.\n    filename: Output filename for the generated Markdown report.",
            inputs=[
                InputPortSpec(
                    name="title",
                    type="str",
                    required=False,
                    default="Execution Report",
                    description="Title displayed as the primary H1 header.",
                ),
                InputPortSpec(
                    name="body",
                    type="str",
                    required=False,
                    default="",
                    description="Descriptive Markdown body content for the report.",
                ),
                InputPortSpec(
                    name="metrics",
                    type="json",
                    required=False,
                    default=None,
                    description="Optional key-value metrics dictionary to render as a list.",
                ),
                InputPortSpec(
                    name="filename",
                    type="str",
                    required=False,
                    default="report.md",
                    description="Output filename for the generated Markdown report.",
                ),
            ],
            outputs=[
                OutputPortSpec(name="report", type="file", media="text/markdown"),
            ],
            source="builtin_packs/standard_io/src/standard_io/files.py",
        ),
        OpEntry(
            id="standard_io/interactive:AskChoice",
            pack="standard_io",
            module="interactive",
            name="AskChoice",
            kind="class",
            title="Ask Choice",
            category="Core / Interactive",
            cacheable=False,
            description="Prompt the user with a question and configurable choices or optional freeform entry.\n\nArgs:\n    question: Question or prompt presented to the user at the checkpoint.\n    options_csv: Comma-separated list of candidate options to select from.\n    allow_freeform: Whether the user is permitted to enter freeform text.",
            inputs=[
                InputPortSpec(
                    name="question",
                    type="str",
                    required=False,
                    default="Please choose an option:",
                    description="Question or prompt presented to the user at the checkpoint.",
                ),
                InputPortSpec(
                    name="options_csv",
                    type="str",
                    required=False,
                    default="Option A, Option B, Option C",
                    description="Comma-separated list of candidate options to select from.",
                ),
                InputPortSpec(
                    name="allow_freeform",
                    type="bool",
                    required=False,
                    default=False,
                    description="Whether the user is permitted to enter freeform text.",
                ),
            ],
            outputs=[
                OutputPortSpec(name="choice", type="str"),
            ],
            source="builtin_packs/standard_io/src/standard_io/interactive.py",
        ),
        OpEntry(
            id="standard_io/interactive:AskQuestions",
            pack="standard_io",
            module="interactive",
            name="AskQuestions",
            kind="class",
            title="Ask Questions",
            category="Core / Interactive",
            cacheable=False,
            description="Prompt the user with a configurable list of checkpoint questions in a single pause.\n\nArgs:\n    questions: Non-empty list of question specification dictionaries (id, question,\n        optional header, options, multi_select, allow_freeform).",
            inputs=[
                InputPortSpec(
                    name="questions",
                    type="json",
                    required=True,
                    description="Non-empty list of question specification dictionaries (id, question, optional header, options, multi_select, allow_freeform).",
                ),
            ],
            outputs=[
                OutputPortSpec(name="answers", type="json"),
                OutputPortSpec(name="summary_markdown", type="str"),
            ],
            source="builtin_packs/standard_io/src/standard_io/interactive.py",
        ),
        OpEntry(
            id="standard_io/interactive:MultiStepQuestionnaire",
            pack="standard_io",
            module="toy_ops",
            name="MultiStepQuestionnaire",
            kind="class",
            title="Multi-Step Questionnaire",
            category="Core / Interactive",
            cacheable=False,
            description="Multi-step questionnaire exercising sequential checkpoints and idempotent replay.\n\nArgs:\n    intro_prompt: Introductory banner message logged to standard output at start.",
            inputs=[
                InputPortSpec(
                    name="intro_prompt",
                    type="str",
                    required=False,
                    default="Starting 3-step interactive questionnaire.",
                    description="Introductory banner message logged to standard output at start.",
                ),
            ],
            outputs=[
                OutputPortSpec(name="step1_answer", type="str"),
                OutputPortSpec(name="step2_answer", type="str"),
                OutputPortSpec(name="step3_answer", type="str"),
                OutputPortSpec(name="summary", type="str"),
            ],
            source="tests/fixtures/toy_ops.py",
        ),
    ]


class FakeRegistry:
    """In-memory ``OpRegistry`` implementation used in Phase 0 and unit tests."""

    def __init__(
        self,
        ops: Iterable[OpEntry] | None = None,
        *,
        discovered_packs: dict[str, Path] | None = None,
    ) -> None:
        initial = default_fake_ops() if ops is None else list(ops)
        self._ops: dict[str, OpEntry] = {entry.id: entry for entry in initial}
        self.discovered_packs: dict[str, Path] = dict(discovered_packs or {})

    def register(self, entry: OpEntry) -> None:
        """Add or replace an ``OpEntry`` in this registry."""
        self._ops[entry.id] = entry

    def get(self, op_id: str) -> OpEntry | None:
        """Return the ``OpEntry`` for ``op_id``, or ``None`` if not registered."""
        return self._ops.get(op_id)

    def list_ops(self) -> list[OpEntry]:
        """Return all registered ``OpEntry`` items sorted by ``id``."""
        return [self._ops[key] for key in sorted(self._ops.keys())]


__all__ = [
    "FakeRegistry",
    "default_fake_ops",
]
