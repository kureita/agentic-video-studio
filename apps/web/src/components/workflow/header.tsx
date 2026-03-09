"use client";

import { ArrowLeft, Loader2, CheckCircle2, Cloud, MessageSquare, Play } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useWorkflowStore } from "@/lib/workflow-store";
import { useRouter } from "next/navigation";
import { useState, useEffect } from "react";
import { useMobileTab } from "@/app/dashboard/layout";

export function WorkflowHeader() {
    const router = useRouter();
    const { name, setName, isSaving, isDirty, saveWorkflow, isRunning, runWorkflow } = useWorkflowStore();
    const [editingName, setEditingName] = useState(name);
    const { setActiveTab } = useMobileTab();

    // Sync local state with store
    useEffect(() => {
        setEditingName(name);
    }, [name]);

    const handleNameBlur = () => {
        if (editingName.trim() !== name) {
            setName(editingName.trim());
            saveWorkflow();
        }
    };

    const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
        if (e.key === "Enter") {
            (e.currentTarget as HTMLInputElement).blur();
        }
    };

    return (
        <div className="h-12 md:h-14 border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 flex items-center justify-between px-2 md:px-4 sticky top-0 z-50">
            <div className="flex items-center gap-2 md:gap-4 min-w-0 flex-1">
                <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => router.push("/dashboard")}
                    className="shrink-0 w-8 h-8 md:w-9 md:h-9"
                >
                    <ArrowLeft className="w-4 h-4" />
                </Button>

                <div className="flex flex-col min-w-0 flex-1">
                    <Input
                        value={editingName}
                        onChange={(e) => setEditingName(e.target.value)}
                        onBlur={handleNameBlur}
                        onKeyDown={handleKeyDown}
                        className="h-7 md:h-8 w-full max-w-[200px] md:max-w-[300px] border-none shadow-none focus-visible:ring-1 px-2 font-medium bg-transparent text-xs md:text-sm"
                    />
                    <div className="flex items-center gap-1.5 px-2 text-[9px] md:text-[10px] text-muted-foreground">
                        {isSaving ? (
                            <>
                                <Loader2 className="w-2.5 h-2.5 md:w-3 md:h-3 animate-spin" />
                                <span>Saving...</span>
                            </>
                        ) : isDirty ? (
                            <>
                                <Cloud className="w-2.5 h-2.5 md:w-3 md:h-3" />
                                <span>Unsaved changes</span>
                            </>
                        ) : (
                            <>
                                <CheckCircle2 className="w-2.5 h-2.5 md:w-3 md:h-3 text-green-500" />
                                <span>All changes saved</span>
                            </>
                        )}
                    </div>
                </div>
            </div>

            <div className="flex items-center gap-2">
                {/* Run All Button (Visible on all screens) */}
                <Button
                    onClick={runWorkflow}
                    disabled={isRunning}
                    className="h-8 shadow-sm gap-2"
                    variant="default"
                >
                    {isRunning ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                        <Play className="w-4 h-4 fill-current" />
                    )}
                    <span className="hidden sm:inline">Run All</span>
                    <span className="sm:hidden">Run</span>
                </Button>

                {/* Mobile: Switch to AI Chat */}
                <button
                    onClick={() => setActiveTab("chat")}
                    className="md:hidden flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-muted/60 transition-colors cursor-pointer"
                    title="Switch to AI Chat"
                >
                    <MessageSquare className="w-4 h-4" />
                    <span>AI Chat</span>
                </button>
            </div>
        </div>
    );
}
