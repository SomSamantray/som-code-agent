"""Deterministic design audit tools for SOM-CODE.

These tools intentionally avoid model/vision dependencies. They turn the
"AI design slop" problem into a concrete harness contract: classify the UI
surface, scan source files for common smells, measure state coverage, and write
machine-readable reports that later repair work can follow.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from harness.sandbox import SubprocessSandbox, ToolResult


IGNORED_DIRS = {'.git', 'node_modules', 'dist', 'build', '.next', '.som-code', '__pycache__', '.pytest_cache'}
DESIGN_EXTENSIONS = {'.tsx', '.jsx', '.ts', '.js', '.css', '.scss', '.html', '.vue', '.svelte'}
PURPOSE_KEYWORDS = {
    'Monitor': ('dashboard', 'metric', 'chart', 'status', 'uptime', 'alert', 'analytics', 'observability'),
    'Operate': ('form', 'submit', 'create', 'edit', 'delete', 'settings', 'workflow', 'action', 'button'),
    'Decide': ('compare', 'pricing', 'option', 'recommend', 'approve', 'review', 'decision', 'tradeoff'),
    'Explore': ('search', 'filter', 'browse', 'catalog', 'gallery', 'discover', 'table', 'list'),
}
SMELL_PATTERNS = {
    'centered_stack_default': re.compile(r'(items-center|text-center|justify-center|place-items-center).{0,80}(min-h-screen|h-screen|w-full)', re.I | re.S),
    'indigo_purple_default_palette': re.compile(r'(indigo|purple|violet|from-blue|to-purple|#6366f1|#8b5cf6)', re.I),
    'unearned_blur_glass': re.compile(r'(backdrop-blur|glass|bg-white/10|bg-white/20|blur-3xl|filter:\s*blur)', re.I),
    'generic_card_grid': re.compile(r'(grid-cols-3|grid-cols-4|feature card|rounded-2xl.{0,80}shadow|shadow-xl.{0,80}card)', re.I | re.S),
    'gradient_hero_slop': re.compile(r'(bg-gradient-to|linear-gradient).{0,120}(hero|headline|title|h1)', re.I | re.S),
    'weak_semantic_structure': re.compile(r'<div[^>]*>\s*<(div|span)[^>]*>', re.I),
}
STATE_PATTERNS = {
    'loading': re.compile(r'loading|isLoading|spinner|skeleton|pending', re.I),
    'empty': re.compile(r'empty|no results|no items|nothing found|zero state', re.I),
    'error': re.compile(r'error|failed|try again|catch\s*\(', re.I),
    'success': re.compile(r'success|saved|complete|toast|created|updated', re.I),
    'disabled': re.compile(r'disabled|aria-disabled|isDisabled', re.I),
}
OKLCH_PATTERN = re.compile(r'oklch\(|oklab\(', re.I)
SPACING_PATTERN = re.compile(r'(gap-|space-y-|space-x-|p-|px-|py-|margin|padding)', re.I)


def _root(sandbox: SubprocessSandbox | None) -> Path:
    return Path(sandbox.workspace if sandbox else os.getcwd()).resolve()


def _resolve_target(root: Path, target: str) -> Path:
    candidate = (root / target).resolve() if not Path(target).is_absolute() else Path(target).resolve()
    if not str(candidate).startswith(str(root)):
        raise ValueError(f"Target '{target}' is outside workspace")
    return candidate


def _iter_design_files(path: Path) -> Iterable[Path]:
    if path.is_file():
        if path.suffix in DESIGN_EXTENSIONS:
            yield path
        return
    if not path.exists():
        return
    for current, dirs, names in os.walk(path):
        dirs[:] = [d for d in sorted(dirs) if d not in IGNORED_DIRS and not d.startswith('.')]
        for name in sorted(names):
            p = Path(current) / name
            if p.suffix in DESIGN_EXTENSIONS:
                yield p


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding='utf-8', errors='replace')
    except Exception:
        return ''


def _classify_purpose(text: str, path_names: str, requested: str) -> str:
    if requested and requested.lower() != 'auto':
        return requested
    haystack = f"{path_names}\n{text}".lower()
    scores = {
        purpose: sum(haystack.count(keyword) for keyword in keywords)
        for purpose, keywords in PURPOSE_KEYWORDS.items()
    }
    best, score = max(scores.items(), key=lambda item: item[1])
    return best if score > 0 else 'General'


def _state_coverage(text: str) -> dict:
    present = {name: bool(pattern.search(text)) for name, pattern in STATE_PATTERNS.items()}
    required = ['loading', 'empty', 'error', 'disabled']
    score = round(sum(1 for name in required if present[name]) / len(required), 2)
    return {
        'score': score,
        'present': present,
        'missing_required': [name for name in required if not present[name]],
    }


def _recommendations(purpose: str, smells: dict, state: dict, has_oklch: bool, has_spacing: bool) -> list[str]:
    recs: list[str] = []
    if purpose == 'Monitor':
        recs.append('Use a monitor-first hierarchy: status summary, anomaly focus, trend/context, then actions.')
    elif purpose == 'Operate':
        recs.append('Use an operate-first hierarchy: current state, primary action, constraints, feedback, recovery.')
    elif purpose == 'Decide':
        recs.append('Use a decide-first hierarchy: criteria, tradeoffs, recommendation, evidence, confirmation path.')
    elif purpose == 'Explore':
        recs.append('Use an explore-first hierarchy: query/filter controls, meaningful groupings, result density, progressive detail.')
    else:
        recs.append('Declare the surface purpose before choosing layout; avoid generic centered hero/card-grid defaults.')

    if not has_oklch:
        recs.append('Define color in OKLCH/OKLAB tokens with semantic roles instead of default indigo-purple accents.')
    if not has_spacing:
        recs.append('Add explicit spacing rhythm tokens/gaps so space management is intentional, not incidental.')
    for smell, count in smells.items():
        if count:
            recs.append(f"Address `{smell}` occurrences ({count}) with purpose-specific composition.")
    if state['missing_required']:
        recs.append('Add explicit UI states: ' + ', '.join(state['missing_required']) + '.')
    return recs


def _markdown_report(report: dict) -> str:
    lines = [
        '# SOM-CODE Design Audit',
        '',
        f"- Target: `{report['target']}`",
        f"- Purpose: **{report['purpose']}**",
        f"- Files scanned: {report['files_scanned']}",
        f"- State coverage: {report['state_coverage']['score']}",
        f"- OKLCH/OKLAB present: {report['tokens']['oklch_present']}",
        '',
        '## Design Smells',
    ]
    for name, count in report['smells'].items():
        lines.append(f"- `{name}`: {count}")
    lines.extend(['', '## State Coverage'])
    for name, present in report['state_coverage']['present'].items():
        lines.append(f"- {name}: {'present' if present else 'missing'}")
    lines.extend(['', '## Recommendations'])
    lines.extend(f"- {rec}" for rec in report['recommendations'])
    return '\n'.join(lines) + '\n'


def design_audit(target: str = '.', purpose: str = 'auto', write_report: bool = True, sandbox: SubprocessSandbox | None = None) -> ToolResult:
    """Audit frontend/design files for purpose fit, AI-design-slop smells, OKLCH usage, and UI state coverage.

    Args:
        target: Workspace-relative file or directory to audit.
        purpose: Surface purpose override: auto, Monitor, Operate, Decide, Explore, or General.
        write_report: Whether to write JSON and Markdown reports under .som-code/design/.
    """
    try:
        root = _root(sandbox)
        target_path = _resolve_target(root, target)
        files = list(_iter_design_files(target_path))
        combined_parts = []
        file_summaries = []
        for file_path in files[:120]:
            text = _read_text(file_path)
            rel = str(file_path.relative_to(root))
            combined_parts.append(f"\n/* {rel} */\n{text[:20000]}")
            file_summaries.append({'path': rel, 'bytes_sampled': min(len(text), 20000)})
        combined = '\n'.join(combined_parts)
        path_names = ' '.join(item['path'] for item in file_summaries)
        classified = _classify_purpose(combined, path_names, purpose)
        smells = {name: len(pattern.findall(combined)) for name, pattern in SMELL_PATTERNS.items()}
        state = _state_coverage(combined)
        has_oklch = bool(OKLCH_PATTERN.search(combined))
        has_spacing = bool(SPACING_PATTERN.search(combined))
        report = {
            'schema': 'som-code.design-audit.v1',
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'target': target,
            'purpose': classified,
            'files_scanned': len(files),
            'files': file_summaries,
            'smells': smells,
            'state_coverage': state,
            'tokens': {
                'oklch_present': has_oklch,
                'spacing_rhythm_present': has_spacing,
            },
            'recommendations': _recommendations(classified, smells, state, has_oklch, has_spacing),
        }
        report_paths = {}
        if write_report:
            stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
            report_dir = root / '.som-code' / 'design'
            report_dir.mkdir(parents=True, exist_ok=True)
            json_path = report_dir / f'design-audit-{stamp}.json'
            md_path = report_dir / f'design-audit-{stamp}.md'
            json_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
            md_path.write_text(_markdown_report(report), encoding='utf-8')
            report_paths = {
                'json': str(json_path.relative_to(root)),
                'markdown': str(md_path.relative_to(root)),
            }
            report['report_paths'] = report_paths
            if sandbox:
                sandbox.files_written.update(report_paths.values())
        summary = [
            f"Design audit complete for `{target}`",
            f"Purpose: {classified}",
            f"Files scanned: {len(files)}",
            f"State coverage: {state['score']} (missing: {', '.join(state['missing_required']) or 'none'})",
            'Top smells: ' + ', '.join(f"{k}={v}" for k, v in smells.items() if v) if any(smells.values()) else 'Top smells: none detected by static scan',
        ]
        if report_paths:
            summary.append(f"Reports: {report_paths['json']}, {report_paths['markdown']}")
        return ToolResult(success=True, output='\n'.join(summary), metadata={'design_audit': report})
    except Exception as exc:
        return ToolResult(success=False, error=f'Design audit failed: {exc}')


def design_repair_brief(target: str = '.', purpose: str = 'auto', sandbox: SubprocessSandbox | None = None) -> ToolResult:
    """Create a repair contract from a design audit without directly editing files.

    Args:
        target: Workspace-relative file or directory to inspect.
        purpose: Surface purpose override: auto, Monitor, Operate, Decide, Explore, or General.
    """
    audit = design_audit(target=target, purpose=purpose, write_report=True, sandbox=sandbox)
    if not audit.success:
        return audit
    report = audit.metadata['design_audit']
    brief = [
        '# Design Repair Brief',
        '',
        f"Target: `{target}`",
        f"Purpose contract: **{report['purpose']}**",
        '',
        '## Non-negotiables',
        '- Replace generic centered hero/card-grid composition with a purpose-first information hierarchy.',
        '- Use OKLCH/OKLAB semantic color tokens before adding accents.',
        '- Preserve strong space management: use available space intentionally without crowding.',
        '- Add or verify explicit loading, empty, error, disabled, and success states.',
        '- Prefer semantic regions/components over nested anonymous div stacks.',
        '',
        '## Audit Evidence',
        f"- Files scanned: {report['files_scanned']}",
        f"- State coverage score: {report['state_coverage']['score']}",
        '- Missing required states: ' + (', '.join(report['state_coverage']['missing_required']) or 'none'),
        '- Report JSON: `' + report.get('report_paths', {}).get('json', 'not written') + '`',
        '',
        '## Required Repairs',
    ]
    brief.extend(f"- {rec}" for rec in report['recommendations'])
    return ToolResult(success=True, output='\n'.join(brief), metadata={'design_repair_brief': {'audit': report}})
