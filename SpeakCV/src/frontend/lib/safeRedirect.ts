/** Returns a path on this site to go to after login, or the fallback if `redirect` could lead anywhere else. */
export function safeRedirect(
  redirect: string | null | undefined,
  fallback: string,
  origin: string = window.location.origin,
): string {
  if (!redirect) return fallback;
  try {
    // The URL parser sees what the browser will see: it drops tabs and newlines and reads "\" as "/".
    const url = new URL(redirect, origin);
    if (url.origin !== origin) return fallback;
    // "/.//host" stays on this origin here but normalises to "//host", which leaves it when navigated to.
    if (url.pathname.startsWith("//")) return fallback;
    return url.pathname + url.search + url.hash;
  } catch {
    return fallback;
  }
}
