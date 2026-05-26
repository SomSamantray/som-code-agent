import React, { useState } from 'react';
import { Box, Text, useInput } from 'ink';
import { theme } from './theme.js';

interface PromptProps {
  onSubmit: (text: string) => void;
  disabled?: boolean;
  placeholder?: string;
  planMode?: boolean;
}

export function Prompt({ onSubmit, disabled, placeholder, planMode }: PromptProps) {
  const [input, setInput] = useState('');
  const [cursor, setCursor] = useState(0);

  useInput((char, key) => {
    if (disabled) return;
    if (key.return) {
      const trimmed = input.trim();
      if (trimmed) onSubmit(trimmed);
      setInput('');
      setCursor(0);
      return;
    }
    if (key.backspace || key.delete) {
      if (cursor <= 0) return;
      setInput(input.slice(0, cursor - 1) + input.slice(cursor));
      setCursor(Math.max(0, cursor - 1));
      return;
    }
    if (key.leftArrow) return setCursor(Math.max(0, cursor - 1));
    if (key.rightArrow) return setCursor(Math.min(input.length, cursor + 1));
    if ((key as any).home || (key.ctrl && char === 'a')) return setCursor(0);
    if ((key as any).end || (key.ctrl && char === 'e')) return setCursor(input.length);
    if (key.ctrl && char === 'u') {
      setInput('');
      setCursor(0);
      return;
    }
    if (key.ctrl && char === 'w') {
      const before = input.slice(0, cursor).replace(/\S+\s*$/, '');
      setInput(before + input.slice(cursor));
      setCursor(before.length);
      return;
    }
    if (char && char.length === 1 && !key.ctrl && !key.meta) {
      setInput(input.slice(0, cursor) + char + input.slice(cursor));
      setCursor(cursor + 1);
    }
  }, { isActive: !disabled });

  const display = disabled ? (placeholder || 'Waiting…') : input.slice(0, cursor) + '█' + input.slice(cursor);

  return (
    <Box flexDirection="column" borderStyle="round" borderColor={planMode ? theme.yellow : theme.border} paddingX={1} marginTop={1}>
      <Box>
        <Text bold color={planMode ? theme.yellow : theme.border}>{planMode ? 'plan' : 'ask'} </Text>
        <Text color={disabled ? theme.dim : theme.text}>› {display}</Text>
      </Box>
      {!disabled && <Text color={theme.dim}>enter send · ctrl+w word delete · ctrl+u clear · esc cancel</Text>}
    </Box>
  );
}
