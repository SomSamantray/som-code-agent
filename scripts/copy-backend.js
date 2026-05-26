#!/usr/bin/env node
/**
 * Build script — copies Python backend files into dist/ for npm packaging.
 */

import { cp, mkdir } from 'node:fs/promises';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const rootDir = join(__dirname, '..');

async function main() {
  // Copy backend Python files
  await mkdir(join(rootDir, 'dist', 'backend'), { recursive: true });
  await cp(
    join(rootDir, 'backend'),
    join(rootDir, 'dist', 'backend'),
    { recursive: true }
  );
  
  // Copy the harness (for development; in production this would be bundled)
  const harnessDir = join(rootDir, '..', 'llm-harness');
  try {
    await cp(
      harnessDir,
      join(rootDir, 'dist', 'llm-harness'),
      { recursive: true, filter: (src) => !src.includes('__pycache__') && !src.includes('.pyc') }
    );
  } catch {
    console.log('Note: llm-harness not found at ../llm-harness. Backend will need it on PYTHONPATH.');
  }

  console.log('✅ Build complete — backend files copied to dist/');
}

main().catch(console.error);
