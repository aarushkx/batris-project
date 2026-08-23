import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-full text-sm font-medium transition-all disabled:pointer-events-none disabled:opacity-45 [&_svg]:pointer-events-none [&_svg:not([class*='size-'])]:size-4 shrink-0 [&_svg]:shrink-0 outline-none focus-visible:ring-[3px] focus-visible:ring-ring/45 cursor-pointer",
  {
    variants: {
      variant: {
        default:
          "bg-ink text-white hover:bg-ink/88 shadow-[0_1px_2px_rgba(12,16,19,0.18)]",
        signal: "bg-signal text-white hover:bg-signal/90",
        destructive: "bg-bad text-white hover:bg-bad/90",
        outline:
          "border border-line bg-paper text-ink hover:bg-mist hover:border-ink/25",
        secondary: "bg-mist text-ink hover:bg-line/70",
        ghost: "text-ink hover:bg-mist",
        link: "text-signal underline-offset-4 hover:underline rounded-none",
      },
      size: {
        default: "h-10 px-5 has-[>svg]:px-4",
        sm: "h-8 px-3.5 text-[13px] has-[>svg]:px-3",
        lg: "h-12 px-7 text-[15px]",
        icon: "size-10",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  },
);

function Button({
  className,
  variant,
  size,
  asChild = false,
  ...props
}: React.ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & { asChild?: boolean }) {
  const Comp = asChild ? Slot : "button";
  return (
    <Comp
      data-slot="button"
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  );
}

export { Button, buttonVariants };
