/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        brand: {
          abyss: 'var(--bg-abyss)',
          dark: 'var(--bg-dark)',
          card: 'var(--bg-card)',
          surface: 'var(--bg-surface)',
          elevated: 'var(--bg-elevated)',
          hover: 'var(--bg-hover)',
          border: 'var(--border-brand)',
          borderSubtle: 'var(--border-subtle)',
          text: 'var(--text-brand)',
          textSecondary: 'var(--text-secondary)',
          muted: 'var(--text-muted)',
          accent: 'var(--accent)',
          accentBg: 'var(--accent-bg)',
          safe: 'var(--safe)',
          safeBg: 'var(--safe-bg)',
          warning: 'var(--warning)',
          warningBg: 'var(--warning-bg)',
          danger: 'var(--danger)',
          dangerBg: 'var(--danger-bg)',
          cyan: 'var(--cyan)',
          cyanBg: 'var(--cyan-bg)',
          purple: 'var(--purple)',
          purpleBg: 'var(--purple-bg)',
          info: 'var(--info)',
          infoBg: 'var(--info-bg)',
          app: 'var(--bg-abyss)'
        },
        maretide: {
          app: 'var(--bg-abyss)',
          dark: 'var(--bg-dark)',
          card: 'var(--bg-card)',
          surface: 'var(--bg-surface)',
          elevated: 'var(--bg-elevated)',
          hover: 'var(--bg-hover)',
          border: 'var(--border-subtle)',
          borderStrong: 'var(--border-brand)',
          text: {
            primary: 'var(--text-brand)',
            secondary: 'var(--text-secondary)',
            muted: 'var(--text-muted)'
          },
          accent: 'var(--accent)',
          accentBg: 'var(--accent-bg)',
          info: 'var(--cyan)',
          infoBg: 'var(--cyan-bg)',
          safe: 'var(--safe)',
          safeBg: 'var(--safe-bg)',
          warning: 'var(--warning)',
          warningBg: 'var(--warning-bg)',
          danger: 'var(--danger)',
          dangerBg: 'var(--danger-bg)',
          purple: 'var(--purple)',
          purpleBg: 'var(--purple-bg)'
        }
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'SFMono-Regular', 'Consolas', 'monospace'],
      },
      boxShadow: {
        'glass': 'var(--shadow-glass)',
        'glass-glow': 'var(--shadow-glass-glow)',
        'glass-inset': 'var(--shadow-glass-inset)',
        'elevation-1': 'var(--shadow-elevation-1)',
        'elevation-2': 'var(--shadow-elevation-2)',
      }
    },
  },
  plugins: [],
}

