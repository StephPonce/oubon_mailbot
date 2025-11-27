/** @type {import('tailwindcss').Config} */
export default {
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
      colors: {
        'brand-blue': '#007aff',
        'glass-white': 'rgba(255, 255, 255, 0.1)',
        'glass-white-hover': 'rgba(255, 255, 255, 0.2)',
        'gray-950': '#0d1117',
        'gray-900': '#161b22',
        'gray-800': '#1c2128',
        'gray-700': '#2d333b',
        'gray-300': '#d0d7de',
        'gray-200': '#f0f6fc',
        'success-green': '#2da44e',
        'warning-yellow': '#e3b341',
      }
    },
  },
  plugins: [],
}
