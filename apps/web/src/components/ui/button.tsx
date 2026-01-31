"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import { Loader2 } from "lucide-react";

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost" | "outline";
  size?: "sm" | "md" | "lg";
  loading?: boolean;
  icon?: React.ReactNode;
  iconPosition?: "left" | "right";
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      className,
      variant = "primary",
      size = "md",
      loading = false,
      icon,
      iconPosition = "left",
      disabled,
      children,
      ...props
    },
    ref
  ) => {
    const variants = {
      primary:
        "bg-foreground text-background hover:bg-foreground/90 shadow-subtle active:scale-[0.98]",
      secondary:
        "bg-accent text-foreground hover:bg-accent-hover shadow-subtle active:scale-[0.98]",
      ghost:
        "bg-transparent hover:bg-background-secondary text-foreground",
      outline:
        "bg-transparent border border-border hover:border-foreground-subtle text-foreground",
    };

    const sizes = {
      sm: "h-9 px-4 text-sm gap-1.5",
      md: "h-11 px-5 text-sm gap-2",
      lg: "h-13 px-7 text-base gap-2.5",
    };

    return (
      <button
        ref={ref}
        disabled={disabled || loading}
        className={cn(
          "relative inline-flex items-center justify-center font-medium rounded-lg transition-all duration-200 disabled:opacity-50 disabled:pointer-events-none",
          variants[variant],
          sizes[size],
          className
        )}
        {...props}
      >
        {loading && (
          <Loader2 className="w-4 h-4 animate-spin absolute" />
        )}
        <span
          className={cn(
            "inline-flex items-center gap-2",
            loading && "opacity-0"
          )}
        >
          {icon && iconPosition === "left" && icon}
          {children}
          {icon && iconPosition === "right" && icon}
        </span>
      </button>
    );
  }
);

Button.displayName = "Button";

