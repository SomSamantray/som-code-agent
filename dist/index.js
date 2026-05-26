#!/usr/bin/env node
import { createRequire } from "node:module"; const require = createRequire(import.meta.url);

// src/index.ts
import { parseArgs } from "node:util";

// src/components/App.tsx
import React7, { useState as useState5, useRef, useEffect } from "react";
import { render, Box as Box7, useInput as useInput6, useApp } from "ink";

// src/components/Prompt.tsx
import { useState } from "react";
import { Box, Text, useInput } from "ink";

// src/components/theme.ts
var theme = {
  bg: "#0b0f14",
  panel: "#111827",
  border: "#2dd4bf",
  borderMuted: "#334155",
  text: "#e5e7eb",
  dim: "#64748b",
  accent: "#7dd3fc",
  violet: "#a78bfa",
  green: "#86efac",
  yellow: "#fde68a",
  red: "#fca5a5"
};
function shortModel(model) {
  const parts = model.split("/");
  return parts.length > 1 ? parts.slice(-2).join("/") : model;
}
function truncate(value, limit = 1200) {
  if (value.length <= limit) return value;
  return `${value.slice(0, limit)}\u2026`;
}

// src/components/Prompt.tsx
import { jsx, jsxs } from "react/jsx-runtime";
function Prompt({ onSubmit, disabled, placeholder, planMode }) {
  const [input, setInput] = useState("");
  const [cursor, setCursor] = useState(0);
  useInput((char, key) => {
    if (disabled) return;
    if (key.return) {
      const trimmed = input.trim();
      if (trimmed) onSubmit(trimmed);
      setInput("");
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
    if (key.home || key.ctrl && char === "a") return setCursor(0);
    if (key.end || key.ctrl && char === "e") return setCursor(input.length);
    if (key.ctrl && char === "u") {
      setInput("");
      setCursor(0);
      return;
    }
    if (key.ctrl && char === "w") {
      const before = input.slice(0, cursor).replace(/\S+\s*$/, "");
      setInput(before + input.slice(cursor));
      setCursor(before.length);
      return;
    }
    if (char && char.length === 1 && !key.ctrl && !key.meta) {
      setInput(input.slice(0, cursor) + char + input.slice(cursor));
      setCursor(cursor + 1);
    }
  }, { isActive: !disabled });
  const display = disabled ? placeholder || "Waiting\u2026" : input.slice(0, cursor) + "\u2588" + input.slice(cursor);
  return /* @__PURE__ */ jsxs(Box, { flexDirection: "column", borderStyle: "round", borderColor: planMode ? theme.yellow : theme.border, paddingX: 1, marginTop: 1, children: [
    /* @__PURE__ */ jsxs(Box, { children: [
      /* @__PURE__ */ jsxs(Text, { bold: true, color: planMode ? theme.yellow : theme.border, children: [
        planMode ? "plan" : "ask",
        " "
      ] }),
      /* @__PURE__ */ jsxs(Text, { color: disabled ? theme.dim : theme.text, children: [
        "\u203A ",
        display
      ] })
    ] }),
    !disabled && /* @__PURE__ */ jsx(Text, { color: theme.dim, children: "enter send \xB7 ctrl+w word delete \xB7 ctrl+u clear \xB7 esc cancel" })
  ] });
}

// src/components/MessageList.tsx
import React4 from "react";
import { Box as Box4, Text as Text4, Static, useInput as useInput4 } from "ink";

// src/components/Thinking.tsx
import React2, { useState as useState2 } from "react";
import { Box as Box2, Text as Text2, useInput as useInput2 } from "ink";
import { jsx as jsx2, jsxs as jsxs2 } from "react/jsx-runtime";
function Thinking({ content, isStreaming }) {
  const [expanded, setExpanded] = useState2(false);
  const frames = ["\u2736", "\u2737", "\u2738", "\u2739"];
  const [frame, setFrame] = React2.useState(0);
  React2.useEffect(() => {
    if (!isStreaming) return;
    const interval = setInterval(() => setFrame((value) => (value + 1) % frames.length), 120);
    return () => clearInterval(interval);
  }, [isStreaming]);
  useInput2((input, key) => {
    if (key.tab) setExpanded((value) => !value);
  });
  if (!content) return null;
  const titleMatch = content.match(/\*\*(.+?)\*\*/);
  const words = content.trim().split(/\s+/).filter(Boolean).length;
  const title = titleMatch ? ` \xB7 ${titleMatch[1]}` : "";
  if (!expanded) {
    return /* @__PURE__ */ jsxs2(Box2, { borderStyle: "single", borderColor: theme.violet, paddingX: 1, marginBottom: 1, children: [
      /* @__PURE__ */ jsxs2(Text2, { color: theme.violet, children: [
        isStreaming ? frames[frame] : "\u25C7",
        " Thought"
      ] }),
      /* @__PURE__ */ jsxs2(Text2, { color: theme.dim, children: [
        title,
        " \xB7 ",
        words,
        " words \xB7 tab expand"
      ] })
    ] });
  }
  return /* @__PURE__ */ jsxs2(Box2, { flexDirection: "column", borderStyle: "round", borderColor: theme.violet, paddingX: 1, marginBottom: 1, children: [
    /* @__PURE__ */ jsxs2(Text2, { bold: true, color: theme.violet, children: [
      isStreaming ? frames[frame] : "\u25C7",
      " Thought trace"
    ] }),
    /* @__PURE__ */ jsx2(Text2, { color: theme.dim, children: truncate(content, 2600) }),
    /* @__PURE__ */ jsx2(Text2, { color: theme.dim, children: "tab collapse" })
  ] });
}

// src/components/ToolCall.tsx
import React3, { useState as useState3 } from "react";
import { Box as Box3, Text as Text3, useInput as useInput3 } from "ink";
import { jsx as jsx3, jsxs as jsxs3 } from "react/jsx-runtime";
function ToolCall({ name, status, output }) {
  const [expanded, setExpanded] = useState3(false);
  const frames = ["\u280B", "\u2819", "\u2839", "\u2838"];
  const [frame, setFrame] = React3.useState(0);
  React3.useEffect(() => {
    if (status !== "running") return;
    const interval = setInterval(() => setFrame((value) => (value + 1) % frames.length), 90);
    return () => clearInterval(interval);
  }, [status]);
  useInput3((input, key) => {
    if (key.tab && output) setExpanded((value) => !value);
  });
  const icon = status === "running" ? frames[frame] : status === "done" ? "\u2713" : "\xD7";
  const color = status === "running" ? theme.yellow : status === "done" ? theme.green : theme.red;
  const summary = output ? output.split("\n").find(Boolean)?.slice(0, 120) || "completed" : status === "running" ? "running\u2026" : "";
  if (!expanded || !output) {
    return /* @__PURE__ */ jsxs3(Box3, { borderStyle: "single", borderColor: theme.borderMuted, paddingX: 1, marginY: 0, children: [
      /* @__PURE__ */ jsxs3(Text3, { color, children: [
        icon,
        " "
      ] }),
      /* @__PURE__ */ jsx3(Text3, { bold: true, color: theme.text, children: name }),
      summary && /* @__PURE__ */ jsxs3(Text3, { color: theme.dim, children: [
        "  ",
        summary,
        output && output.length > 120 ? "\u2026" : ""
      ] })
    ] });
  }
  return /* @__PURE__ */ jsxs3(Box3, { flexDirection: "column", borderStyle: "round", borderColor: color, paddingX: 1, marginY: 0, children: [
    /* @__PURE__ */ jsxs3(Text3, { bold: true, color, children: [
      icon,
      " tool \xB7 ",
      name
    ] }),
    /* @__PURE__ */ jsx3(Text3, { color: theme.text, children: truncate(output, 2400) }),
    /* @__PURE__ */ jsx3(Text3, { color: theme.dim, children: "tab collapse" })
  ] });
}

// src/components/MessageList.tsx
import { jsx as jsx4, jsxs as jsxs4 } from "react/jsx-runtime";
function MessageList({
  messages,
  currentAssistant,
  toolCalls,
  isThinking,
  thinkingContent,
  isStreaming,
  planText,
  onPlanApprove
}) {
  const completed = currentAssistant ? messages.filter((m) => m.id !== currentAssistant.id) : messages;
  return /* @__PURE__ */ jsxs4(Box4, { flexDirection: "column", flexGrow: 1, paddingX: 1, children: [
    /* @__PURE__ */ jsx4(Static, { items: completed, children: (msg) => /* @__PURE__ */ jsx4(TimelineMessage, { message: msg, onPlanApprove }, msg.id) }),
    currentAssistant && /* @__PURE__ */ jsxs4(Box4, { flexDirection: "column", marginY: 1, children: [
      /* @__PURE__ */ jsx4(MessageHeader, { role: "assistant", live: isStreaming }),
      isThinking && thinkingContent && /* @__PURE__ */ jsx4(Thinking, { content: thinkingContent, isStreaming }),
      Array.from(toolCalls.values()).map((tc, i) => /* @__PURE__ */ jsx4(ToolCall, { name: tc.name, status: tc.status, output: tc.output }, `${tc.name}-${i}`)),
      currentAssistant.content && /* @__PURE__ */ jsx4(AssistantBubble, { content: currentAssistant.content }),
      planText && /* @__PURE__ */ jsx4(PlanDisplay, { plan: planText, onApprove: onPlanApprove }),
      isStreaming && !thinkingContent && !currentAssistant.content && toolCalls.size === 0 && /* @__PURE__ */ jsx4(Spinner, { text: "thinking" })
    ] })
  ] });
}
function TimelineMessage({ message, onPlanApprove }) {
  return /* @__PURE__ */ jsxs4(Box4, { flexDirection: "column", marginY: 1, children: [
    /* @__PURE__ */ jsx4(MessageHeader, { role: message.role }),
    message.content && (message.role === "assistant" ? /* @__PURE__ */ jsx4(AssistantBubble, { content: message.content }) : /* @__PURE__ */ jsx4(UserBubble, { content: message.content, role: message.role })),
    message.thinking && /* @__PURE__ */ jsx4(Thinking, { content: message.thinking, isStreaming: false }),
    message.toolCalls?.map((tc, i) => /* @__PURE__ */ jsx4(ToolCall, { name: tc.name, status: tc.status, output: tc.output }, `${tc.name}-${i}`)),
    message.plan && /* @__PURE__ */ jsx4(PlanDisplay, { plan: message.plan, onApprove: onPlanApprove })
  ] });
}
function MessageHeader({ role, live = false }) {
  const label = role === "user" ? "You" : role === "system" ? "System" : "SOM-CODE";
  const color = role === "user" ? theme.green : role === "system" ? theme.yellow : theme.accent;
  return /* @__PURE__ */ jsxs4(Box4, { gap: 1, children: [
    /* @__PURE__ */ jsx4(Text4, { color: theme.dim, children: "\u256D\u2500" }),
    /* @__PURE__ */ jsx4(Text4, { bold: true, color, children: label }),
    live && /* @__PURE__ */ jsx4(Text4, { color: theme.green, children: "live" })
  ] });
}
function UserBubble({ content, role }) {
  return /* @__PURE__ */ jsx4(Box4, { borderStyle: "round", borderColor: role === "system" ? theme.yellow : theme.green, paddingX: 1, children: /* @__PURE__ */ jsx4(Text4, { color: theme.text, children: content }) });
}
function AssistantBubble({ content }) {
  return /* @__PURE__ */ jsx4(Box4, { borderStyle: "round", borderColor: theme.borderMuted, paddingX: 1, flexDirection: "column", children: /* @__PURE__ */ jsx4(Text4, { color: theme.text, children: content }) });
}
function Spinner({ text }) {
  const frames = ["\u280B", "\u2819", "\u2839", "\u2838", "\u283C", "\u2834"];
  const [frame, setFrame] = React4.useState(0);
  React4.useEffect(() => {
    const interval = setInterval(() => setFrame((f) => (f + 1) % frames.length), 80);
    return () => clearInterval(interval);
  }, []);
  return /* @__PURE__ */ jsxs4(Text4, { color: theme.dim, children: [
    frames[frame],
    " ",
    text,
    "\u2026"
  ] });
}
function PlanDisplay({ plan, onApprove }) {
  const [feedbackMode, setFeedbackMode] = React4.useState(false);
  const [feedback, setFeedback] = React4.useState("");
  useInput4((input, key) => {
    if (feedbackMode) {
      if (key.return) onApprove(false, "refine", feedback);
      else if (key.backspace || key.delete) setFeedback((value) => value.slice(0, -1));
      else if (input && !key.ctrl && !key.meta) setFeedback((value) => value + input);
      return;
    }
    if (input === "1") onApprove(true, "execute");
    if (input === "2") onApprove(true, "acceptEdits");
    if (input === "3") setFeedbackMode(true);
    if (input === "4") onApprove(false, "save");
  });
  return /* @__PURE__ */ jsxs4(Box4, { flexDirection: "column", borderStyle: "round", borderColor: theme.yellow, paddingX: 1, marginY: 1, children: [
    /* @__PURE__ */ jsx4(Text4, { bold: true, color: theme.yellow, children: "\u25A3 Plan review" }),
    /* @__PURE__ */ jsx4(Text4, { color: theme.text, children: truncate(plan, 3200) }),
    /* @__PURE__ */ jsxs4(Box4, { flexDirection: "column", marginTop: 1, children: [
      /* @__PURE__ */ jsx4(Text4, { color: theme.dim, children: "1 execute \xB7 2 accept edits \xB7 3 refine \xB7 4 save" }),
      feedbackMode && /* @__PURE__ */ jsxs4(Text4, { color: theme.yellow, children: [
        "feedback \u203A ",
        feedback || "\u2588"
      ] })
    ] })
  ] });
}

// src/components/StatusBar.tsx
import React5 from "react";
import { Box as Box5, Text as Text5 } from "ink";
import { jsx as jsx5, jsxs as jsxs5 } from "react/jsx-runtime";
function StatusBar({
  model,
  turn,
  status,
  planMode,
  tokens,
  isStreaming
}) {
  const frames = ["\u25C6", "\u25C7", "\u25C8", "\u25C7"];
  const [frame, setFrame] = React5.useState(0);
  React5.useEffect(() => {
    if (!isStreaming) return;
    const interval = setInterval(() => setFrame((value) => (value + 1) % frames.length), 140);
    return () => clearInterval(interval);
  }, [isStreaming]);
  return /* @__PURE__ */ jsxs5(Box5, { flexDirection: "column", marginBottom: 1, children: [
    /* @__PURE__ */ jsxs5(Box5, { borderStyle: "round", borderColor: planMode ? theme.yellow : theme.border, paddingX: 1, justifyContent: "space-between", children: [
      /* @__PURE__ */ jsxs5(Box5, { gap: 2, children: [
        /* @__PURE__ */ jsx5(Text5, { bold: true, color: theme.border, children: "\u2726 SOM-CODE" }),
        /* @__PURE__ */ jsx5(Text5, { color: theme.accent, children: shortModel(model) }),
        /* @__PURE__ */ jsx5(Text5, { color: theme.dim, children: "workspace agent" }),
        planMode && /* @__PURE__ */ jsx5(Text5, { color: theme.yellow, children: "PLAN-FIRST" })
      ] }),
      /* @__PURE__ */ jsxs5(Box5, { gap: 2, children: [
        turn > 0 && /* @__PURE__ */ jsxs5(Text5, { color: theme.dim, children: [
          "turn ",
          turn
        ] }),
        tokens.total > 0 && /* @__PURE__ */ jsxs5(Text5, { color: theme.dim, children: [
          tokens.total.toLocaleString(),
          " tok"
        ] }),
        /* @__PURE__ */ jsxs5(Text5, { color: isStreaming ? theme.green : theme.dim, children: [
          isStreaming ? frames[frame] : "\u25CF",
          " ",
          status
        ] })
      ] })
    ] }),
    /* @__PURE__ */ jsxs5(Box5, { paddingX: 2, justifyContent: "space-between", children: [
      /* @__PURE__ */ jsx5(Text5, { color: theme.dim, children: "Claude/OpenCode-style loop \xB7 thoughts \xB7 tools \xB7 permissions \xB7 resume-ready" }),
      /* @__PURE__ */ jsx5(Text5, { color: theme.dim, children: "esc cancel \xB7 ctrl+c quit" })
    ] })
  ] });
}

// src/components/AskUserQuestion.tsx
import { useState as useState4 } from "react";
import { Box as Box6, Text as Text6, useInput as useInput5 } from "ink";
import { jsx as jsx6, jsxs as jsxs6 } from "react/jsx-runtime";
function AskUserQuestion({ questions, onAnswer }) {
  const [currentQ, setCurrentQ] = useState4(0);
  const [selected, setSelected] = useState4(/* @__PURE__ */ new Set());
  const [otherText, setOtherText] = useState4("");
  const [inOther, setInOther] = useState4(false);
  const [answers, setAnswers] = useState4({});
  const q = questions[currentQ];
  if (!q) return null;
  const isMulti = q.multiSelect || false;
  const maxChoice = q.options.length + 1;
  useInput5((char, key) => {
    if (inOther) {
      if (key.return) {
        const newAnswers = { ...answers, [q.question]: [otherText] };
        if (currentQ < questions.length - 1) {
          setAnswers(newAnswers);
          setCurrentQ(currentQ + 1);
          setSelected(/* @__PURE__ */ new Set());
          setOtherText("");
          setInOther(false);
        } else {
          onAnswer(newAnswers);
        }
        return;
      }
      if (key.backspace) {
        setOtherText((prev) => prev.slice(0, -1));
        return;
      }
      if (char && char.length === 1) {
        setOtherText((prev) => prev + char);
      }
      return;
    }
    const num = parseInt(char);
    if (num >= 1 && num <= maxChoice) {
      if (num === maxChoice) {
        setInOther(true);
        setOtherText("");
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
        const newAnswers = {
          ...answers,
          [q.question]: q.options[idx].label
        };
        if (currentQ < questions.length - 1) {
          setAnswers(newAnswers);
          setCurrentQ(currentQ + 1);
          setSelected(/* @__PURE__ */ new Set());
        } else {
          onAnswer(newAnswers);
        }
      }
      return;
    }
    if (key.return && isMulti && selected.size > 0) {
      const selectedLabels = Array.from(selected).map((i) => q.options[i].label);
      const newAnswers = { ...answers, [q.question]: selectedLabels };
      if (currentQ < questions.length - 1) {
        setAnswers(newAnswers);
        setCurrentQ(currentQ + 1);
        setSelected(/* @__PURE__ */ new Set());
      } else {
        onAnswer(newAnswers);
      }
      return;
    }
  }, { isActive: true });
  return /* @__PURE__ */ jsxs6(Box6, { flexDirection: "column", borderStyle: "double", borderColor: "magenta", paddingX: 1, marginY: 1, children: [
    /* @__PURE__ */ jsxs6(Text6, { bold: true, color: "magenta", children: [
      "\u2753 ",
      q.header,
      " ",
      currentQ + 1,
      "/",
      questions.length
    ] }),
    /* @__PURE__ */ jsx6(Text6, { children: q.question }),
    /* @__PURE__ */ jsxs6(Box6, { flexDirection: "column", marginY: 1, children: [
      q.options.map((opt, i) => {
        const isSelected = selected.has(i);
        const marker = isMulti ? isSelected ? "\u2611" : "\u2610" : `${i + 1}.`;
        return /* @__PURE__ */ jsxs6(Text6, { color: isSelected ? "green" : void 0, children: [
          marker,
          " ",
          opt.label,
          " \u2014 ",
          opt.description
        ] }, i);
      }),
      /* @__PURE__ */ jsxs6(Text6, { dimColor: true, children: [
        maxChoice,
        ". Other (type your answer)"
      ] })
    ] }),
    inOther && /* @__PURE__ */ jsxs6(Box6, { children: [
      /* @__PURE__ */ jsx6(Text6, { children: "  Your answer: " }),
      /* @__PURE__ */ jsx6(Text6, { color: "yellow", children: otherText || "_" }),
      /* @__PURE__ */ jsx6(Text6, { dimColor: true, children: " (Enter to submit)" })
    ] }),
    !inOther && /* @__PURE__ */ jsx6(Text6, { dimColor: true, children: isMulti ? `Select with numbers, Enter to confirm (${selected.size} selected)` : "Choose a number or type your answer" })
  ] });
}

// src/agent/backend.ts
import { spawn } from "node:child_process";
import { createInterface } from "node:readline";
import { EventEmitter } from "node:events";
import { fileURLToPath } from "node:url";
import { dirname, join as join2 } from "node:path";
import { existsSync as existsSync2 } from "node:fs";

// src/session/store.ts
import { existsSync, mkdirSync, readdirSync, readFileSync, renameSync, statSync, writeFileSync } from "node:fs";
import { basename, join, resolve } from "node:path";
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
function sessionDir(workspace = process.cwd()) {
  return join(resolve(workspace), ".som-code", "sessions");
}
function createSessionId(seed = `${Date.now()}-${Math.random()}`) {
  const ts = (/* @__PURE__ */ new Date()).toISOString().replace(/[-:TZ.]/g, "").slice(0, 14);
  const hash = createHash("sha1").update(seed).digest("hex").slice(0, 8);
  return `${ts}-${hash}`;
}
function sessionPath(workspace, id) {
  return join(sessionDir(workspace), `${id}.json`);
}
function atomicWrite(path, content) {
  const tmp = `${path}.tmp`;
  writeFileSync(tmp, content);
  renameSync(tmp, path);
}
function buildRepoMap(workspace = process.cwd(), maxFiles = 160) {
  const root = resolve(workspace);
  let gitBranch;
  let gitHead;
  try {
    gitBranch = execFileSync("git", ["rev-parse", "--abbrev-ref", "HEAD"], { cwd: root, encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] }).trim();
    gitHead = execFileSync("git", ["rev-parse", "--short", "HEAD"], { cwd: root, encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] }).trim();
  } catch {
  }
  const files = [];
  const ignored = /* @__PURE__ */ new Set([".git", "node_modules", "dist", ".som-code", ".venv", "__pycache__"]);
  const walk = (dir, prefix = "") => {
    if (files.length >= maxFiles) return;
    let entries = [];
    try {
      entries = readdirSync(dir).sort();
    } catch {
      return;
    }
    for (const entry of entries) {
      if (files.length >= maxFiles || ignored.has(entry)) continue;
      const full = join(dir, entry);
      const rel = prefix ? `${prefix}/${entry}` : entry;
      let st;
      try {
        st = statSync(full);
      } catch {
        continue;
      }
      if (st.isDirectory()) walk(full, rel);
      else if (st.isFile()) files.push(rel);
    }
  };
  walk(root);
  return {
    workspace: root,
    rootName: basename(root),
    gitBranch,
    gitHead,
    files,
    generatedAt: (/* @__PURE__ */ new Date()).toISOString()
  };
}
function createSession(options) {
  const workspace = resolve(options.workspace || process.cwd());
  mkdirSync(sessionDir(workspace), { recursive: true });
  const now = (/* @__PURE__ */ new Date()).toISOString();
  const record = {
    id: createSessionId(`${workspace}-${options.model}-${now}`),
    title: options.title || "New session",
    model: options.model,
    workspace,
    permission: options.permission,
    createdAt: now,
    updatedAt: now,
    messages: [],
    repoMap: buildRepoMap(workspace)
  };
  saveSession(record);
  return record;
}
function saveSession(record) {
  mkdirSync(sessionDir(record.workspace), { recursive: true });
  record.updatedAt = (/* @__PURE__ */ new Date()).toISOString();
  atomicWrite(sessionPath(record.workspace, record.id), `${JSON.stringify(record, null, 2)}
`);
}
function payloadObject(payload) {
  return payload && typeof payload === "object" ? payload : {};
}
function appendSessionMessage(record, message) {
  record.messages.push(message);
  const payload = payloadObject(message.payload);
  if (message.type === "task" && typeof payload.task === "string" && record.title === "New session") {
    record.title = payload.task.slice(0, 80);
  }
  if (message.type === "compact" && typeof payload.summary === "string") {
    record.summary = payload.summary;
  }
  saveSession(record);
  return record;
}
function listSessions(workspace = process.cwd()) {
  const dir = sessionDir(workspace);
  if (!existsSync(dir)) return [];
  return readdirSync(dir).filter((file) => file.endsWith(".json")).map((file) => JSON.parse(readFileSync(join(dir, file), "utf8"))).sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
}
function resolveResumeSession(workspace = process.cwd(), idOrLatest) {
  const sessions = listSessions(workspace);
  if (!sessions.length) return null;
  if (!idOrLatest || idOrLatest === "latest") return sessions[0];
  return sessions.find((s) => s.id.startsWith(idOrLatest) || s.id === idOrLatest) || null;
}

// src/agent/backend.ts
var __dirname = dirname(fileURLToPath(import.meta.url));
function firstExistingPath(candidates) {
  for (const candidate of candidates) {
    if (existsSync2(candidate)) return candidate;
  }
  return candidates[0];
}
function resolveBackendDir() {
  return firstExistingPath([
    // Built package: dist/index.js + dist/backend/server.py
    join2(__dirname, "backend"),
    // Source tree: src/agent/backend.ts + backend/server.py
    join2(__dirname, "..", "..", "backend"),
    // Fallback for unusual launchers from package root.
    join2(process.cwd(), "backend")
  ]);
}
var BACKEND_DIR = resolveBackendDir();
var AgentBackend = class extends EventEmitter {
  process = null;
  pythonPath = "python3";
  ready = false;
  buffer = "";
  msgCounter = 0;
  session = null;
  constructor(pythonPath) {
    super();
    if (pythonPath) this.pythonPath = pythonPath;
  }
  async start(model, workspace, session) {
    if (session) this.session = session;
    const backendScript = join2(BACKEND_DIR, "server.py");
    const args = [
      "-u",
      backendScript,
      "--model",
      model
    ];
    if (workspace) args.push("--workspace", workspace);
    this.process = spawn(this.pythonPath, args, {
      stdio: ["pipe", "pipe", "pipe"],
      env: {
        ...process.env,
        PYTHONUNBUFFERED: "1",
        PYTHONDONTWRITEBYTECODE: "1"
      }
    });
    this.process.on("error", (err) => {
      this.emit("backend_error", err);
    });
    this.process.on("exit", (code) => {
      this.ready = false;
      this.emit("backend_exit", code);
    });
    const rl = createInterface({ input: this.process.stdout });
    rl.on("line", (line) => {
      try {
        const msg = JSON.parse(line);
        if (this.session) appendSessionMessage(this.session, msg);
        this.emit("message", msg);
        switch (msg.type) {
          case "delta":
            this.emit("delta", msg.payload);
            break;
          case "tool_call":
            this.emit("tool_call", msg.payload);
            break;
          case "tool_result":
            this.emit("tool_result", msg.payload);
            break;
          case "thinking":
            this.emit("thinking", msg.payload);
            break;
          case "question":
            this.emit("question", msg.payload);
            break;
          case "done":
            this.emit("done", msg.payload);
            break;
          case "plan_enter":
            this.emit("plan_enter", msg.payload);
            break;
          case "plan_exit":
            this.emit("plan_exit", msg.payload);
            break;
          case "compact":
            this.emit("compact", msg.payload);
            break;
          case "pong":
            this.ready = true;
            this.emit("ready");
            break;
          case "error":
            this.emit("agent_error", msg.error || msg.payload);
            break;
        }
      } catch {
      }
    });
    if (this.process.stderr) {
      this.process.stderr.on("data", (data) => {
        this.emit("stderr", data.toString());
      });
    }
    return new Promise((resolve2, reject) => {
      const timeout = setTimeout(() => {
        reject(new Error("Backend startup timed out after 15s"));
      }, 15e3);
      const onReady = () => {
        clearTimeout(timeout);
        this.off("ready", onReady);
        this.off("backend_error", onError);
        resolve2();
      };
      const onError = (err) => {
        clearTimeout(timeout);
        this.off("ready", onReady);
        this.off("backend_error", onError);
        reject(err);
      };
      this.once("ready", onReady);
      this.once("backend_error", onError);
      this.send({ type: "ping" });
    });
  }
  send(msg) {
    if (!this.process?.stdin?.writable) {
      this.emit("error", new Error("Backend not connected"));
      return;
    }
    const fullMsg = {
      id: String(++this.msgCounter),
      type: msg.type || "task",
      payload: msg.payload,
      timestamp: Date.now(),
      ...msg
    };
    this.process.stdin.write(JSON.stringify(fullMsg) + "\n");
    if (this.session && fullMsg.type !== "ping") appendSessionMessage(this.session, fullMsg);
  }
  sendTask(task2, permission2) {
    this.send({
      type: "task",
      payload: { task: task2, permission: permission2 }
    });
  }
  sendAnswer(answers) {
    this.send({
      type: "answer",
      payload: { answers }
    });
  }
  sendPlanApproval(approved, mode, feedback) {
    this.send({
      type: approved ? "plan_approve" : "plan_refine",
      payload: { mode, feedback }
    });
  }
  cancel() {
    this.send({ type: "cancel" });
  }
  async stop() {
    if (this.process) {
      this.process.stdin?.end();
      this.process.kill("SIGTERM");
      setTimeout(() => {
        if (this.process && !this.process.killed) {
          this.process.kill("SIGKILL");
        }
      }, 5e3);
    }
    this.ready = false;
  }
  isReady() {
    return this.ready;
  }
};

// src/commands/design.ts
function expandSlashCommand(input) {
  const trimmed = input.trim();
  const match = trimmed.match(/^\/design(?:\s+(.*))?$/i);
  if (!match) return input;
  const rest = (match[1] || "").trim();
  const [rawMode, ...argParts] = rest ? rest.split(/\s+/) : ["audit"];
  const mode = rawMode.toLowerCase();
  const args = argParts.join(" ").trim() || ".";
  if (mode === "audit") {
    return [
      "Run the SOM-CODE design harness in AUDIT mode.",
      "",
      `Target: ${args}`,
      "",
      "Required workflow:",
      '1. Use design_audit with the target and purpose="auto".',
      "2. Inspect the generated JSON/Markdown report paths.",
      "3. Summarize purpose classification, top design smells, state coverage, and recommended fixes.",
      "4. Do not edit files in audit mode unless the user explicitly asks for repair.",
      "5. Call task_complete after the audit summary includes report paths."
    ].join("\n");
  }
  if (mode === "repair") {
    return [
      "Run the SOM-CODE design harness in REPAIR mode.",
      "",
      `Target: ${args}`,
      "",
      "Required workflow:",
      '1. Use design_repair_brief with the target and purpose="auto".',
      "2. Read the relevant frontend files before editing.",
      "3. Apply the brief as a contract: purpose-first layout, OKLCH color, semantic spacing, explicit empty/loading/error/success states, and removal of generic AI-design-slop patterns.",
      "4. Run the project build/test command if available.",
      "5. Call task_complete only after reporting changed files and verification evidence."
    ].join("\n");
  }
  return [
    `Unknown /design mode: ${rawMode}`,
    "",
    "Supported modes:",
    "- /design audit [target]",
    "- /design repair [target]",
    "",
    `Original input: ${input}`
  ].join("\n");
}

// src/components/App.tsx
import { jsx as jsx7, jsxs as jsxs7 } from "react/jsx-runtime";
function App({
  model,
  task: task2,
  permission: permission2,
  workspace,
  backend,
  session,
  onExit
}) {
  const { exit } = useApp();
  const [state, setState] = useState5({
    messages: session.messages.length ? [{
      id: `resume-${session.id}`,
      role: "system",
      content: `\u21A9 Resumed session ${session.id} \xB7 ${session.messages.length} protocol events \xB7 ${session.repoMap?.files.length || 0} repo files mapped`
    }] : [],
    currentAssistant: null,
    isStreaming: false,
    isThinking: false,
    thinkingContent: "",
    toolCalls: /* @__PURE__ */ new Map(),
    question: null,
    planMode: false,
    planText: "",
    statusText: "Starting...",
    tokens: { prompt: 0, completion: 0, total: 0 },
    turn: 0
  });
  const stateRef = useRef(state);
  stateRef.current = state;
  const update = (patch) => {
    setState((prev) => ({ ...prev, ...patch }));
  };
  const submitTask = (text) => {
    const userMsg = {
      id: `user-${Date.now()}`,
      role: "user",
      content: text
    };
    const assistantMsg = {
      id: `assistant-${Date.now()}`,
      role: "assistant",
      content: ""
    };
    setState((prev) => ({
      ...prev,
      messages: [...prev.messages, userMsg, assistantMsg],
      currentAssistant: assistantMsg,
      isStreaming: true,
      isThinking: false,
      thinkingContent: "",
      toolCalls: /* @__PURE__ */ new Map(),
      question: null,
      planText: "",
      statusText: "Thinking...",
      turn: prev.turn + 1
    }));
    const expandedText = expandSlashCommand(text);
    backend.sendTask(expandedText, permission2);
  };
  useEffect(() => {
    const onDelta = (payload) => {
      const current = stateRef.current.currentAssistant;
      if (current) {
        current.content += payload.content;
        setState((prev) => ({
          ...prev,
          currentAssistant: { ...current },
          statusText: "Generating..."
        }));
      }
    };
    const onThinking = (payload) => {
      const current = stateRef.current.currentAssistant;
      if (current) {
        current.thinking = (current.thinking || "") + payload.content;
        setState((prev) => ({
          ...prev,
          currentAssistant: { ...current },
          isThinking: true,
          thinkingContent: current.thinking,
          statusText: "Thinking..."
        }));
      }
    };
    const onToolCall = (payload) => {
      const tc = stateRef.current.toolCalls;
      tc.set(payload.id, {
        name: payload.name,
        args: payload.args,
        status: "running"
      });
      setState((prev) => ({
        ...prev,
        toolCalls: new Map(tc),
        statusText: `Running: ${payload.name}`
      }));
    };
    const onToolResult = (payload) => {
      const tc = stateRef.current.toolCalls;
      for (const [id, call] of tc) {
        if (call.name === payload.name && call.status === "running") {
          call.status = payload.success ? "done" : "error";
          call.output = payload.output || payload.error || "";
          break;
        }
      }
      const current = stateRef.current.currentAssistant;
      if (current) {
        current.toolCalls = Array.from(tc.values());
      }
      setState((prev) => ({
        ...prev,
        toolCalls: new Map(tc),
        currentAssistant: current ? { ...current } : null,
        statusText: prev.turn > 0 ? `Turn ${prev.turn}` : "Working..."
      }));
    };
    const onQuestion = (payload) => {
      setState((prev) => ({
        ...prev,
        question: payload,
        statusText: "Question pending..."
      }));
    };
    const onPlanEnter = () => {
      setState((prev) => ({
        ...prev,
        planMode: true,
        statusText: "Plan Mode \u2014 Researching..."
      }));
    };
    const onPlanExit = (payload) => {
      const current = stateRef.current.currentAssistant;
      if (current) {
        current.plan = payload.plan;
      }
      setState((prev) => ({
        ...prev,
        planMode: false,
        planText: payload.plan,
        currentAssistant: current ? { ...current } : null,
        statusText: "Plan ready for approval"
      }));
    };
    const onDone = (payload) => {
      const current = stateRef.current.currentAssistant;
      if (current) {
        current.done = true;
      }
      setState((prev) => ({
        ...prev,
        currentAssistant: current ? { ...current } : null,
        isStreaming: false,
        isThinking: false,
        statusText: payload.success ? "\u2705 Done \xB7 verified" : `\u26A0\uFE0F Finished \xB7 ${payload.finish_reason || "review needed"}`,
        tokens: payload.tokens || prev.tokens
      }));
    };
    const onError = (error) => {
      const current = stateRef.current.currentAssistant;
      if (current) {
        current.content += `

\u274C Error: ${error}`;
      }
      setState((prev) => ({
        ...prev,
        currentAssistant: current ? { ...current } : null,
        isStreaming: false,
        statusText: "Error"
      }));
    };
    const onCompact = (payload) => {
      const info = {
        id: `compact-${Date.now()}`,
        role: "system",
        content: `\u{1F4E6} Context compacted. ${payload.summary || ""}`,
        compact: true
      };
      setState((prev) => ({
        ...prev,
        messages: [...prev.messages, info]
      }));
    };
    backend.on("delta", onDelta);
    backend.on("thinking", onThinking);
    backend.on("tool_call", onToolCall);
    backend.on("tool_result", onToolResult);
    backend.on("question", onQuestion);
    backend.on("plan_enter", onPlanEnter);
    backend.on("plan_exit", onPlanExit);
    backend.on("done", onDone);
    backend.on("agent_error", onError);
    backend.on("compact", onCompact);
    if (task2) {
      setTimeout(() => submitTask(task2), 100);
    }
    return () => {
      backend.off("delta", onDelta);
      backend.off("thinking", onThinking);
      backend.off("tool_call", onToolCall);
      backend.off("tool_result", onToolResult);
      backend.off("question", onQuestion);
      backend.off("plan_enter", onPlanEnter);
      backend.off("plan_exit", onPlanExit);
      backend.off("done", onDone);
      backend.off("agent_error", onError);
      backend.off("compact", onCompact);
    };
  }, []);
  useInput6((input, key) => {
    if (key.escape) {
      if (state.isStreaming) {
        backend.cancel();
      } else {
        onExit();
      }
    }
    if (key.ctrl && input === "c") {
      backend.stop();
      onExit();
    }
  });
  const handleQuestionAnswer = (answers) => {
    backend.sendAnswer(answers);
    setState((prev) => ({
      ...prev,
      question: null,
      statusText: "Resuming..."
    }));
  };
  const handlePlanApprove = (approved, mode, feedback) => {
    backend.sendPlanApproval(approved, mode, feedback);
    setState((prev) => ({
      ...prev,
      planText: "",
      statusText: approved ? "Executing plan..." : "Refining plan..."
    }));
  };
  return /* @__PURE__ */ jsxs7(Box7, { flexDirection: "column", height: "100%", children: [
    /* @__PURE__ */ jsx7(
      StatusBar,
      {
        model,
        turn: state.turn,
        status: state.statusText,
        planMode: state.planMode,
        tokens: state.tokens,
        isStreaming: state.isStreaming
      }
    ),
    /* @__PURE__ */ jsx7(
      MessageList,
      {
        messages: state.messages,
        currentAssistant: state.currentAssistant,
        toolCalls: state.toolCalls,
        isThinking: state.isThinking,
        thinkingContent: state.thinkingContent,
        isStreaming: state.isStreaming,
        planMode: state.planMode,
        planText: state.planText,
        onPlanApprove: handlePlanApprove
      }
    ),
    state.question && /* @__PURE__ */ jsx7(
      AskUserQuestion,
      {
        questions: state.question.questions,
        onAnswer: handleQuestionAnswer
      }
    ),
    !state.question && !state.planText && /* @__PURE__ */ jsx7(
      Prompt,
      {
        onSubmit: submitTask,
        disabled: state.isStreaming,
        placeholder: state.isStreaming ? "Waiting for response... (esc to cancel)" : "Ask SOM-CODE anything...",
        planMode: state.planMode
      }
    )
  ] });
}
async function startTUI(options) {
  const backend = new AgentBackend(options.pythonPath);
  const session = options.session || createSession({
    model: options.model,
    workspace: options.workspace,
    permission: options.permission,
    title: options.task
  });
  try {
    await backend.start(options.model, options.workspace, session);
  } catch (err) {
    console.error("Failed to start agent backend:", err);
    console.error("Make sure python3 is installed and the harness is at ../llm-harness/");
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
    React7.createElement(App, {
      model: options.model,
      task: options.task,
      permission: options.permission,
      workspace: options.workspace,
      backend,
      session,
      onExit
    }),
    { exitOnCtrlC: false }
  );
  await waitUntilExit();
  backend.stop();
}

// src/doctor.ts
import { spawnSync } from "node:child_process";
import { existsSync as existsSync3 } from "node:fs";
import { dirname as dirname2, join as join3 } from "node:path";
import { fileURLToPath as fileURLToPath2 } from "node:url";
var __dirname2 = dirname2(fileURLToPath2(import.meta.url));
function firstExistingPath2(candidates) {
  for (const candidate of candidates) {
    if (existsSync3(candidate)) return candidate;
  }
  return candidates[0];
}
function resolveBackendScript() {
  return firstExistingPath2([
    join3(__dirname2, "backend", "server.py"),
    join3(__dirname2, "..", "backend", "server.py"),
    join3(process.cwd(), "backend", "server.py")
  ]);
}
function ok(label, detail) {
  console.log(`  \u2705 ${label}: ${detail}`);
}
function warn(label, detail) {
  console.log(`  \u26A0\uFE0F  ${label}: ${detail}`);
}
function fail(label, detail) {
  console.log(`  \u274C ${label}: ${detail}`);
}
function commandVersion(cmd, args) {
  const result = spawnSync(cmd, args, { encoding: "utf8" });
  return {
    success: result.status === 0,
    text: (result.stdout || result.stderr || "").trim()
  };
}
function runDoctor() {
  console.log("SOM-CODE doctor");
  console.log("\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500");
  let failures = 0;
  const node = commandVersion(process.execPath, ["--version"]);
  node.success ? ok("Node", node.text) : (fail("Node", "not runnable"), failures++);
  const py = commandVersion("python3", ["--version"]);
  py.success ? ok("Python", py.text) : (fail("Python", "python3 not found"), failures++);
  const backendScript = resolveBackendScript();
  if (existsSync3(backendScript)) {
    ok("Backend script", backendScript);
  } else {
    fail("Backend script", `missing at ${backendScript}`);
    failures++;
  }
  if (py.success && existsSync3(backendScript)) {
    const ping = spawnSync("python3", [backendScript, "--model", "mock"], {
      input: '{"id":"doctor","type":"ping"}\n',
      encoding: "utf8",
      env: { ...process.env, PYTHONUNBUFFERED: "1", PYTHONDONTWRITEBYTECODE: "1" },
      timeout: 1e4
    });
    const combined = `${ping.stdout || ""}${ping.stderr || ""}`;
    if (ping.status === 0 && combined.includes('"type": "pong"')) {
      ok("Backend ping", "mock JSONL server responded");
    } else {
      fail("Backend ping", combined.trim() || `exit ${ping.status}`);
      failures++;
    }
  }
  const providerChecks = [
    ["OpenCode Go key", "OPENCODE_GO_API_KEY"],
    ["OpenCode Go base URL", "OPENCODE_GO_BASE_URL"],
    ["OpenRouter key", "OPENROUTER_API_KEY"],
    ["OpenAI key", "OPENAI_API_KEY"],
    ["Anthropic key", "ANTHROPIC_API_KEY"]
  ];
  for (const [label, envName] of providerChecks) {
    if (process.env[envName]) ok(label, `${envName} set`);
    else warn(label, `${envName} not set`);
  }
  const ollama = spawnSync("curl", ["-fsS", "http://127.0.0.1:11434/api/tags"], {
    encoding: "utf8",
    timeout: 2e3
  });
  if (ollama.status === 0) ok("Ollama", "reachable at 127.0.0.1:11434");
  else warn("Ollama", "not reachable locally");
  if (failures === 0) {
    console.log("\nDoctor result: ready");
    return 0;
  }
  console.log(`
Doctor result: ${failures} failure(s)`);
  return 1;
}

// src/index.ts
var { values, positionals } = parseArgs({
  options: {
    model: { type: "string", short: "m", default: process.env.SOM_MODEL || process.env.OPENROUTER_MODEL || "openrouter/anthropic/claude-sonnet-4" },
    permission: { type: "string", short: "p", default: "default" },
    workspace: { type: "string", short: "w" },
    plan: { type: "boolean" },
    chat: { type: "boolean" },
    exec: { type: "boolean" },
    resume: { type: "string", short: "r" },
    "list-sessions": { type: "boolean" },
    help: { type: "boolean", short: "h" },
    version: { type: "boolean", short: "v" }
  },
  allowPositionals: true
});
if (values.help) {
  console.log(`
SOM-CODE \u2014 Your AI coding agent

Usage:
  som-code                          Interactive TUI
  som-code "Build a REST API"       Start with a task
  som-code --plan "Design auth"     Plan mode
  som-code exec "Write quicksort"   Non-interactive
  som-code --model ollama/qwen2.5:7b
  som-code --resume latest             Resume latest session
  som-code --list-sessions             List saved sessions
  som-code init                     Create SOM.md
  som-code doctor                   Check runtime, backend, and providers
  som-code --help                   This help

Environment:
  SOM_MODEL                Default model
  OPENROUTER_API_KEY       OpenRouter API key
  OPENCODE_GO_API_KEY      OpenCode Go subscription API key
  OPENCODE_GO_BASE_URL     OpenCode Go OpenAI-compatible base URL
  OPENCODE_GO_MODEL        Default model for opencode-go
  OPENAI_API_KEY           OpenAI API key
  ANTHROPIC_API_KEY        Anthropic API key
`);
  process.exit(0);
}
if (positionals[0] === "doctor") {
  process.exit(runDoctor());
}
if (values["list-sessions"] || positionals[0] === "sessions") {
  const sessions = listSessions(values.workspace);
  if (!sessions.length) {
    console.log("No saved sessions found.");
  } else {
    for (const session of sessions) {
      const repo = session.repoMap?.gitBranch ? `${session.repoMap.gitBranch}@${session.repoMap.gitHead || "unknown"}` : session.repoMap?.rootName || "workspace";
      console.log(`${session.id}  ${session.updatedAt}  ${repo}  ${session.title}`);
    }
  }
  process.exit(0);
}
if (values.version) {
  const pkg = JSON.parse(await import("fs").then((fs) => fs.readFileSync(new URL("../package.json", import.meta.url), "utf-8")));
  console.log(`som-code v${pkg.version}`);
  process.exit(0);
}
var commandPositionals = positionals[0] === "exec" || positionals[0] === "init" || positionals[0] === "config" ? positionals.slice(1) : positionals;
var task = commandPositionals.join(" ").trim() || void 0;
var resumedSession = values.resume ? resolveResumeSession(values.workspace, values.resume) : null;
if (values.resume && !resumedSession) {
  console.error(`No saved session found matching '${values.resume}'. Run 'som-code --list-sessions' first.`);
  process.exit(1);
}
var permission = values.plan ? "plan" : values.permission;
console.log(`\u{1F9E0} SOM-CODE \u2014 starting with ${values.model}...`);
if (resumedSession) console.log(`   Resuming session ${resumedSession.id}: ${resumedSession.title}`);
console.log(`   Press Ctrl+C to quit, Esc to cancel`);
await startTUI({
  model: values.model,
  task,
  permission,
  workspace: values.workspace,
  session: resumedSession || void 0
});
//# sourceMappingURL=index.js.map
