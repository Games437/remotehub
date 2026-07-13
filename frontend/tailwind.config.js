/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        base: "#0B0E14",
        panel: "#12161F",
        line: "#1E2430",
        text: "#E4E7EC",
        muted: "#8B93A3",
        accent: "#5B8DEF",
        online: "#3DDC97",
        offline: "#5A6376",
        danger: "#E5654F",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};
