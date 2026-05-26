export const theme = {
  bg: '#0b0f14',
  panel: '#111827',
  border: '#2dd4bf',
  borderMuted: '#334155',
  text: '#e5e7eb',
  dim: '#64748b',
  accent: '#7dd3fc',
  violet: '#a78bfa',
  green: '#86efac',
  yellow: '#fde68a',
  red: '#fca5a5',
};

export function shortModel(model: string) {
  const parts = model.split('/');
  return parts.length > 1 ? parts.slice(-2).join('/') : model;
}

export function truncate(value: string, limit = 1200) {
  if (value.length <= limit) return value;
  return `${value.slice(0, limit)}…`;
}
