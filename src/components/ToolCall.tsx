import React, { useState } from 'react';
import { Box, Text, useInput } from 'ink';
import { theme, truncate } from './theme.js';

interface ToolCallProps {
  name: string;
  status: 'running' | 'done' | 'error';
  output?: string;
}

export function ToolCall({ name, status, output }: ToolCallProps) {
  const [expanded, setExpanded] = useState(false);
  const frames = ['⠋', '⠙', '⠹', '⠸'];
  const [frame, setFrame] = React.useState(0);

  React.useEffect(() => {
    if (status !== 'running') return;
    const interval = setInterval(() => setFrame(value => (value + 1) % frames.length), 90);
    return () => clearInterval(interval);
  }, [status]);

  useInput((input, key) => {
    if (key.tab && output) setExpanded(value => !value);
  });

  const icon = status === 'running' ? frames[frame] : status === 'done' ? '✓' : '×';
  const color = status === 'running' ? theme.yellow : status === 'done' ? theme.green : theme.red;
  const summary = output ? output.split('\n').find(Boolean)?.slice(0, 120) || 'completed' : status === 'running' ? 'running…' : '';

  if (!expanded || !output) {
    return (
      <Box borderStyle="single" borderColor={theme.borderMuted} paddingX={1} marginY={0}>
        <Text color={color}>{icon} </Text>
        <Text bold color={theme.text}>{name}</Text>
        {summary && <Text color={theme.dim}>  {summary}{output && output.length > 120 ? '…' : ''}</Text>}
      </Box>
    );
  }

  return (
    <Box flexDirection="column" borderStyle="round" borderColor={color} paddingX={1} marginY={0}>
      <Text bold color={color}>{icon} tool · {name}</Text>
      <Text color={theme.text}>{truncate(output, 2400)}</Text>
      <Text color={theme.dim}>tab collapse</Text>
    </Box>
  );
}
