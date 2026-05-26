/**
 * Agent Backend — spawns the Python harness as a child process
 * and communicates via JSONL protocol over stdio.
 */

import { spawn, ChildProcess } from 'node:child_process';
import { createInterface } from 'node:readline';
import { EventEmitter } from 'node:events';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { existsSync } from 'node:fs';
import type { ProtocolMessage } from '../protocol/types.js';
import { appendSessionMessage, type SessionRecord } from '../session/store.js';

const __dirname = dirname(fileURLToPath(import.meta.url));

function firstExistingPath(candidates: string[]): string {
  for (const candidate of candidates) {
    if (existsSync(candidate)) return candidate;
  }
  return candidates[0];
}

function resolveBackendDir(): string {
  return firstExistingPath([
    // Built package: dist/index.js + dist/backend/server.py
    join(__dirname, 'backend'),
    // Source tree: src/agent/backend.ts + backend/server.py
    join(__dirname, '..', '..', 'backend'),
    // Fallback for unusual launchers from package root.
    join(process.cwd(), 'backend'),
  ]);
}

const BACKEND_DIR = resolveBackendDir();

export class AgentBackend extends EventEmitter {
  private process: ChildProcess | null = null;
  private pythonPath: string = 'python3';
  private ready: boolean = false;
  private buffer: string = '';
  private msgCounter: number = 0;
  private session: SessionRecord | null = null;

  constructor(pythonPath?: string) {
    super();
    if (pythonPath) this.pythonPath = pythonPath;
  }

  async start(model: string, workspace?: string, session?: SessionRecord): Promise<void> {
    if (session) this.session = session;
    const backendScript = join(BACKEND_DIR, 'server.py');
    
    const args = [
      '-u', backendScript,
      '--model', model,
    ];
    if (workspace) args.push('--workspace', workspace);

    this.process = spawn(this.pythonPath, args, {
      stdio: ['pipe', 'pipe', 'pipe'],
      env: {
        ...process.env,
        PYTHONUNBUFFERED: '1',
        PYTHONDONTWRITEBYTECODE: '1',
      },
    });

    this.process.on('error', (err) => {
      this.emit('backend_error', err);
    });

    this.process.on('exit', (code) => {
      this.ready = false;
      this.emit('backend_exit', code);
    });

    // Parse stdout as JSONL
    const rl = createInterface({ input: this.process.stdout! });
    rl.on('line', (line: string) => {
      try {
        const msg: ProtocolMessage = JSON.parse(line);
        if (this.session) appendSessionMessage(this.session, msg);
        this.emit('message', msg);
        
        // Route specific message types
        switch (msg.type) {
          case 'delta':
            this.emit('delta', msg.payload);
            break;
          case 'tool_call':
            this.emit('tool_call', msg.payload);
            break;
          case 'tool_result':
            this.emit('tool_result', msg.payload);
            break;
          case 'thinking':
            this.emit('thinking', msg.payload);
            break;
          case 'question':
            this.emit('question', msg.payload);
            break;
          case 'done':
            this.emit('done', msg.payload);
            break;
          case 'plan_enter':
            this.emit('plan_enter', msg.payload);
            break;
          case 'plan_exit':
            this.emit('plan_exit', msg.payload);
            break;
          case 'compact':
            this.emit('compact', msg.payload);
            break;
          case 'pong':
            this.ready = true;
            this.emit('ready');
            break;
          case 'error':
            this.emit('agent_error', msg.error || msg.payload);
            break;
        }
      } catch {
        // Non-JSON output (debug logs, etc.) — ignore
      }
    });

    // Stderr for debug
    if (this.process.stderr) {
      this.process.stderr.on('data', (data: Buffer) => {
        this.emit('stderr', data.toString());
      });
    }

    // Wait for backend to be ready
    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        reject(new Error('Backend startup timed out after 15s'));
      }, 15000);

      const onReady = () => {
        clearTimeout(timeout);
        this.off('ready', onReady);
        this.off('backend_error', onError);
        resolve();
      };
      const onError = (err: Error) => {
        clearTimeout(timeout);
        this.off('ready', onReady);
        this.off('backend_error', onError);
        reject(err);
      };

      this.once('ready', onReady);
      this.once('backend_error', onError);

      // Send ping
      this.send({ type: 'ping' });
    });
  }

  send(msg: Partial<ProtocolMessage>): void {
    if (!this.process?.stdin?.writable) {
      this.emit('error', new Error('Backend not connected'));
      return;
    }
    const fullMsg: ProtocolMessage = {
      id: String(++this.msgCounter),
      type: msg.type || 'task',
      payload: msg.payload,
      timestamp: Date.now(),
      ...msg,
    };
    this.process.stdin.write(JSON.stringify(fullMsg) + '\n');
    if (this.session && fullMsg.type !== 'ping') appendSessionMessage(this.session, fullMsg);
  }

  sendTask(task: string, permission?: string): void {
    this.send({
      type: 'task',
      payload: { task, permission },
    });
  }

  sendAnswer(answers: Record<string, string | string[]>): void {
    this.send({
      type: 'answer',
      payload: { answers },
    });
  }

  sendPlanApproval(approved: boolean, mode?: string, feedback?: string): void {
    this.send({
      type: approved ? 'plan_approve' : 'plan_refine',
      payload: { mode, feedback },
    });
  }

  cancel(): void {
    this.send({ type: 'cancel' });
  }

  async stop(): Promise<void> {
    if (this.process) {
      this.process.stdin?.end();
      this.process.kill('SIGTERM');
      // Force kill after 5s
      setTimeout(() => {
        if (this.process && !this.process.killed) {
          this.process.kill('SIGKILL');
        }
      }, 5000);
    }
    this.ready = false;
  }

  isReady(): boolean {
    return this.ready;
  }
}
