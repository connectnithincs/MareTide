/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          dark: 'var(--bg-dark)',
          card: 'var(--bg-card)',
          border: 'var(--border-brand)',
          text: 'var(--text-brand)',
          muted: 'var(--text-muted)',
          accent: 'var(--accent)',
          accentBg: 'var(--accent-bg)',
          danger: 'var(--danger)',
          dangerBg: 'var(--danger-bg)'
        }
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      }
    },
  },
  plugins: [],
}
