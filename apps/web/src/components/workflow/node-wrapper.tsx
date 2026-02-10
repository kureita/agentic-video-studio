import { memo } from "react";
import { Handle, Position } from "@xyflow/react";
import { Copy, Trash2, Play, Type, Image as ImageIcon, Video, Music, Loader2, Eraser } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

interface NodeHandle {
    id: string;
    label?: string;
    type?: "text" | "image" | "video" | "audio" | "any";
    style?: React.CSSProperties;
}

interface NodeWrapperProps {
    children: React.ReactNode;
    title: string;
    icon: React.ReactNode;
    selected?: boolean;
    inputs?: Array<NodeHandle>;
    outputs?: Array<NodeHandle>;
    color?: string;
    onDelete?: () => void;
    onRun?: () => void;
    onClear?: () => void;
    isRunning?: boolean;
    inputBaseOffset?: number;
    contentClassName?: string;
    style?: React.CSSProperties;
}

const getHandleIcon = (type?: string) => {
    switch (type) {
        case "text": return <Type className="w-2.5 h-2.5" />;
        case "image": return <ImageIcon className="w-2.5 h-2.5" />;
        case "video": return <Video className="w-2.5 h-2.5" />;
        case "audio": return <Music className="w-2.5 h-2.5" />;
        default: return <div className="w-1.5 h-1.5 rounded-full bg-current" />;
    }
};

export const NodeWrapper = memo(({
    children,
    title,
    selected,
    inputs = [],
    outputs = [],
    onDelete,
    onRun,
    onClear,
    isRunning,
    contentClassName,
    style,
    inputBaseOffset = 75,
}: NodeWrapperProps) => {

    return (
        <div className="relative group/node">
            {/* Title - Positioned Above */}
            <div className="absolute -top-6 left-0 px-1">
                <span className="text-xs font-bold text-muted-foreground/80 tracking-tight uppercase">{title}</span>
            </div>

            {/* Action Bar (Visible on Selection) */}
            <div className={cn(
                "absolute -top-10 right-0 flex items-center gap-1 bg-background/80 backdrop-blur-md border border-border/50 rounded-full shadow-xl p-0.5 transition-all duration-200 z-50 scale-90 origin-right",
                selected ? "opacity-100 translate-y-0" : "opacity-0 translate-y-2 pointer-events-none"
            )}>
                {onRun && (
                    <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7 text-green-500 hover:text-green-600 hover:bg-green-500/10 rounded-full disabled:opacity-50"
                        onClick={onRun}
                        disabled={isRunning}
                    >
                        {isRunning ? (
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                            <Play className="h-3.5 w-3.5 fill-current" />
                        )}
                    </Button>
                )}
                {onRun && <div className="w-[1px] h-3 bg-border/50" />}

                {onClear && (
                    <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7 text-muted-foreground hover:text-amber-500 hover:bg-amber-500/10 rounded-full"
                        onClick={onClear}
                        title="Clear Output"
                    >
                        <Eraser className="h-3.5 w-3.5" />
                    </Button>
                )}

                <Button variant="ghost" size="icon" className="h-7 w-7 text-muted-foreground hover:text-foreground rounded-full">
                    <Copy className="h-3.5 w-3.5" />
                </Button>
                <Button variant="ghost" size="icon" className="h-7 w-7 text-destructive/70 hover:text-destructive hover:bg-destructive/10 rounded-full" onClick={onDelete}>
                    <Trash2 className="h-3.5 w-3.5" />
                </Button>
            </div>

            {/* Running Overlay */}
            {isRunning && (
                <div className="absolute inset-0 bg-background/50 backdrop-blur-sm rounded-[20px] z-40 flex items-center justify-center pointer-events-none">
                    <div className="flex items-center gap-2 bg-background/90 rounded-full px-3 py-1.5 shadow-lg">
                        <Loader2 className="w-4 h-4 animate-spin text-primary" />
                        <span className="text-xs font-medium">Running...</span>
                    </div>
                </div>
            )}

            {/* Main Node Content Box */}
            <div
                className={cn(
                    "min-w-[300px] rounded-[20px] bg-card border-[3px] transition-all duration-300 overflow-hidden",
                    selected
                        ? "border-primary/20 shadow-[0_0_40px_-10px_hsl(var(--primary)/0.2)] ring-1 ring-primary/40"
                        : "border-border/40 shadow-sm hover:border-border/80",
                    isRunning && "ring-2 ring-primary/30 ring-offset-2 ring-offset-background"
                )}
                style={style}
            >
                <div className={cn("p-0 relative", contentClassName)}>
                    {children}
                </div>
            </div>

            {/* Input Handles - Bottom Left Bias */}
            {inputs.map((input, index) => (
                <div key={input.id} className="absolute -left-[14px] nodrag" style={input.style || { top: `${inputBaseOffset - (inputs.length - 1 - index) * 15}%`, transform: 'translateY(-50%)' }}>
                    <div className="relative w-7 h-7 z-50 group/handle cursor-crosshair">
                        {/* Visual Ring & BG */}
                        <div className="absolute inset-0 rounded-full border-2 border-border bg-background shadow-sm transition-colors group-hover/handle:border-primary pointer-events-none" />

                        {/* Icon */}
                        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 pointer-events-none text-muted-foreground group-hover/handle:text-primary transition-colors flex items-center justify-center">
                            {getHandleIcon(input.type)}
                        </div>

                        {/* Actual Handle - HIT AREA */}
                        <Handle
                            type="target"
                            position={Position.Left}
                            id={`${input.type || 'any'}|${input.id}`}
                            className="!w-full !h-full !absolute !top-0 !left-0 !opacity-0 !rounded-full !border-none !bg-transparent z-50 cursor-crosshair !transform-none"
                        />

                        {/* Tooltip */}
                        <div className="absolute left-full ml-2 px-2 py-1 bg-popover text-popover-foreground text-[10px] rounded border shadow-sm opacity-0 group-hover/handle:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-50">
                            {input.label}
                        </div>
                    </div>
                </div>
            ))}

            {/* Output Handles - Top Right Bias */}
            {outputs.map((output, index) => (
                <div key={output.id} className="absolute -right-[14px] nodrag" style={output.style || { top: `${25 + index * 15}%`, transform: 'translateY(-50%)' }}>
                    <div className="relative w-7 h-7 z-50 group/handle cursor-crosshair">
                        {/* Visual Ring & BG */}
                        <div className="absolute inset-0 rounded-full border-2 border-border bg-background shadow-sm transition-colors group-hover/handle:border-primary pointer-events-none" />

                        {/* Icon */}
                        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 pointer-events-none text-muted-foreground group-hover/handle:text-primary transition-colors flex items-center justify-center">
                            {getHandleIcon(output.type)}
                        </div>

                        {/* Actual Handle - HIT AREA */}
                        <Handle
                            type="source"
                            position={Position.Right}
                            id={`${output.type || 'any'}|${output.id}`}
                            className="!w-full !h-full !absolute !top-0 !left-0 !opacity-0 !rounded-full !border-none !bg-transparent z-50 cursor-crosshair !transform-none"
                        />

                        {/* Tooltip */}
                        <div className="absolute right-full mr-2 px-2 py-1 bg-popover text-popover-foreground text-[10px] rounded border shadow-sm opacity-0 group-hover/handle:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-50">
                            {output.label}
                        </div>
                    </div>
                </div>
            ))}
        </div>
    );
});

NodeWrapper.displayName = "NodeWrapper";
