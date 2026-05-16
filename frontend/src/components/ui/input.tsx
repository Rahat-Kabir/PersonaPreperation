import * as React from "react";

import { cn } from "@/lib/utils";

export type InputProps = React.InputHTMLAttributes<HTMLInputElement>;

const Input = React.forwardRef<HTMLInputElement, InputProps>(({ className, type = "text", ...props }, ref) => {
  return (
    <input
      type={type}
      className={cn(
        "flex h-[52px] w-full rounded-none border-0 border-b border-[var(--rule-strong)] bg-transparent px-0 py-3 text-lg text-[var(--text-primary)] placeholder:text-[var(--text-quaternary)] placeholder:italic focus-visible:outline-none focus-visible:border-[var(--accent)] transition-colors duration-200",
        className
      )}
      ref={ref}
      {...props}
    />
  );
});
Input.displayName = "Input";

export { Input };
