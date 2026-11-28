# Guide: Setting Up Agentic Workflows

PLynx runs coding-agent operations (`AgentOp` and `StageValidatorOp`) by spawning local non-interactive CLI coding harnesses inside isolated node working directories. This guide covers provider installation, credentials, workspace configuration, and offline testing.

## 1. Supported Providers & CLI Binaries

Install and authenticate at least one supported coding-agent CLI on your machine (`PATH`):

| `provider` value | CLI Binary | Typical Authentication |
| :--- | :--- | :--- |
| `claude` | `claude` (Claude Code) | `claude login` session or `ANTHROPIC_API_KEY` |
| `cursor` | `cursor-agent` | `cursor-agent login` session or `CURSOR_API_KEY` |
| `codex` | `codex` (OpenAI Codex CLI) | `codex login` session or `OPENAI_API_KEY` |
| `gemini` | `gemini` (or `agy`) | Google OAuth CLI login or `GEMINI_API_KEY` |
| `opencode` | `opencode` | Provider API keys (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc.) or local Ollama |
| `goose` | `goose` | `goose configure` or provider API keys |
| `aider` | `aider` | Provider API keys (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc.) or local Ollama |
| `custom` | User command template | Configured via `agent.custom_command` in `plynx.yaml` or `PLYNX_AGENT_CUSTOM_COMMAND` |
| `mock` | *(built-in, no CLI)* | Offline deterministic provider for `pytest` and local dry runs |

All CLI adapters run non-interactively (`stdin=DEVNULL`), omit `--bare` so workspace `.agents/skills/` and `AGENTS.md` are discovered upward, and pass explicit `--resume <session_id>` (never `--continue`) across `checkpoint_batch()` restarts.

### Provider & Model Specifics

- **`gemini` (`gemini` vs. `agy`)**: Uses `gemini` (`@google/gemini-cli`) if on `PATH`, otherwise falls back automatically to `agy` (Antigravity CLI, e.g. `model: gemini-3.8-flash-medium`). Run `agy models` to list valid Antigravity model IDs.
- **`claude` (Claude Code)**: Enforces structured output via `--json-schema`. Numeric `Range(min, max)` bounds are moved into field descriptions for Anthropic's decoder and strictly validated by PLynx on return.
- **`codex` (OpenAI Codex CLI)**: Runs with the `workspace-write` sandbox and the `on-request` approval policy. Normalizes closed `Outputs(TypedDict)` schemas into OpenAI's `strict: true` subset (`turn_schema.codex.json`). For open map schemas (such as `StageValidatorOp` `graph_patch` or `dict` ports), Codex writes `workdir/turn_output.json` directly. `codex exec resume` reuses the prior thread without `--output-schema`.
- **`opencode` & `aider` model IDs**: Pass provider-prefixed model strings (`provider/model`, e.g. `anthropic/claude-sonnet-4-5` or `ollama/qwen2.5-coder`). `aider` runs with `--no-auto-commits --no-gitignore` so it can write `turn_output.json` inside `.plynx/` without creating Git commits in your workspace, and does not persist cross-process session IDs (multi-turn context is passed via PLynx's prompt envelope).
- **Large prompts**: Prompts exceeding 24 KB are read from `workdir/turn_prompt.md` rather than passed inline on `argv`, avoiding Windows (`32 KB`) and POSIX `ARG_MAX` limits.

## 2. Credentials & Secrets (`.env` vs. Host CLI Login)

PLynx never stores credentials in `workflow.yaml`, `plynx.yaml`, snapshots, manifests, or SQLite. Node subprocesses receive credentials from two sources:

1. **Existing CLI Login Sessions (OAuth / Subscription)**:
   - By default (`env_passthrough` unset or `["*"]`), PLynx inherits your host environment including `HOME`, `PATH`, and OS keychain/config paths.
   - If you already signed in via `claude`, `cursor-agent`, `codex`, or `gemini` in your terminal, PLynx agent nodes work with no extra API keys.
2. **API Keys in `.env` (BYO Key / CI)**:
   - Create a gitignored `.env` file at your workspace root:
     ```bash
     ANTHROPIC_API_KEY=sk-ant-...
     OPENAI_API_KEY=sk-...
     GEMINI_API_KEY=...
     ```
   - Ensure `.env` is listed in `.gitignore`. PLynx loads `.env` into node child processes automatically (overriding inherited host values of the same name).
3. **Restricting Host Environment (`env_passthrough`)**:
   - If you set `env_passthrough` in `plynx.yaml` to restrict which host variables reach child processes, list any API key or provider config variables your CLI needs:
     ```yaml
     env_passthrough:
       - ANTHROPIC_API_KEY
       - OPENAI_API_KEY
       - GEMINI_API_KEY
       - PLYNX_AGENT_PROVIDER
       - PLYNX_AGENT_MODEL
     ```
   - Essential OS variables (`PATH`, `HOME`, `USER`, `TMPDIR`, `SSL_CERT_FILE`, etc.) are always preserved automatically.

## 3. Configuring Provider, Model & Guardrails

Set workspace defaults in `plynx.yaml`:

```yaml
workflows: workflows
packs:
  - custom_packs
agent:
  provider: claude
  model: ""
  agent_concurrency: 2
  max_injected_nodes: 3
  models:
    - claude-sonnet-4-5
    - gpt-5
```

- Leave `model: ""` to let the CLI tool use its own configured default model.
- `agent.models` populates optional `<datalist>` autocomplete suggestions in the Web UI `.PropertiesBar`.
- `agent.agent_concurrency` limits concurrent `AgentOp` / `StageValidatorOp` executions separately from CPU `concurrency`.
- `agent.max_injected_nodes` caps total dynamic nodes a validator or agent may inject in one run (default `3`).

**Precedence** (lowest to highest; resolved values are written into `inputs.json` before cache-key hashing):

1. `plynx.yaml` `agent.provider` / `agent.model` (or `PLYNX_AGENT_PROVIDER` / `PLYNX_AGENT_MODEL` env vars)
2. `workflow.yaml` top-level `agent: { provider, model }`
3. CLI flags: `plynx run --agent-provider codex --agent-model gpt-5 workflows/my_flow.yaml`
4. Node input port `provider` / `model` (or `--set my_node.model=gpt-5`)

## 4. Using Built-in Agent Ops

`standard_io` ships five ready-to-use agent ops:

- `standard_io/agent:AgentPrompt` — takes `prompt` / `prompt_file`, `provider`, `model`, and arbitrary `**extra` inputs; returns `response: MarkdownFile`.
- `standard_io/agent:AgentText` — returns `text: str` for direct wiring into string ports or stage-validator adapter splices.
- `standard_io/agent:AgentJson` — returns `data: dict` and `file: JsonFile` (pair with `standard_io/data:JsonExtract` to fan out fields).
- `standard_io/agent:AgentBool` — returns `value: bool` and `reason: str`.
- `standard_io/agent:StageSupervisor` — attaches to `stages.<stage_id>.validator:` to inspect stage outputs, `self.warn()` warnings, and failure logs, and optionally propose a bounded graph patch.

```yaml
version: 1
name: agent_summary_demo
stages:
  ingest:
    title: "1. Ingest"
    validator:
      op: standard_io/agent:StageSupervisor
      mode: on_anomaly
      allow_graph_edits: confirm
      inputs:
        prompt: "Inspect any stage warnings and propose a bounded adapter splice if needed."
  summarize:
    title: "2. Summarize"
nodes:
  source_text:
    op: standard_io/demo:Echo
    stage: ingest
    inputs:
      text: "Quarterly revenue rose 14% driven by enterprise renewals."
  draft_brief:
    op: standard_io/agent:AgentPrompt
    stage: summarize
    inputs:
      prompt: "Write a 3-bullet executive brief from the input text."
      source: $source_text.text
```

## 5. Offline Testing with `provider: mock`

For CI or fast local testing without calling external LLMs, set `--agent-provider mock` and supply scripted JSON envelopes via `PLYNX_MOCK_AGENT_RESPONSES` (either an inline JSON string or a path to a JSON file):

```bash
export PLYNX_MOCK_AGENT_RESPONSES='{"draft_brief": [{"status": "completed", "outputs": {"response": "# Executive Brief\n\n- Revenue rose 14%.\n"}}]}'
plynx run --non-interactive --agent-provider mock workflows/agent_summary_demo.yaml
```
