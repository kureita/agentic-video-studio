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
}

export function WorkflowToolbar({
    onAddNode,
    activeTool,
    onToolChange,
    onUndo,
    onRedo,
    canUndo,
    canRedo,
}: WorkflowToolbarProps) {
    const [isSelectorOpen, setIsSelectorOpen] = useState(false);

    return (
        <>
            {/* ==================== Desktop Toolbar (left vertical) ==================== */}
            <div className="hidden md:flex absolute left-4 top-1/2 -translate-y-1/2 flex-col gap-2 z-10">
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
                </div>
            </div>

            {/* ==================== Mobile Toolbar (bottom horizontal) ==================== */}
            <div className="flex md:hidden absolute bottom-14 left-1/2 -translate-x-1/2 z-10">
                <div className="bg-card/95 backdrop-blur-md border border-border rounded-full p-1 flex flex-row items-center gap-0.5 shadow-xl">

                    {/* Add Button with Menu */}
                    <div className="relative">
                        <Button
                            variant="ghost"
                            size="icon"
                            className={cn(
                                "rounded-full w-9 h-9 hover:bg-accent",
                                isSelectorOpen ? "bg-accent text-accent-foreground" : ""
                            )}
                            onClick={() => setIsSelectorOpen(!isSelectorOpen)}
                        >
                            <Plus className="w-4 h-4" />
                        </Button>

                        {/* Popover Menu - Opens above on mobile */}
                        {isSelectorOpen && (
                            <div className="absolute bottom-12 left-0 z-50">
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

                    <div className="w-[1px] h-5 bg-border mx-0.5" />

                    {/* Primary Tools */}
                    <Button variant={activeTool === "pointer" ? "secondary" : "ghost"} size="icon" className="rounded-full w-9 h-9" onClick={() => onToolChange("pointer")}>
                        <MousePointer2 className="w-4 h-4" />
                    </Button>
                    <Button variant={activeTool === "hand" ? "secondary" : "ghost"} size="icon" className="rounded-full w-9 h-9" onClick={() => onToolChange("hand")}>
                        <Hand className="w-4 h-4" />
                    </Button>
                    <Button variant={activeTool === "cut" ? "secondary" : "ghost"} size="icon" className="rounded-full w-9 h-9" onClick={() => onToolChange("cut")}>
                        <Scissors className="w-4 h-4" />
                    </Button>

                    <div className="w-[1px] h-5 bg-border mx-0.5" />

                    {/* History */}
                    <Button
                        variant="ghost"
                        size="icon"
                        className="rounded-full w-9 h-9 text-muted-foreground hover:text-foreground disabled:opacity-50"
                        onClick={onUndo}
                        disabled={!canUndo}
                    >
                        <Undo2 className="w-4 h-4" />
                    </Button>
                    <Button
                        variant="ghost"
                        size="icon"
                        className="rounded-full w-9 h-9 text-muted-foreground hover:text-foreground disabled:opacity-50"
                        onClick={onRedo}
                        disabled={!canRedo}
                    >
                        <Redo2 className="w-4 h-4" />
                    </Button>
                </div>
            </div>
        </>
    );
}
