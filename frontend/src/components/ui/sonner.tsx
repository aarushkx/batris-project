"use client";
import { Toaster as Sonner, type ToasterProps } from "sonner";

const Toaster = ({ ...props }: ToasterProps) => (
  <Sonner
    className="toaster group"
    position="bottom-right"
    toastOptions={{
      classNames: {
        toast:
          "group toast group-[.toaster]:bg-paper group-[.toaster]:text-ink group-[.toaster]:border-line group-[.toaster]:shadow-lg group-[.toaster]:rounded-xl",
        description: "group-[.toast]:text-ink-soft",
      },
    }}
    {...props}
  />
);

export { Toaster };
