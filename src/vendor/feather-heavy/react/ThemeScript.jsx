import { THEME_STORAGE_KEY } from "./theme.js";

// Put in <head> of the root layout, with <html suppressHydrationWarning>.
// Runs while the HTML is parsed, before first paint, so a saved light/dark
// choice never flashes the OS theme first.
const script = `(function(){try{var t=localStorage.getItem(${JSON.stringify(THEME_STORAGE_KEY)});if(t==="light"||t==="dark")document.documentElement.setAttribute("data-theme",t)}catch(e){}})()`;

export function ThemeScript() {
  return <script dangerouslySetInnerHTML={{ __html: script }} />;
}
