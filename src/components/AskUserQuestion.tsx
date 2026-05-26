/**
 * AskUserQuestion — interactive multi-choice clarification.
 * Exact match to Claude Code's AskUserQuestion pattern:
 * 2-4 options per question, numbered selection, "Other" free-text fallback.
 */

import React, { useState } from 'react';
import { Box, Text, useInput } from 'ink';

interface Question {
  question: string;
  header: string;
  options: Array<{label: string; description: string}>;
  multiSelect?: boolean;
}

interface AskUserQuestionProps {
  questions: Question[];
  onAnswer: (answers: Record<string, string | string[]>) => void;
}

export function AskUserQuestion({ questions, onAnswer }: AskUserQuestionProps) {
  const [currentQ, setCurrentQ] = useState(0);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [otherText, setOtherText] = useState('');
  const [inOther, setInOther] = useState(false);
  const [answers, setAnswers] = useState<Record<string, string | string[]>>({});

  const q = questions[currentQ];
  if (!q) return null;

  const isMulti = q.multiSelect || false;
  const maxChoice = q.options.length + 1; // +1 for "Other"

  useInput((char, key) => {
    if (inOther) {
      if (key.return) {
        // Submit other text
        const newAnswers = { ...answers, [q.question]: [otherText] };
        if (currentQ < questions.length - 1) {
          setAnswers(newAnswers);
          setCurrentQ(currentQ + 1);
          setSelected(new Set());
          setOtherText('');
          setInOther(false);
        } else {
          onAnswer(newAnswers);
        }
        return;
      }
      if (key.backspace) {
        setOtherText(prev => prev.slice(0, -1));
        return;
      }
      if (char && char.length === 1) {
        setOtherText(prev => prev + char);
      }
      return;
    }

    // Number selection
    const num = parseInt(char);
    if (num >= 1 && num <= maxChoice) {
      if (num === maxChoice) {
        // "Other" selected
        setInOther(true);
        setOtherText('');
        return;
      }

      const idx = num - 1;
      if (isMulti) {
        const newSelected = new Set(selected);
        if (newSelected.has(idx)) {
          newSelected.delete(idx);
        } else {
          newSelected.add(idx);
        }
        setSelected(newSelected);
      } else {
        // Single select: immediately proceed
        const newAnswers = { 
          ...answers, 
          [q.question]: q.options[idx].label 
        };
        if (currentQ < questions.length - 1) {
          setAnswers(newAnswers);
          setCurrentQ(currentQ + 1);
          setSelected(new Set());
        } else {
          onAnswer(newAnswers);
        }
      }
      return;
    }

    // Multi-select: Enter to confirm
    if (key.return && isMulti && selected.size > 0) {
      const selectedLabels = Array.from(selected).map(i => q.options[i].label);
      const newAnswers = { ...answers, [q.question]: selectedLabels };
      if (currentQ < questions.length - 1) {
        setAnswers(newAnswers);
        setCurrentQ(currentQ + 1);
        setSelected(new Set());
      } else {
        onAnswer(newAnswers);
      }
      return;
    }
  }, { isActive: true });

  return (
    <Box flexDirection="column" borderStyle="double" borderColor="magenta" paddingX={1} marginY={1}>
      <Text bold color="magenta">
        ❓ {q.header} {currentQ + 1}/{questions.length}
      </Text>
      <Text>{q.question}</Text>
      
      <Box flexDirection="column" marginY={1}>
        {q.options.map((opt, i) => {
          const isSelected = selected.has(i);
          const marker = isMulti 
            ? (isSelected ? '☑' : '☐')
            : `${i + 1}.`;
          return (
            <Text key={i} color={isSelected ? 'green' : undefined}>
              {marker} {opt.label} — {opt.description}
            </Text>
          );
        })}
        <Text dimColor>
          {maxChoice}. Other (type your answer)
        </Text>
      </Box>

      {inOther && (
        <Box>
          <Text>  Your answer: </Text>
          <Text color="yellow">{otherText || '_'}</Text>
          <Text dimColor> (Enter to submit)</Text>
        </Box>
      )}

      {!inOther && (
        <Text dimColor>
          {isMulti 
            ? `Select with numbers, Enter to confirm (${selected.size} selected)` 
            : 'Choose a number or type your answer'}
        </Text>
      )}
    </Box>
  );
}
