import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        mns: {
          navy: '#0A0A0A',
          'navy-800': '#171717',
          'navy-700': '#262626',
          gold: '#C6A15B',
          'gold-light': '#E0C178',
          cream: '#FAF7F0',
          ink: '#141414',
          mute: '#6B6B6B',
          line: '#E7E3D9',
          danger: '#B91C1C',
          success: '#15803D',
          warn: '#B45309',
        },
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        display: ['Fraunces', '"Playfair Display"', 'Georgia', 'serif'],
      },
      boxShadow: {
        card: '0 1px 2px rgba(10,10,10,0.05), 0 10px 30px rgba(10,10,10,0.08)',
        gold: '0 1px 2px rgba(198,161,91,0.2), 0 8px 24px rgba(198,161,91,0.15)',
      },
      borderRadius: {
        xl2: '1.25rem',
      },
    },
  },
  plugins: [],
} satisfies Config
