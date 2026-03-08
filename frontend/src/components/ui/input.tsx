import * as React from "react";

import { cn } from "@/lib/utils";

export type InputProps = React.InputHTMLAttributes<HTMLInputElement>;

const Input = React.forwardRef<HTMLInputElement, InputProps>(({ className, type = "text", ...props }, ref) => {
  return (
    <input
      type={type}
      className={cn(
        "flex h-12 w-full rounded-xl border border-[#2A2A2E] bg-[#222226] px-5 text-base text-[#F0EDE6] placeholder:text-[#5C5955] focus-visible:outline-none focus-visible:border-[#E8C872]/40 focus-visible:ring-1 focus-visible:ring-[#E8C872]/20 transition-colors duration-200",
        className
      )}
      ref={ref}
      {...props}
    />
  );
});
Input.displayName = "Input";

export { Input };
