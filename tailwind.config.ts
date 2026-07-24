import type { Config } from 'tailwindcss';

export default {
  content: ['./index.html', './shop.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Poppins', 'system-ui', 'sans-serif'],
      },
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
          bg: '#050816',
          deep: '#0a0a1a',
          surface: 'rgba(20, 20, 30, 0.7)',
          border: 'rgba(255, 255, 255, 0.08)',
          borderHover: 'rgba(255, 255, 255, 0.15)',
          text: '#f4f4f6',
          secondary: '#aaa6c3',
          muted: '#64648a',
          accent: '#818cf8',
          accentDim: '#6366f1',
          success: '#22c55e',
          error: '#ef4444',
          warn: '#f59e0b',
        },
      },
      boxShadow: {
        glass: '0 8px 32px rgba(0, 0, 0, 0.3)',
        glow: '0 0 20px rgba(99, 102, 241, 0.15)',
      },
      backdropBlur: {
        glass: '12px',
      },
    },
  },
  plugins: [],
} satisfies Config;
