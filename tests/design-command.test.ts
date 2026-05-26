import test from 'node:test';
import assert from 'node:assert/strict';

import { expandSlashCommand } from '../src/commands/design.ts';

test('/design defaults to audit current directory', () => {
  const expanded = expandSlashCommand('/design');
  assert.match(expanded, /AUDIT mode/);
  assert.match(expanded, /Target: \./);
  assert.match(expanded, /design_audit/);
});

test('/design audit preserves target', () => {
  const expanded = expandSlashCommand('/design audit src/app');
  assert.match(expanded, /AUDIT mode/);
  assert.match(expanded, /Target: src\/app/);
  assert.doesNotMatch(expanded, /Apply the brief/);
});

test('/design repair creates repair workflow', () => {
  const expanded = expandSlashCommand('/design repair components/Button.tsx');
  assert.match(expanded, /REPAIR mode/);
  assert.match(expanded, /design_repair_brief/);
  assert.match(expanded, /components\/Button\.tsx/);
});

test('unknown commands pass through unchanged', () => {
  assert.equal(expandSlashCommand('/other audit src'), '/other audit src');
});
