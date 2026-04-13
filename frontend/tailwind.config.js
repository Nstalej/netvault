import forms from '@tailwindcss/forms';

/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        surface: {
          900: '#0F1117',
          800: '#1A1D27',
          700: '#252836',
          600: '#2E3347',
        },
        teal: {
          DEFAULT: '#0D7377',
          hover: '#14A8AD',
        },
        status: {
          online: '#15803D',
          offline: '#DC2626',
          warning: '#D97706',
          unknown: '#718096',
        },
      },
      fontFamily: {
        sans: ['Inter', 'Segoe UI', 'Tahoma', 'sans-serif'],
        mono: ['JetBrains Mono', 'Consolas', 'monospace'],
      },
    },
  },
  plugins: [forms],
};
