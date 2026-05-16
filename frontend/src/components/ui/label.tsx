import * as React from "react";
import { cn } from "@/lib/utils";

export type LabelProps = React.LabelHTMLAttributes<HTMLLabelElement>;

const Label = React.forwardRef<HTMLLabelElement, LabelProps>(({ className, ...props }, ref) => (
  <label
    ref={ref}
    className={cn(
      "font-mono text-[11px] font-medium uppercase tracking-[0.14em] text-[var(--text-tertiary)]",
      className
    )}
    {...props}
  />
));
Label.displayName = "Label";

export { Label };
