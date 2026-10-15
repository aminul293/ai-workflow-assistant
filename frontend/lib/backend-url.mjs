/**
 * The dashboard uses /api/proxy/api/..., so the catch-all path already
 * contains "api". Never prepend a second /api segment.
 * @param {string} base Server-controlled backend origin, not a user URL.
 * @param {string[]} path Next.js catch-all route segments.
 * @returns {string}
 */
export function buildBackendUrl(base, path) {
  if (!Array.isArray(path) || path.length < 2 || path[0] !== 'api' ||
      path.some(part => typeof part !== 'string' || !/^[-_a-zA-Z0-9]+$/.test(part))) {
    throw new Error('Invalid API path');
  }
  const origin = new URL(base);
  if (!['http:', 'https:'].includes(origin.protocol) || origin.username ||
      origin.password || origin.search || origin.hash || origin.pathname !== '/') {
    throw new Error('BACKEND_URL must be an HTTP(S) origin');
  }
  return origin.origin + '/' + path.join('/');
}
