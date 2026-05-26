import React from 'react';
import { Box, Text } from 'ink';
import { shortModel, theme } from './theme.js';

export function StatusBar({
  model,
  turn,
  status,
  planMode,
  tokens,
  isStreaming,
}: {
  model: string;
  turn: number;
  status: string;
  planMode: boolean;
  tokens: {prompt: number; completion: number; total: number};
  isStreaming: boolean;
}) {
  const frames = ['◆', '◇', '◈', '◇'];
  const [frame, setFrame] = React.useState(0);

  React.useEffect(() => {
    if (!isStreaming) return;
    const interval = setInterval(() => setFrame(value => (value + 1) % frames.length), 140);
    return () => clearInterval(interval);
  }, [isStreaming]);

  return (
    <Box flexDirection="column" marginBottom={1}>
      <Box borderStyle="round" borderColor={planMode ? theme.yellow : theme.border} paddingX={1} justifyContent="space-between">
        <Box gap={2}>
          <Text bold color={theme.border}>✦ SOM-CODE</Text>
          <Text color={theme.accent}>{shortModel(model)}</Text>
          <Text color={theme.dim}>workspace agent</Text>
          {planMode && <Text color={theme.yellow}>PLAN-FIRST</Text>}
        </Box>
        <Box gap={2}>
          {turn > 0 && <Text color={theme.dim}>turn {turn}</Text>}
          {tokens.total > 0 && <Text color={theme.dim}>{tokens.total.toLocaleString()} tok</Text>}
          <Text color={isStreaming ? theme.green : theme.dim}>{isStreaming ? frames[frame] : '●'} {status}</Text>
        </Box>
      </Box>
      <Box paddingX={2} justifyContent="space-between">
        <Text color={theme.dim}>Claude/OpenCode-style loop · thoughts · tools · permissions · resume-ready</Text>
        <Text color={theme.dim}>esc cancel · ctrl+c quit</Text>
      </Box>
    </Box>
  );
}
