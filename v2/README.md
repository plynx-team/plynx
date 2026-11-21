# PLynx v2

**PLynx v2** is a domain-agnostic, local-first platform for building and running reproducible workflows (DAGs).

PLynx combines the simplicity of declarative YAML workflows, the power of isolated Python Node Packs, content-addressed caching, human-in-the-loop checkpoints, and an interactive modern web UI.

---

## Highlights

* **Local-First & Fast**: Zero daemon or database setup required. Runs purely against local files, SQLite, and a content-addressed blob store in `.plynx/`.
* **Isolated Node Execution**: Operations run in isolated virtual environments managed by `uv`, ensuring reproducible dependencies per pack without conflict.
* **Deterministic Caching**: Fine-grained content-addressed caching keyed by op AST source code, `uv.lock`, inputs, parameters, and checkpoint answers.
* **Human-in-the-Loop**: Interactive `checkpoint()` prompts let nodes pause execution for user decisions, questions, or approval gates, then resume seamlessly.
* **Modern Web UI**: Switch between a sequential Stepper view and an interactive React Flow DAG editor with live SSE logs, artifact previews, and drag-and-drop wiring.
* **Isolated Scratch Debugging**: Re-run and reproduce failing node attempts in a temporary scratch directory with `plynx run-node <node_dir>`.

---

## Installation

### Run directly with `uvx` (No installation needed)

```bash
uvx plynx --help
uvx plynx ui
```

### Install using `uv` or `pip`

```bash
# Using uv (recommended)
uv tool install plynx

# Or with pip into a virtual environment
pip install plynx
```

### Prerequisites

* Python **3.11+**
* [uv](https://docs.astral.sh/uv/) (recommended package installer and environment runner)

---

## Quickstart

### 1. Validate a Workflow

Statically validate workflow DAG structure, wiring ports, and pack requirements:

```bash
plynx validate examples/workflows/foo_or_woo.yaml
```

### 2. Run a Workflow

Execute a workflow directly in your terminal:

```bash
plynx run --answer pick.cp_0=foo examples/workflows/foo_or_woo.yaml
```

For interactive checkpoint prompts, omit `--answer` to answer directly from your terminal:

```bash
plynx run examples/workflows/foo_or_woo.yaml
```

### 3. Inspect Runs

List recent workflow runs:

```bash
plynx runs
```

Inspect the detailed state, parameters, and node statuses of a specific run:

```bash
plynx runs <run_id>
```

### 4. Start the Web UI

Launch the local PLynx web server (bound to `127.0.0.1:8080`) and open your browser:

```bash
plynx ui
```

### 5. Clean Old Runs (Garbage Collection)

Reclaim disk space by pruning old unpinned runs, orphaned cache entries, and unreferenced blobs:

```bash
plynx clean --days 7
```

---

## Curated Showcase Workflows

PLynx includes production-grade reference workflows in `examples/workflows/`, complete with interactive `.layout.json` sidecars:

| Workflow | Category Focus | Highlights |
| :--- | :--- | :--- |
| [`interactive_wizard_staged.yaml`](examples/workflows/interactive_wizard_staged.yaml) | `Core / Interactive` | Multi-step interactive survey with idempotent `checkpoint()` replay, human-in-the-loop stage approval gate (`require_approval: true`), string template formatting, and Markdown report generation. |
| [`data_bundle_pipeline.yaml`](examples/workflows/data_bundle_pipeline.yaml) | `Core / Data & Files` | Full type-coverage data pipeline across `int`, `float`, `bool`, `dict`, `list`, `CsvFile`, `JsonFile`, `Directory`, and `MarkdownFile`. Combines CSV ingestion, math calculations, JSON merging, and directory bundling. |
| [`generative_art_studio.yaml`](examples/workflows/generative_art_studio.yaml) | `Image` | Procedural digital art pipeline generating Mandelbrot fractals, geometric vector waves, edge enhancement filters, studio presentation cards, and media metadata auditing. |
| [`midi_groove_studio.yaml`](examples/workflows/midi_groove_studio.yaml) | `Audio` | Cross-pack music composition pipeline combining Roman numeral chord progression (`vi - IV - I - V`), a 16-step ASCII drum/bass sequencer, MIDI merger, piano-roll visualizer, analog `PolySynth`, 808 `DrumSynth`, multi-track `AudioMixer`, and Pedalboard mastering. |
| [`bach_prelude_c_major.yaml`](examples/workflows/bach_prelude_c_major.yaml) | `Audio` | Classical physical modeling: J.S. Bach Prelude I (BWV 846) MIDI score, concert grand acoustic piano synthesis, Spotify Pedalboard spatial effects (tone filter, chorus, delay, reverb), studio limiter, and waveform visualizer. |
| [`podcast_producer_macos.yaml`](examples/workflows/podcast_producer_macos.yaml) | `Audio / Voice` | Automated podcast producer composing macOS native speech synthesis (`say`), lo-fi Rhodes chord progression, automatic sidechain audio ducking mixer, waveform visualizer, and Markdown show notes. *(macOS only)* |

---

## Built-in Operation Categories

PLynx v2 features 40+ built-in operations organized into **8 cohesive categories**:

* **`Core / Text & Data`**: `Echo`, `Concat`, `TemplateFormat`, `MathOp`, `JsonExtract`, `JsonMerge`, `CsvSummary`
* **`Core / Files`**: `ReadText`, `WriteText`, `ListDirectory`, `BundleDirectory`, `MarkdownReport`
* **`Core / Interactive`**: `AskChoice`, `AskFooOrWoo`, `MultiStepQuestionnaire`, `SecretCodeChallenge`
* **`Audio / Score`**: `BachPreludeScore`, `ChordProgressionScore`, `StepSequencer`, `MidiMerge` *(all output `MidiFile`)*
* **`Audio / Synth & Voice`**: `AcousticPianoSynth`, `PolySynth`, `DrumSynth`, `ToneSynth`, `TextToSpeech` *(macOS only)*
* **`Audio / Effects & Mixing`**: `AudioMixer` *(multi-track with dynamic ducking)*, `PedalboardToneFilter`, `PedalboardChorus`, `PedalboardDelay`, `PedalboardReverb`, `PedalboardMastering`, `AudioEchoFilter`
* **`Image`**: `MandelbrotFractal`, `GeometricPattern`, `ImageFilterOp`, `CardOrPoster`
* **`Inspect & Visualize`**: `AudioWaveformVisualizer`, `MidiPianoRoll`, `AudioStats`, `MediaMetadataInspector`, `ShowNotesGenerator`

---

## Development Setup

To build and run PLynx from source:

```bash
# 1. Clone repository and navigate to v2
git clone https://github.com/plynx-team/plynx.git
cd plynx/v2

# 2. Sync workspace dependencies
uv sync

# 3. Build UI assets
cd ui
npm ci
npm run build
cd ..

# 4. Run tests and linting
uv run ruff check
uv run ruff format --check
uv run mypy
uv run pytest

# 5. Build wheels
uv run python scripts/build.py
```

---

## Documentation

* [Architecture & Invariants](docs/ARCHITECTURE.md)
* [Protocol & Schema Specifications](docs/PROTOCOL.md)
* [Pack Rules & Best Practices](docs/PACK_RULES.md)
* [Guide: Creating a Workflow](docs/guides/create_workflow.md)
* [Guide: Authoring a Node Pack](docs/guides/author_pack.md)
* [Guide: Debugging with `run-node`](docs/guides/debug_failed_node.md)

---

## License

Apache-2.0
