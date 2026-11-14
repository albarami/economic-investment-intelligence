/** Same-origin check shared by the early listener and the scan after readiness. */
export function foreignRequest(url, origin) {
  if (url.startsWith('data:') || url.startsWith('blob:')) return '';
  if (url.startsWith('http://') || url.startsWith('https://')) {
    try {
      return new URL(url).origin === origin ? '' : url;
    } catch {
      return url;
    }
  }
  return '';
}

/**
 * Refuse a request only once the page URL is http(s).
 * Before the navigation commits, the page URL is not http, so the address is only recorded.
 */
export function foreignBeforeCommit(url, pageUrl) {
  if (!pageUrl.startsWith('http')) return '';
  try {
    return foreignRequest(url, new URL(pageUrl).origin);
  } catch {
    return '';
  }
}

/** Scan addresses recorded during the load. This is what sees a foreign address from before commit. */
export function refuseForeignAfterReady(seen, origin) {
  for (const url of seen) {
    const foreign = foreignRequest(url, origin);
    if (foreign !== '') {
      throw new Error(`non-same-origin request: ${foreign}`);
    }
  }
}
