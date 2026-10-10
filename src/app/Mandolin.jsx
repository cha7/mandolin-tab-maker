// The app's mark, in place of the design system's Feather (same API): a
// mandolin, neck up and to the right. Draws in currentColor, so it takes the
// color around it (.fh-masthead__brand svg: --fh-accent). Decorative unless
// given a title. src/app/icon.svg is the same drawing.
export function Mandolin({ size = 24, title, ...props }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      role={title ? "img" : undefined}
      aria-hidden={title ? undefined : true}
      {...props}
    >
      {title && <title>{title}</title>}
      <g transform="translate(-0.4 0.9) rotate(45 12 12)">
        <path d="M12 9C15.4 9.6 17 12.6 17 15.4A5 5 0 0 1 7 15.4C7 12.6 8.6 9.6 12 9Z" />
        <circle cx="12" cy="13.6" r="1.7" />
        <path d="M11 17.9H13" />
        <path d="M12 9V5" />
        <path d="M11 5H13L12.7 1.6H11.3Z" />
        <path d="M11.1 2.9H10.1M12.9 2.9H13.9" />
      </g>
    </svg>
  );
}
