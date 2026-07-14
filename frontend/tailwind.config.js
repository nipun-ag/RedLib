/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        background: "#131313",
        "surface-low": "#1c1b1b",
        surface: "#201f1f",
        "surface-high": "#2a2a2a",
        "surface-highest": "#353534",
        primary: "#e50914",
        "primary-dark": "#c0000c",
        "on-primary": "#fff7f6",
        "on-surface": "#e5e2e1",
        "on-surface-variant": "#e9bcb6",
        "outline-variant": "#5e3f3b",
        outline: "#af8782",
        secondary: "#64de8d",
        tertiary: "#ffb960",
      },
    },
  },
  plugins: [],
}
