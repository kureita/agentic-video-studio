"use client";

import { memo, forwardRef, HTMLAttributes, ReactNode } from "react";
import { Handle, Position } from "@xyflow/react";
import { Loader2, CheckCircle2, AlertCircle, Circle } from "lucide-react";
import { cn } from "@/lib/utils";
import { NodeStatus } from "@/lib/canvas-store";

// Status icons mapping
const statusIcons: Record<NodeStatus, ReactNode> = {
  idle: <Circle className="w-4 h-4 text-foreground-subtle" />,
  loading: <Loader2 className="w-4 h-4 text-amber-500 animate-spin" />,
  success: <CheckCircle2 className="w-4 h-4 text-emerald-500" />,
  error: <AlertCircle className="w-4 h-4 text-red-500" />,
};

// BaseNode - Main container
interface BaseNodeProps extends HTMLAttributes<HTMLDivElement> {
  selected?: boolean;
  status?: NodeStatus;
  hasInput?: boolean;
  hasOutput?: boolean;
}

export const BaseNode = forwardRef<HTMLDivElement, BaseNodeProps>(
  ({ className, selected, status = "idle", hasInput = true, hasOutput = true, children, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn(
          "rounded-xl border bg-background shadow-lg transition-all duration-200",
          "min-w-[320px] max-w-[420px]",
          selected && "ring-2 ring-accent",
          status === "loading" && "ring-2 ring-amber-500/50",
          status === "success" && "ring-2 ring-emerald-500/50",
          status === "error" && "ring-2 ring-red-500/50",
          className
        )}
        {...props}
      >
        {/* Input Handle - Left side for horizontal flow */}
        {hasInput && (
          <Handle
            type="target"
            position={Position.Left}
            className="!w-3 !h-3 !bg-foreground-subtle !border-2 !border-background !-left-1.5"
          />
        )}

        {children}

        {/* Output Handle - Right side for horizontal flow */}
        {hasOutput && (
          <Handle
            type="source"
            position={Position.Right}
            className="!w-3 !h-3 !bg-foreground-subtle !border-2 !border-background !-right-1.5"
          />
        )}
      </div>
    );
  }
);
BaseNode.displayName = "BaseNode";

// BaseNodeHeader
interface BaseNodeHeaderProps extends HTMLAttributes<HTMLDivElement> {
  icon?: ReactNode;
  status?: NodeStatus;
}

export const BaseNodeHeader = forwardRef<HTMLDivElement, BaseNodeHeaderProps>(
  ({ className, icon, status = "idle", children, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn(
          "flex items-center gap-3 px-4 py-3 border-b border-border",
          className
        )}
        {...props}
      >
        {icon && (
          <div className="w-8 h-8 rounded-lg bg-background-secondary flex items-center justify-center text-foreground shrink-0">
            {icon}
          </div>
        )}
        <div className="flex-1 font-medium text-foreground">{children}</div>
        {statusIcons[status]}
      </div>
    );
  }
);
BaseNodeHeader.displayName = "BaseNodeHeader";

// BaseNodeContent - includes nowheel class for scrollable content
export const BaseNodeContent = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, children, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn("p-4 nowheel", className)}
        {...props}
      >
        {children}
      </div>
    );
  }
);
BaseNodeContent.displayName = "BaseNodeContent";

// BaseNodeFooter
export const BaseNodeFooter = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, children, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn("px-4 pb-4", className)}
        {...props}
      >
        {children}
      </div>
    );
  }
);
BaseNodeFooter.displayName = "BaseNodeFooter";

// Error display component
interface BaseNodeErrorProps {
  message?: string | null;
}

export const BaseNodeError = memo(function BaseNodeError({ message }: BaseNodeErrorProps) {
  if (!message) return null;
  
  return (
    <div className="px-4 pb-4">
      <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-600 text-sm">
        {message}
      </div>
    </div>
  );
});
