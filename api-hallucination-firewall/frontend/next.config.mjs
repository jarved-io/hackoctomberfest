/** @type {import('next').NextConfig} */
// The browser only ever calls same-origin /api/*; Next proxies it to the FastAPI backend.
const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";

const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${BACKEND_URL}/api/:path*` }];
  },
};
export default nextConfig;
