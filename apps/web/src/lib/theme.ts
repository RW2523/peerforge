/**
 * Reading and following the active theme from code.
 *
 * The theme lives on the root element as data-theme, set before paint so
 * there is no flash. Components that render their own colours — canvases,
 * diagrams, anything not styled by CSS — need to read it rather than assume.
 */
export type Theme = 'light' | 'dark';

export function currentTheme(): Theme {
  if (typeof document === 'undefined') return 'light';
  const attr = document.documentElement.getAttribute('data-theme');
  if (attr === 'dark' || attr === 'light') return attr;
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

/**
 * Call back whenever the theme changes, and return an unsubscribe.
 *
 * Watches the attribute rather than only the media query, because the in-app
 * toggle changes the attribute without the OS preference moving.
 */
export function onThemeChange(handler: (theme: Theme) => void): () => void {
  if (typeof document === 'undefined') return () => {};

  const observer = new MutationObserver(() => handler(currentTheme()));
  observer.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ['data-theme'],
  });

  const media = window.matchMedia?.('(prefers-color-scheme: dark)');
  const onMedia = () => handler(currentTheme());
  media?.addEventListener?.('change', onMedia);

  return () => {
    observer.disconnect();
    media?.removeEventListener?.('change', onMedia);
  };
}
