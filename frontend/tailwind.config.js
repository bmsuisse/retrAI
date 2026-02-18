/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#f3f0ff',
          100: '#e9e3ff',
          200: '#d4caff',
          300: '#b3a4ff',
          400: '#8b72ff',
          500: '#6d3cff',
          600: '#5a1bf7',
          700: '#4c0ee3',
          800: '#3f0cbf',
          900: '#350d9c',
          950: '#1f0669',
        },
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'spin-slow': 'spin 3s linear infinite',
      },
    },
  },
  plugins: [],
}
