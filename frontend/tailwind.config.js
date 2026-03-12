/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        display: ['Noto Serif TC', 'serif'],
        sans: ['Noto Sans TC', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
      },
      colors: {
        brand: {
          DEFAULT: '#C17F59',
          light: '#E8D5C4',
          dark: '#9A5C3D',
        },
        paper: {
          50: '#FAF8F5',
          100: '#F5F1EB',
          200: '#EBE4DA',
          300: '#D4C4B0',
        },
        ink: {
          400: '#8B7B6B',
          500: '#6B5D52',
          600: '#4A4038',
          700: '#2D2822',
          800: '#1C1916',
        },
      },
      borderRadius: {
        '2xl': '1rem',
        '3xl': '1.5rem',
      },
      boxShadow: {
        'paper': '0 2px 12px rgba(45, 40, 34, 0.06), 0 1px 3px rgba(45, 40, 34, 0.04)',
        'paper-lg': '0 8px 32px rgba(45, 40, 34, 0.08), 0 2px 8px rgba(45, 40, 34, 0.04)',
        'paper-hover': '0 12px 40px rgba(45, 40, 34, 0.1), 0 4px 12px rgba(45, 40, 34, 0.06)',
      },
      keyframes: {
        'fade-in-up': {
          '0%': { opacity: '0', transform: 'translateY(12px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'fade-in': {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        'pulse-soft': {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.7' },
        },
        'scale-in': {
          '0%': { opacity: '0', transform: 'scale(0.9)' },
          '100%': { opacity: '1', transform: 'scale(1)' },
        },
        'check-pop': {
          '0%': { transform: 'scale(0)' },
          '50%': { transform: 'scale(1.2)' },
          '100%': { transform: 'scale(1)' },
        },
      },
      animation: {
        'fade-in-up': 'fade-in-up 0.5s ease-out forwards',
        'fade-in': 'fade-in 0.4s ease-out forwards',
        'pulse-soft': 'pulse-soft 1.5s ease-in-out infinite',
        'scale-in': 'scale-in 0.3s ease-out forwards',
        'check-pop': 'check-pop 0.35s ease-out forwards',
      },
      animationDelay: {
        '100': '100ms',
        '200': '200ms',
        '300': '300ms',
        '400': '400ms',
        '500': '500ms',
      },
    },
  },
  plugins: [],
}
