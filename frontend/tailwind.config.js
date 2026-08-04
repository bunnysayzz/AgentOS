/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // Warm near-black surfaces — driven by --surface-* CSS vars (light/dark)
        surface: {
          50: 'hsl(var(--surface-50) / <alpha-value>)',
          100: 'hsl(var(--surface-100) / <alpha-value>)',
          200: 'hsl(var(--surface-200) / <alpha-value>)',
          300: 'hsl(var(--surface-300) / <alpha-value>)',
          400: 'hsl(var(--surface-400) / <alpha-value>)',
          500: 'hsl(var(--surface-500) / <alpha-value>)',
          600: 'hsl(var(--surface-600) / <alpha-value>)',
          700: 'hsl(var(--surface-700) / <alpha-value>)',
          800: 'hsl(var(--surface-800) / <alpha-value>)',
          900: 'hsl(var(--surface-900) / <alpha-value>)',
          950: 'hsl(var(--surface-950) / <alpha-value>)',
        },
        // Gold accent — the signature hue (was indigo)
        primary: {
          50: 'hsl(var(--primary-50) / <alpha-value>)',
          100: 'hsl(var(--primary-100) / <alpha-value>)',
          200: 'hsl(var(--primary-200) / <alpha-value>)',
          300: 'hsl(var(--primary-300) / <alpha-value>)',
          400: 'hsl(var(--primary-400) / <alpha-value>)',
          500: 'hsl(var(--primary-500) / <alpha-value>)',
          600: 'hsl(var(--primary-600) / <alpha-value>)',
          700: 'hsl(var(--primary-700) / <alpha-value>)',
          800: 'hsl(var(--primary-800) / <alpha-value>)',
          900: 'hsl(var(--primary-900) / <alpha-value>)',
          950: 'hsl(var(--primary-950) / <alpha-value>)',
        },
        // Semantic market colors (used for verdicts / status accents)
        gold: {
          DEFAULT: 'hsl(var(--gold) / <alpha-value>)',
          bright: 'hsl(var(--gold-bright) / <alpha-value>)',
          soft: 'rgba(227, 184, 98, 0.14)',
        },
        bull: {
          DEFAULT: 'hsl(var(--bull) / <alpha-value>)',
          bright: 'hsl(var(--bull-bright) / <alpha-value>)',
        },
        bear: {
          DEFAULT: 'hsl(var(--bear) / <alpha-value>)',
          bright: 'hsl(var(--bear-bright) / <alpha-value>)',
        },
        info: 'hsl(var(--info) / <alpha-value>)',
      },
      fontFamily: {
        sans: ['Geist', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'Helvetica Neue', 'Arial', 'sans-serif'],
        mono: ['Geist Mono', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
        display: ['"Instrument Serif"', 'Georgia', 'serif'],
      },
      borderRadius: {
        '4xl': '2rem',
      },
      boxShadow: {
        'gold-glow': '0 0 34px rgba(227, 184, 98, 0.35)',
        'gold-btn': '0 8px 40px -8px rgba(227, 184, 98, 0.25)',
        'glass': '0 8px 40px -12px rgba(0, 0, 0, 0.5)',
      },
      keyframes: {
        'grain-shift': {
          '0%': { transform: 'translate(0, 0)' },
          '25%': { transform: 'translate(-3%, 2%)' },
          '50%': { transform: 'translate(2%, -3%)' },
          '75%': { transform: 'translate(-2%, -2%)' },
          '100%': { transform: 'translate(0, 0)' },
        },
        'pulse-dot': {
          '0%, 100%': { opacity: '1', transform: 'scale(1)' },
          '50%': { opacity: '0.35', transform: 'scale(0.8)' },
        },
      },
      animation: {
        'grain-shift': 'grain-shift 9s steps(8) infinite',
        'pulse-dot': 'pulse-dot 1.4s ease-in-out infinite',
      },
    },
  },
  plugins: [],
}
