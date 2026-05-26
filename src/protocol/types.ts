export const MESSAGE_TYPES = [
  'task',
  'delta',
  'tool_call',
  'tool_result',
  'thinking',
  'question',
  'answer',
  'done',
  'error',
  'plan_enter',
  'plan_exit',
  'plan_approve',
  'plan_refine',
  'compact',
  'cancel',
  'ping',
  'pong',
  'feature_list',
  'evaluation',
  'sprint_contract',
  'clean_state',
  'progress',
] as const;

export type MessageType = typeof MESSAGE_TYPES[number];

export interface ProtocolMessage {
  id: string;
  type: MessageType;
  payload?: unknown;
  error?: string;
  timestamp?: number;
}

export interface TaskPayload {
  task: string;
  permission: 'plan' | 'default' | 'acceptEdits' | 'bypass';
  workspace?: string;
  model?: string;
}

export interface ToolCallPayload {
  name: string;
  args: Record<string, unknown>;
  id: string;
}

export interface ToolResultPayload {
  name: string;
  success: boolean;
  output?: string;
  error?: string;
  exit_code?: number;
  metadata?: Record<string, unknown>;
}

export interface QuestionPayload {
  questions: Array<{
    question: string;
    header: string;
    options: Array<{label: string; description: string}>;
    multiSelect?: boolean;
  }>;
}

export interface AnswerPayload {
  answers: Record<string, string | string[]>;
}

export interface DeltaPayload {
  content: string;
  turn?: number;
}

export interface ThinkingPayload {
  content: string;
  collapsed?: boolean;
}

export interface PlanPayload {
  plan: string;
}

export interface DonePayload {
  summary: string;
  success: boolean;
  turns: number;
  tool_calls: number;
  tokens?: {prompt: number; completion: number; total: number};
  finish_reason?: 'task_complete' | 'error' | 'no_turns' | 'incomplete_no_task_complete' | 'cancelled';
  verified?: boolean;
  requires_review?: boolean;
  error?: string;
}

export interface CompactPayload {
  summary: string;
  files_modified: string[];
  turn_count: number;
}

export function isMessageType(value: unknown): value is MessageType {
  return typeof value === 'string' && (MESSAGE_TYPES as readonly string[]).includes(value);
}

export function validateProtocolMessage(value: unknown): {ok: true; message: ProtocolMessage} | {ok: false; error: string} {
  if (!value || typeof value !== 'object') return {ok: false, error: 'message must be an object'};
  const msg = value as Record<string, unknown>;
  if (typeof msg.id !== 'string' || msg.id.length === 0) return {ok: false, error: 'message.id must be a non-empty string'};
  if (!isMessageType(msg.type)) return {ok: false, error: `message.type must be one of: ${MESSAGE_TYPES.join(', ')}`};
  if (msg.timestamp !== undefined && typeof msg.timestamp !== 'number') return {ok: false, error: 'message.timestamp must be a number when present'};
  if (msg.error !== undefined && typeof msg.error !== 'string') return {ok: false, error: 'message.error must be a string when present'};
  const payloadError = validatePayload(msg.type, msg.payload);
  if (payloadError) return {ok: false, error: payloadError};
  return {ok: true, message: msg as unknown as ProtocolMessage};
}

function validatePayload(type: MessageType, payload: unknown) {
  if (type === 'task') {
    if (!payload || typeof payload !== 'object') return 'task.payload must be an object';
    const task = payload as Record<string, unknown>;
    if (typeof task.task !== 'string' || task.task.length === 0) return 'task.payload.task must be a non-empty string';
    if (task.permission !== undefined && !['plan', 'default', 'acceptEdits', 'bypass'].includes(String(task.permission))) return 'task.payload.permission is invalid';
  }
  if (type === 'delta' && payload && typeof (payload as Record<string, unknown>).content !== 'string') return 'delta.payload.content must be a string';
  if (type === 'done') {
    if (!payload || typeof payload !== 'object') return 'done.payload must be an object';
    const done = payload as Record<string, unknown>;
    if (typeof done.summary !== 'string') return 'done.payload.summary must be a string';
    if (typeof done.success !== 'boolean') return 'done.payload.success must be a boolean';
  }
  if (type === 'tool_call') {
    if (!payload || typeof payload !== 'object') return 'tool_call.payload must be an object';
    const call = payload as Record<string, unknown>;
    if (typeof call.name !== 'string') return 'tool_call.payload.name must be a string';
    if (typeof call.id !== 'string') return 'tool_call.payload.id must be a string';
  }
  return '';
}
