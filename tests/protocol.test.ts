import * as assert from 'node:assert/strict';
import { validateProtocolMessage } from '../src/protocol/types.js';

const validTask = validateProtocolMessage({
  id: '1',
  type: 'task',
  payload: { task: 'write tests', permission: 'plan' },
});
assert.equal(validTask.ok, true);

const invalidType = validateProtocolMessage({ id: '1', type: 'wat' });
assert.equal(invalidType.ok, false);

const invalidTask = validateProtocolMessage({
  id: '1',
  type: 'task',
  payload: { task: '', permission: 'bypass' },
});
assert.equal(invalidTask.ok, false);

const validDone = validateProtocolMessage({
  id: '1',
  type: 'done',
  payload: { summary: 'ok', success: true, turns: 1, tool_calls: 0 },
});
assert.equal(validDone.ok, true);

console.log('protocol validation tests passed');
