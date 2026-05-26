export function expandSlashCommand(input: string): string {
  const trimmed = input.trim();
  const match = trimmed.match(/^\/design(?:\s+(.*))?$/i);
  if (!match) return input;

  const rest = (match[1] || '').trim();
  const [rawMode, ...argParts] = rest ? rest.split(/\s+/) : ['audit'];
  const mode = rawMode.toLowerCase();
  const args = argParts.join(' ').trim() || '.';

  if (mode === 'audit') {
    return [
      'Run the SOM-CODE design harness in AUDIT mode.',
      '',
      `Target: ${args}`,
      '',
      'Required workflow:',
      '1. Use design_audit with the target and purpose="auto".',
      '2. Inspect the generated JSON/Markdown report paths.',
      '3. Summarize purpose classification, top design smells, state coverage, and recommended fixes.',
      '4. Do not edit files in audit mode unless the user explicitly asks for repair.',
      '5. Call task_complete after the audit summary includes report paths.',
    ].join('\n');
  }

  if (mode === 'repair') {
    return [
      'Run the SOM-CODE design harness in REPAIR mode.',
      '',
      `Target: ${args}`,
      '',
      'Required workflow:',
      '1. Use design_repair_brief with the target and purpose="auto".',
      '2. Read the relevant frontend files before editing.',
      '3. Apply the brief as a contract: purpose-first layout, OKLCH color, semantic spacing, explicit empty/loading/error/success states, and removal of generic AI-design-slop patterns.',
      '4. Run the project build/test command if available.',
      '5. Call task_complete only after reporting changed files and verification evidence.',
    ].join('\n');
  }

  return [
    `Unknown /design mode: ${rawMode}`,
    '',
    'Supported modes:',
    '- /design audit [target]',
    '- /design repair [target]',
    '',
    `Original input: ${input}`,
  ].join('\n');
}
