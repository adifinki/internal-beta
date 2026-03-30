/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "-apple-system", "BlinkMacSystemFont", "sans-serif"],
      },
      colors: {
        base: "#0a0e17",
      },
      borderRadius: {
        "2xl": "16px",
        xl: "12px",
        lg: "10px",
      },
      boxShadow: {
        "card-hover": "0 8px 32px rgba(0,0,0,0.3)",
        "tab-active": "0 1px 3px rgba(0,0,0,0.2)",
        "glow-blue": "0 0 20px rgba(59,130,246,0.1)",
        "glow-green": "0 0 20px rgba(34,197,94,0.08)",
        "glow-red": "0 0 20px rgba(239,68,68,0.08)",
      },
    },
  },
  plugins: [],
};
