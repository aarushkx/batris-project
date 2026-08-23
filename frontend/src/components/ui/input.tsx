import * as React from "react";
import { cn } from "@/lib/utils";

function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  return (
    <input
      type={type}
      data-slot="input"
      className={cn(
        "flex h-10 w-full min-w-0 rounded-lg border border-line bg-paper px-3 py-2 text-sm shadow-none transition-colors",
        "placeholder:text-ink-soft/70 selection:bg-ink selection:text-white",
        "file:mr-3 file:h-7 file:rounded-md file:border-0 file:bg-mist file:px-3 file:text-[12px] file:font-medium file:text-ink",
        "focus-visible:border-ink/35 focus-visible:ring-[3px] focus-visible:ring-ring/30 outline-none",
        "disabled:cursor-not-allowed disabled:opacity-50",
        "aria-invalid:border-bad aria-invalid:ring-bad/20",
        className,
      )}
      {...props}
    />
  );
}

export { Input };
