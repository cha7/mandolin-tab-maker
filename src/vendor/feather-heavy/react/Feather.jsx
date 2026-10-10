// The Feather Heavy mark. A placeholder: swap the paths, keep the API.
// Draws in currentColor, so it takes the color of the text around it (or
// set `color` / a class). Decorative unless given a title.
export function Feather({ size = 24, title, ...props }) {
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
      <path d="M7.5 16.5C6.6 13.6 7 11.6 8.4 9.9L10.6 11.1 10.1 8.2C12.6 5.6 16 4.2 20 4c0 5-1.6 9-5 11.3L12.9 14.6 13.4 16.3C11.4 16.9 9.5 16.9 7.5 16.5Z" />
      <path d="M4 20 16.5 7.5" />
    </svg>
  );
}
