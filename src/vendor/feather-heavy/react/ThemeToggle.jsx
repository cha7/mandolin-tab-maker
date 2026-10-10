"use client";

import { useLayoutEffect, useSyncExternalStore } from "react";
import { THEMES, applyTheme, readTheme, saveTheme } from "./theme.js";

const LABELS = { system: "System", light: "Light", dark: "Dark" };
const CHANGE = "fh-theme-change";

function subscribe(onChange) {
  window.addEventListener("storage", onChange); // other tabs
  window.addEventListener(CHANGE, onChange); // this tab
  return () => {
    window.removeEventListener("storage", onChange);
    window.removeEventListener(CHANGE, onChange);
  };
}

// The server can't know the choice, so it renders "system" and React swaps
// in the stored one right after hydrating (no hydration error). The page's
// colors are already right by then: ThemeScript set them before paint.
export function ThemeToggle({ className = "fh-button fh-button--plain fh-button--sm" }) {
  const theme = useSyncExternalStore(subscribe, readTheme, () => "system");
  const next = THEMES[(THEMES.indexOf(theme) + 1) % THEMES.length];

  // In development, Strict Mode's remount clears attributes React doesn't
  // own from <html>; put data-theme back. A no-op in production.
  useLayoutEffect(() => applyTheme(readTheme()), []);

  return (
    <button
      type="button"
      className={className}
      onClick={() => {
        saveTheme(next);
        window.dispatchEvent(new Event(CHANGE));
      }}
      aria-label={`Theme: ${LABELS[theme]}. Switch to ${LABELS[next]}.`}
      title={`Switch to ${LABELS[next]} theme`}
    >
      <ThemeIcon theme={theme} />
      <span>{LABELS[theme]}</span>
    </button>
  );
}

function ThemeIcon({ theme }) {
  const common = {
    width: 16,
    height: 16,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 2,
    strokeLinecap: "round",
    strokeLinejoin: "round",
    "aria-hidden": true,
  };
  if (theme === "light")
    return (
      <svg {...common}>
        <circle cx="12" cy="12" r="4" />
        <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
      </svg>
    );
  if (theme === "dark")
    return (
      <svg {...common}>
        <path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5Z" />
      </svg>
    );
  return (
    <svg {...common}>
      <rect x="3" y="4" width="18" height="12" rx="2" />
      <path d="M8 20h8M12 16v4" />
    </svg>
  );
}
