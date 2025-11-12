const path = require("path");

const nextConfig = {
  experimental: {
    externalDir: true,
  },
  webpack: (config) => {
    config.resolve.alias["@"] = path.resolve(__dirname, "../dashboard/src");
    return config;
  },
};

module.exports = nextConfig;
