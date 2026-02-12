"use client";

import { ArrowLeft, Play, Loader2, CheckCircle2, Cloud } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useWorkflowStore } from "@/lib/workflow-store";
import { useRouter } from "next/navigation";
import { useState, useEffect } from "react";
import { cn } from "@/lib/utils";

export function WorkflowHeader() {
    const router = useRouter();
    const { name, setName, isSaving, isDirty, runWorkflow, isRunning, saveWorkflow } = useWorkflowStore();
    const [editingName, setEditingName] = useState(name);

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
        <div className="h-14 border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 flex items-center justify-between px-4 sticky top-0 z-50">
            <div className="flex items-center gap-4">
                <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => router.push("/dashboard")}
                    className="shrink-0"
                >
                    <ArrowLeft className="w-4 h-4" />
                </Button>

                <div className="flex flex-col">
                    <Input
                        value={editingName}
                        onChange={(e) => setEditingName(e.target.value)}
                        onBlur={handleNameBlur}
                        onKeyDown={handleKeyDown}
                        className="h-8 w-[200px] md:w-[300px] border-none shadow-none focus-visible:ring-1 px-2 font-medium bg-transparent text-sm"
                    />
                    <div className="flex items-center gap-1.5 px-2 text-[10px] text-muted-foreground">
                        {isSaving ? (
                            <>
                                <Loader2 className="w-3 h-3 animate-spin" />
                                <span>Saving...</span>
                            </>
                        ) : isDirty ? (
                            <>
                                <Cloud className="w-3 h-3" />
                                <span>Unsaved changes</span>
                            </>
                        ) : (
                            <>
                                <CheckCircle2 className="w-3 h-3 text-green-500" />
                                <span>All changes saved</span>
                            </>
                        )}
                    </div>
                </div>
            </div>

            <div className="flex items-center gap-2">
                <Button
                    onClick={() => runWorkflow()}
                    disabled={isRunning}
                    size="sm"
                    className={cn(
                        "gap-2 transition-all shadow-md active:scale-95",
                        isRunning ? "bg-accent text-accent-foreground" : "bg-primary text-primary-foreground hover:bg-primary/90"
                    )}
                >
                    {isRunning ? (
                        <>
                            <Loader2 className="w-4 h-4 animate-spin" />
                            Running...
                        </>
                    ) : (
                        <>
                            <Play className="w-4 h-4 fill-current" />
                            Run Workflow
                        </>
                    )}
                </Button>
            </div>
        </div>
    );
}
