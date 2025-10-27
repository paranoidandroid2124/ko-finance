/** @type {import('next').NextConfig} */
const API_PROXY_TARGET = process.env.API_PROXY_TARGET;

const nextConfig = {
  experimental: {
    typedRoutes: true
  },
  webpack: (config) => {
    config.resolve = config.resolve || {};
    config.resolve.alias = {
      ...config.resolve.alias,
      canvas: false
    };
    config.resolve.fallback = {
      ...config.resolve.fallback,
      canvas: false
    };
    return config;
  },
  async rewrites() {
    if (!API_PROXY_TARGET) {
      return [];
    }
    const sanitized = API_PROXY_TARGET.replace(/\/$/, "");
    return [
      {
        source: "/api/v1/:path*",
        destination: `${sanitized}/api/v1/:path*`
      }
    ];
  }
};

module.exports = nextConfig;
