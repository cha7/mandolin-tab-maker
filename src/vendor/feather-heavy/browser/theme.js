// The theme toggle for pages without React (a plain HTML tool page, a
// server-rendered form). Load it as a classic, blocking script in <head>, from
// your own origin so a strict CSP (script-src 'self') allows it:
//
//   <script src="/fh-theme.js"></script>
//
// It applies the saved theme before first paint, and makes every
// <button data-fh-theme-toggle> cycle System → Light → Dark. Same storage
// key and behavior as ThemeScript / ThemeToggle (react/theme.js).
(function () {
  var KEY = "fh-theme";
  var THEMES = ["system", "light", "dark"];
  var LABELS = { system: "System", light: "Light", dark: "Dark" };
  var ICON =
    '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">';
  var ICONS = {
    system: ICON + '<rect x="3" y="4" width="18" height="12" rx="2"/><path d="M8 20h8M12 16v4"/></svg>',
    light:
      ICON +
      '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>',
    dark: ICON + '<path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5Z"/></svg>',
  };

  function read() {
    try {
      var t = localStorage.getItem(KEY);
      return t === "light" || t === "dark" ? t : "system";
    } catch (e) {
      return "system";
    }
  }

  // Kept here too, so the toggle still works for this page when storage is
  // blocked (private mode).
  var current = read();

  function apply() {
    var root = document.documentElement;
    if (current === "system") root.removeAttribute("data-theme");
    else root.setAttribute("data-theme", current);
  }

  function render() {
    var next = THEMES[(THEMES.indexOf(current) + 1) % THEMES.length];
    var buttons = document.querySelectorAll("[data-fh-theme-toggle]");
    for (var i = 0; i < buttons.length; i++) {
      var b = buttons[i];
      b.innerHTML = ICONS[current] + "<span>" + LABELS[current] + "</span>";
      b.setAttribute("aria-label", "Theme: " + LABELS[current] + ". Switch to " + LABELS[next] + ".");
      b.title = "Switch to " + LABELS[next] + " theme";
    }
  }

  function set(theme) {
    current = theme;
    try {
      if (theme === "system") localStorage.removeItem(KEY);
      else localStorage.setItem(KEY, theme);
    } catch (e) {
      // Storage blocked: the choice lasts for this page only.
    }
    apply();
    render();
  }

  apply();

  document.addEventListener("click", function (e) {
    var b = e.target.closest && e.target.closest("[data-fh-theme-toggle]");
    if (b) set(THEMES[(THEMES.indexOf(current) + 1) % THEMES.length]);
  });

  // A choice made in another tab.
  window.addEventListener("storage", function (e) {
    if (e.key !== KEY) return;
    current = read();
    apply();
    render();
  });

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", render);
  else render();
})();
