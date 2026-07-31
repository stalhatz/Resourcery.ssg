// vitest.config.js
import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'jsdom',
    environmentOptions: {
      jsdom: {
        // jsdom's default document URL is about:blank, which blocks
        // history.pushState to http://localhost/... URLs. Seed the origin
        // so the setup-file reset (pushState to http://localhost/) and the
        // per-test loadFresh({ url: 'http://localhost/browse.html' }) work.
        url: 'http://localhost/',
      },
    },
    globals: true,
    setupFiles: ['./tests/js/helpers/setup.js'],
    // Top-level include makes `npm test` (vitest run) deterministic: it picks
    // up exactly the JS suite under tests/js/. (The `projects` split below is
    // kept for structural intent / future Vitest that supports `test.projects`
    // as an inline array; Vitest 2.1.x discovers the unit/integration split
    // via the path-filter scripts test:unit / test:integration instead — the
    // plan's sanctioned fallback when `--project` is unavailable.)
    include: ['tests/js/**/*.test.js'],
    projects: [
      { test: { name: 'unit',        include: ['tests/js/unit/**/*.test.js'] } },
      { test: { name: 'integration', include: ['tests/js/integration/**/*.test.js'] } },
    ],
    alias: [
      {
        // state.js imports '../vendor/nanostores.js' (gitignored on a fresh
        // clone). Resolve any such import to the real package in node_modules.
        find: /^.*\/vendor\/nanostores\.js$/,
        replacement: 'nanostores', // bare specifier → node_modules via package exports
      },
    ],
  },
});