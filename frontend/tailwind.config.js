/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#17332f',
        moss: '#195c48',
        tide: '#0f766e',
        sand: '#f4ead7',
        parchment: '#fffaf1',
        ember: '#8c5a2b',
        roseclay: '#b36f5c',
      },
      boxShadow: {
        float: '0 24px 80px rgba(22, 51, 47, 0.14)',
        panel: '0 14px 40px rgba(23, 51, 47, 0.10)',
      },
      fontFamily: {
        sans: ['"IBM Plex Sans KR"', '"Noto Sans KR"', 'sans-serif'],
        display: ['Fraunces', '"Times New Roman"', 'serif'],
      },
      backgroundImage: {
        grid: 'linear-gradient(rgba(25,92,72,0.08) 1px, transparent 1px), linear-gradient(90deg, rgba(25,92,72,0.08) 1px, transparent 1px)',
      },
    },
  },
  plugins: [],
}
