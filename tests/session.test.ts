import * as assert from 'node:assert/strict';
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import {
  appendSessionMessage,
  buildRepoMap,
  createSession,
  listSessions,
  loadSession,
  resolveResumeSession,
} from '../src/session/store.js';

const workspace = mkdtempSync(join(tmpdir(), 'som-code-session-'));
try {
  mkdirSync(join(workspace, 'src'));
  mkdirSync(join(workspace, 'node_modules'));
  writeFileSync(join(workspace, 'src', 'index.ts'), 'console.log("hi")');
  writeFileSync(join(workspace, 'node_modules', 'ignored.js'), 'ignored');

  const repoMap = buildRepoMap(workspace);
  assert.equal(repoMap.rootName.startsWith('som-code-session-'), true);
  assert.deepEqual(repoMap.files, ['src/index.ts']);

  const session = createSession({ model: 'mock/test', workspace, permission: 'plan' });
  appendSessionMessage(session, {
    id: '1',
    type: 'task',
    payload: { task: 'Build a thing' },
    timestamp: Date.now(),
  });
  appendSessionMessage(session, {
    id: '2',
    type: 'compact',
    payload: { summary: 'short summary' },
    timestamp: Date.now(),
  });

  const loaded = loadSession(workspace, session.id);
  assert.equal(loaded.title, 'Build a thing');
  assert.equal(loaded.summary, 'short summary');
  assert.equal(loaded.messages.length, 2);

  const sessions = listSessions(workspace);
  assert.equal(sessions.length, 1);
  assert.equal(resolveResumeSession(workspace, 'latest')?.id, session.id);
  assert.equal(resolveResumeSession(workspace, session.id.slice(0, 10))?.id, session.id);

  console.log('session store tests passed');
} finally {
  rmSync(workspace, { recursive: true, force: true });
}
