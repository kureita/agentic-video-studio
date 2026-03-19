import { memo, useState, useRef } from "react";
import { Handle, Position } from "@xyflow/react";
import { Copy, Trash2, Play, Type, Image as ImageIcon, Video, Music, Loader2, Eraser, Scan, SkipForward, Clock } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { usePublicView } from "@/lib/public-view-context";

interface NodeHandle {
    id: string;
    label?: string;
    type?: "text" | "image" | "video" | "audio" | "any";
    style?: React.CSSProperties;
    /** Frame preview data-URI. When set, hovering shows the image. */
    framePreview?: string;
    /** True if a video exists and frames can be extracted (shows Generate Preview button). */
    hasVideoOutput?: boolean;
    /** Callback to trigger frame extraction — wired up by the parent node */
    onExtractFrames?: () => void;
    /** Whether frame extraction is currently in-flight */
    isExtractingFrames?: boolean;
    /** Error message to display if extraction failed */
    extractionError?: string;
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
    executionStatus?: "queued" | "running" | "completed" | "failed" | "skipped" | null;
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
    executionStatus,
    contentClassName,
    style,
    inputBaseOffset = 75,
}: NodeWrapperProps) => {
    const { isPublicView, requireLogin } = usePublicView();

    const gatedOnRun = isPublicView
        ? () => requireLogin("Sign in to run nodes and generate media.")
        : onRun;
    const gatedOnDelete = isPublicView ? undefined : onDelete;
    const gatedOnClear = isPublicView ? undefined : onClear;

    // ── Per-handle hover state (avoids CSS group-hover bleed between adjacent handles) ──
    const [activeHandle, setActiveHandle] = useState<string | null>(null);
    const hideTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

    const openCard = (id: string) => {
        if (hideTimer.current) clearTimeout(hideTimer.current);
        setActiveHandle(id);
    };
    const scheduleClose = () => {
        hideTimer.current = setTimeout(() => setActiveHandle(null), 100);
    };

    // Execution status styles
    const executionBorderClass = executionStatus === "completed"
        ? "border-green-500/60 shadow-[0_0_20px_-5px_rgba(34,197,94,0.3)]"
        : executionStatus === "running"
            ? "border-amber-500/60 shadow-[0_0_20px_-5px_rgba(245,158,11,0.3)] animate-pulse"
            : executionStatus === "failed"
                ? "border-red-500/60 shadow-[0_0_20px_-5px_rgba(239,68,68,0.3)]"
                : executionStatus === "queued"
                    ? "border-blue-400/40 shadow-[0_0_12px_-5px_rgba(96,165,250,0.2)]"
                    : executionStatus === "skipped"
                        ? "border-border/40 opacity-60"
                        : "";

    return (
        <div className="relative group/node">
            {/* Execution Status Badge */}
            {executionStatus && (
                <div className={cn(
                    "absolute -top-10 left-1/2 -translate-x-1/2 flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-medium whitespace-nowrap z-50 transition-all duration-300",
                    executionStatus === "running" && "bg-amber-500/10 text-amber-500 border border-amber-500/20",
                    executionStatus === "completed" && "bg-green-500/10 text-green-500 border border-green-500/20",
                    executionStatus === "failed" && "bg-red-500/10 text-red-500 border border-red-500/20",
                    executionStatus === "queued" && "bg-blue-400/10 text-blue-400 border border-blue-400/20",
                    executionStatus === "skipped" && "bg-muted text-muted-foreground border border-border/40"
                )}>
                    {executionStatus === "running" && <Loader2 className="w-2.5 h-2.5 animate-spin" />}
                    {executionStatus === "completed" && <div className="w-2 h-2 rounded-full bg-green-500" />}
                    {executionStatus === "failed" && <div className="w-2 h-2 rounded-full bg-red-500" />}
                    {executionStatus === "queued" && <Clock className="w-2.5 h-2.5" />}
                    {executionStatus === "skipped" && <SkipForward className="w-2.5 h-2.5" />}
                    {executionStatus.charAt(0).toUpperCase() + executionStatus.slice(1)}
                </div>
            )}

            {/* Title - Positioned Above */}
            <div className="absolute -top-6 left-0 px-1">
                <span className="text-xs font-bold text-muted-foreground/80 tracking-tight uppercase">{title}</span>
            </div>

            {/* Action Bar (Visible on Selection) */}
            <div className={cn(
                "absolute -top-10 right-0 flex items-center gap-1 bg-background/80 backdrop-blur-md border border-border/50 rounded-full shadow-xl p-0.5 transition-all duration-200 z-50 scale-90 origin-right",
                selected && !isRunning && executionStatus !== "running" && executionStatus !== "queued" ? "opacity-100 translate-y-0" : "opacity-0 translate-y-2 pointer-events-none"
            )}>
                {gatedOnRun && (
                    <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7 text-green-500 hover:text-green-600 hover:bg-green-500/10 rounded-full disabled:opacity-50"
                        onClick={gatedOnRun}
                        disabled={isRunning}
                    >
                        {isRunning ? (
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                            <Play className="h-3.5 w-3.5 fill-current" />
                        )}
                    </Button>
                )}
                {gatedOnRun && <div className="w-[1px] h-3 bg-border/50" />}

                {gatedOnClear && (
                    <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7 text-muted-foreground hover:text-amber-500 hover:bg-amber-500/10 rounded-full"
                        onClick={gatedOnClear}
                        title="Clear Output"
                    >
                        <Eraser className="h-3.5 w-3.5" />
                    </Button>
                )}

                {!isPublicView && (
                    <>
                        <Button variant="ghost" size="icon" className="h-7 w-7 text-muted-foreground hover:text-foreground rounded-full">
                            <Copy className="h-3.5 w-3.5" />
                        </Button>
                        <Button variant="ghost" size="icon" className="h-7 w-7 text-destructive/70 hover:text-destructive hover:bg-destructive/10 rounded-full" onClick={gatedOnDelete}>
                            <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                    </>
                )}
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
                    "min-w-[240px] md:min-w-[300px] rounded-[20px] bg-card border-[3px] transition-all duration-300",
                    executionBorderClass || (
                        selected
                            ? "border-primary/20 shadow-[0_0_40px_-10px_color-mix(in_srgb,var(--primary)_20%,transparent)] ring-1 ring-primary/40"
                            : "border-border/40 shadow-sm hover:border-border/80"
                    ),
                    isRunning && "ring-2 ring-primary/30 ring-offset-2 ring-offset-background"
                )}
                style={style}
            >
                <div className={cn("p-0 relative rounded-[17px]", contentClassName)}>
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
            {outputs.map((output, index) => {
                const hasCard = !!(output.framePreview || (output.hasVideoOutput && output.onExtractFrames));
                const isCardOpen = activeHandle === output.id || !!output.isExtractingFrames;
                const isActive = activeHandle === output.id;

                return (
                    <div
                        key={output.id}
                        className="absolute -right-[14px] nodrag"
                        style={output.style || { top: `${25 + index * 15}%`, transform: 'translateY(-50%)' }}
                    >
                        {/* Dot — 28×28px, no overlap with other handles */}
                        <div
                            className="relative w-7 h-7 z-50 cursor-crosshair"
                            onMouseEnter={() => hasCard && openCard(output.id)}
                            onMouseLeave={() => hasCard && scheduleClose()}
                        >
                            {/* Visual ring */}
                            <div className={cn(
                                "absolute inset-0 rounded-full border-2 bg-background shadow-sm transition-colors pointer-events-none",
                                isActive ? "border-primary" : "border-border"
                            )} />
                            {/* Icon */}
                            <div className={cn(
                                "absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 pointer-events-none transition-colors flex items-center justify-center",
                                isActive ? "text-primary" : "text-muted-foreground"
                            )}>
                                {getHandleIcon(output.type)}
                            </div>
                            {/* ReactFlow handle hit area */}
                            <Handle
                                type="source"
                                position={Position.Right}
                                id={`${output.type || 'any'}|${output.id}`}
                                className="!w-full !h-full !absolute !top-0 !left-0 !opacity-0 !rounded-full !border-none !bg-transparent z-50 cursor-crosshair !transform-none"
                            />
                            {/* Plain label tooltip — only for handles without a card */}
                            {!hasCard && (
                                <div className="absolute right-full mr-2 px-2 py-1 bg-popover text-popover-foreground text-[10px] rounded border shadow-sm opacity-0 group-hover/handle:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-50">
                                    {output.label}
                                </div>
                            )}
                        </div>

                        {/* Popup card — sibling to the dot, controlled by React state */}
                        {hasCard && (
                            <div
                                className={cn(
                                    "absolute z-[100] transition-all duration-150 nopan nodrag nowheel",
                                    isCardOpen
                                        ? "opacity-100 translate-x-0 pointer-events-auto"
                                        : "opacity-0 translate-x-1 pointer-events-none"
                                )}
                                style={{
                                    top: '50%',
                                    transform: 'translateY(-50%)',
                                    right: '38px',  // 28px dot + 10px gap
                                    width: 164,
                                }}
                                onMouseEnter={() => openCard(output.id)}
                                onMouseLeave={scheduleClose}
                                onMouseDown={(e) => e.stopPropagation()}
                            >
                                {output.framePreview ? (
                                    /* ── State 1: frame image ready ── */
                                    <div className="bg-popover border border-border/60 rounded-xl shadow-2xl overflow-hidden">
                                        {/* eslint-disable-next-line @next/next/no-img-element */}
                                        <img
                                            src={output.framePreview}
                                            alt={output.label || 'Frame'}
                                            className="w-full object-cover block"
                                            style={{ maxHeight: 104 }}
                                        />
                                        <div className="px-2.5 py-1.5 flex items-center gap-1.5">
                                            <div className="w-1.5 h-1.5 rounded-full bg-green-500 flex-shrink-0" />
                                            <span className="text-[9px] font-medium text-muted-foreground">{output.label}</span>
                                        </div>
                                    </div>
                                ) : output.extractionError ? (
                                    /* ── State 2x: extraction failed ── */
                                    <div className="bg-destructive/10 border border-destructive/20 rounded-xl shadow-2xl overflow-hidden">
                                        <div className="px-3 pt-3 pb-2 text-center">
                                            <div className="w-6 h-6 rounded-full bg-destructive/20 text-destructive flex items-center justify-center mx-auto mb-2">
                                                <Scan className="w-3.5 h-3.5" />
                                            </div>
                                            <span className="text-[10px] font-semibold text-destructive">{output.extractionError}</span>
                                        </div>
                                        <div className="px-3 pb-3">
                                            <button
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    e.preventDefault();
                                                    output.onExtractFrames?.();
                                                }}
                                                onMouseDown={(e) => e.stopPropagation()}
                                                className="w-full flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg bg-destructive text-destructive-foreground text-[9px] font-semibold transition-all hover:bg-destructive/90 active:scale-[0.97] shadow-sm nopan nodrag nowheel cursor-pointer"
                                            >
                                                Retry Capture
                                            </button>
                                        </div>
                                    </div>
                                ) : output.isExtractingFrames ? (
                                    /* ── State 2a: currently extracting ── */
                                    <div className="bg-popover border border-border/60 rounded-xl shadow-2xl overflow-hidden">
                                        <div className="relative overflow-hidden bg-muted/60" style={{ height: 80 }}>
                                            <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/10 to-transparent animate-shimmer" style={{ backgroundSize: '200% 100%' }} />
                                            <div className="absolute inset-0 flex flex-col items-center justify-center gap-1.5">
                                                <Loader2 className="w-5 h-5 text-primary animate-spin" />
                                                <span className="text-[9px] font-medium text-muted-foreground">Capturing frame…</span>
                                            </div>
                                        </div>
                                        <div className="px-2.5 py-1.5 flex items-center gap-1.5">
                                            <div className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse flex-shrink-0" />
                                            <span className="text-[9px] font-medium text-muted-foreground">{output.label}</span>
                                        </div>
                                    </div>
                                ) : (
                                    /* ── State 2b: video exists, extract button ── */
                                    <div className="bg-popover border border-border/60 rounded-xl shadow-2xl overflow-hidden">
                                        <div className="px-3 pt-3 pb-1">
                                            <div className="flex items-center gap-2 mb-1.5">
                                                <Scan className="w-3 h-3 text-muted-foreground flex-shrink-0" />
                                                <span className="text-[10px] font-semibold text-foreground">{output.label}</span>
                                            </div>
                                            <p className="text-[9px] text-muted-foreground/70 leading-relaxed mb-2">
                                                Preview the extracted frame, then drag to connect.
                                            </p>
                                        </div>
                                        <div className="px-3 pb-3">
                                            <button
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    e.preventDefault();
                                                    console.log('[ExtractFrames] Button clicked!');
                                                    output.onExtractFrames?.();
                                                }}
                                                onMouseDown={(e) => e.stopPropagation()}
                                                className="w-full flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg bg-primary text-primary-foreground text-[9px] font-semibold transition-all hover:bg-primary/90 active:scale-[0.97] shadow-sm nopan nodrag nowheel cursor-pointer"
                                            >
                                                <Scan className="w-3 h-3" />
                                                Generate Preview
                                            </button>
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                );
            })}
        </div>
    );
});

NodeWrapper.displayName = "NodeWrapper";
