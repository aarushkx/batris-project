import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex w-fit shrink-0 items-center justify-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11px] font-semibold tracking-[0.01em] whitespace-nowrap [&>svg]:size-3",
  {
    variants: {
      variant: {
        default: "border-line bg-mist text-ink-soft",
        good: "border-good/30 bg-good/10 text-good",
        warn: "border-warn/30 bg-warn/10 text-warn",
        bad: "border-bad/30 bg-bad/10 text-bad",
        signal: "border-signal/30 bg-signal/10 text-signal",
        estimated: "border-estimated/30 bg-estimated/10 text-estimated",
        outline: "border-line bg-transparent text-ink-soft",
        solid: "border-ink bg-ink text-white",
      },
    },
    defaultVariants: { variant: "default" },
  },
);

function Badge({
  className,
  variant,
  asChild = false,
  ...props
}: React.ComponentProps<"span"> &
  VariantProps<typeof badgeVariants> & { asChild?: boolean }) {
  const Comp = asChild ? Slot : "span";
  return (
    <Comp
      data-slot="badge"
      className={cn(badgeVariants({ variant }), className)}
      {...props}
    />
  );
}

export { Badge, badgeVariants };
