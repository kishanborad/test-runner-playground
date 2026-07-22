import type { Config } from 'tailwindcss';

export default {
  content: [
    './index.html',
    './shop.html',
    './src/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        shop: {
          bg: '#f8fafc',
          card: '#ffffff',
          accent: '#3b82f6',
          text: '#0f172a',
          muted: '#64748b',
          border: '#e2e8f0',
          success: '#22c55e',
          error: '#ef4444',
        },
        panel: {
          bg: '#1e1e1e',
          surface: '#252526',
          border: '#3e3e42',
          text: '#cccccc',
          accent: '#007acc',
          success: '#4ec9b0',
          error: '#f14c4c',
          warn: '#cca700',
        },
      },
    },
  },
  plugins: [],
} satisfies Config;
