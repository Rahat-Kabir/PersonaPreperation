import * as React from "react";

import { cn } from "@/lib/utils";

export type InputProps = React.InputHTMLAttributes<HTMLInputElement>;

const Input = React.forwardRef<HTMLInputElement, InputProps>(({ className, type = "text", ...props }, ref) => {
  return (
    <input
      type={type}
      className={cn(
        "flex h-12 w-full rounded-full border border-[#1a1814]/30 bg-white/90 px-6 text-base text-[#1c1915] shadow-panel placeholder:text-[#5f5c55] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-black/10",
        className
      )}
      ref={ref}
      {...props}
    />
  );
});
Input.displayName = "Input";

export { Input };
