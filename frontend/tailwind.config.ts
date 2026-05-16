import type { Config } from "tailwindcss";
import { fontFamily } from "tailwindcss/defaultTheme";

const config: Config = {
  content: [
    "./src/pages/**/*.{ts,tsx}",
    "./src/components/**/*.{ts,tsx}",
    "./src/app/**/*.{ts,tsx}"
  ],
  theme: {
    extend: {
      fontFamily: {
        serif: ["'Source Serif 4'", "'Source Serif Pro'", ...fontFamily.serif],
        sans: ["'Inter Tight'", "system-ui", ...fontFamily.sans],
        mono: ["'JetBrains Mono'", ...fontFamily.mono]
      },
      colors: {
        paper: {
          bg: "#F4F1EA",
          surface: "#ECE7DC",
          card: "#FFFFFF"
        },
        ink: {
          DEFAULT: "#171717",
          soft: "#4A463E",
          mute: "#8A867E"
        },
        accent: {
          DEFAULT: "#A63D2A",
          hover: "#8F3324"
        }
      }
    }
  },
  plugins: [require("@tailwindcss/typography")]
};

export default config;
