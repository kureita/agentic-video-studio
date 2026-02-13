"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, useCallback } from "react";
import { Plus, MoreHorizontal, Clock, Trash2, Pencil, Loader2 } from "lucide-react";
import { WorkflowPreview } from "@/components/workflow/workflow-preview";
import { Button } from "@/components/ui/button";
import { workflowApi, WorkflowListItem } from "@/lib/workflow-api";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

export default function DashboardPage() {
    const router = useRouter();
    const [workflows, setWorkflows] = useState<WorkflowListItem[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [editingId, setEditingId] = useState<string | null>(null);
    const [editingName, setEditingName] = useState("");
    const [menuOpenId, setMenuOpenId] = useState<string | null>(null);

    // Fetch workflows on mount
    useEffect(() => {
        loadWorkflows();
    }, []);

    const loadWorkflows = async () => {
        setIsLoading(true);
        setError(null);
        try {
            const response = await workflowApi.list();
            setWorkflows(response.data);
        } catch (err) {
            console.error("Failed to load workflows:", err);
            setError("Failed to load workflows");
            toast.error("Failed to load workflows");
        } finally {
            setIsLoading(false);
        }
    };

    const createNewWorkflow = useCallback(async () => {
        try {
            const response = await workflowApi.create("Untitled Workflow");
            const newWorkflow = response.data;
            router.push(`/dashboard/workflow?id=${newWorkflow.id}`);
        } catch (err) {
            console.error("Failed to create workflow:", err);
            toast.error("Failed to create workflow");
        }
    }, [router]);

    const handleRename = useCallback(async (id: string) => {
        if (!editingName.trim()) {
            setEditingId(null);
            return;
        }
        try {
            await workflowApi.update(id, { name: editingName.trim() });
            setWorkflows((prev) =>
                prev.map((w) => (w.id === id ? { ...w, name: editingName.trim() } : w))
            );
            toast.success("Workflow renamed");
        } catch (err) {
            console.error("Failed to rename workflow:", err);
            toast.error("Failed to rename workflow");
        }
        setEditingId(null);
        setMenuOpenId(null);
    }, [editingName]);

    const handleDelete = useCallback(async (id: string) => {
        if (!confirm("Are you sure you want to delete this workflow?")) return;
        try {
            await workflowApi.delete(id);
            setWorkflows((prev) => prev.filter((w) => w.id !== id));
            toast.success("Workflow deleted");
        } catch (err) {
            console.error("Failed to delete workflow:", err);
            toast.error("Failed to delete workflow");
        }
        setMenuOpenId(null);
    }, []);

    const startEditing = useCallback((workflow: WorkflowListItem) => {
        setEditingId(workflow.id);
        setEditingName(workflow.name);
        setMenuOpenId(null);
    }, []);

    const formatDate = (dateString: string) => {
        const date = new Date(dateString);
        const now = new Date();
        const diffMs = now.getTime() - date.getTime();
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMins / 60);
        const diffDays = Math.floor(diffHours / 24);

        if (diffMins < 1) return "Just now";
        if (diffMins < 60) return `${diffMins}m ago`;
        if (diffHours < 24) return `${diffHours}h ago`;
        if (diffDays < 7) return `${diffDays}d ago`;
        return date.toLocaleDateString();
    };

    return (
        <div className="space-y-5 animate-fade-in">
            {/* Header */}
            <div className="flex items-end justify-between">
                <div>
                    <h1 className="text-xl font-semibold tracking-tight">Workflows</h1>
                    <p className="text-[13px] text-muted-foreground/80 mt-0.5">
                        Manage your creative automation pipelines
                    </p>
                </div>
                <Button
                    onClick={createNewWorkflow}
                    size="sm"
                    className="h-8 px-3 text-[13px] font-medium shadow-sm"
                >
                    <Plus className="mr-1.5 h-3.5 w-3.5" />
                    New Workflow
                </Button>
            </div>

            {error && (
                <div className="bg-destructive/10 text-destructive text-[13px] px-3 py-2 rounded-md">
                    {error}
                </div>
            )}

            {isLoading ? (
                <div className="flex items-center justify-center py-12">
                    <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
                </div>
            ) : (
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
                    {workflows.map((workflow) => (
                        <div key={workflow.id} className="group relative">
                            <Link
                                href={{ pathname: '/dashboard/workflow', query: { id: workflow.id } }}
                                className="block"
                            >
                                <div className="relative aspect-[4/3] rounded-lg border border-border/60 bg-card overflow-hidden transition-all duration-200 hover:border-border hover:shadow-sm hover:shadow-primary/5">
                                    <div className="absolute inset-0 bg-[hsl(230,15%,8%)]">
                                        <WorkflowPreview nodes={workflow.nodes} edges={workflow.edges} />
                                    </div>

                                    {/* Node count badge */}
                                    {workflow.node_count > 0 && (
                                        <div className="absolute bottom-1.5 left-1.5 px-1.5 py-0.5 bg-background/70 backdrop-blur-sm rounded text-[10px] text-muted-foreground/80 font-medium">
                                            {workflow.node_count} {workflow.node_count === 1 ? "node" : "nodes"}
                                        </div>
                                    )}
                                </div>
                            </Link>

                            {/* Overlay Actions */}
                            <div className={cn(
                                "absolute top-1.5 right-1.5 transition-opacity duration-150",
                                menuOpenId === workflow.id ? "opacity-100" : "opacity-0 group-hover:opacity-100"
                            )}>
                                <div className="relative">
                                    <Button
                                        variant="ghost"
                                        size="icon"
                                        className="h-6 w-6 bg-background/60 backdrop-blur-sm hover:bg-background/90 rounded-md"
                                        onClick={(e) => {
                                            e.preventDefault();
                                            e.stopPropagation();
                                            setMenuOpenId(menuOpenId === workflow.id ? null : workflow.id);
                                        }}
                                    >
                                        <MoreHorizontal className="w-3.5 h-3.5" />
                                    </Button>

                                    {/* Dropdown Menu */}
                                    {menuOpenId === workflow.id && (
                                        <div className="absolute right-0 top-full mt-1 w-32 bg-popover border border-border/60 rounded-md shadow-lg shadow-black/20 py-0.5 z-50">
                                            <button
                                                className="w-full px-2.5 py-1.5 text-left text-[13px] hover:bg-muted/80 flex items-center gap-2 transition-colors"
                                                onClick={(e) => {
                                                    e.preventDefault();
                                                    e.stopPropagation();
                                                    startEditing(workflow);
                                                }}
                                            >
                                                <Pencil className="w-3 h-3" />
                                                Rename
                                            </button>
                                            <button
                                                className="w-full px-2.5 py-1.5 text-left text-[13px] text-destructive hover:bg-destructive/10 flex items-center gap-2 transition-colors"
                                                onClick={(e) => {
                                                    e.preventDefault();
                                                    e.stopPropagation();
                                                    handleDelete(workflow.id);
                                                }}
                                            >
                                                <Trash2 className="w-3 h-3" />
                                                Delete
                                            </button>
                                        </div>
                                    )}
                                </div>
                            </div>

                            <div className="mt-2 px-0.5">
                                {editingId === workflow.id ? (
                                    <input
                                        type="text"
                                        value={editingName}
                                        onChange={(e) => setEditingName(e.target.value)}
                                        onBlur={() => handleRename(workflow.id)}
                                        onKeyDown={(e) => {
                                            if (e.key === "Enter") handleRename(workflow.id);
                                            if (e.key === "Escape") setEditingId(null);
                                        }}
                                        autoFocus
                                        className="text-[13px] font-medium bg-transparent border-b border-primary outline-none w-full"
                                    />
                                ) : (
                                    <h3 className="text-[13px] font-medium truncate group-hover:text-foreground transition-colors text-foreground/90">
                                        {workflow.name}
                                    </h3>
                                )}
                                <div className="flex items-center text-[11px] text-muted-foreground/60 mt-0.5">
                                    <Clock className="w-2.5 h-2.5 mr-1" />
                                    <span>{formatDate(workflow.updated_at)}</span>
                                </div>
                            </div>
                        </div>
                    ))}

                    {/* Create New Placeholder Card */}
                    <button
                        onClick={createNewWorkflow}
                        className="group/create relative aspect-[4/3] rounded-lg border border-dashed border-border/40 bg-transparent hover:border-border/70 hover:bg-muted/5 transition-all duration-200 flex flex-col items-center justify-center gap-1.5 text-muted-foreground/50 hover:text-muted-foreground/80"
                    >
                        <div className="w-8 h-8 rounded-full border border-current/30 flex items-center justify-center transition-colors">
                            <Plus className="w-4 h-4" />
                        </div>
                        <span className="text-[12px] font-medium">New workflow</span>
                    </button>
                </div>
            )}

            {/* Close menu when clicking outside */}
            {menuOpenId && (
                <div
                    className="fixed inset-0 z-40"
                    onClick={() => setMenuOpenId(null)}
                />
            )}
        </div>
    );
}
