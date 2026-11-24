export const ADDRESS_SEARCH_PATH = '/api/address-search';

export function assertRelative(path, text) {
  if (path.includes('://') || path.startsWith('//')) {
    throw new Error('absolute URL');
  }
  if (text !== '' && path.includes(text)) {
    throw new Error('text in URL');
  }
}

export async function postAddressSearch(text, lang, fetchImpl = fetch) {
  const path = ADDRESS_SEARCH_PATH;
  assertRelative(path, text);
  const response = await requestLocal(
    path,
    {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ text, lang }),
    },
    fetchImpl,
  );
  if (response.status === 404) {
    return { state: 'gazetteer_only' };
  }
  return { results: readSearchResults(await response.json()) };
}

export function readSearchResults(payload) {
  const malformed = new Error('address_search_malformed');
  if (typeof payload !== 'object' || payload === null || Array.isArray(payload))
    throw malformed;
  if (Object.keys(payload).join(',') !== 'results') throw malformed;
  if (!Array.isArray(payload.results)) throw malformed;
  for (const item of payload.results) {
    if (typeof item !== 'object' || item === null) throw malformed;
    if (Object.keys(item).sort().join(',') !== 'label,point') throw malformed;
    if (typeof item.label !== 'string' || item.label === '') throw malformed;
    const point = item.point;
    if (typeof point !== 'object' || point === null) throw malformed;
    if (Object.keys(point).sort().join(',') !== 'latitude,longitude')
      throw malformed;
    if (
      !Number.isFinite(point.longitude) ||
      point.longitude < -180 ||
      point.longitude > 180 ||
      !Number.isFinite(point.latitude) ||
      point.latitude < -90 ||
      point.latitude > 90
    )
      throw malformed;
  }
  return payload.results;
}

/** Shared local transport; map availability and tiles use no-store explicitly. */
export function requestLocal(path, options, fetchImpl = fetch) {
  assertRelative(path, '');
  if (!path.startsWith('/api/')) throw new Error('non-local route');
  return fetchImpl(path, options);
}
