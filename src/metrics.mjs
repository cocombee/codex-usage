// Pure presentation rules. Missing values never become a synthetic zero.
export function weeklyWindow(entries) {
  if (!Array.isArray(entries)) return null;
  for (const entry of entries) {
    // Host adapters select the relevant model bucket before calling this.
    for (const window of [entry?.snapshot?.primary, entry?.snapshot?.secondary]) {
      if (window?.windowDurationMins === 10080 && Number.isFinite(window.usedPercent)) return window;
    }
  }
  return null;
}

export function contextPercent(usage) {
  const capacity = usage?.modelContextWindow;
  const used = usage?.last?.totalTokens;
  return Number.isFinite(capacity) && capacity > 0 && Number.isFinite(used) && used >= 0
    ? Math.min(100, used / capacity * 100) : null;
}

export const clampPercent = n => Math.max(0, Math.min(100, n));
export const remainingPercent = n => Number.isFinite(n) ? 100-clampPercent(n) : null;
export const percentText = n => Number.isFinite(n) ? `${Math.round(n)}%` : '—';

export function resetText(resetsAt, now = Date.now(), compact = false) {
  if (!Number.isFinite(resetsAt)) return '—';
  const seconds = Math.ceil(resetsAt - now / 1000);
  if (seconds <= 0) return 'Updating';
  const minutes = Math.ceil(seconds / 60);
  const days = Math.floor(minutes / 1440);
  const hours = Math.floor(minutes % 1440 / 60);
  return compact ? (days ? `${days}d` : hours ? `${hours}h` : `${minutes}m`)
    : days ? `${days}d ${hours}h` : hours ? `${hours}h` : `${minutes}m`;
}
// Product warning policy: remaining quota, inclusive critical boundary.
export function quotaTone(usedPercent) {
  const remaining = remainingPercent(usedPercent);
  return remaining == null ? 'normal' : remaining <= 10 ? 'low' : remaining <= 20 ? 'warning' : 'normal';
}
