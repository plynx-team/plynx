# Operations Reorganization, Audio Ecosystem & Demo Expansion Plan

This document is a self-contained, multi-stage engineering checklist for reorganizing Plynx v2's built-in operations, unifying categories, adding rich interactive/data ops, building a universal MIDI-based audio ecosystem, and curating clean showcase workflows.

---

## Agent Handoff Instructions

### Required Reading (Read First)
Before modifying any files, read these core documents inside `v2/`:
1. [`v2/AGENTS.md`](../AGENTS.md) — workspace ground rules, workflow vs. examples policy, dependency isolation policy.
2. [`v2/docs/ARCHITECTURE.md`](ARCHITECTURE.md) — system invariants, non-goals, IPC model, and process isolation.
3. [`v2/docs/PROTOCOL.md`](PROTOCOL.md) — exact schemas for `workflow.yaml`, AST subset, IPC manifests, cache keys, REST API.
4. [`v2/docs/PACK_RULES.md`](PACK_RULES.md) — authoring contract for Node Packs and ops.

### Ground Rules
- **`v2/` is the root.** Run commands from `v2/`. Never edit, rename, move, or delete any file outside `v2/`.
- **One task = one commit.** Tick the checkbox `- [x]` in this file in the same commit once its acceptance criteria and checks pass.
- **Lockfiles & Generated Types:**
  - Any time a pack's dependencies or code change, ensure `<pack>/uv.lock` is kept up to date (`cp v2/uv.lock v2/builtin_packs/<pack>/uv.lock` or `uv lock`).
  - Any time `plynx/api_models.py` changes, run `uv run python scripts/gen_ts_types.py` so `ui/src/api/types.gen.ts` stays in sync.
- **Keep dependencies lightweight and isolated:** `plynx-sdk` must remain 100% stdlib-only (`dependencies = []`). Core `plynx` stays free of heavy audio/ML/image libraries.

### Standard Verification Suite
Every code commit must pass:
```bash
python3 scripts/check_legacy_untouched.py
uv run ruff check
uv run ruff format --check
uv run mypy
uv run pytest
```
For UI changes, also run:
```bash
npm --prefix ui run lint
npm --prefix ui run typecheck
npm --prefix ui test -- --run
npm --prefix ui run build
```

### Effort & Model Selection Guide
- **Low Effort** *(Fast / lightweight model, e.g., Gemini Flash Low)*: Mechanical refactors, removing duplicates, renaming `CATEGORY` strings, updating hardcoded references in tests, writing/updating `.layout.json` and YAML examples.
- **Medium Effort** *(Balanced model, e.g., Gemini Flash High / Claude Sonnet)*: Implementing new domain ops, writing a pure-Python MIDI parser/writer, writing stereo-safe audio synthesis & mixing, extending AST docstring/parameter extraction, building UI form widgets.
- **High Effort** *(Strong reasoning model, e.g., Gemini Pro / Claude Opus)*: Cross-layer protocol and engine features spanning `PROTOCOL.md`, `plynx-sdk/harness.py`, `extractor.py`, `api_models.py`, `validator.py`, `cas/cache_key.py`, and frontend `NodeInspector.tsx` / `layout.ts` (e.g., `ALLOW_EXTRA_INPUTS`).

---

## Open Design Decisions (Confirm or Edit Before Executing)

Review these decisions with the project owner before starting Stage 1+. Defaults marked **[Recommended]** will be used unless changed:

- **D1. Canonical Score Format:** Standard MIDI (`MidiFile = Annotated[Path, Media("audio/midi")]`) **[Recommended]** vs. versioned Score JSON (`JsonFile`).
  - *Why MIDI wins:* Enforces strict port typing (prevents accidentally wiring arbitrary JSON into synths), is interoperable with external DAWs/tools, aligns with `v2/docs/TODO.md` (WebMIDI/Strudel), and pairs with `MidiPianoRoll` (`MidiFile -> ImageFile`) for visual inspection in the browser.
- **D2. "Extra Parameters" Scope:** **[Recommended: Both, phased]**
  - *Part A (Stage 3.1 — Medium):* Better structured/freeform widgets in `LiteralWidget.tsx` (custom text inputs with quick-fill preset chips, multiline grid editor for patterns/chords, `list[str]` add/remove editor). Requires zero protocol changes.
  - *Part B (Stage 3.2–3.3 — High):* Dynamic extra input ports (`ALLOW_EXTRA_INPUTS = True` / typed `**extra` in `run()`, `+ Add input` button in `NodeInspector`) for variadic ops like multi-track `AudioMixer`, `MidiMerge`, `TemplateFormat`, and future `AgentOp`.
- **D3. Pack Consolidation (`podcast_studio` & `media_studio`):** **[Recommended: Slim & Compose]**
  - Slim `podcast_studio` to a zero-heavy-dep macOS native voice & publishing pack (`TextToSpeech` + `ShowNotesGenerator`), removing its duplicated `WaveformVisualizer` and `BGMTrackGenerator`, and moving stereo-capable `AudioMixer` into a shared audio pack (`pedalboard_studio` or `media_studio`) so `podcast_producer_macos.yaml` genuinely composes ops across packs.
  - Decide whether to keep `media_studio/audio:AudioEchoFilter` as a lightweight stdlib-only alternative to `PedalboardDelay` or remove it to avoid confusion.
- **D4. Minimal Test Fixtures (`foo_or_woo.yaml`, `staged.yaml`) vs. Curated `examples/workflows/`:** **[Recommended: Decouple Test Fixtures]**
  - Currently ~12 test files (`test_cli_interaction.py`, `test_readme_quickstart.py`, `test_cli_runs.py`, `test_server.py`, `test_standard_io.py`, `test_resume.py`, `test_validator.py`, `test_models.py`, `tests/e2e/test_skeleton.py`, `test_dead_owner.py`) hardcode `examples/workflows/foo_or_woo.yaml`.
  - Moving barebones test fixtures into `tests/fixtures/workflows/` keeps `examples/workflows/` focused on 5–6 polished showcase pipelines (or keep `foo_or_woo.yaml` if explicitly wanted as the "Hello World" minimal quickstart).
- **D5. Category Grouping in `OpPalette.tsx`:** **[Recommended: Flat `"Domain / Subcategory"` strings in Stage 0]**
  - `OpPalette.tsx` already groups flatly by `op.category` across all packs (ignoring `op.pack`). Standardizing on clean `"Domain / Subcategory"` labels works immediately with zero UI code changes. A 2-level collapsible tree can be added as an optional polish item later.

---

## Audit Snapshot (Current Codebase Issues)

1. **Duplicate #1 (`Concat text`):** Exists in BOTH `builtin_packs/standard_io/src/standard_io/demo.py` (`standard_io/demo:Concat`) and `builtin_packs/standard_io/src/standard_io/text.py` (`standard_io/text:Concat`), and both appear in `default_fake_ops()` (`plynx/registry/__init__.py`). Because `PackRegistry` walks all `.py` files under `src/<pack>/` regardless of `__init__.py`, the UI shows two identical `"Concat text"` ops. Tests and UI tests are split between the two IDs.
2. **Duplicate #2 (`Audio Waveform Visualizer`):** Exists in BOTH `pedalboard_studio/inspect:AudioWaveformVisualizer` and `podcast_studio/visuals:WaveformVisualizer` with identical `TITLE = "Audio Waveform Visualizer"`.
3. **Category Fragmentation:** 27 ops are scattered across 16 categories; 9 categories have only 1 operation (`Audio / Mastering`, `Audio / Score`, `Media / Tools`, `Podcast / Mixing`, `Podcast / Music`, `Podcast / Publishing`, `Podcast / Visuals`, `Podcast / Voice (macOS only)`).
4. **Docstring Truncation Bug:** `NodeInspector.tsx` (line 1079) already renders `opEntry.description` using `<MarkdownPreviewer>`, **but** `plynx/registry/extractor.py` (lines 539–541 and 681–683) discards everything except the first non-empty line (`doc_lines[0]`). Additionally, `InputPortSpec` has no `description` field for per-parameter help.
5. **Audio Interoperability Bug:** `media_studio/audio.py` and `podcast_studio/mixer.py` collapse stereo WAVs to mono on read and always write 1-channel mono; `podcast_studio/mixer.py` misinterprets 32-bit PCM (`sampwidth == 4`) as float32; `media_studio/audio.py` silently returns zeros on non-16-bit WAVs.
6. **Missing Core Type Coverage in `standard_io`:** Zero ops exercise `int`, `float`, `bool`, `json` (`dict`/`list`), `CsvFile`, `JsonFile`, `MarkdownFile`, `Directory`, `Literal`, `Range`, or multi-question checkpoints.

---

## Target Category Taxonomy & Interchange Contracts

Consolidate from 16 fragmented categories down to **8 cohesive categories** (3–6 operations each, zero singletons, zero duplicates):

| Category | Pack(s) | Operations |
| :--- | :--- | :--- |
| `Core / Text & Data` | `standard_io` | `Echo`, `Concat` (`standard_io/text:Concat` only), `TemplateFormat`, `MathOp`, `JsonExtract`, `JsonMerge`, `CsvSummary` |
| `Core / Files` | `standard_io` | `ReadText`, `WriteText`, `ListDirectory`, `BundleDirectory`, `MarkdownReport` |
| `Core / Interactive` | `standard_io` | `AskFooOrWoo` (or `AskChoice`), `MultiStepQuestionnaire`, `SecretCodeChallenge` |
| `Audio / Score` | `pedalboard_studio` | `BachPreludeScore`, `ChordProgressionScore`, `StepSequencer`, `MidiMerge` *(all produce `MidiFile`)* |
| `Audio / Synth & Voice` | `pedalboard_studio`, `media_studio`, `podcast_studio` | `AcousticPianoSynth`, `PolySynth`, `DrumSynth`, `ToneSynth`, `TextToSpeech` *(macOS only)* |
| `Audio / Effects & Mixing` | `pedalboard_studio`, `media_studio` | `PedalboardToneFilter`, `PedalboardChorus`, `PedalboardDelay`, `PedalboardReverb`, `PedalboardMastering`, `AudioMixer` |
| `Image` | `media_studio` | `MandelbrotFractal`, `GeometricPattern`, `ImageFilterOp`, `CardOrPoster` |
| `Inspect & Visualize` | `media_studio`, `pedalboard_studio`, `podcast_studio` | `AudioWaveformVisualizer` *(unified single op)*, `MidiPianoRoll`, `AudioStats`, `MediaMetadataInspector`, `ShowNotesGenerator` |

### Canonical Cross-Pack File Contracts
1. **`AudioWav` (`audio/wav`)**: Standard PCM 16-bit WAV (`sampwidth == 2`), 44.1 kHz, mono (1 ch) or stereo (2 ch). Every producer outputs valid finalized RIFF headers with PCM16; every consumer supports both 1-channel and 2-channel inputs and preserves stereo when any input is stereo.
2. **`MidiFile` (`audio/midi`)**: Standard MIDI File (SMF Type 0/1) with tempo meta-events (`0x51`), note on/off events, velocity, and channel assignments (Channel 9 / 1-indexed Channel 10 reserved for GM drums/percussion). Zero external dependencies required to read/write SMF bytes in pure Python.

---

## Multistage Development Checklist

### Stage 0: Cleanup, Deduplication & Category Reorganization
*Effort: **Low** | Recommended Model: **Fast (Gemini Flash Low / Haiku)***

- [x] **0.1 Remove duplicate `Concat` operation**
  - **Files:** `builtin_packs/standard_io/src/standard_io/demo.py`, `builtin_packs/standard_io/src/standard_io/__init__.py`, `packages/plynx/src/plynx/registry/__init__.py`, `packages/plynx/src/plynx/engine/fake_executor.py`, and tests referencing `standard_io/demo:Concat`.
  - **Changes:** Delete `Concat` from `standard_io/demo.py`; keep `standard_io/text:Concat` as the single canonical `Concat` op. Remove `standard_io/demo:Concat` from `default_fake_ops()` and update `tests/` and `examples/workflows/foo_or_woo.yaml` references to `standard_io/text:Concat`.
  - **Accept:** `plynx ops --json` lists exactly one `Concat text` op (`standard_io/text:Concat`); all existing tests pass.

- [x] **0.2 Remove duplicate `Audio Waveform Visualizer`**
  - **Files:** `builtin_packs/media_studio/src/media_studio/inspect.py`, `builtin_packs/pedalboard_studio/src/pedalboard_studio/inspect.py`, `builtin_packs/podcast_studio/src/podcast_studio/visuals.py`, `examples/workflows/bach_prelude_c_major.yaml`, `examples/workflows/podcast_producer_macos.yaml`.
  - **Changes:** Consolidate `AudioWaveformVisualizer` into a single implementation in `media_studio/inspect.py` (using Pillow + stdlib `wave`, supporting mono/stereo and color themes, so no heavy DSP dependency is needed to plot waveforms). Remove duplicates from `pedalboard_studio` and `podcast_studio`; point showcase workflows to the unified op.
  - **Accept:** `plynx ops --json` shows exactly one `"Audio Waveform Visualizer"`; both workflows render waveform PNGs cleanly.

- [x] **0.3 Reorganize `CATEGORY` metadata across all packs**
  - **Files:** All `*.py` op files in `builtin_packs/{standard_io,media_studio,pedalboard_studio,podcast_studio}` and `packages/plynx/src/plynx/registry/__init__.py`.
  - **Changes:** Update `CATEGORY` literals to match the 8 target categories (`Core / Text & Data`, `Core / Files`, `Core / Interactive`, `Audio / Score`, `Audio / Synth & Voice`, `Audio / Effects & Mixing`, `Image`, `Inspect & Visualize`). Ensure zero singleton categories remain.
  - **Accept:** `uv run python -m plynx.cli ops --json` reports <= 8 categories and every category contains >= 2 ops.

- [x] **0.4 Standardize stereo-safe `AudioWav` contract across packs**
  - **Files:** `builtin_packs/media_studio/src/media_studio/audio.py`, `builtin_packs/podcast_studio/src/podcast_studio/mixer.py`, `builtin_packs/pedalboard_studio/src/pedalboard_studio/effects.py`, `tests/`.
  - **Changes:** Fix WAV readers so both mono (1 ch) and stereo (2 ch) 16-bit/24-bit/32-bit PCM files decode properly without collapsing stereo tracks to mono; ensure `AudioMixer` outputs 2-channel stereo whenever either input is stereo. Add cross-pack round-trip test (`media_studio` / `podcast_studio` -> `pedalboard_studio` -> `AudioWaveformVisualizer`).
  - **Accept:** Feeding stereo audio from `pedalboard_studio` through `AudioMixer` preserves 2 stereo channels without clipping or distortion.

---

### Stage 1: Rich Operator & Parameter Documentation
*Effort: **Medium** | Recommended Model: **Balanced (Gemini Flash High / Sonnet)***

- [ ] **1.1 Preserve full Markdown docstrings in AST extractor**
  - **Files:** `v2/docs/PROTOCOL.md`, `packages/plynx/src/plynx/registry/extractor.py`.
  - **Changes:** Update `PROTOCOL.md` section 3 and `extractor.py` (`_extract_class_op` & `_extract_function_op`) to use `inspect.cleandoc(doc)` instead of taking only `doc_lines[0]`, preserving full multi-paragraph Markdown usage notes, examples, and chord/pattern syntax docs. Add a `summary` (first line) or keep first line cleanly usable in tooltips while passing full markdown in `OpEntry.description`.
  - **Accept:** Multi-line Markdown docstrings appear completely in `OpEntry.description` and render cleanly in `NodeInspector`'s `<MarkdownPreviewer>`; `OpPalette` hover tooltips truncate gracefully to the first line.

- [ ] **1.2 Extract per-parameter descriptions from docstrings**
  - **Files:** `packages/plynx/src/plynx/api_models.py`, `packages/plynx/src/plynx/registry/extractor.py`, `scripts/gen_ts_types.py`, `ui/src/api/types.gen.ts`.
  - **Changes:** Add optional `description: str = ""` to `InputPortSpec` (and optionally `OutputPortSpec`). Parse Google-style `Args:` blocks in `run()` / `@op` function docstrings during AST extraction so each parameter carries its help text. Re-run `gen_ts_types.py`.
  - **Accept:** Regenerating TS types produces zero diff on repeat runs; parameter docstrings show up in `GET /ops`.

- [ ] **1.3 Display parameter tooltips & expandable op docs in UI**
  - **Files:** `ui/src/graph/NodeInspector.tsx`, `ui/src/graph/OpPalette.tsx`.
  - **Changes:** Show parameter `description` on hover / info icon (`help-circle`) next to each input port in `NodeInspector`. Ensure `OpPalette` shows clean one-line summary tooltips rather than dumping walls of Markdown into HTML `title`.
  - **Accept:** `npm --prefix ui test` and `npm --prefix ui run build` pass; new Vitest test verifies port help text renders.

---

### Stage 2: Core Primitive, File & Interactive Ops (`standard_io`)
*Effort: **Medium** | Recommended Model: **Balanced (Gemini Flash High / Sonnet)***

All operations in `standard_io` must use **Python Standard Library only** (`dependencies = ["plynx-sdk"]`).

- [ ] **2.1 Add primitive & data transformation ops (`Core / Text & Data`)**
  - **Files:** `builtin_packs/standard_io/src/standard_io/data.py` (or `text.py`).
  - **Changes:** Implement and test:
    - `TemplateFormat`: Python template string formatting (`{a}`, `{b}`, ...) converting scalars into formatted `str`.
    - `MathOp`: `a: float`, `b: float`, `operation: Literal["add", "sub", "mul", "div", "pow", "mod"]` -> `result: float`, `is_positive: bool` (tests `float`, `int`, `bool`, `Literal`).
    - `JsonExtract`: Extract value/key path from `JsonFile` or `dict` -> scalar/JSON outputs.
    - `JsonMerge`: Merge two JSON objects (`dict`) -> merged `dict` + `JsonFile`.
    - `CsvSummary`: Parse `CsvFile` via stdlib `csv` module -> `row_count: int`, `column_names: list`, `stats_json: JsonFile`, `summary_md: MarkdownFile`.
  - **Accept:** Unit tests cover every primitive type (`str`, `int`, `float`, `bool`, `json`) and semantic file type (`CsvFile`, `JsonFile`, `MarkdownFile`).

- [ ] **2.2 Add file & directory ops (`Core / Files`)**
  - **Files:** `builtin_packs/standard_io/src/standard_io/files.py`.
  - **Changes:** Implement and test:
    - `ListDirectory`: Accepts `Directory`, returns `file_count: int`, `filenames: list`, `manifest: JsonFile`.
    - `BundleDirectory`: Bundles up to 3 optional `Path` inputs into a single output `Directory` inside `workdir/bundle/`.
    - `MarkdownReport`: Builds a clean `MarkdownFile` report from title, body, and optional metrics `dict`.
  - **Accept:** Directory blob tree hashing and read-only materialization pass end-to-end tests via `LocalExecutor`.

- [ ] **2.3 Add `MultiStepQuestionnaire` & generic `AskChoice` (`Core / Interactive`)**
  - **Files:** `builtin_packs/standard_io/src/standard_io/demo.py` (or `interactive.py`), `packages/plynx/src/plynx/registry/__init__.py`.
  - **Changes:**
    - Implement `MultiStepQuestionnaire` (`CACHEABLE = False`): sequentially calls `self.checkpoint(...)` 3 times (e.g., Q1 choice from options, Q2 freeform string input with `allow_freeform=True`, Q3 confirmation/numeric selection), logging progress to both `stdout` and `stderr` to demonstrate Plynx's idempotent replay model (`cp_0`, `cp_1`, `cp_2`).
    - Implement flexible `AskChoice` accepting configurable `question: str`, `options_csv: str`, and `allow_freeform: bool`. (Keep `AskFooOrWoo` only if D4 retains `foo_or_woo.yaml`.)
  - **Accept:** Engine test executes `MultiStepQuestionnaire` with 3 sequential checkpoint resumes and verifies deterministic replay of `cp_0`, `cp_1`, `cp_2`.

- [ ] **2.4 Refresh `standard_io/uv.lock` and validate `default_fake_ops()`**
  - **Files:** `builtin_packs/standard_io/uv.lock`, `packages/plynx/src/plynx/registry/__init__.py`.
  - **Accept:** Zero `uv.lock` validation warnings; `plynx validate` passes on all workflows using new `standard_io` ops.

---

### Stage 3: Structured Widgets & Dynamic Extra Inputs (`ALLOW_EXTRA_INPUTS`)
*Effort: **High** | Recommended Model: **Strong (Gemini Pro / Claude Opus)***

- [ ] **3.1 Upgrade `LiteralWidget.tsx` for ergonomic freeform & structured editing**
  - **Files:** `ui/src/graph/LiteralWidget.tsx`, `v2/docs/PROTOCOL.md` (optional `examples`/`presets` or convention), tests in `ui/src/graph/`.
  - **Changes:** Add quick-fill preset suggestions or toggleable "Custom value" editing for string parameters (e.g., typing custom chord progressions like `"vi - IV - I - V"` alongside one-click preset buttons for classic progressions), and add an interactive string-list editor widget when typing array/JSON lists cleanly.
  - **Accept:** User can either pick a preset or type custom chords/patterns directly in the Inspector; Vitest UI tests pass.

- [ ] **3.2 Protocol & Engine support for `ALLOW_EXTRA_INPUTS` (variadic ops)**
  - **Files:** `v2/docs/PROTOCOL.md`, `packages/plynx-sdk/src/plynx_sdk/op.py`, `packages/plynx-sdk/src/plynx_sdk/harness.py`, `packages/plynx/src/plynx/api_models.py`, `packages/plynx/src/plynx/registry/extractor.py`, `packages/plynx/src/plynx/workflow/validator.py`, `packages/plynx/src/plynx/cas/cache_key.py`.
  - **Changes:**
    - Update `PROTOCOL.md` first: define `ALLOW_EXTRA_INPUTS = True` (or `@op(..., allow_extra_inputs=True)`) and typed `**extra: <Type>` in `run(...)`.
    - Add `allow_extra_inputs: bool = False` and `extra_inputs_type: InputPortSpec | None = None` to `OpEntry`.
    - Teach `extractor.py`, `harness.py` (`_prepare_call_kwargs`), `validator.py` (stop rejecting unknown ports on ops with `allow_extra_inputs=True`, validate types against `extra_inputs_type`), and `cache_key.py` (include extra file/scalar inputs deterministically).
    - Re-run `scripts/gen_ts_types.py`.
  - **Accept:** Test workflow wires arbitrary N inputs (e.g. `track_1`, `track_2`, `track_3`) into a variadic op; validation, cache hits/misses, and execution all pass.

- [ ] **3.3 UI support for adding/wiring dynamic extra inputs**
  - **Files:** `ui/src/graph/NodeInspector.tsx`, `ui/src/graph/layout.ts`, `ui/src/graph/OperationNode.tsx`, `ui/src/graph/GraphView.tsx`.
  - **Changes:** When `opEntry.allow_extra_inputs` is true, render dynamically added input ports as connectable handles on `OperationNode` and add an `+ Add input` control in `NodeInspector` (prompting for `snake_case` port name).
  - **Accept:** Vitest tests verify adding, wiring, and removing dynamic extra input ports on canvas and inspector.

---

### Stage 4: Universal MIDI Score Ecosystem & Creative Audio Ops
*Effort: **Medium–High** | Recommended Model: **Balanced/Strong (Gemini Flash High / Pro)***

- [ ] **4.1 Add `MidiFile` semantic type (`audio/midi`)**
  - **Files:** `v2/docs/PROTOCOL.md`, `packages/plynx-sdk/src/plynx_sdk/types.py`, `packages/plynx/src/plynx/registry/extractor.py`, `ui/src/components/FeatherIcon.tsx`, `tests/`.
  - **Changes:** Add `MidiFile = Annotated[Path, Media("audio/midi")]` and register `"MidiFile": "audio/midi"` in `SEMANTIC_MEDIA_ALIASES`. Map `audio/midi` to a music/sliders icon in UI.
  - **Accept:** `MidiFile` ports reject `AudioWav` wires and accept `MidiFile` wires cleanly during validation.

- [ ] **4.2 Implement stdlib Standard MIDI File (SMF) helper + `Audio / Score` ops**
  - **Files:** `builtin_packs/pedalboard_studio/src/pedalboard_studio/midi_io.py`, `builtin_packs/pedalboard_studio/src/pedalboard_studio/score.py` (or `synth.py`).
  - **Changes:** Implement pure-Python SMF reader/writer helper and build/update ops outputting `MidiFile`:
    - `BachPreludeScore`: Outputs authentic BWV 846 as `MidiFile` (keep JSON metadata summary as secondary output if helpful).
    - `ChordProgressionScore`: Parses user-editable Roman numeral patterns (e.g., `"vi - IV - I - V"`, `"ii7 - V7 - Imaj7 - VI7"`, `"I - V - vi - IV"`) in any `key` (`C`, `Dm`, `F#`, `Ab`, etc.), with `bpm`, `bars`, `voicing_style` (`block`, `arpeggio`, `waltz`, `strumming`), and thorough Markdown docstring documenting the Roman numeral DSL.
    - `StepSequencer`: Parses a 16-step ASCII/text grid (or multi-track drum + bassline pattern lines like `"kick:  x...x...x...x...\nsnare: ....x.......x...\nhat:   x.x.x.x.x.x.x.x.\nbass:  C2..E2..G2..A2.."`) into a synced multi-channel `MidiFile` (Channel 9 for drums, Channel 0 for melodic synth). Document pattern syntax thoroughly in docstring.
    - `MidiMerge`: Merges multiple `MidiFile` inputs (2 base tracks or N via `ALLOW_EXTRA_INPUTS`) onto separate MIDI channels cleanly.
  - **Accept:** Every score op produces valid Type 0/1 `.mid` files readable by standard MIDI parsers; custom user patterns parse reliably.

- [ ] **4.3 Upgrade synths & mixers for universal MIDI -> WAV -> Mastering composition**
  - **Files:** `builtin_packs/pedalboard_studio/src/pedalboard_studio/synth.py`, `builtin_packs/pedalboard_studio/src/pedalboard_studio/effects.py`, `builtin_packs/pedalboard_studio/src/pedalboard_studio/mastering.py`.
  - **Changes:**
    - Update `AcousticPianoSynth` to consume `MidiFile` (ignoring drum channel 9 or rendering melodic channels cleanly).
    - Add `PolySynth` (warm analog saw/pad/pluck waveforms with ADSR filter envelope, consuming `MidiFile`) and `DrumSynth` (synthesizing kick, snare, closed/open hi-hat, tom, clap from Channel 9 MIDI notes into stereo `AudioWav`).
    - Add/move stereo-preserving multi-track `AudioMixer` (supporting N tracks via Stage 3 `ALLOW_EXTRA_INPUTS` plus optional sidechain/ducking mode for voiceover over music).
  - **Accept:** Any score op (`BachPreludeScore`, `ChordProgressionScore`, `StepSequencer`, `MidiMerge`) wires interchangeably into any synthesizer (`AcousticPianoSynth`, `PolySynth`, `DrumSynth`), and any synth/TTS output wires into `Pedalboard*` effects and `AudioMixer`.

- [ ] **4.4 Add `MidiPianoRoll` visualizer (`Inspect & Visualize`)**
  - **Files:** `builtin_packs/media_studio/src/media_studio/inspect.py` (or `pedalboard_studio/inspect.py`).
  - **Changes:** Implement `MidiPianoRoll`: converts `MidiFile -> ImageFile` by rendering pitch-vs-time note rectangles colored by MIDI channel/velocity with dark studio piano-roll styling.
  - **Accept:** Users can preview generated MIDI sequences directly inside Plynx's UI before/alongside audio rendering.

- [ ] **4.5 Slim down `podcast_studio` to macOS voice & publishing (`macOS only`)**
  - **Files:** `builtin_packs/podcast_studio/`.
  - **Changes:** Keep `TextToSpeech` *(note `(macOS only)` in title & Markdown docstring)* and `ShowNotesGenerator`; retire redundant `BGMTrackGenerator` and `WaveformVisualizer`; point `podcast_producer_macos.yaml` to compose `ChordProgressionScore -> PolySynth` (or `ToneSynth`), `TextToSpeech`, shared `AudioMixer` (with ducking enabled), `AudioWaveformVisualizer`, and `ShowNotesGenerator`.
  - **Accept:** `podcast_studio` has near-zero dependencies, clearly notes macOS requirement on `TextToSpeech`, and demonstrates true cross-pack composition.

---

### Stage 5: Curated Demo Workflow Suite & Test Hygiene
*Effort: **Low–Medium** | Recommended Model: **Fast / Balanced***

- [ ] **5.1 Separate internal test fixtures from showcase `examples/workflows/` (per D4)**
  - **Files:** `tests/fixtures/workflows/`, test files referencing `examples/workflows/foo_or_woo.yaml`, `examples/workflows/`.
  - **Changes:** If D4 opts to clean up `examples/workflows/`, copy `foo_or_woo.yaml` and `staged.yaml` into `tests/fixtures/workflows/` and repoint unit tests there, leaving `examples/workflows/` clean for the curated showcase workflows.
  - **Accept:** Full pytest suite passes with zero reliance on user showcase examples (except dedicated workflow validation tests).

- [ ] **5.2 Create & polish the 5–6 curated showcase workflows (with `.layout.json` sidecars)**
  Target 5–6 high-signal examples spanning all domains and complexity levels:
  1. **`interactive_wizard_staged.yaml`** *(Simple — Core / Interactive + Stage Gates)*: Demonstrates `AskChoice` + `MultiStepQuestionnaire` (multiple sequential checkpoints + stdout/stderr logs) -> Stage Approval Gate (`require_approval: true`) -> `TemplateFormat` -> `MarkdownReport`.
  2. **`data_bundle_pipeline.yaml`** *(Simple/Medium — Core / Data & Files)*: Demonstrates `CsvSummary` + `MathOp` + `JsonMerge` + `WriteText` -> `BundleDirectory` -> `ListDirectory` -> `MarkdownReport`. Exercises `int`, `float`, `bool`, `dict`, `list`, `CsvFile`, `JsonFile`, `Directory`, `MarkdownFile`.
  3. **`generative_art_studio.yaml`** *(Medium — Image)*: Combines `MandelbrotFractal`, `GeometricPattern`, `ImageFilterOp`, `CardOrPoster`, and `MediaMetadataInspector`.
  4. **`midi_groove_studio.yaml`** *(Medium/Complex — Cross-Pack Music Composition)*: Combines `ChordProgressionScore` (`"vi - IV - I - V"`) + `StepSequencer` (custom drum/bass pattern) -> `MidiMerge` -> `MidiPianoRoll` preview + parallel `PolySynth` & `DrumSynth` -> `AudioMixer` -> `PedalboardReverb` -> `PedalboardMastering` -> `AudioWaveformVisualizer`.
  5. **`bach_prelude_c_major.yaml`** *(Complex — Audio Score -> Physical Synth -> Pedalboard Mastering)*: Updated to use `BachPreludeScore (MidiFile)` -> `MidiPianoRoll` & `AcousticPianoSynth` -> `PedalboardToneFilter` -> `PedalboardChorus` -> `PedalboardReverb` -> `PedalboardMastering` -> `AudioWaveformVisualizer` + `AudioStats`.
  6. **`podcast_producer_macos.yaml`** *(Medium — macOS-only Cross-Pack Podcast Producer)*: Uses `TextToSpeech` *(macOS only)* + `ChordProgressionScore -> PolySynth` -> `AudioMixer` (auto-ducking) -> `AudioWaveformVisualizer` + `ShowNotesGenerator`.
  - **Accept:** Every example in `examples/workflows/` has a clean `.layout.json` sidecar, validates with zero errors or `uv.lock` warnings, and runs cleanly end-to-end.

- [ ] **5.3 Update documentation (`v2/README.md`, walkthroughs)**
  - **Files:** `v2/README.md`, `v2/docs/PLAN.md` (if needed).
  - **Changes:** Document the curated showcase examples and the 8 op categories clearly. Run full verification suite (`ruff`, `mypy`, `pytest`, UI `lint`/`typecheck`/`test`/`build`, `check_legacy_untouched.py`).
  - **Accept:** All checks pass cleanly on a fresh run.

---

## Stage Summary Table

| Stage | Focus | Effort Level | Recommended Model Tier |
| :--- | :--- | :--- | :--- |
| **Stage 0** | Dedupe `Concat` & `WaveformVisualizer`, unify 8 categories, fix stereo WAV contract | **Low** | Fast *(Flash Low / Haiku)* |
| **Stage 1** | Full Markdown op docstrings & per-port parameter help extraction + UI tooltips | **Medium** | Balanced *(Flash High / Sonnet)* |
| **Stage 2** | Core stdlib ops in `standard_io` (`MathOp`, `CsvSummary`, `Directory`, `MultiStepQuestionnaire`) | **Medium** | Balanced *(Flash High / Sonnet)* |
| **Stage 3** | Structured widgets (`LiteralWidget`) + Protocol/Engine/UI support for `ALLOW_EXTRA_INPUTS` | **High** | Strong *(Pro / Opus)* |
| **Stage 4** | `MidiFile` type, Roman chord parser, `StepSequencer`, `PolySynth`, `DrumSynth`, `MidiPianoRoll`, slim `podcast_studio` | **Medium–High** | Balanced / Strong |
| **Stage 5** | Decouple test fixtures, build/layout 5–6 curated showcase workflows, end-to-end validation | **Low–Medium** | Fast / Balanced |
