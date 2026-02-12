"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, useCallback } from "react";
import { Plus, MoreHorizontal, Clock, Trash2, Pencil, Loader2 } from "lucide-react";
import { WorkflowPreview } from "@/components/workflow/workflow-preview";
import { Button } from "@/components/ui/button";
import { workflowApi, WorkflowListItem } from "@/lib/workflow-api";
import { cn } from "@/lib/utils";

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
            setError("Failed to create workflow");
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
        } catch (err) {
            console.error("Failed to rename workflow:", err);
        }
        setEditingId(null);
        setMenuOpenId(null);
    }, [editingName]);

    const handleDelete = useCallback(async (id: string) => {
        if (!confirm("Are you sure you want to delete this workflow?")) return;
        try {
            await workflowApi.delete(id);
            setWorkflows((prev) => prev.filter((w) => w.id !== id));
        } catch (err) {
            console.error("Failed to delete workflow:", err);
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
        if (diffMins < 60) return `${diffMins} min ago`;
        if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? "s" : ""} ago`;
        if (diffDays < 7) return `${diffDays} day${diffDays > 1 ? "s" : ""} ago`;
        return date.toLocaleDateString();
    };

    return (
        <div className="space-y-8 animate-fade-in">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight">Workflows</h1>
                    <p className="text-muted-foreground mt-2">
                        Manage your creative automation pipelines.
                    </p>
                </div>
                <Button onClick={createNewWorkflow} size="lg" className="shadow-lg shadow-primary/20">
                    <Plus className="mr-2 h-4 w-4" />
                    New Workflow
                </Button>
            </div>

            {error && (
                <div className="bg-destructive/10 text-destructive px-4 py-3 rounded-lg">
                    {error}
                </div>
            )}

            {isLoading ? (
                <div className="flex items-center justify-center py-16">
                    <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
                </div>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {workflows.map((workflow) => (
                        <div key={workflow.id} className="group relative">
                            <Link
                                href={{ pathname: '/dashboard/workflow', query: { id: workflow.id } }}
                                className="block"
                            >
                                <div className="relative aspect-video rounded-lg border border-border bg-card overflow-hidden transition-all hover:border-accent hover:shadow-md">
                                    <div className="absolute inset-0 bg-[hsl(230,15%,10%)]">
                                        <WorkflowPreview nodes={workflow.nodes} edges={workflow.edges} />
                                    </div>

                                    {/* Node count badge */}
                                    {workflow.node_count > 0 && (
                                        <div className="absolute bottom-2 left-2 px-2 py-1 bg-background/80 backdrop-blur-sm rounded text-xs text-muted-foreground">
                                            {workflow.node_count} nodes
                                        </div>
                                    )}
                                </div>
                            </Link>

                            {/* Overlay Actions */}
                            <div className={cn(
                                "absolute top-2 right-2 transition-opacity",
                                menuOpenId === workflow.id ? "opacity-100" : "opacity-0 group-hover:opacity-100"
                            )}>
                                <div className="relative">
                                    <Button
                                        variant="ghost"
                                        size="icon"
                                        className="h-8 w-8 bg-background/50 hover:bg-background"
                                        onClick={(e) => {
                                            e.preventDefault();
                                            e.stopPropagation();
                                            setMenuOpenId(menuOpenId === workflow.id ? null : workflow.id);
                                        }}
                                    >
                                        <MoreHorizontal className="w-4 h-4" />
                                    </Button>

                                    {/* Dropdown Menu */}
                                    {menuOpenId === workflow.id && (
                                        <div className="absolute right-0 top-full mt-1 w-36 bg-popover border border-border rounded-md shadow-lg py-1 z-50">
                                            <button
                                                className="w-full px-3 py-1.5 text-left text-sm hover:bg-muted flex items-center gap-2"
                                                onClick={(e) => {
                                                    e.preventDefault();
                                                    e.stopPropagation();
                                                    startEditing(workflow);
                                                }}
                                            >
                                                <Pencil className="w-3.5 h-3.5" />
                                                Rename
                                            </button>
                                            <button
                                                className="w-full px-3 py-1.5 text-left text-sm text-destructive hover:bg-destructive/10 flex items-center gap-2"
                                                onClick={(e) => {
                                                    e.preventDefault();
                                                    e.stopPropagation();
                                                    handleDelete(workflow.id);
                                                }}
                                            >
                                                <Trash2 className="w-3.5 h-3.5" />
                                                Delete
                                            </button>
                                        </div>
                                    )}
                                </div>
                            </div>

                            <div className="mt-3">
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
                                        className="font-medium bg-transparent border-b border-primary outline-none w-full"
                                    />
                                ) : (
                                    <h3 className="font-medium truncate group-hover:text-primary transition-colors">
                                        {workflow.name}
                                    </h3>
                                )}
                                <div className="flex items-center text-xs text-muted-foreground mt-1">
                                    <Clock className="w-3 h-3 mr-1" />
                                    <span>Edited {formatDate(workflow.updated_at)}</span>
                                </div>
                            </div>
                        </div>
                    ))}

                    {/* Create New Placeholder Card */}
                    <button
                        onClick={createNewWorkflow}
                        className="group relative aspect-video rounded-lg border border-dashed border-border bg-transparent hover:border-accent/50 hover:bg-accent/5 transition-all flex flex-col items-center justify-center gap-2 text-muted-foreground hover:text-accent"
                    >
                        <div className="w-12 h-12 rounded-full border border-current flex items-center justify-center mb-2">
                            <Plus className="w-6 h-6" />
                        </div>
                        <span className="font-medium text-sm">Create new workflow</span>
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
