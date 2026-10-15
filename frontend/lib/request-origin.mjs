/**
 * Compare the browser Origin with an explicitly configured public app origin.
 * Do not infer it from forwarded headers or Next.js' internal request URL.
 * @param {string|null} origin Request Origin header.
 * @param {string|undefined} configuredOrigin Server-owned APP_ORIGIN.
 */
export function isAllowedOrigin(origin, configuredOrigin) {
  if (!origin || !configuredOrigin) return false;
  try {
    const expected = new URL(configuredOrigin);
    const supplied = new URL(origin);
    if (!['http:', 'https:'].includes(expected.protocol) || expected.username ||
        expected.password || expected.search || expected.hash || expected.pathname !== '/') return false;
    return origin === supplied.origin && supplied.origin === expected.origin;
  } catch {
    return false;
  }
}
