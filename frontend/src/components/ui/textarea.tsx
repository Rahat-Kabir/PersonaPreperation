import * as React from "react";

import { cn } from "@/lib/utils";

export type TextareaProps = React.TextareaHTMLAttributes<HTMLTextAreaElement>;

const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(({ className, ...props }, ref) => {
  return (
    <textarea
      className={cn(
        "flex min-h-[96px] w-full rounded-none border-0 border-b border-[var(--rule-strong)] bg-transparent px-0 py-3 text-lg text-[var(--text-primary)] placeholder:text-[var(--text-quaternary)] placeholder:italic focus-visible:outline-none focus-visible:border-[var(--accent)] transition-colors duration-200 resize-none leading-snug",
        className
      )}
      ref={ref}
      {...props}
    />
  );
});
Textarea.displayName = "Textarea";

export { Textarea };
