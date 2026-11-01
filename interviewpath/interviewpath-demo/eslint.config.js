import js from '@eslint/js';
import globals from 'globals';
import reactHooks from 'eslint-plugin-react-hooks';

export default [
  {
    ignores: [
      'dist',
      'playwright-report',
      'test-results',
      // Kept on disk until Blocks 2 and 3 connect them; not in any route.
      'src/routes/WorkflowPage.jsx',
      'src/components/CandidateCard.jsx',
      'src/components/CandidateDetailPanel.jsx',
      'src/components/MetricCard.jsx',
      'src/components/Toast.jsx',
      'src/data/**',
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
