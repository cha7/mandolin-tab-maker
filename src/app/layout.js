import "@/vendor/feather-heavy/css/index.css";
import "./globals.css";
import Link from "next/link";
import { ThemeScript, ThemeToggle } from "@/vendor/feather-heavy/react/index.js";
import { Mandolin } from "./Mandolin";

export const metadata = {
  title: "Mandolin Tab Maker",
  description: "Pull the melody out of a YouTube recording and arrange it as a mandolin tab.",
};

// FH_HUE (.env, fixed at build by next.config.mjs) gives the app its own color;
// unset is the design system's forest green.
const hue = process.env.FH_HUE;

// suppressHydrationWarning: ThemeScript sets data-theme on <html> before
// React hydrates (README: Design).
export default function RootLayout({ children }) {
  return (
    <html lang="en" style={hue ? { "--fh-hue": hue } : undefined} suppressHydrationWarning>
      <head>
        <ThemeScript />
      </head>
      <body>
        <header className="fh-masthead">
          <div className="fh-container fh-masthead__inner">
            <Link href="/" className="fh-masthead__brand">
              <Mandolin size={22} />
              Mandolin Tab Maker
            </Link>
            <div className="fh-masthead__actions">
              <ThemeToggle />
            </div>
          </div>
        </header>
        {children}
      </body>
    </html>
  );
}
