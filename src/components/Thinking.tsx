import React, { useState } from 'react';
import { Box, Text, useInput } from 'ink';
import { theme, truncate } from './theme.js';

interface ThinkingProps {
  content: string;
  isStreaming: boolean;
}

export function Thinking({ content, isStreaming }: ThinkingProps) {
  const [expanded, setExpanded] = useState(false);
  const frames = ['✶', '✷', '✸', '✹'];
  const [frame, setFrame] = React.useState(0);

  React.useEffect(() => {
    if (!isStreaming) return;
    const interval = setInterval(() => setFrame(value => (value + 1) % frames.length), 120);
    return () => clearInterval(interval);
  }, [isStreaming]);

  useInput((input, key) => {
    if (key.tab) setExpanded(value => !value);
  });

  if (!content) return null;

  const titleMatch = content.match(/\*\*(.+?)\*\*/);
  const words = content.trim().split(/\s+/).filter(Boolean).length;
  const title = titleMatch ? ` · ${titleMatch[1]}` : '';

  if (!expanded) {
    return (
      <Box borderStyle="single" borderColor={theme.violet} paddingX={1} marginBottom={1}>
        <Text color={theme.violet}>{isStreaming ? frames[frame] : '◇'} Thought</Text>
        <Text color={theme.dim}>{title} · {words} words · tab expand</Text>
      </Box>
    );
  }

  return (
    <Box flexDirection="column" borderStyle="round" borderColor={theme.violet} paddingX={1} marginBottom={1}>
      <Text bold color={theme.violet}>{isStreaming ? frames[frame] : '◇'} Thought trace</Text>
      <Text color={theme.dim}>{truncate(content, 2600)}</Text>
      <Text color={theme.dim}>tab collapse</Text>
    </Box>
  );
}
