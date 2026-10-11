"use client";

import { THEME_STORAGE_KEY } from "./theme.js";

// Put in <head> of the root layout, with <html suppressHydrationWarning>.
// Runs while the HTML is parsed, before first paint, so a saved light/dark
// choice never flashes the OS theme first.
const script = `(function(){try{var t=localStorage.getItem(${JSON.stringify(THEME_STORAGE_KEY)});if(t==="light"||t==="dark")document.documentElement.setAttribute("data-theme",t)}catch(e){}})()`;

// Only the server-rendered copy runs. When React creates the tag in the
// browser instead (a client render: Fast Refresh, recovering from a
// hydration error) it would never run anyway, and React warns about an
// executable <script>; text/plain marks that copy as data. A client
// component so the browser render sees `window`.
export function ThemeScript() {
  const type = typeof window === "undefined" ? undefined : "text/plain";
  return <script type={type} suppressHydrationWarning dangerouslySetInnerHTML={{ __html: script }} />;
}
