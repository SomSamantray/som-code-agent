# Design Harness and Superpowers Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a SOM-CODE-native `/design` harness and bundle the MIT-licensed `obra/superpowers` skills so agents can load stronger process skills by default.

**Architecture:** Implement design as a harness contract, not a prompt-only feature: slash commands expand into explicit audit/repair tasks, backend tools generate deterministic JSON/Markdown reports in `.som-code/design/`, and the base system prompt teaches the agent to use those tools. Integrate Superpowers by adding packaged skills under `backend/skills/superpowers/` and expanding the `SkillLoader` search path to include packaged, workspace, and home skill directories.

**Tech Stack:** TypeScript/Ink frontend, Python backend tools, existing `SkillLoader`, Python `unittest`, Node built-in test runner, npm build.

---

## Research Summary

- `mattapperson/noetic` is not suitable to vendor into SOM-CODE because it is ELv2 and Bun/framework-heavy, but its design-deck pattern validates a harness-level command for design work.
- `obra/superpowers` is MIT licensed. Its skills are plain `SKILL.md` directories with compatible frontmatter (`name`, `description`). Direct bundling is license-compatible if attribution is retained.
- SOM-CODE already has `skill_search`, `skill_view`, and `skill_list`, but its loader only checks `~/.hermes/skills` and `./skills`; packaged default skills are not guaranteed in npm installs.
- SOM-CODE has no true slash-command router; task text is sent directly from TUI to backend. A small frontend command expander is the lowest-risk way to support `/design` without changing protocol shape.
- Backend tool registration is centralized in `backend/som/tools/all_tools.py`; new deterministic design tools fit there.

## Finalized Scope

### In scope
- Add `/design`, `/design audit`, and `/design repair` prompt expansion in TypeScript.
- Add deterministic backend tools:
  - `design_audit(target='.', purpose='auto', write_report=True)`
  - `design_repair_brief(target='.', purpose='auto')`
- Add design report files under `.som-code/design/`:
  - JSON report with purpose, smell counts, state coverage, recommendations.
  - Markdown companion report.
- Add packaged Superpowers skills under `backend/skills/superpowers/` preserving original skill names.
- Add attribution for bundled Superpowers skills.
- Extend `SkillLoader` to discover packaged default skills in addition to home/workspace skills.
- Add tests for command expansion, design tools, and packaged skill discovery.

### Out of scope for this pass
- Browser screenshot/vision-based visual QA.
- Full Noetic design-deck UI.
- Any ELv2 code or direct Noetic dependency.
- Interactive visual deck inside Ink.

## Recheck and Corrections Applied

Initial idea: add a heavy `/design` backend protocol message.
- Rejected: protocol changes are unnecessary and riskier.
- Revised: expand slash commands into normal task text in the TUI.

Initial idea: only tell agents to use OKLCH/design taste in system prompt.
- Rejected: prompt-only design guidance is the same contract gap that caused the original problem.
- Revised: add callable deterministic design tools and report schemas.

Initial idea: install Superpowers via npm/git at runtime.
- Rejected: runtime network dependency and version instability.
- Revised: bundle MIT skills in package with attribution and fixed behavior.

Initial idea: prefix skills as `superpowers:<name>`.
- Rejected: user prefers third-party Hermes skills to keep source repo names.
- Revised: preserve exact skill names (`writing-plans`, `systematic-debugging`, etc.).

## File Changes

### Create: `src/commands/design.ts`
- Export `expandSlashCommand(input: string): string`.
- Recognize `/design`, `/design audit`, and `/design repair`.
- Preserve user arguments after the subcommand.
- Return normal input unchanged for unknown commands.

### Modify: `src/components/App.tsx`
- Import `expandSlashCommand`.
- In `submitTask`, compute `expandedText = expandSlashCommand(text)`.
- Display the user’s original input but send expanded text to backend.

### Create: `tests/design-command.test.ts`
- Node tests for audit, repair, default, and unknown command expansion.

### Create: `backend/som/tools/design.py`
- Implement static scan helpers:
  - find frontend/design files while ignoring `.git`, `node_modules`, `dist`, `.som-code`, caches.
  - classify purpose as `Monitor`, `Operate`, `Decide`, `Explore`, or `General` from file/content signals.
  - detect design smells: centered stacks, indigo/purple default palettes, unearned blur, generic cards, lack of OKLCH, missing empty/loading/error states, weak semantic layout.
  - calculate state coverage.
  - write `.som-code/design/design-audit-<timestamp>.json` and `.md`.
- Implement `design_repair_brief` that turns an audit into a concise repair contract.

### Modify: `backend/som/tools/all_tools.py`
- Import design tool functions.
- Add `design_audit` and `design_repair_brief` registry entries.
- Add them to read-only permission allow-list in `backend/server.py`.

### Modify: `backend/server.py`
- Add design tools to `READ_ONLY_TOOLS`.
- Add `/design` guidance to the system prompt.

### Modify: `backend/harness/skills.py`
- Add packaged skills path: `<backend>/skills`.
- Keep existing home and workspace paths.
- Preserve exact skill names from frontmatter.

### Create: `backend/skills/superpowers/...`
- Copy MIT `obra/superpowers/skills/*/SKILL.md` preserving directory names and skill names.
- Add `backend/skills/superpowers/NOTICE.md` with source URL and MIT license note.

### Create: `tests/test_design_tools.py`
- Validate audit detects smells and writes reports.
- Validate repair brief mentions purpose, states, OKLCH, and report path.

### Create: `tests/test_packaged_skills.py`
- Validate packaged skill discovery includes representative Superpowers skills.
- Validate exact names like `writing-plans` and `verification-before-completion`.

## Execution Steps

### Task 1: Add slash command expansion
- [ ] Create `src/commands/design.ts` with pure expansion function.
- [ ] Add TypeScript node tests.
- [ ] Wire expansion in `App.tsx`.
- [ ] Run `node --test tests/design-command.test.ts` after build or via TS-compatible path if available.

### Task 2: Add deterministic design backend tools
- [ ] Create `backend/som/tools/design.py`.
- [ ] Register tools in `all_tools.py`.
- [ ] Add permission/system prompt support in `server.py`.
- [ ] Add Python tests for audit and repair brief.

### Task 3: Bundle Superpowers skills
- [ ] Copy Superpowers `skills/*/SKILL.md` into `backend/skills/superpowers/`.
- [ ] Add `NOTICE.md` attribution.
- [ ] Extend packaged skill discovery.
- [ ] Add discovery tests.

### Task 4: Verification
- [ ] Run `python3 -m unittest discover -s tests`.
- [ ] Run `npm run build`.
- [ ] Run `node --test dist/tests` only if tests are emitted; otherwise run available package test command.
- [ ] Inspect `git diff --stat` and relevant diffs.

## Success Criteria

- `/design audit src` sends a concrete design-audit task to the backend.
- `design_audit` writes JSON and Markdown reports in `.som-code/design/`.
- `design_repair_brief` produces a contract the agent can follow for repair work.
- `skill_list` includes Superpowers skills out of the box in packaged installs.
- All Python tests pass.
- npm build passes.
