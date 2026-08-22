/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Enables the minimal, self-contained server.js build that
  // frontend/Dockerfile copies out of the build stage — standard
  // Next.js Docker deployment pattern, avoids shipping the full
  // node_modules tree into the runtime image.
  output: "standalone",
};

export default nextConfig;
