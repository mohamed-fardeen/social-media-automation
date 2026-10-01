"use client";

import { cn } from "@/lib/utils";
import { forwardRef, type ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "ghost" | "danger" | "outline";
type Size = "sm" | "md" | "lg";

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  iconLeft?: React.ReactNode;
  iconRight?: React.ReactNode;
}

const variantStyles: Record<Variant, string> = {
  primary:
    "bg-sodium-500 text-ink-950 hover:bg-sodium-400 active:bg-sodium-600",
  secondary:
    "bg-ink-750 text-ink-50 border border-ink-600 hover:bg-ink-700 hover:border-ink-500",
  ghost: "text-ink-100 hover:bg-ink-800",
  outline:
    "bg-transparent text-ink-50 border border-ink-600 hover:bg-ink-800 hover:border-ink-500",
  danger:
    "bg-live-reject/10 text-live-reject border border-live-reject/30 hover:bg-live-reject/20",
};

const sizeStyles: Record<Size, string> = {
  sm: "h-7 px-2.5 text-xs gap-1.5",
  md: "h-9 px-3.5 text-[13px] gap-2",
  lg: "h-11 px-5 text-sm gap-2",
};

export const Button = forwardRef<HTMLButtonElement, Props>(function Button(
  { className, variant = "secondary", size = "md", loading, iconLeft, iconRight, children, disabled, ...props },
  ref,
) {
  return (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={cn(
        "relative inline-flex items-center justify-center rounded-md font-medium tracking-tight",
        "transition-[background,border-color,box-shadow,opacity] duration-150",
        "disabled:opacity-50 disabled:pointer-events-none whitespace-nowrap",
        variantStyles[variant],
        sizeStyles[size],
        className,
      )}
      {...props}
    >
      {loading && (
        <span className="absolute inset-0 grid place-items-center">
          <span className="h-3.5 w-3.5 rounded-full border-2 border-current border-t-transparent animate-spin" />
        </span>
      )}
      <span className={cn("inline-flex items-center", size === "sm" ? "gap-1.5" : size === "lg" ? "gap-2" : "gap-2", loading && "opacity-0")}>
        {iconLeft}
        {children}
        {iconRight}
      </span>
    </button>
  );
});
