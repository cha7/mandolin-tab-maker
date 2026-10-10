// The visitor's theme choice lives in localStorage, never a cookie: a cookie
// would have to be in CloudFront's cache key, and every page would be cached
// once per theme. No stored value means "follow the OS".
export const THEME_STORAGE_KEY = "fh-theme";
export const THEMES = ["system", "light", "dark"];

export function readTheme() {
  try {
    const t = localStorage.getItem(THEME_STORAGE_KEY);
    return t === "light" || t === "dark" ? t : "system";
  } catch {
    return "system";
  }
}

export function applyTheme(theme) {
  const root = document.documentElement;
  if (theme === "light" || theme === "dark") root.setAttribute("data-theme", theme);
  else root.removeAttribute("data-theme");
}

export function saveTheme(theme) {
  try {
    if (theme === "system") localStorage.removeItem(THEME_STORAGE_KEY);
    else localStorage.setItem(THEME_STORAGE_KEY, theme);
  } catch {
    // Storage blocked (private mode): the choice lasts for this page only.
  }
  applyTheme(theme);
}
