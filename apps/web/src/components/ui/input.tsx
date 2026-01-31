"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  hint?: string;
  icon?: React.ReactNode;
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, label, error, hint, icon, type = "text", ...props }, ref) => {
    const id = React.useId();

    return (
      <div className="space-y-2">
        {label && (
          <label
            htmlFor={id}
            className="block text-sm font-medium text-foreground"
          >
            {label}
          </label>
        )}
        <div className="relative">
          {icon && (
            <div className="absolute left-4 top-1/2 -translate-y-1/2 text-foreground-subtle">
              {icon}
            </div>
          )}
          <input
            ref={ref}
            id={id}
            type={type}
            className={cn(
              "w-full h-12 px-4 bg-surface border border-border rounded-lg text-foreground placeholder:text-foreground-subtle transition-all duration-200",
              "focus:outline-none focus:border-foreground-muted focus:ring-2 focus:ring-accent/10",
              "disabled:opacity-50 disabled:cursor-not-allowed",
              icon && "pl-12",
              error && "border-red-500 focus:border-red-500 focus:ring-red-500/10",
              className
            )}
            {...props}
          />
        </div>
        {hint && !error && (
          <p className="text-sm text-foreground-subtle">{hint}</p>
        )}
        {error && <p className="text-sm text-red-500">{error}</p>}
      </div>
    );
  }
);

Input.displayName = "Input";

