import { existsSync, mkdirSync, readdirSync, readFileSync, renameSync, statSync, writeFileSync } from 'node:fs';
import { basename, join, resolve } from 'node:path';
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import type { ProtocolMessage } from '../protocol/types.js';

export interface RepoMap {
  workspace: string;
  rootName: string;
  gitBranch?: string;
  gitHead?: string;
  files: string[];
  generatedAt: string;
}

export interface SessionRecord {
  id: string;
  title: string;
  model: string;
  workspace: string;
  permission?: string;
  createdAt: string;
  updatedAt: string;
  messages: ProtocolMessage[];
  repoMap?: RepoMap;
  summary?: string;
}

export function sessionDir(workspace = process.cwd()): string {
  return join(resolve(workspace), '.som-code', 'sessions');
}

export function createSessionId(seed = `${Date.now()}-${Math.random()}`): string {
  const ts = new Date().toISOString().replace(/[-:TZ.]/g, '').slice(0, 14);
  const hash = createHash('sha1').update(seed).digest('hex').slice(0, 8);
  return `${ts}-${hash}`;
}

function sessionPath(workspace: string, id: string): string {
  return join(sessionDir(workspace), `${id}.json`);
}

function atomicWrite(path: string, content: string): void {
  const tmp = `${path}.tmp`;
  writeFileSync(tmp, content);
  renameSync(tmp, path);
}

export function buildRepoMap(workspace = process.cwd(), maxFiles = 160): RepoMap {
  const root = resolve(workspace);
  let gitBranch: string | undefined;
  let gitHead: string | undefined;
  try {
    gitBranch = execFileSync('git', ['rev-parse', '--abbrev-ref', 'HEAD'], { cwd: root, encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }).trim();
    gitHead = execFileSync('git', ['rev-parse', '--short', 'HEAD'], { cwd: root, encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }).trim();
  } catch {
    // Non-git workspaces are valid.
  }

  const files: string[] = [];
  const ignored = new Set(['.git', 'node_modules', 'dist', '.som-code', '.venv', '__pycache__']);
  const walk = (dir: string, prefix = '') => {
    if (files.length >= maxFiles) return;
    let entries: string[] = [];
    try { entries = readdirSync(dir).sort(); } catch { return; }
    for (const entry of entries) {
      if (files.length >= maxFiles || ignored.has(entry)) continue;
      const full = join(dir, entry);
      const rel = prefix ? `${prefix}/${entry}` : entry;
      let st;
      try { st = statSync(full); } catch { continue; }
      if (st.isDirectory()) walk(full, rel);
      else if (st.isFile()) files.push(rel);
    }
  };
  walk(root);

  return {
    workspace: root,
    rootName: basename(root),
    gitBranch,
    gitHead,
    files,
    generatedAt: new Date().toISOString(),
  };
}

export function createSession(options: { model: string; workspace?: string; permission?: string; title?: string }): SessionRecord {
  const workspace = resolve(options.workspace || process.cwd());
  mkdirSync(sessionDir(workspace), { recursive: true });
  const now = new Date().toISOString();
  const record: SessionRecord = {
    id: createSessionId(`${workspace}-${options.model}-${now}`),
    title: options.title || 'New session',
    model: options.model,
    workspace,
    permission: options.permission,
    createdAt: now,
    updatedAt: now,
    messages: [],
    repoMap: buildRepoMap(workspace),
  };
  saveSession(record);
  return record;
}

export function saveSession(record: SessionRecord): void {
  mkdirSync(sessionDir(record.workspace), { recursive: true });
  record.updatedAt = new Date().toISOString();
  atomicWrite(sessionPath(record.workspace, record.id), `${JSON.stringify(record, null, 2)}\n`);
}

function payloadObject(payload: unknown): Record<string, unknown> {
  return payload && typeof payload === 'object' ? payload as Record<string, unknown> : {};
}

export function appendSessionMessage(record: SessionRecord, message: ProtocolMessage): SessionRecord {
  record.messages.push(message);
  const payload = payloadObject(message.payload);
  if (message.type === 'task' && typeof payload.task === 'string' && record.title === 'New session') {
    record.title = payload.task.slice(0, 80);
  }
  if (message.type === 'compact' && typeof payload.summary === 'string') {
    record.summary = payload.summary;
  }
  saveSession(record);
  return record;
}

export function loadSession(workspace: string, id: string): SessionRecord {
  const path = sessionPath(workspace, id);
  if (!existsSync(path)) throw new Error(`Session not found: ${id}`);
  return JSON.parse(readFileSync(path, 'utf8')) as SessionRecord;
}

export function listSessions(workspace = process.cwd()): SessionRecord[] {
  const dir = sessionDir(workspace);
  if (!existsSync(dir)) return [];
  return readdirSync(dir)
    .filter(file => file.endsWith('.json'))
    .map(file => JSON.parse(readFileSync(join(dir, file), 'utf8')) as SessionRecord)
    .sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
}

export function resolveResumeSession(workspace = process.cwd(), idOrLatest?: string): SessionRecord | null {
  const sessions = listSessions(workspace);
  if (!sessions.length) return null;
  if (!idOrLatest || idOrLatest === 'latest') return sessions[0];
  return sessions.find(s => s.id.startsWith(idOrLatest) || s.id === idOrLatest) || null;
}
