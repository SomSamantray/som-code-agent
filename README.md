# SOM-CODE 🧠

**Your AI coding agent. Terminal-native TUI. Works with any LLM.**

```bash
npm install -g som-code
som-code "Build a REST API with FastAPI"
```

## Features

- 🖥️ **Terminal-native TUI** — Built with Ink/React, same patterns as Claude Code & OpenCode
- 🤖 **Any LLM** — OpenAI, Anthropic, OpenRouter, Ollama, DeepSeek, Groq, and more
- 📋 **Plan Mode** — Research → Plan → Approve → Execute flow
- 💬 **AskUserQuestion** — Interactive multi-choice clarification
- 🔧 **18 Tools** — grep, glob, edit, web_search, web_fetch, todo, and more
- 📦 **Context Compaction** — Automatic for long sessions
- 📄 **SOM.md** — Project context injection (like CLAUDE.md)
- 🔒 **Permission Modes** — default, acceptEdits, plan, bypass
- 📚 **Skills** — Load and use Hermes-compatible skill files

## Quick Start

```bash
# Install globally
npm install -g som-code

# Set your API key
export OPENROUTER_API_KEY="sk-or-v1-..."

# Start coding
som-code

# Or with a task directly
som-code "Write a Python quicksort with tests"

# Plan mode
som-code --plan "Design an authentication system"

# Use a different model
som-code --model ollama/qwen2.5:7b

# View help
som-code --help
```

## Commands

| Command | Description |
|---------|-------------|
| `som-code` | Interactive TUI coding session |
| `som-code "task"` | Start with a task |
| `som-code --plan "task"` | Plan mode (read-only research) |
| `som-code --model openrouter/gpt-4o` | Use specific model |
| `som-code --permission bypass` | YOLO mode |
| `som-code --workspace /path/to/project` | Set workspace |

## TUI Layout

```
┌─ SOM-CODE ─────────── model: claude-sonnet-4 ──────── Turn 3 ────┐
│                                                                     │
│  You: Build a REST API                                              │
│                                                                     │
│  🤖 Assistant:                                                      │
│  ⠋ Thinking: Planning the architecture...                           │
│                                                                     │
│  ✅ read src/main.py                                                │
│  ✅ glob **/*.py (14 files)                                         │
│                                                                     │
│  📋 PLAN:                                                           │
│  ┌───────────────────────────────────────────────────┐             │
│  │ 1. Create router.py                               │             │
│  │ 2. Create models/user.py                          │             │
│  │ 3. Write tests                                    │             │
│  └───────────────────────────────────────────────────┘             │
│                                                                     │
│─────────────────────────────────────────────────────────────────────│
│ > _                                         esc menu  ctrl+c quit  │
└─────────────────────────────────────────────────────────────────────┘
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `OPENROUTER_API_KEY` | OpenRouter API key |
| `OPENAI_API_KEY` | OpenAI API key |
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `DEEPSEEK_API_KEY` | DeepSeek API key |
| `SOM_MODEL` | Default model (e.g., `openrouter/anthropic/claude-sonnet-4`) |

## SOM.md Project Config

Create a `SOM.md` in your project root to inject context into every session:

```markdown
# My Project

## Tech Stack
- Python 3.11, FastAPI, PostgreSQL

## Conventions
- Use type hints everywhere
- Test with pytest
- Format with black

## Commands
- Run: python -m src.main
- Test: pytest -xvs
```

Resolution order: `SOM.local.md` → `.som/SOM.md` → `SOM.md` → `~/.som/SOM.md`

## Development

```bash
# Clone and install
git clone <repo>
cd som-code
npm install

# Development mode (hot reload)
npm run dev

# Build
npm run build

# Type check
npm run typecheck

# Test Python backend
echo '{"id":"1","type":"ping"}' | python3 backend/server.py --model mock
```

## Architecture

```
som-code/
├── bin/som-code.js         # npm bin entry point
├── src/
│   ├── index.ts            # Main entry + CLI args
│   ├── components/
│   │   ├── App.tsx         # Main TUI app shell
│   │   ├── Prompt.tsx      # Text input with cursor
│   │   ├── MessageList.tsx # Scrollback + streaming
│   │   ├── StatusBar.tsx   # Top status bar
│   │   ├── Thinking.tsx    # Collapsible reasoning
│   │   ├── ToolCall.tsx    # Inline/block tool display
│   │   └── AskUserQuestion.tsx  # Multi-choice questions
│   ├── agent/
│   │   └── backend.ts      # Python backend spawner
│   └── protocol/
│       └── types.ts        # JSONL message types
├── backend/
│   └── server.py           # Python agent server
├── scripts/
│   └── build.js            # esbuild bundler
└── dist/                   # Compiled output (gitignored)
    ├── index.js
    ├── backend/
    └── llm-harness/        # Bundled Python harness
```

## License

MIT
