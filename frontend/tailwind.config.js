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
        // Primary text colors matching CSS variables
        'primary': '#1D1D1F',
        'secondary': '#6E6E73',
        'tertiary': '#86868B',
        'quaternary': '#AEAEB2',
        
        // Accent color
        'accent': '#0071E3',
        'accent-hover': '#0077ED',
        
        // Legacy names
        'brand-blue': '#0071E3',
        'glass-white': 'rgba(255, 255, 255, 0.1)',
        'glass-white-hover': 'rgba(255, 255, 255, 0.2)',
        'gray-950': '#0d1117',
        'gray-900': '#161b22',
        'gray-800': '#1c2128',
        'gray-700': '#2d333b',
        'gray-300': '#d0d7de',
        'gray-200': '#f0f6fc',
        
        // Status colors
        'success': '#34C759',
        'warning': '#FF9500',
        'error': '#FF3B30',
        'info': '#007AFF',
        'success-green': '#34C759',
        'warning-yellow': '#FF9500',
        'error-red': '#FF3B30',
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
