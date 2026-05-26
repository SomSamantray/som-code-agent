import { spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));

function firstExistingPath(candidates: string[]): string {
  for (const candidate of candidates) {
    if (existsSync(candidate)) return candidate;
  }
  return candidates[0];
}

export function resolvePackageRoot(): string {
  return firstExistingPath([
    // Built: dist/index.js -> package root
    join(__dirname, '..'),
    // Source: src/doctor.ts -> package root
    join(__dirname, '..'),
    process.cwd(),
  ]);
}

export function resolveBackendScript(): string {
  return firstExistingPath([
    join(__dirname, 'backend', 'server.py'),
    join(__dirname, '..', 'backend', 'server.py'),
    join(process.cwd(), 'backend', 'server.py'),
  ]);
}

function ok(label: string, detail: string) {
  console.log(`  ✅ ${label}: ${detail}`);
}

function warn(label: string, detail: string) {
  console.log(`  ⚠️  ${label}: ${detail}`);
}

function fail(label: string, detail: string) {
  console.log(`  ❌ ${label}: ${detail}`);
}

function commandVersion(cmd: string, args: string[]): { success: boolean; text: string } {
  const result = spawnSync(cmd, args, { encoding: 'utf8' });
  return {
    success: result.status === 0,
    text: (result.stdout || result.stderr || '').trim(),
  };
}

export function runDoctor(): number {
  console.log('SOM-CODE doctor');
  console.log('────────────────');

  let failures = 0;

  const node = commandVersion(process.execPath, ['--version']);
  node.success ? ok('Node', node.text) : (fail('Node', 'not runnable'), failures++);

  const py = commandVersion('python3', ['--version']);
  py.success ? ok('Python', py.text) : (fail('Python', 'python3 not found'), failures++);

  const backendScript = resolveBackendScript();
  if (existsSync(backendScript)) {
    ok('Backend script', backendScript);
  } else {
    fail('Backend script', `missing at ${backendScript}`);
    failures++;
  }

  if (py.success && existsSync(backendScript)) {
    const ping = spawnSync('python3', [backendScript, '--model', 'mock'], {
      input: '{"id":"doctor","type":"ping"}\n',
      encoding: 'utf8',
      env: { ...process.env, PYTHONUNBUFFERED: '1', PYTHONDONTWRITEBYTECODE: '1' },
      timeout: 10000,
    });
    const combined = `${ping.stdout || ''}${ping.stderr || ''}`;
    if (ping.status === 0 && combined.includes('"type": "pong"')) {
      ok('Backend ping', 'mock JSONL server responded');
    } else {
      fail('Backend ping', combined.trim() || `exit ${ping.status}`);
      failures++;
    }
  }

  const providerChecks: Array<[string, string]> = [
    ['OpenCode Go key', 'OPENCODE_GO_API_KEY'],
    ['OpenCode Go base URL', 'OPENCODE_GO_BASE_URL'],
    ['OpenRouter key', 'OPENROUTER_API_KEY'],
    ['OpenAI key', 'OPENAI_API_KEY'],
    ['Anthropic key', 'ANTHROPIC_API_KEY'],
  ];

  for (const [label, envName] of providerChecks) {
    if (process.env[envName]) ok(label, `${envName} set`);
    else warn(label, `${envName} not set`);
  }

  const ollama = spawnSync('curl', ['-fsS', 'http://127.0.0.1:11434/api/tags'], {
    encoding: 'utf8',
    timeout: 2000,
  });
  if (ollama.status === 0) ok('Ollama', 'reachable at 127.0.0.1:11434');
  else warn('Ollama', 'not reachable locally');

  if (failures === 0) {
    console.log('\nDoctor result: ready');
    return 0;
  }
  console.log(`\nDoctor result: ${failures} failure(s)`);
  return 1;
}
