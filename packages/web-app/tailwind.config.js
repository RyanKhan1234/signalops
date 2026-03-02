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
          50: '#f0f7ff',
          100: '#e0effe',
          200: '#bae0fd',
          300: '#7cc8fb',
          400: '#36aaf5',
          500: '#0c8ee4',
          600: '#006ec2',
          700: '#00579d',
          800: '#044a82',
          900: '#093e6c',
          950: '#062748',
        },
      },
    },
  },
  plugins: [],
}
