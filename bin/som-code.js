#!/usr/bin/env node
/**
 * SOM-CODE — bin entry point for npm global install.
 * Loads the compiled dist/index.js.
 */

import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const distPath = join(__dirname, '..', 'dist', 'index.js');

// Try to run the compiled version first
try {
  await import(distPath);
} catch (err) {
  // Fallback: try tsx for development
  console.error('Compiled version not found, trying development mode...');
  const child = spawn('npx', ['tsx', join(__dirname, '..', 'src', 'index.ts')], {
    stdio: 'inherit',
    shell: true,
  });
  child.on('exit', (code) => process.exit(code || 0));
}
