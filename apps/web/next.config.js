/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: 'standalone',
  webpack(config) {
    // @popperjs/core v2.11 ships lib/index.js as ESM entry (module field) but
    // the lib/ sub-files reference missing dom-utils/utils dirs; force webpack
    // to resolve the bundled CJS build instead.
    config.resolve.alias = {
      ...config.resolve.alias,
      '@popperjs/core': require.resolve('@popperjs/core/dist/cjs/popper.js'),
    };
    return config;
  },
}

module.exports = nextConfig
