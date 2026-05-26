import React from 'react';
import { Box, Text, Static, useInput } from 'ink';
import { Thinking } from './Thinking.js';
import { ToolCall } from './ToolCall.js';
import { theme, truncate } from './theme.js';
import type { Message } from './App.js';

interface MessageListProps {
  messages: Message[];
  currentAssistant: Message | null;
  toolCalls: Map<string, any>;
  isThinking: boolean;
  thinkingContent: string;
  isStreaming: boolean;
  planMode: boolean;
  planText: string;
  onPlanApprove: (approved: boolean, mode?: string, feedback?: string) => void;
}

export function MessageList({
  messages,
  currentAssistant,
  toolCalls,
  isThinking,
  thinkingContent,
  isStreaming,
  planText,
  onPlanApprove,
}: MessageListProps) {
  const completed = currentAssistant ? messages.filter(m => m.id !== currentAssistant.id) : messages;

  return (
    <Box flexDirection="column" flexGrow={1} paddingX={1}>
      <Static items={completed}>
        {(msg) => <TimelineMessage key={msg.id} message={msg} onPlanApprove={onPlanApprove} />}
      </Static>

      {currentAssistant && (
        <Box flexDirection="column" marginY={1}>
          <MessageHeader role="assistant" live={isStreaming} />
          {isThinking && thinkingContent && <Thinking content={thinkingContent} isStreaming={isStreaming} />}
          {Array.from(toolCalls.values()).map((tc, i) => (
            <ToolCall key={`${tc.name}-${i}`} name={tc.name} status={tc.status} output={tc.output} />
          ))}
          {currentAssistant.content && <AssistantBubble content={currentAssistant.content} />}
          {planText && <PlanDisplay plan={planText} onApprove={onPlanApprove} />}
          {isStreaming && !thinkingContent && !currentAssistant.content && toolCalls.size === 0 && <Spinner text="thinking" />}
        </Box>
      )}
    </Box>
  );
}

function TimelineMessage({ message, onPlanApprove }: {message: Message; onPlanApprove: MessageListProps['onPlanApprove']}) {
  return (
    <Box flexDirection="column" marginY={1}>
      <MessageHeader role={message.role} />
      {message.content && (message.role === 'assistant' ? <AssistantBubble content={message.content} /> : <UserBubble content={message.content} role={message.role} />)}
      {message.thinking && <Thinking content={message.thinking} isStreaming={false} />}
      {message.toolCalls?.map((tc, i) => <ToolCall key={`${tc.name}-${i}`} name={tc.name} status={tc.status} output={tc.output} />)}
      {message.plan && <PlanDisplay plan={message.plan} onApprove={onPlanApprove} />}
    </Box>
  );
}

function MessageHeader({ role, live = false }: {role: Message['role']; live?: boolean}) {
  const label = role === 'user' ? 'You' : role === 'system' ? 'System' : 'SOM-CODE';
  const color = role === 'user' ? theme.green : role === 'system' ? theme.yellow : theme.accent;
  return (
    <Box gap={1}>
      <Text color={theme.dim}>╭─</Text>
      <Text bold color={color}>{label}</Text>
      {live && <Text color={theme.green}>live</Text>}
    </Box>
  );
}

function UserBubble({ content, role }: {content: string; role: Message['role']}) {
  return (
    <Box borderStyle="round" borderColor={role === 'system' ? theme.yellow : theme.green} paddingX={1}>
      <Text color={theme.text}>{content}</Text>
    </Box>
  );
}

function AssistantBubble({ content }: {content: string}) {
  return (
    <Box borderStyle="round" borderColor={theme.borderMuted} paddingX={1} flexDirection="column">
      <Text color={theme.text}>{content}</Text>
    </Box>
  );
}

function Spinner({ text }: { text: string }) {
  const frames = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴'];
  const [frame, setFrame] = React.useState(0);

  React.useEffect(() => {
    const interval = setInterval(() => setFrame(f => (f + 1) % frames.length), 80);
    return () => clearInterval(interval);
  }, []);

  return <Text color={theme.dim}>{frames[frame]} {text}…</Text>;
}

function PlanDisplay({ plan, onApprove }: { plan: string; onApprove: MessageListProps['onPlanApprove'] }) {
  const [feedbackMode, setFeedbackMode] = React.useState(false);
  const [feedback, setFeedback] = React.useState('');

  useInput((input, key) => {
    if (feedbackMode) {
      if (key.return) onApprove(false, 'refine', feedback);
      else if (key.backspace || key.delete) setFeedback(value => value.slice(0, -1));
      else if (input && !key.ctrl && !key.meta) setFeedback(value => value + input);
      return;
    }
    if (input === '1') onApprove(true, 'execute');
    if (input === '2') onApprove(true, 'acceptEdits');
    if (input === '3') setFeedbackMode(true);
    if (input === '4') onApprove(false, 'save');
  });

  return (
    <Box flexDirection="column" borderStyle="round" borderColor={theme.yellow} paddingX={1} marginY={1}>
      <Text bold color={theme.yellow}>▣ Plan review</Text>
      <Text color={theme.text}>{truncate(plan, 3200)}</Text>
      <Box flexDirection="column" marginTop={1}>
        <Text color={theme.dim}>1 execute · 2 accept edits · 3 refine · 4 save</Text>
        {feedbackMode && <Text color={theme.yellow}>feedback › {feedback || '█'}</Text>}
      </Box>
    </Box>
  );
}
