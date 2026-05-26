/**
 * SOM-CODE TUI — the main App component.
 * 
 * Layout:
 * ┌─ Status Bar (model, session, tokens) ───────────────────┐
 * │                                                           │
 * │  Message scrollback area                                  │
 * │  (Static for completed, Box for streaming)                │
 * │                                                           │
 * │───────────────────────────────────────────────────────────│
 * │  Prompt input area                                  esc   │
 * └───────────────────────────────────────────────────────────┘
 */

import React, { useState, useRef, useEffect } from 'react';
import { render, Box, Text, useInput, useApp, Static } from 'ink';
import { Prompt } from './Prompt.js';
import { MessageList } from './MessageList.js';
import { StatusBar } from './StatusBar.js';
import { AskUserQuestion } from './AskUserQuestion.js';
import { AgentBackend } from '../agent/backend.js';
import type { ProtocolMessage, ToolCallPayload, ToolResultPayload, 
  QuestionPayload, DeltaPayload, ThinkingPayload, DonePayload, PlanPayload } from '../protocol/types.js';
import { createSession, type SessionRecord } from '../session/store.js';

// ── Types ──────────────────────────────────────────────────────

interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  thinking?: string;
  toolCalls?: {name: string; args: Record<string,any>; status: 'running'|'done'|'error'; output?: string}[];
  plan?: string;
  done?: boolean;
  compact?: boolean;
}

export type { Message };

interface AppState {
  messages: Message[];
  currentAssistant: Message | null;
  isStreaming: boolean;
  isThinking: boolean;
  thinkingContent: string;
  toolCalls: Map<string, {name: string; args: Record<string,any>; status: 'running'|'done'|'error'; output?: string}>;
  question: QuestionPayload | null;
  planMode: boolean;
  planText: string;
  statusText: string;
  tokens: {prompt: number; completion: number; total: number};
  turn: number;
}

// ── Main App ───────────────────────────────────────────────────

export function App({ 
  model, 
  task, 
  permission,
  workspace,
  backend,
  session,
  onExit,
}: { 
  model: string; 
  task?: string;
  permission?: string;
  workspace?: string;
  backend: AgentBackend;
  session: SessionRecord;
  onExit: () => void;
}) {
  const { exit } = useApp();
  const [state, setState] = useState<AppState>({
    messages: session.messages.length ? [{
      id: `resume-${session.id}`,
      role: 'system',
      content: `↩ Resumed session ${session.id} · ${session.messages.length} protocol events · ${session.repoMap?.files.length || 0} repo files mapped`,
    }] : [],
    currentAssistant: null,
    isStreaming: false,
    isThinking: false,
    thinkingContent: '',
    toolCalls: new Map(),
    question: null,
    planMode: false,
    planText: '',
    statusText: 'Starting...',
    tokens: {prompt: 0, completion: 0, total: 0},
    turn: 0,
  });

  const stateRef = useRef(state);
  stateRef.current = state;

  // Update state helper
  const update = (patch: Partial<AppState>) => {
    setState(prev => ({ ...prev, ...patch }));
  };

  // Submit a user message
  const submitTask = (text: string) => {
    const userMsg: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: text,
    };
    const assistantMsg: Message = {
      id: `assistant-${Date.now()}`,
      role: 'assistant',
      content: '',
    };

    setState(prev => ({
      ...prev,
      messages: [...prev.messages, userMsg, assistantMsg],
      currentAssistant: assistantMsg,
      isStreaming: true,
      isThinking: false,
      thinkingContent: '',
      toolCalls: new Map(),
      question: null,
      planText: '',
      statusText: 'Thinking...',
      turn: prev.turn + 1,
    }));

    backend.sendTask(text, permission);
  };

  // Handle backend events
  useEffect(() => {
    const onDelta = (payload: DeltaPayload) => {
      const current = stateRef.current.currentAssistant;
      if (current) {
        current.content += payload.content;
        setState(prev => ({
          ...prev,
          currentAssistant: { ...current },
          statusText: 'Generating...',
        }));
      }
    };

    const onThinking = (payload: ThinkingPayload) => {
      const current = stateRef.current.currentAssistant;
      if (current) {
        current.thinking = (current.thinking || '') + payload.content;
        setState(prev => ({
          ...prev,
          currentAssistant: { ...current },
          isThinking: true,
          thinkingContent: current.thinking,
          statusText: 'Thinking...',
        }));
      }
    };

    const onToolCall = (payload: ToolCallPayload) => {
      const tc = stateRef.current.toolCalls;
      tc.set(payload.id, {
        name: payload.name,
        args: payload.args,
        status: 'running',
      });
      setState(prev => ({
        ...prev,
        toolCalls: new Map(tc),
        statusText: `Running: ${payload.name}`,
      }));
    };

    const onToolResult = (payload: ToolResultPayload) => {
      const tc = stateRef.current.toolCalls;
      // Find the tool call by name (most recent matching)
      for (const [id, call] of tc) {
        if (call.name === payload.name && call.status === 'running') {
          call.status = payload.success ? 'done' : 'error';
          call.output = payload.output || payload.error || '';
          break;
        }
      }
      
      // Add to current assistant's toolCalls
      const current = stateRef.current.currentAssistant;
      if (current) {
        current.toolCalls = Array.from(tc.values());
      }

      setState(prev => ({
        ...prev,
        toolCalls: new Map(tc),
        currentAssistant: current ? { ...current } : null,
        statusText: prev.turn > 0 ? `Turn ${prev.turn}` : 'Working...',
      }));
    };

    const onQuestion = (payload: QuestionPayload) => {
      setState(prev => ({
        ...prev,
        question: payload,
        statusText: 'Question pending...',
      }));
    };

    const onPlanEnter = () => {
      setState(prev => ({
        ...prev,
        planMode: true,
        statusText: 'Plan Mode — Researching...',
      }));
    };

    const onPlanExit = (payload: PlanPayload) => {
      const current = stateRef.current.currentAssistant;
      if (current) {
        current.plan = payload.plan;
      }
      setState(prev => ({
        ...prev,
        planMode: false,
        planText: payload.plan,
        currentAssistant: current ? { ...current } : null,
        statusText: 'Plan ready for approval',
      }));
    };

    const onDone = (payload: DonePayload) => {
      const current = stateRef.current.currentAssistant;
      if (current) {
        current.done = true;
      }
      setState(prev => ({
        ...prev,
        currentAssistant: current ? { ...current } : null,
        isStreaming: false,
        isThinking: false,
        statusText: payload.success ? '✅ Done · verified' : `⚠️ Finished · ${payload.finish_reason || 'review needed'}`,
        tokens: payload.tokens || prev.tokens,
      }));
    };

    const onError = (error: string) => {
      const current = stateRef.current.currentAssistant;
      if (current) {
        current.content += `\n\n❌ Error: ${error}`;
      }
      setState(prev => ({
        ...prev,
        currentAssistant: current ? { ...current } : null,
        isStreaming: false,
        statusText: 'Error',
      }));
    };

    const onCompact = (payload: any) => {
      const info: Message = {
        id: `compact-${Date.now()}`,
        role: 'system',
        content: `📦 Context compacted. ${payload.summary || ''}`,
        compact: true,
      };
      setState(prev => ({
        ...prev,
        messages: [...prev.messages, info],
      }));
    };

    backend.on('delta', onDelta);
    backend.on('thinking', onThinking);
    backend.on('tool_call', onToolCall);
    backend.on('tool_result', onToolResult);
    backend.on('question', onQuestion);
    backend.on('plan_enter', onPlanEnter);
    backend.on('plan_exit', onPlanExit);
    backend.on('done', onDone);
    backend.on('agent_error', onError);
    backend.on('compact', onCompact);

    // If task provided, submit it immediately
    if (task) {
      setTimeout(() => submitTask(task), 100);
    }

    return () => {
      backend.off('delta', onDelta);
      backend.off('thinking', onThinking);
      backend.off('tool_call', onToolCall);
      backend.off('tool_result', onToolResult);
      backend.off('question', onQuestion);
      backend.off('plan_enter', onPlanEnter);
      backend.off('plan_exit', onPlanExit);
      backend.off('done', onDone);
      backend.off('agent_error', onError);
      backend.off('compact', onCompact);
    };
  }, []);

  // Keyboard shortcuts
  useInput((input, key) => {
    if (key.escape) {
      if (state.isStreaming) {
        backend.cancel();
      } else {
        onExit();
      }
    }
    if (key.ctrl && input === 'c') {
      backend.stop();
      onExit();
    }
  });

  // Handle AskUserQuestion answers
  const handleQuestionAnswer = (answers: Record<string, string | string[]>) => {
    backend.sendAnswer(answers);
    setState(prev => ({
      ...prev,
      question: null,
      statusText: 'Resuming...',
    }));
  };

  // Handle plan approval
  const handlePlanApprove = (approved: boolean, mode?: string, feedback?: string) => {
    backend.sendPlanApproval(approved, mode, feedback);
    setState(prev => ({
      ...prev,
      planText: '',
      statusText: approved ? 'Executing plan...' : 'Refining plan...',
    }));
  };

  return (
    <Box flexDirection="column" height="100%">
      <StatusBar
        model={model}
        turn={state.turn}
        status={state.statusText}
        planMode={state.planMode}
        tokens={state.tokens}
        isStreaming={state.isStreaming}
      />
      
      <MessageList
        messages={state.messages}
        currentAssistant={state.currentAssistant}
        toolCalls={state.toolCalls}
        isThinking={state.isThinking}
        thinkingContent={state.thinkingContent}
        isStreaming={state.isStreaming}
        planMode={state.planMode}
        planText={state.planText}
        onPlanApprove={handlePlanApprove}
      />

      {state.question && (
        <AskUserQuestion
          questions={state.question.questions}
          onAnswer={handleQuestionAnswer}
        />
      )}

      {!state.question && !state.planText && (
        <Prompt
          onSubmit={submitTask}
          disabled={state.isStreaming}
          placeholder={state.isStreaming ? 'Waiting for response... (esc to cancel)' : 'Ask SOM-CODE anything...'}
          planMode={state.planMode}
        />
      )}
    </Box>
  );
}

// ── Entry Point ──────────────────────────────────────────────────

export async function startTUI(options: {
  model: string;
  task?: string;
  permission?: string;
  workspace?: string;
  pythonPath?: string;
  session?: SessionRecord;
}) {
  const backend = new AgentBackend(options.pythonPath);
  const session = options.session || createSession({
    model: options.model,
    workspace: options.workspace,
    permission: options.permission,
    title: options.task,
  });

  try {
    await backend.start(options.model, options.workspace, session);
  } catch (err) {
    console.error('Failed to start agent backend:', err);
    console.error('Make sure python3 is installed and the harness is at ../llm-harness/');
    process.exit(1);
  }

  let exited = false;
  const onExit = () => {
    if (exited) return;
    exited = true;
    backend.stop();
    process.exit(0);
  };

  const { waitUntilExit } = render(
    React.createElement(App, {
      model: options.model,
      task: options.task,
      permission: options.permission,
      workspace: options.workspace,
      backend,
      session,
      onExit,
    }),
    { exitOnCtrlC: false }
  );

  await waitUntilExit();
  backend.stop();
}
