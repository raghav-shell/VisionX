/** @type {import('next').NextConfig} */
const apiOrigin = (process.env.VISIONX_API_ORIGIN ?? "http://127.0.0.1:8000").replace(/\/$/, "");

const nextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${apiOrigin}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
