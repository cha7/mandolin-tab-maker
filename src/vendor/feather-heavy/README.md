# Feather Heavy design system

A small design system for the cha7 Next.js apps: forest-green tokens, light and
dark mode, element defaults, and a handful of components for technical pages
(tables, labels, alerts, forms). Modeled on [PatternFly](https://www.patternfly.org/)'s
ideas (two tiers of tokens, `--fh-` prefix, status colors, block--modifier
classes), not its code. Plain CSS plus three small React components; no build
step.

Primary consumer: [`feather-heavy-nextjs`](https://github.com/cha7/feather-heavy-nextjs).
Every page and component is on `/examples/design` there.

## Install

From GitHub Packages, like `@cha7/terraform_core` (the app's `.npmrc` has
`@cha7:registry=https://npm.pkg.github.com`; your user `~/.npmrc` has the token):

```bash
npm install @cha7/feather-heavy-design-system
```

`next.config.mjs` - the components ship as JSX:

```js
transpilePackages: ["@cha7/feather-heavy-design-system"],
```

Root layout:

```jsx
import "@cha7/feather-heavy-design-system/css";
import { Feather, ThemeScript, ThemeToggle } from "@cha7/feather-heavy-design-system";

export default function RootLayout({ children }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <ThemeScript />
      </head>
      <body>{children}</body>
    </html>
  );
}
```

Favicon: copy `assets/icon.svg` to `src/app/icon.svg` (Next picks it up).

## Light and dark

Every color token is `light-dark(<light>, <dark>)`, so it follows the page's
`color-scheme`:

- No `data-theme` on `<html>`: follows the OS.
- `<html data-theme="light">` or `"dark"`: pinned.

`ThemeToggle` cycles System → Light → Dark and saves the choice in
`localStorage` (`fh-theme`); `ThemeScript` applies it before first paint.
Never a cookie: CloudFront would have to cache every page once per theme.

**Pages without React** (a plain HTML tool page): serve `browser/theme.js`
(`@cha7/feather-heavy-design-system/theme.js`) from your own origin and load
it as a blocking script in `<head>`. It does what ThemeScript does, and turns
every `<button data-fh-theme-toggle>` into the same toggle, same storage key:

```html
<script src="/fh-theme.js"></script>
...
<button type="button" data-fh-theme-toggle></button>
```

Don't set `color-scheme` yourself on an element, or its tokens follow that
instead.

## Tokens

Use roles, never the palette (`--fh-green-*`, `--fh-gray-*`) or hex values.

| Token | For | Light | Dark |
|---|---|---|---|
| `--fh-bg` | page background | `#f6f8f6` | `#0b130e` |
| `--fh-surface` | cards, inputs, masthead | `#ffffff` | `#111b15` |
| `--fh-surface-muted` | hover rows, code, wells | `#eef3ef` | `#17241c` |
| `--fh-line` | borders, dividers | `#d9e2db` | `#24342a` |
| `--fh-line-strong` | stronger dividers | `#bccac0` | `#3a473f` |
| `--fh-field-border` | input borders (3:1) | `#6b7c71` | `#6b7c71` |
| `--fh-text` | body text | `#13201a` | `#e2ebe5` |
| `--fh-text-muted` | secondary text | `#56655c` | `#93a69a` |
| `--fh-accent` | links, primary buttons | `#2a6342` | `#7fb894` |
| `--fh-accent-hover` | their hover | `#214f35` | `#b0d3bc` |
| `--fh-accent-soft` | accent tint | `#eef5f0` | green 12% |
| `--fh-on-accent` | text on accent | `#ffffff` | `#0b130e` |
| `--fh-focus` | focus ring | = accent | = accent |
| `--fh-success` / `-soft` | ok | `#3a7a26` | `#8fd07a` |
| `--fh-warning` / `-soft` | caution | `#8f5400` | `#f0b44c` |
| `--fh-danger` / `-soft` | error, destructive | `#b42318` | `#f2877d` |
| `--fh-info` / `-soft` | neutral notice | `#2b5f8a` | `#8fb8de` |

All text colors are at least 4.5:1 (WCAG AA) on `bg`, `surface` and
`surface-muted` in both modes.

Also: `--fh-font-sans|mono`, `--fh-text-xs…2xl`, `--fh-space-1…12` (4px
scale), `--fh-radius-sm|md|lg|pill`, `--fh-shadow-sm|md`, `--fh-duration`.

## Components

Classes on plain HTML, `fh-block fh-block--modifier`:

| Class | Parts / modifiers |
|---|---|
| `.fh-masthead` | `__inner` (with `.fh-container`), `__brand`, `__nav` (`aria-current="page"`), `__actions` |
| `.fh-button` | `--primary` `--secondary` `--plain` `--danger`, `--sm` |
| `.fh-card` | `__header` `__title` `__body` `__footer` |
| `.fh-alert` | `--success` `--warning` `--danger` (info by default); `__title` |
| `.fh-label` | `--accent` `--success` `--warning` `--danger` `--info` |
| `.fh-table` | `--compact`; `.fh-num` on number cells; wrap in `.fh-table-scroll` |
| `.fh-field` | `label`, `.fh-input` / `.fh-select` / `.fh-textarea`, `__help`, `__error`; `aria-invalid="true"` |
| `.fh-toolbar` | `__spacer` |
| Layout | `.fh-container`, `.fh-stack`, `.fh-cluster` (`--fh-gap`), `.fh-muted`, `.fh-mono`, `.fh-visually-hidden` |

React: `<Feather size title />`, `<ThemeScript />`, `<ThemeToggle className />`.
Plain pages: `browser/theme.js` and `<button data-fh-theme-toggle>`.

## Tailwind v4 apps

```css
@import "tailwindcss";
@import "@cha7/feather-heavy-design-system/tailwind.css";
```

Gives `bg-fh-surface`, `text-fh-muted`, `border-fh-line`, `text-fh-accent`,
`bg-fh-danger-soft`, `rounded-fh-md`, `shadow-fh-sm`, ... - they switch with
the theme on their own, no `dark:` variants. Add `css/base.css` /
`css/components.css` too if you want the element defaults and `.fh-*` classes.

## Moving an existing app over

Most apps already keep colors in their own custom properties. Point those at
the roles and delete the app's dark-mode block:

```css
:root {
  --bg: var(--fh-bg);
  --surface: var(--fh-surface);
  --line: var(--fh-line);
  --text: var(--fh-text);
  --text-muted: var(--fh-text-muted);
  --accent: var(--fh-accent);
  --positive: var(--fh-success);
  --negative: var(--fh-danger);
}
/* @media (prefers-color-scheme: dark) { ... }  <- delete */
```

Then add `ThemeScript` / `ThemeToggle` to the layout, remove any
`color-scheme: light` the app sets, and look at every page in both modes.

## Releasing

Bump `version` in `package.json`, commit, then `git tag vX.Y.Z && git push
origin vX.Y.Z`. `.github/workflows/publish.yml` runs `npm test` and publishes.
Apps update with `npm run ui:update`.
