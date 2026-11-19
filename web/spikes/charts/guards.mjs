const fixtures = new Set(['hourly', 'comparison', 'range']);
export function validateInput(input, render) {
  if (
    !input ||
    Object.keys(input).sort().join(',') !== 'fixture,selection' ||
    !fixtures.has(input.fixture) ||
    !['first', 'second'].includes(input.selection)
  )
    throw Error('closed-input');
  return render(input);
}
// This validates a proposed view descriptor only. It does not certify a DOM or a Fact chip.
export function validateView(view) {
  if (!Array.isArray(view.table) || !view.table.length)
    throw Error('missing-table');
  if (typeof view.description !== 'string' || !view.description.trim())
    throw Error('missing-description');
  if (JSON.stringify(view.table) !== JSON.stringify(view.marks))
    throw Error('fact-equality');
  if (/[0-9]/u.test(view.text)) throw Error('numeral-outside-chip');
  if (/[\u0660-\u0669]/u.test(view.digits)) throw Error('arabic-indic');
  if (/[\u06f0-\u06f9]/u.test(view.digits))
    throw Error('extended-arabic-indic');
  if (!/^[0-9]+$/.test(view.digits) || view.digits !== view.arabicDigits)
    throw Error('parity');
  if (view.lineage !== true) throw Error('lineage');
  if (view.texture !== 'series') throw Error('origin-texture');
}
export function isolated(graph) {
  const pending = Object.keys(graph).filter((key) => key.startsWith('src/'));
  const seen = new Set();
  while (pending.length) {
    const key = pending.pop();
    if (seen.has(key)) continue;
    seen.add(key);
    if (key.startsWith('spikes/')) return false;
    pending.push(...(graph[key] ?? []));
  }
  return true;
}
