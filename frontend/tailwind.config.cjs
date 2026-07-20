// tailwind.config.cjs
module.exports = {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: "hsl(220, 60%, 55%)",
        secondary: "hsl(210, 40%, 40%)",
        background: "hsl(220, 15%, 12%)",
        card: "hsl(210, 30%, 20%)",
        accent: "hsl(340, 70%, 55%)",
      },
      backdropBlur: {
        xs: "2px",
        sm: "4px",
        md: "8px",
      },
    },
  },
  darkMode: "class",
  plugins: [],
};
