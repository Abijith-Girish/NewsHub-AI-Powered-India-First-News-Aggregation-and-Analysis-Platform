/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        ink: {
          50: '#f7f7f5',
          100: '#eeece7',
          200: '#dcd8cf',
          300: '#b8b1a3',
          400: '#8b8374',
          500: '#6b6457',
          600: '#514b40',
          700: '#3c372f',
          800: '#26231e',
          900: '#141210',
          950: '#0b0a09',
        },
        accent: {
          50: '#fff1f2',
          100: '#ffe4e6',
          200: '#fecdd3',
          300: '#fda4af',
          400: '#fb7185',
          500: '#e11d48',
          600: '#be123c',
          700: '#9f1239',
          800: '#881337',
          900: '#4c0519',
        },
        signal: {
          500: '#0f766e',
          600: '#0d5f59',
        },
      },
      fontFamily: {
        sans: [
          'Inter',
          'system-ui',
          '-apple-system',
          'Segoe UI',
          'Roboto',
          'Helvetica Neue',
          'Arial',
          'sans-serif',
        ],
        display: ['Georgia', 'Cambria', 'Times New Roman', 'serif'],
      },
      boxShadow: {
        card: '0 1px 2px rgba(20, 18, 16, 0.04), 0 8px 24px -16px rgba(20, 18, 16, 0.25)',
        lift: '0 2px 4px rgba(20, 18, 16, 0.05), 0 18px 40px -24px rgba(20, 18, 16, 0.35)',
      },
      animation: {
        'fade-in': 'fadeIn 220ms ease-out',
        shimmer: 'shimmer 1.6s infinite linear',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0', transform: 'translateY(4px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-480px 0' },
          '100%': { backgroundPosition: '480px 0' },
        },
      },
    },
  },
  plugins: [],
};
