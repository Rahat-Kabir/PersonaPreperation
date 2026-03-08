import * as React from "react";
import { cn } from "@/lib/utils";

export type LabelProps = React.LabelHTMLAttributes<HTMLLabelElement>;

const Label = React.forwardRef<HTMLLabelElement, LabelProps>(({ className, ...props }, ref) => (
  <label
    ref={ref}
    className={cn("text-xs font-medium uppercase tracking-[0.15em] text-[#9A9690]", className)}
    {...props}
  />
));
Label.displayName = "Label";

export { Label };
