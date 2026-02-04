"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useState, useCallback } from "react";
import { ArrowLeft, Save, Play, Settings2, Loader2, Check, Pencil } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import FlowEditor from "@/components/workflow/flow-editor";
import { useWorkflowStore } from "@/lib/workflow-store";

export default function WorkflowEditorPage() {
    const params = useParams();
    const router = useRouter();
    const id = params.id as string;

    const {
        id: workflowId,
        name,
        isDirty,
        isSaving,
        isRunning,
        isLoading,
        error,
        setName,
        createWorkflow,
        saveWorkflow,
        runWorkflow,
    } = useWorkflowStore();

    const [isEditingName, setIsEditingName] = useState(false);
    const [editedName, setEditedName] = useState(name);

    // Handle "new" workflow - create one and redirect
    useEffect(() => {
        if (id === "new" && !workflowId) {
            createWorkflow("Untitled Workflow").then((newId) => {
                if (newId) {
                    router.replace(`/dashboard/workflow/${newId}`);
                }
            });
        }
    }, [id, workflowId, createWorkflow, router]);

    // Sync edited name with store name
    useEffect(() => {
        setEditedName(name);
    }, [name]);

    const handleSaveName = useCallback(() => {
        if (editedName.trim() && editedName !== name) {
            setName(editedName.trim());
        }
        setIsEditingName(false);
    }, [editedName, name, setName]);

    const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
        if (e.key === "Enter") {
            handleSaveName();
        } else if (e.key === "Escape") {
            setEditedName(name);
            setIsEditingName(false);
        }
    }, [handleSaveName, name]);

    const handleSave = useCallback(async () => {
        await saveWorkflow();
    }, [saveWorkflow]);

    const handleRun = useCallback(async () => {
        await runWorkflow();
    }, [runWorkflow]);

    // Show loading state while creating new workflow
    if (id === "new") {
        return (
            <div className="h-[calc(100vh-2rem)] flex flex-col items-center justify-center rounded-xl border border-border bg-background shadow-2xl">
                <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
                <p className="text-muted-foreground mt-4">
                    Creating workflow...
                </p>
            </div>
        );
    }

    return (
        <div className="h-[calc(100vh-2rem)] flex flex-col overflow-hidden rounded-xl border border-border bg-background shadow-2xl">
            {/* Editor Toolbar */}
            <div className="h-14 border-b border-border bg-card/50 px-4 flex items-center justify-between shrink-0">
                <div className="flex items-center gap-4">
                    <Link
                        href="/dashboard"
                        className="text-muted-foreground hover:text-foreground transition-colors p-2 -ml-2 rounded-md hover:bg-muted"
                    >
                        <ArrowLeft className="w-5 h-5" />
                    </Link>
                    <div className="h-4 w-[1px] bg-border" />
                    <div>
                        {isEditingName ? (
                            <input
                                type="text"
                                value={editedName}
                                onChange={(e) => setEditedName(e.target.value)}
                                onBlur={handleSaveName}
                                onKeyDown={handleKeyDown}
                                autoFocus
                                className="font-medium text-sm bg-transparent border-b border-primary outline-none px-0 py-0.5 min-w-[150px]"
                            />
                        ) : (
                            <button
                                onClick={() => setIsEditingName(true)}
                                className="group flex items-center gap-2 font-medium text-sm hover:text-primary transition-colors"
                            >
                                {name}
                                <Pencil className="w-3 h-3 opacity-0 group-hover:opacity-100 transition-opacity" />
                            </button>
                        )}
                        <p className="text-[10px] text-muted-foreground">
                            {isDirty ? "unsaved changes" : "saved"}
                        </p>
                    </div>
                </div>

                <div className="flex items-center gap-2">
                    {error && (
                        <span className="text-xs text-destructive mr-2">{error}</span>
                    )}
                    <Button variant="ghost" size="sm">
                        <Settings2 className="w-4 h-4 mr-2" />
                        Settings
                    </Button>
                    <Button
                        variant="outline"
                        size="sm"
                        className="hidden sm:flex"
                        onClick={handleSave}
                        disabled={isSaving || !isDirty}
                    >
                        {isSaving ? (
                            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        ) : isDirty ? (
                            <Save className="w-4 h-4 mr-2" />
                        ) : (
                            <Check className="w-4 h-4 mr-2 text-green-500" />
                        )}
                        {isSaving ? "Saving..." : isDirty ? "Save" : "Saved"}
                    </Button>
                    <Button
                        size="sm"
                        className="bg-accent text-accent-foreground hover:bg-accent/90"
                        onClick={handleRun}
                        disabled={isRunning}
                    >
                        {isRunning ? (
                            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        ) : (
                            <Play className="w-4 h-4 mr-2 fill-current" />
                        )}
                        {isRunning ? "Running..." : "Run Workflow"}
                    </Button>
                </div>
            </div>

            {/* Main Canvas Area */}
            <div className="flex-1 relative bg-grid-pattern h-full">
                {isLoading && (
                    <div className="absolute inset-0 z-50 flex flex-col items-center justify-center bg-background/80 backdrop-blur-sm">
                        <Loader2 className="w-8 h-8 animate-spin text-primary" />
                        <p className="text-muted-foreground mt-4">Loading workflow...</p>
                    </div>
                )}
                <FlowEditor workflowId={id} />
            </div>
        </div>
    );
}
