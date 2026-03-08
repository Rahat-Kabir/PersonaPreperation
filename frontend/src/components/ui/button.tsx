import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center whitespace-nowrap rounded-full text-sm font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#E8C872]/30 disabled:pointer-events-none disabled:opacity-40",
  {
    variants: {
      variant: {
        default:
          "bg-[#E8C872] text-[#0C0C0E] hover:bg-[#F2D98A] shadow-glow",
        ghost: "bg-transparent text-[#9A9690] hover:text-[#F0EDE6] hover:bg-white/5",
        outline:
          "border border-[#3A3A40] bg-transparent text-[#F0EDE6] hover:border-[#E8C872]/40 hover:text-[#E8C872]",
        danger:
          "bg-transparent text-[#F87171] hover:bg-[#F87171]/10 border border-[#F87171]/20"
      },
      size: {
        default: "h-11 px-8 py-2",
        sm: "h-9 px-5 text-xs",
        lg: "h-12 px-10 text-base"
      }
    },
    defaultVariants: {
      variant: "default",
      size: "default"
    }
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    );
  }
);
Button.displayName = "Button";

export { Button, buttonVariants };
