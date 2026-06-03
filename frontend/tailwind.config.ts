import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './app/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        terminal: {
          bg: '#0d1117',
          panel: '#161b22',
          border: '#30363d',
          text: '#e6edf3',
          muted: '#8b949e',
          yellow: '#ecad0a',
          blue: '#209dd7',
          purple: '#753991',
          green: '#3fb950',
          red: '#f85149',
        }
      }
    }
  },
  plugins: [],
}

export default config
