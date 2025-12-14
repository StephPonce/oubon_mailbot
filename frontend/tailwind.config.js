import tailwindcssAnimate from 'tailwindcss-animate';
import tailwindScrollbarHide from 'tailwind-scrollbar-hide';
import tailwindTypography from '@tailwindcss/typography';
import defaultTheme from 'tailwindcss/defaultTheme';

/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ['class', '[data-theme="dark"]'],
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  safelist: [
    'aurora-bg',
    'aurora-orb',
    'orb-1',
    'orb-2',
    'orb-3',
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['SF Pro Display', 'Inter', ...defaultTheme.fontFamily.sans],
      },
      colors: {
        // Ospra Dark Theme - Primary text colors
        'primary': '#F5F5F7',
        'secondary': '#A1A1A6',
        'tertiary': '#6E6E73',
        'quaternary': '#48484A',

        // Ospra Accent colors - Cyan/Teal
        'accent': '#06b6d4',
        'accent-hover': '#14b8a6',
        'accent-secondary': '#8b5cf6',

        // Dark mode backgrounds
        'bg-dark': '#0a0a0f',
        'bg-dark-elevated': '#16161f',
        'bg-dark-layer': '#1a1a2e',

        // Legacy names for compatibility
        'brand-blue': '#06b6d4',
        'glass-white': 'rgba(255, 255, 255, 0.05)',
        'glass-white-hover': 'rgba(255, 255, 255, 0.08)',
        'gray-950': '#0a0a0f',
        'gray-900': '#16161f',
        'gray-800': '#1a1a2e',
        'gray-700': '#2d333b',
        'gray-300': '#6E6E73',
        'gray-200': '#A1A1A6',

        // Status colors
        'success': '#10b981',
        'warning': '#f59e0b',
        'error': '#ef4444',
        'info': '#06b6d4',
        'success-green': '#10b981',
        'warning-yellow': '#f59e0b',
        'error-red': '#ef4444',
      },
      textColor: {
        'primary': 'var(--text-primary)',
        'secondary': 'var(--text-secondary)',
        'tertiary': 'var(--text-tertiary)',
        'quaternary': 'var(--text-quaternary)',
        'accent': 'var(--accent)',
      },
      backgroundColor: {
        'accent': 'var(--accent)',
        'accent-soft': 'var(--accent-soft)',
      },
      borderColor: {
        'accent': 'var(--accent)',
      },
      backdropBlur: {
        xs: '2px',
      },
      animation: {
        'shimmer': 'shimmer 2s linear infinite',
        'glow': 'glow 2s ease-in-out infinite alternate',
        'float': 'float 6s ease-in-out infinite',
        'refraction': 'refraction 3s ease-in-out infinite',
        'fadeIn': 'fadeIn 0.3s ease-in-out',
        'slideUp': 'slideUp 0.3s ease-out',
        'pulse': 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      },
      keyframes: {
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        glow: {
          '0%': { boxShadow: '0 0 20px rgba(0, 113, 227, 0.3)' },
          '100%': { boxShadow: '0 0 30px rgba(0, 113, 227, 0.6)' },
        },
        float: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-10px)' },
        },
        refraction: {
          '0%, 100%': { filter: 'hue-rotate(0deg)' },
          '50%': { filter: 'hue-rotate(30deg)' },
        },
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
    },
  },
  plugins: [
    tailwindcssAnimate,
    tailwindScrollbarHide,
    tailwindTypography,
  ],
}
