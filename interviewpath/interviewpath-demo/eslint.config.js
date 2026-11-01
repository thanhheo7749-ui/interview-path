import js from '@eslint/js';
import globals from 'globals';
import reactHooks from 'eslint-plugin-react-hooks';

export default [
  {
    ignores: [
      'dist',
      'playwright-report',
      'test-results',
      // Kept on disk until Block 5 decides; not used by any route.
      'src/components/MetricCard.jsx',
      'src/components/Toast.jsx',
    ],
  },
  js.configs.recommended,
  {
    files: ['src/**/*.{js,jsx}', 'e2e/**/*.js'],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: { ...globals.browser, ...globals.node },
      parserOptions: { ecmaFeatures: { jsx: true } },
    },
    plugins: { 'react-hooks': reactHooks },
    rules: {
      ...reactHooks.configs.recommended.rules,
      'no-unused-vars': ['error', { varsIgnorePattern: '^[A-Z_]' }],
    },
  },
];
