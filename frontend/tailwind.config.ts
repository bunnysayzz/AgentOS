/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        primary: {
          50: 'hsl(var(--primary-50, 221 100% 97%))',
          100: 'hsl(var(--primary-100, 221 85% 93%))',
          200: 'hsl(var(--primary-200, 221 80% 85%))',
          300: 'hsl(var(--primary-300, 221 75% 73%))',
          400: 'hsl(var(--primary-400, 221 70% 58%))',
          500: 'hsl(var(--primary-500, 221 75% 48%))',
          600: 'hsl(var(--primary-600, 221 80% 42%))',
          700: 'hsl(var(--primary-700, 221 82% 35%))',
          800: 'hsl(var(--primary-800, 221 80% 28%))',
          900: 'hsl(var(--primary-900, 221 78% 22%))',
          950: 'hsl(var(--primary-950, 221 75% 16%))',
        },
        surface: {
          50: 'hsl(var(--surface-50, 210 40% 98%))',
          100: 'hsl(var(--surface-100, 210 40% 96%))',
          200: 'hsl(var(--surface-200, 214 32% 91%))',
          300: 'hsl(var(--surface-300, 213 27% 84%))',
          400: 'hsl(var(--surface-400, 215 20% 65%))',
          500: 'hsl(var(--surface-500, 215 16% 47%))',
          600: 'hsl(var(--surface-600, 215 19% 35%))',
          700: 'hsl(var(--surface-700, 215 25% 27%))',
          800: 'hsl(var(--surface-800, 217 33% 17%))',
          900: 'hsl(var(--surface-900, 222 47% 11%))',
          950: 'hsl(var(--surface-950, 222 84% 5%))',
        },
      },
    },
  },
  plugins: [],
}
