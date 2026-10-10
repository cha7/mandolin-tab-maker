/** @type {import('next').NextConfig} */
const nextConfig = {
  // Pin the project root: if a parent folder has a lockfile, Next would
  // treat it as the workspace root.
  turbopack: {
    root: import.meta.dirname,
  },
};

export default nextConfig;
