#!/usr/bin/env node
/**
 * Build script — bundles TypeScript with esbuild and copies backend.
 */

import * as esbuild from 'esbuild';
import { cp, mkdir, rm } from 'node:fs/promises';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const rootDir = join(__dirname, '..');

async function main() {
  console.log('Building SOM-CODE...');

  // Start from a clean build directory so stale Python caches or removed files
  // cannot leak into the published npm artifact.
  await rm(join(rootDir, 'dist'), { recursive: true, force: true });
  await mkdir(join(rootDir, 'dist'), { recursive: true });

  // Bundle TypeScript → ESM
  await esbuild.build({
    entryPoints: [join(rootDir, 'src', 'index.ts')],
    bundle: true,
    platform: 'node',
    target: 'node18',
    format: 'esm',
    outfile: join(rootDir, 'dist', 'index.js'),
    external: [
      'react',
      'ink',
      'node:child_process',
      'node:readline',
      'node:events',
      'node:url',
      'node:path',
      'node:fs',
      'node:fs/promises',
      'node:util',
    ],
    banner: {
      js: 'import { createRequire } from "node:module"; const require = createRequire(import.meta.url);',
    },
    sourcemap: true,
    minify: false,
  });

  // Copy the self-contained backend Python package. The backend directory now
  // contains its harness/som runtime dependencies, so installed packages do not
  // depend on a sibling ../llm-harness checkout.
  await mkdir(join(rootDir, 'dist', 'backend'), { recursive: true });
  await cp(
    join(rootDir, 'backend'),
    join(rootDir, 'dist', 'backend'),
    {
      recursive: true,
      filter: (src) => !src.includes('__pycache__') && !src.endsWith('.pyc') && !src.includes('.pytest_cache'),
    }
  );

  console.log('✅ Build complete — dist/index.js + dist/backend/ ready');
}

main().catch(err => {
  console.error('Build failed:', err);
  process.exit(1);
});
