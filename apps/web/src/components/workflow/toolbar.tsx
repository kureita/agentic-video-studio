"use client";

import { useState } from "react";
import {
    Plus,
    Hand,
    Scissors,
    MessageSquare,
    Undo2,
    Redo2,
    Settings,
    MousePointer2,
    Play,
    Loader2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { NodeSelector } from "./node-selector";

export interface WorkflowToolbarProps {
    onAddNode: (type: string) => void;
    activeTool: string;
    onToolChange: (tool: string) => void;
    onUndo: () => void;
    onRedo: () => void;
    canUndo: boolean;
    canRedo: boolean;
    onRunAll?: () => void;
    isRunningAll?: boolean;
    executionProgress?: { current: number; total: number } | null;
}

export function WorkflowToolbar({
    onAddNode,
    activeTool,
    onToolChange,
    onUndo,
    onRedo,
    canUndo,
    canRedo,
    onRunAll,
    isRunningAll,
    executionProgress,
}: WorkflowToolbarProps) {
    const [isSelectorOpen, setIsSelectorOpen] = useState(false);

    return (
        <div className="absolute left-4 top-1/2 -translate-y-1/2 flex flex-col gap-2 z-10">
            <div className="bg-card border border-border rounded-full p-1 flex flex-col gap-1 shadow-lg">

                {/* Add Button with Menu */}
                <div className="relative">
                    <Button
                        variant="ghost"
                        size="icon"
                        className={cn(
                            "rounded-full w-10 h-10 hover:bg-accent",
                            isSelectorOpen ? "bg-accent text-accent-foreground" : ""
                        )}
                        onClick={() => setIsSelectorOpen(!isSelectorOpen)}
                    >
                        <Plus className="w-5 h-5" />
                    </Button>

                    {/* Popover Menu */}
                    {isSelectorOpen && (
                        <div className="absolute left-14 top-0 z-50">
                            <NodeSelector
                                onSelect={(type) => {
                                    onAddNode(type);
                                    setIsSelectorOpen(false);
                                }}
                                onClose={() => setIsSelectorOpen(false)}
                            />
                        </div>
                    )}
                </div>

                <div className="w-full h-[1px] bg-border my-1" />

                {/* Primary Tools */}
                <Button variant={activeTool === "pointer" ? "secondary" : "ghost"} size="icon" className="rounded-full w-10 h-10" onClick={() => onToolChange("pointer")}>
                    <MousePointer2 className="w-5 h-5" />
                </Button>
                <Button variant={activeTool === "hand" ? "secondary" : "ghost"} size="icon" className="rounded-full w-10 h-10" onClick={() => onToolChange("hand")}>
                    <Hand className="w-5 h-5" />
                </Button>
                <Button variant={activeTool === "cut" ? "secondary" : "ghost"} size="icon" className="rounded-full w-10 h-10" onClick={() => onToolChange("cut")}>
                    <Scissors className="w-5 h-5" />
                </Button>
                <Button variant={activeTool === "comment" ? "secondary" : "ghost"} size="icon" className="rounded-full w-10 h-10" onClick={() => onToolChange("comment")}>
                    <MessageSquare className="w-5 h-5" />
                </Button>

                <div className="w-full h-[1px] bg-border my-1" />

                {/* History */}
                <Button
                    variant="ghost"
                    size="icon"
                    className="rounded-full w-10 h-10 text-muted-foreground hover:text-foreground disabled:opacity-50"
                    onClick={onUndo}
                    disabled={!canUndo}
                >
                    <Undo2 className="w-5 h-5" />
                </Button>
                <Button
                    variant="ghost"
                    size="icon"
                    className="rounded-full w-10 h-10 text-muted-foreground hover:text-foreground disabled:opacity-50"
                    onClick={onRedo}
                    disabled={!canRedo}
                >
                    <Redo2 className="w-5 h-5" />
                </Button>

                <div className="w-full h-[1px] bg-border my-1" />

                <Button variant="ghost" size="icon" className="rounded-full w-10 h-10 text-muted-foreground hover:text-foreground">
                    <Settings className="w-5 h-5" />
                </Button>

                {onRunAll && (
                    <>
                        <div className="w-full h-[1px] bg-border my-1" />

                        {/* Run All Button */}
                        <Button
                            variant="ghost"
                            size="icon"
                            className={cn(
                                "rounded-full w-10 h-10 transition-all duration-200",
                                isRunningAll
                                    ? "text-amber-500 bg-amber-500/10 hover:bg-amber-500/20"
                                    : "text-green-500 hover:text-green-600 hover:bg-green-500/10"
                            )}
                            onClick={onRunAll}
                            disabled={isRunningAll}
                            title={isRunningAll
                                ? `Running... ${executionProgress ? `${executionProgress.current}/${executionProgress.total}` : ""}`
                                : "Run All Nodes"
                            }
                        >
                            {isRunningAll ? (
                                <Loader2 className="w-5 h-5 animate-spin" />
                            ) : (
                                <Play className="w-5 h-5 fill-current" />
                            )}
                        </Button>

                        {/* Progress indicator */}
                        {isRunningAll && executionProgress && executionProgress.total > 0 && (
                            <div className="text-[9px] text-center font-mono text-amber-500/80 -mt-1">
                                {executionProgress.current}/{executionProgress.total}
                            </div>
                        )}
                    </>
                )}
            </div>
        </div>
    );
}
