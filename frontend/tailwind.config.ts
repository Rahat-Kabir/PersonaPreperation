import type { Config } from "tailwindcss";
import { fontFamily } from "tailwindcss/defaultTheme";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./src/pages/**/*.{ts,tsx}",
    "./src/components/**/*.{ts,tsx}",
    "./src/app/**/*.{ts,tsx}"
  ],
  theme: {
    extend: {
      fontFamily: {
        serif: ["'Playfair Display'", ...fontFamily.serif],
        sans: ["'Inter'", ...fontFamily.sans]
      },
      colors: {
        shell: {
          background: "#f5f4f0",
          border: "#d4d1c7",
          accent: "#141210"
        }
      },
      boxShadow: {
        soft: "0 25px 60px rgba(20, 18, 16, 0.08)",
        panel: "inset 0 1px 0 rgba(255,255,255,0.8), 0 20px 35px rgba(0,0,0,0.08)"
      }
    }
  },
  plugins: [require("@tailwindcss/typography")]
};

export default config;
