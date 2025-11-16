import * as React from "react";
import { cn } from "@/lib/utils";

export type LabelProps = React.HTMLAttributes<HTMLLabelElement>;

const Label = React.forwardRef<HTMLLabelElement, LabelProps>(({ className, ...props }, ref) => (
  <label
    ref={ref}
    className={cn("text-sm font-medium uppercase tracking-[0.2em] text-[#3a3830]", className)}
    {...props}
  />
));
Label.displayName = "Label";

export { Label };
