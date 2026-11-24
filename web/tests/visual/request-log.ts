/**
 * Append-only request log for the drawing harness.
 * The latest body stays on the singular attribute for existing readers.
 * Earlier bodies stay in the list attribute.
 */

export function rememberRequest(
  root: HTMLElement,
  kind: 'areaRequest' | 'shapeRequest',
  body: string,
): void {
  const logKey = kind === 'areaRequest' ? 'areaRequests' : 'shapeRequests';
  const prior = root.dataset[logKey];
  const list = prior ? (JSON.parse(prior) as string[]) : [];
  list.push(body);
  root.dataset[logKey] = JSON.stringify(list);
  root.dataset[kind] = body;
}
