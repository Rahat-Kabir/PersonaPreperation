import * as React from "react";

import { cn } from "@/lib/utils";

export type TextareaProps = React.TextareaHTMLAttributes<HTMLTextAreaElement>;

const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(({ className, ...props }, ref) => {
  return (
    <textarea
      className={cn(
        "flex min-h-[120px] w-full rounded-xl border border-[#2A2A2E] bg-[#222226] px-5 py-4 text-base text-[#F0EDE6] placeholder:text-[#5C5955] focus-visible:outline-none focus-visible:border-[#E8C872]/40 focus-visible:ring-1 focus-visible:ring-[#E8C872]/20 transition-colors duration-200 resize-none",
        className
      )}
      ref={ref}
      {...props}
    />
  );
});
Textarea.displayName = "Textarea";

export { Textarea };
