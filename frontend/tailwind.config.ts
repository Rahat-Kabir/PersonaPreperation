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
        serif: ["'Instrument Serif'", ...fontFamily.serif],
        sans: ["'Geist'", "system-ui", ...fontFamily.sans],
        mono: ["'Geist Mono'", ...fontFamily.mono]
      },
      colors: {
        shell: {
          background: "#0C0C0E",
          border: "#2A2A2E",
          accent: "#E8C872"
        }
      },
      boxShadow: {
        soft: "0 25px 60px rgba(0, 0, 0, 0.3)",
        panel: "0 1px 0 rgba(255,255,255,0.03), 0 20px 40px rgba(0,0,0,0.25)",
        glow: "0 0 40px rgba(232, 200, 114, 0.08)"
      }
    }
  },
  plugins: [require("@tailwindcss/typography")]
};

export default config;
