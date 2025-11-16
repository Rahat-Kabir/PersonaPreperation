import * as React from "react";

import { cn } from "@/lib/utils";

export type TextareaProps = React.TextareaHTMLAttributes<HTMLTextAreaElement>;

const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(({ className, ...props }, ref) => {
  return (
    <textarea
      className={cn(
        "flex min-h-[120px] w-full rounded-[32px] border border-[#1a1814]/30 bg-white/90 px-6 py-4 text-base text-[#1c1915] shadow-panel placeholder:text-[#5f5c55] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-black/10",
        className
      )}
      ref={ref}
      {...props}
    />
  );
});
Textarea.displayName = "Textarea";

export { Textarea };
