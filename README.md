# SOM-CODE

**A premium terminal-native AI coding agent with an Ink/React TUI, Python tool harness, OpenCode Go support, durable sessions, permission gates, and multi-model provider routing.**

SOM-CODE is a Claude Code / OpenCode-inspired coding agent that runs in your terminal. The frontend is a polished TypeScript + Ink interface; the backend is a Python JSONL agent server with tools, sandboxing, provider adapters, permission policy, sessions, and finish-gate metadata.

> Status: v1.0.0 initial public release. The package has been smoke-tested locally from the packed npm tarball and from a clean temporary install.

---

## Why SOM-CODE exists

Most LLMs can write code, but a useful coding agent needs more than raw chat:

- A terminal UI that shows thoughts, tool calls, progress, and final state clearly.
- Deterministic tool execution boundaries.
- Permission modes that actually block risky actions.
- Provider flexibility instead of being locked to one model vendor.
- Durable session logs so work can be resumed and audited.
- A clean packaged runtime that works after install, not only from source.

SOM-CODE is an attempt to build that harness in a small, understandable codebase.

---

## Highlights

- **Terminal-native TUI** built with Ink and React.
- **Python backend harness** with JSONL streaming between Node and Python.
- **OpenCode Go support** via OpenAI-compatible provider routing.
- **OpenRouter, OpenAI, Anthropic, Ollama, DeepSeek, Groq-style provider support** through model spec aliases.
- **Real permission modes** enforced in backend hooks, not just displayed in the UI.
- **Plan mode** that restricts the agent to read-only/research tools.
- **Durable sessions** in `.som-code/sessions/` with resume/list support.
- **Repo map snapshots** stored with session metadata.
- **Finish gates** that mark whether the task truly completed or needs review.
- **Safe subagent scaffolds** for read-only repo mapping, review, and test planning.
- **SOM.md context files** for project-specific conventions.
- **npm package cleanup**: published package ships the runnable built backend under `dist/backend`.

---

## Repository

```bash
git clone https://github.com/SomSamantray/som-code-agent.git
cd som-code-agent
```

GitHub: <https://github.com/SomSamantray/som-code-agent>

---

## Requirements

You need:

- **Node.js 18+**
- **Python 3.10+**
- `npm`
- At least one model provider/API key, unless you only want to run local smoke checks or `doctor`

Check versions:

```bash
node --version
python3 --version
npm --version
```

---

## Install from source

```bash
git clone https://github.com/SomSamantray/som-code-agent.git
cd som-code-agent
npm install
npm run build
node bin/som-code.js doctor
```

Run in development mode:

```bash
npm run dev
```

Run the built CLI directly:

```bash
node bin/som-code.js
```

Install globally from the local checkout:

```bash
npm install -g .
som-code doctor
```

---

## Install from a packed tarball

The local package flow is:

```bash
npm run build
npm pack
npm install -g ./som-code-1.0.0.tgz
som-code doctor
```

The package tarball is intentionally small and contains:

- `bin/som-code.js`
- `dist/index.js`
- `dist/backend/...`
- `README.md`
- `LICENSE`
- `package.json`

It does **not** ship `node_modules`, `.env` files, local sessions, or packed `.tgz` artifacts.

---

## Quick start

Set a provider key, then launch the TUI:

```bash
export OPENROUTER_API_KEY="sk-or-v1-..."
som-code
```

Start with a task:

```bash
som-code "Inspect this repo and explain how it works"
```

Use plan mode:

```bash
som-code --plan "Design a safe refactor for the authentication module"
```

Use a specific workspace:

```bash
som-code --workspace /path/to/project "Find the test command and run a safe review"
```

Resume the latest session:

```bash
som-code --resume latest
```

List sessions:

```bash
som-code --list-sessions
# or
som-code sessions
```

---

## CLI commands

```bash
som-code                          Interactive TUI
som-code "Build a REST API"       Start with a task
som-code --plan "Design auth"     Plan mode
som-code exec "Write quicksort"   Non-interactive entry style
som-code --model ollama/qwen2.5:7b
som-code --resume latest          Resume latest session
som-code --list-sessions          List saved sessions
som-code sessions                 List saved sessions
som-code init                     Create SOM.md-style project context
som-code doctor                   Check runtime, backend, and providers
som-code --help                   Show help
som-code --version                Show version
```

Common flags:

```bash
-m, --model <model>          Select model/provider spec
-p, --permission <mode>     Permission mode: plan, default, acceptEdits, bypass
-w, --workspace <path>      Project workspace root
-r, --resume <id|latest>    Resume a saved session
--plan                      Force plan/read-only mode
--list-sessions             List saved sessions
```

---

## Provider and model configuration

SOM-CODE uses model specs like:

```text
provider/model-name
```

Examples:

```bash
som-code --model openrouter/anthropic/claude-sonnet-4
som-code --model openrouter/openai/gpt-4o
som-code --model opencode-go/gpt-5.5
som-code --model opencode/my-model
som-code --model ollama/qwen2.5:7b
```

### Environment variables

Core variables:

```bash
export SOM_MODEL="openrouter/anthropic/claude-sonnet-4"
export OPENROUTER_API_KEY="sk-or-v1-..."
```

OpenCode Go:

```bash
export OPENCODE_GO_API_KEY="..."
export OPENCODE_GO_BASE_URL="https://your-opencode-go-compatible-endpoint/v1"
export OPENCODE_GO_MODEL="your-default-model"
```

Other providers:

```bash
export OPENAI_API_KEY="..."
export ANTHROPIC_API_KEY="..."
export DEEPSEEK_API_KEY="..."
export GROQ_API_KEY="..."
```

Local Ollama:

```bash
ollama serve
ollama pull qwen2.5:7b
som-code --model ollama/qwen2.5:7b
```

### OpenCode Go aliases

These aliases resolve to the OpenCode Go provider adapter:

```bash
opencode-go/<model>
opencode/<model>
opencode_go/<model>
```

That means these are equivalent in intent:

```bash
som-code --model opencode-go/gpt-5.5
som-code --model opencode/gpt-5.5
som-code --model opencode_go/gpt-5.5
```

---

## Permission modes

SOM-CODE has backend-enforced permission modes.

### `plan`

Read/research only. This mode allows safe inspection tools and blocks write/edit/shell execution.

Use it when you want analysis before changes:

```bash
som-code --plan "Study the repo and propose a migration plan"
```

Allowed categories include:

- file reads
- directory listing
- grep/glob search
- web fetch/search
- todo/plan tools
- skill lookup
- safe subagent scaffolds

Blocked categories include:

- file writes
- edits
- shell execution

### `default`

General safe mode. Allows reads/searches and safe shell commands, but blocks edits/writes.

```bash
som-code --permission default "Inspect the test suite"
```

### `acceptEdits`

Allows file edits/writes while still blocking dangerous shell/network/publish-style commands.

```bash
som-code --permission acceptEdits "Fix the README typo and update tests"
```

### `bypass`

Bypasses the policy layer. Use only when you understand the risk.

```bash
som-code --permission bypass "Refactor this package"
```

---

## Sessions and resume

SOM-CODE stores durable session records under the active workspace:

```text
<workspace>/.som-code/sessions/<session-id>.json
```

A session stores:

- session id
- title/task
- model
- workspace path
- created/updated timestamps
- JSONL protocol events
- repo map snapshot
- git branch/head metadata when available

List sessions:

```bash
som-code --list-sessions
```

Resume latest:

```bash
som-code --resume latest
```

Resume by id prefix:

```bash
som-code --resume 20260525
```

The TUI displays a resume banner with the session id, number of protocol events, and mapped repo files.

---

## Repo map

When a session starts, SOM-CODE builds a compact repository snapshot. It records the files most useful for context and avoids noisy/generated folders such as:

- `.git`
- `node_modules`
- `dist`
- `.som-code`
- `.venv`
- `__pycache__`

This lets resumed sessions know the workspace shape without dumping the entire tree into the model context.

---

## Finish gates

The backend returns explicit finish metadata in `done` messages:

```json
{
  "success": true,
  "finish_reason": "task_complete",
  "verified": true,
  "requires_review": false
}
```

If the model exits without an explicit `task_complete`, the result is marked as needing review instead of being silently treated as complete.

Possible finish reasons include:

- `task_complete`
- `incomplete_no_task_complete`
- `no_turns`
- `error`
- `cancelled`

---

## Safe subagent scaffolds

The backend includes safe, read-only scaffolding tools:

- `subagent_repo_map`
- `subagent_review`
- `subagent_test_plan`

These are intentionally conservative. They inspect structure and produce review/test plans without writing files or running commands.

They are allowed in `plan` mode because they are read-only/suggestion-only.

---

## SOM.md project context

Create a `SOM.md` file in your project root to tell the agent about your project.

Example:

```markdown
# My Project

## Tech stack

- Python 3.11
- FastAPI
- PostgreSQL
- pytest

## Commands

- Install: pip install -e .
- Test: pytest -q
- Lint: ruff check .
- Format: ruff format .

## Conventions

- Use type hints everywhere.
- Keep handlers thin and move logic into services.
- Add regression tests for every bug fix.
```

Resolution order:

1. `SOM.local.md`
2. `.som/SOM.md`
3. `SOM.md`
4. `~/.som/SOM.md`

Use `SOM.local.md` for personal/private notes that should not be committed.

---

## TUI overview

The interface is designed around a clear coding-agent timeline:

```text
┌─ SOM-CODE ───────────── model: openrouter/anthropic/claude-sonnet-4 ─────┐
│                                                                          │
│  You                                                                      │
│  Build a REST API with tests.                                             │
│                                                                          │
│  Assistant                                                               │
│  Thinking: reading project structure and test commands...                 │
│                                                                          │
│  ✅ read package.json                                                     │
│  ✅ grep "test" .                                                        │
│  ✅ subagent_test_plan                                                    │
│                                                                          │
│  Plan                                                                     │
│  1. Inspect existing API routes.                                          │
│  2. Add endpoint and schema.                                              │
│  3. Add tests.                                                           │
│  4. Run verification.                                                     │
│                                                                          │
│──────────────────────────────────────────────────────────────────────────│
│ > _                                                        ctrl+c quit    │
└──────────────────────────────────────────────────────────────────────────┘
```

TUI components include:

- status bar
- prompt input
- message timeline
- thinking blocks
- tool-call cards
- multi-choice question UI
- session resume banner

---

## Architecture

```text
som-code-agent/
├── bin/
│   └── som-code.js              npm executable entrypoint
├── src/
│   ├── index.ts                 CLI args and app startup
│   ├── doctor.ts                Runtime/backend/provider diagnostics
│   ├── agent/
│   │   └── backend.ts           Node child-process bridge to Python JSONL server
│   ├── components/
│   │   ├── App.tsx              Main Ink app state machine
│   │   ├── StatusBar.tsx        Model/mode/turn/token display
│   │   ├── MessageList.tsx      Conversation timeline
│   │   ├── Prompt.tsx           Terminal input
│   │   ├── Thinking.tsx         Thinking block display
│   │   ├── ToolCall.tsx         Tool call/result display
│   │   ├── AskUserQuestion.tsx  Choice UI
│   │   └── theme.ts             Premium color/theme tokens
│   ├── protocol/
│   │   └── types.ts             JSONL protocol types and runtime validation
│   └── session/
│       └── store.ts             Durable session storage and repo map
├── backend/
│   ├── server.py                Python JSONL backend server
│   ├── harness/                 Core coding-agent harness
│   │   ├── core.py              Agent loop/session result
│   │   ├── providers.py         Provider adapters and aliases
│   │   ├── tools.py             Tool registry/schema generation
│   │   ├── hooks.py             Hook context/policy integration
│   │   ├── repair.py            Tool-input repair helpers
│   │   ├── sandbox.py           Workspace sandbox and tool result model
│   │   └── skills.py            Skill discovery/loading
│   └── som/
│       ├── cli.py               Python-side CLI utilities
│       ├── evaluator.py         Evaluation/finish concepts
│       ├── state.py             Clean-state/feature state concepts
│       ├── agent/               Plan and compaction helpers
│       ├── context/             SOM.md loading
│       ├── session/             Session/history helpers
│       └── tools/               SOM-specific tool registry
├── tests/
│   ├── protocol.test.ts         Protocol validation tests
│   ├── session.test.ts          Session/repo-map tests
│   ├── test_policy.py           Permission and finish-gate tests
│   └── test_subagents.py        Safe subagent scaffold tests
├── scripts/
│   ├── build.js                 esbuild + backend copy
│   └── copy-backend.js          backend packaging helper
├── package.json
├── tsconfig.json
└── README.md
```

### Runtime flow

```text
Terminal user
  ↓
Ink/React TUI in Node.js
  ↓ JSONL over stdin/stdout
Python backend server
  ↓
Coding harness loop
  ↓
Provider adapter + model
  ↓
Tool calls through sandbox/hooks/policy
  ↓
Results streamed back to TUI
```

---

## JSONL protocol

The Node frontend and Python backend communicate with one JSON object per line.

Frontend to backend:

```json
{"id":"1","type":"task","payload":{"task":"Inspect this repo"}}
{"id":"2","type":"cancel"}
{"id":"3","type":"ping"}
```

Backend to frontend:

```json
{"id":"1","type":"thinking","payload":{"text":"Reading project files..."}}
{"id":"1","type":"tool_call","payload":{"name":"read","args":{"path":"package.json"}}}
{"id":"1","type":"tool_result","payload":{"name":"read","success":true}}
{"id":"1","type":"done","payload":{"success":true,"finish_reason":"task_complete"}}
```

Protocol types are defined in:

```text
src/protocol/types.ts
```

Runtime validation is covered by:

```text
tests/protocol.test.ts
```

---

## Development

Install dependencies:

```bash
npm install
```

Run development TUI:

```bash
npm run dev
```

Run with a task:

```bash
npm run dev -- "Explain this repository"
```

Build:

```bash
npm run build
```

Typecheck:

```bash
npm run typecheck
```

Run all tests:

```bash
npm test
```

Doctor:

```bash
node bin/som-code.js doctor
```

Pack dry-run:

```bash
npm pack --dry-run
```

Full local release gate:

```bash
npm run typecheck
npm test
npm run build
node bin/som-code.js doctor
npm pack --dry-run
```

---

## Tests

The current test suite intentionally uses low-surprise dependencies.

`npm test` runs:

```bash
npm run build
npx tsx tests/protocol.test.ts
npx tsx tests/session.test.ts
python3 tests/test_policy.py
python3 tests/test_subagents.py
```

Coverage areas:

- TypeScript protocol validation
- Session creation/list/load/append
- Repo map exclusions
- Permission policy enforcement
- Finish-gate metadata
- Safe subagent registration and no-write behavior

---

## Doctor output

`som-code doctor` checks:

- Node availability
- Python availability
- packaged backend script path
- backend JSONL ping
- key provider environment variables
- local Ollama reachability

Example:

```text
SOM-CODE doctor
────────────────
  ✅ Node: v22.22.2
  ✅ Python: Python 3.10.12
  ✅ Backend script: /path/to/node_modules/som-code/dist/backend/server.py
  ✅ Backend ping: mock JSONL server responded
  ⚠️  OpenCode Go key: OPENCODE_GO_API_KEY not set
  ⚠️  OpenRouter key: OPENROUTER_API_KEY not set
  ⚠️  Ollama: not reachable locally

Doctor result: ready
```

Warnings about missing provider keys are normal if you have not configured those providers yet.

---

## Troubleshooting

### `som-code: command not found`

Install globally or run through npm:

```bash
npm install -g .
som-code doctor
```

Or from the repo:

```bash
node bin/som-code.js doctor
```

### Backend startup failed

Run:

```bash
node bin/som-code.js doctor
```

Check:

- Python 3.10+ is installed.
- `dist/backend/server.py` exists after `npm run build`.
- You are not running from a half-built checkout.

### Provider key warning

Export the relevant API key:

```bash
export OPENROUTER_API_KEY="..."
export OPENCODE_GO_API_KEY="..."
export OPENCODE_GO_BASE_URL="..."
```

### Ollama not reachable

Start Ollama:

```bash
ollama serve
```

Then pull and use a model:

```bash
ollama pull qwen2.5:7b
som-code --model ollama/qwen2.5:7b
```

### Session not found

List available sessions first:

```bash
som-code --list-sessions
```

Then resume with `latest` or an id prefix:

```bash
som-code --resume latest
som-code --resume <prefix>
```

---

## Security notes

- Do not commit `.env`, `.env.*`, tokens, private keys, local `.som-code` sessions, or packed `.tgz` artifacts.
- `.gitignore` excludes common secret/runtime files.
- `plan` mode is the safest mode for reconnaissance because it blocks edits and shell execution.
- `bypass` mode should be treated as dangerous and used only in trusted workspaces.
- API keys are read from environment variables; they should not be placed in prompts or committed files.

---

## Public release verification

This repository was prepared with the following local verification gate:

```bash
npm run typecheck
npm test
npm run build
node bin/som-code.js doctor
npm pack --dry-run
npm pack
```

The packed artifact was also installed into a clean temporary npm project and verified with:

```bash
./node_modules/.bin/som-code doctor
./node_modules/.bin/som-code --list-sessions
```

---

## Roadmap ideas

Useful next improvements:

- GitHub Actions CI for typecheck/test/build.
- Published npm package under a scoped name.
- Real multi-process subagents instead of safe scaffolds only.
- Richer non-interactive `exec` mode output.
- MCP tool integration.
- More provider-specific tool-call dialect fallbacks.
- Release assets attached to GitHub Releases.
- Screenshots/GIFs of the TUI.

---

## License

MIT. See [LICENSE](LICENSE).
