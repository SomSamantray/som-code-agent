#!/usr/bin/env node
/**
 * SOM-CODE — Main entry point.
 * 
 * Usage:
 *   som-code                     Interactive TUI
 *   som-code "Build a REST API"  Start with task
 *   som-code --model claude-sonnet-4
 *   som-code --plan "Design auth"
 *   som-code --chat "Hello"
 *   som-code exec "Write quicksort"
 *   som-code init
 *   som-code config
 */

import { parseArgs } from 'node:util';
import { startTUI } from './components/App.js';
import { runDoctor } from './doctor.js';
import { listSessions, resolveResumeSession } from './session/store.js';

const { values, positionals } = parseArgs({
  options: {
    model:       { type: 'string', short: 'm', default: process.env.SOM_MODEL || process.env.OPENROUTER_MODEL || 'openrouter/anthropic/claude-sonnet-4' },
    permission:  { type: 'string', short: 'p', default: 'default' },
    workspace:   { type: 'string', short: 'w' },
    plan:        { type: 'boolean' },
    chat:        { type: 'boolean' },
    exec:        { type: 'boolean' },
    resume:      { type: 'string', short: 'r' },
    'list-sessions': { type: 'boolean' },
    help:        { type: 'boolean', short: 'h' },
    version:     { type: 'boolean', short: 'v' },
  },
  allowPositionals: true,
});

if (values.help) {
  console.log(`
SOM-CODE — Your AI coding agent

Usage:
  som-code                          Interactive TUI
  som-code "Build a REST API"       Start with a task
  som-code --plan "Design auth"     Plan mode
  som-code exec "Write quicksort"   Non-interactive
  som-code --model ollama/qwen2.5:7b
  som-code --resume latest             Resume latest session
  som-code --list-sessions             List saved sessions
  som-code init                     Create SOM.md
  som-code doctor                   Check runtime, backend, and providers
  som-code --help                   This help

Environment:
  SOM_MODEL                Default model
  OPENROUTER_API_KEY       OpenRouter API key
  OPENCODE_GO_API_KEY      OpenCode Go subscription API key
  OPENCODE_GO_BASE_URL     OpenCode Go OpenAI-compatible base URL
  OPENCODE_GO_MODEL        Default model for opencode-go
  OPENAI_API_KEY           OpenAI API key
  ANTHROPIC_API_KEY        Anthropic API key
`);
  process.exit(0);
}

if (positionals[0] === 'doctor') {
  process.exit(runDoctor());
}

if (values['list-sessions'] || positionals[0] === 'sessions') {
  const sessions = listSessions(values.workspace);
  if (!sessions.length) {
    console.log('No saved sessions found.');
  } else {
    for (const session of sessions) {
      const repo = session.repoMap?.gitBranch ? `${session.repoMap.gitBranch}@${session.repoMap.gitHead || 'unknown'}` : session.repoMap?.rootName || 'workspace';
      console.log(`${session.id}  ${session.updatedAt}  ${repo}  ${session.title}`);
    }
  }
  process.exit(0);
}

if (values.version) {
  const pkg = JSON.parse(await import('fs').then(fs => fs.readFileSync(new URL('../package.json', import.meta.url), 'utf-8')));
  console.log(`som-code v${pkg.version}`);
  process.exit(0);
}

// Get task from positional args
const commandPositionals = positionals[0] === 'exec' || positionals[0] === 'init' || positionals[0] === 'config'
  ? positionals.slice(1)
  : positionals;
const task = commandPositionals.join(' ').trim() || undefined;

const resumedSession = values.resume ? resolveResumeSession(values.workspace, values.resume) : null;
if (values.resume && !resumedSession) {
  console.error(`No saved session found matching '${values.resume}'. Run 'som-code --list-sessions' first.`);
  process.exit(1);
}

// Override permission for plan mode
const permission = values.plan ? 'plan' : values.permission;

console.log(`🧠 SOM-CODE — starting with ${values.model}...`);
if (resumedSession) console.log(`   Resuming session ${resumedSession.id}: ${resumedSession.title}`);
console.log(`   Press Ctrl+C to quit, Esc to cancel`);

await startTUI({
  model: values.model!,
  task,
  permission,
  workspace: values.workspace,
  session: resumedSession || undefined,
});
