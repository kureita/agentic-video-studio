"use client";

import Link from "next/link";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { useEffect, useState, useCallback, useRef } from "react";
import { Plus, MoreHorizontal, Clock, Trash2, Pencil, Loader2, ArrowRight, Sparkles, Film, AlertCircle } from "lucide-react";
import { WorkflowPreview } from "@/components/workflow/workflow-preview";
import { Button } from "@/components/ui/button";
import { workflowApi, WorkflowListItem } from "@/lib/workflow-api";
import { workflowInspirations, WorkflowInspiration } from "@/lib/inspirations"
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

    // Hero input state
    const [heroInput, setHeroInput] = useState("");
    const [isCreating, setIsCreating] = useState(false);
    const [creatingInspirationId, setCreatingInspirationId] = useState<string | null>(null);
    const heroInputRef = useRef<HTMLInputElement>(null);

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

    const createFromPrompt = useCallback(async () => {
        const prompt = heroInput.trim();
        if (!prompt || isCreating) return;

        setIsCreating(true);
        try {
            const response = await workflowApi.create("Untitled Workflow");
            const newWorkflow = response.data;

            // store prompt for the agent sidebar to pick up
            sessionStorage.setItem("kureita_initial_prompt", prompt);

            router.push(`/dashboard/workflow?id=${newWorkflow.id}`);
        } catch (err) {
            console.error("Failed to create workflow:", err);
            toast.error("Failed to create workflow");
            setIsCreating(false);
        }
    }, [heroInput, isCreating, router]);

    const createFromInspiration = useCallback(async (inspiration: WorkflowInspiration) => {
        if (creatingInspirationId) return;

        setCreatingInspirationId(inspiration.id);
        try {
            // create the workflow
            const createResponse = await workflowApi.create(inspiration.name);
            const newWorkflow = createResponse.data;

            // populate with inspiration nodes and edges
            await workflowApi.update(newWorkflow.id, {
                nodes: inspiration.nodes,
                edges: inspiration.edges,
            });

            router.push(`/dashboard/workflow?id=${newWorkflow.id}`);
        } catch (err) {
            console.error("Failed to create workflow:", err);
            toast.error("Failed to create workflow");
            setCreatingInspirationId(null);
        }
    }, [creatingInspirationId, router]);

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

    const hasWorkflows = workflows.length > 0;

    return (
        <div className="animate-fade-in">
            {/* hero input section */}
            <section className={cn(
                "flex flex-col items-center text-center",
                hasWorkflows ? "pt-10 pb-8" : "pt-20 pb-12"
            )}>
                <h1 className={cn(
                    "font-semibold tracking-tight text-foreground/90",
                    hasWorkflows ? "text-xl" : "text-2xl"
                )}>
                    What would you like to create?
                </h1>

                <div className="w-full max-w-xl mt-5">
                    <div className={cn(
                        "relative flex items-center rounded-xl border transition-all duration-200",
                        "bg-muted/20 border-border/50",
                        "focus-within:border-primary/40 focus-within:bg-muted/30",
                        "focus-within:shadow-lg focus-within:shadow-primary/5",
                    )}>
                        <input
                            ref={heroInputRef}
                            type="text"
                            value={heroInput}
                            onChange={(e) => setHeroInput(e.target.value)}
                            onKeyDown={(e) => {
                                if (e.key === "Enter" && heroInput.trim()) {
                                    createFromPrompt();
                                }
                            }}
                            placeholder="Describe your video idea..."
                            disabled={isCreating}
                            className={cn(
                                "flex-1 bg-transparent px-4 py-3 text-sm placeholder:text-muted-foreground/40",
                                "focus:outline-none",
                                isCreating && "opacity-50 cursor-not-allowed"
                            )}
                        />
                        <button
                            onClick={createFromPrompt}
                            disabled={!heroInput.trim() || isCreating}
                            className={cn(
                                "mr-2 p-2 rounded-lg transition-all duration-200",
                                heroInput.trim()
                                    ? "bg-primary text-primary-foreground shadow-sm hover:bg-primary/90"
                                    : "bg-transparent text-muted-foreground/25 cursor-default"
                            )}
                        >
                            {isCreating ? (
                                <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                                <ArrowRight className="w-4 h-4" />
                            )}
                        </button>
                    </div>

                    {/* Or create a blank workflow */}
                    <div className="mt-3 flex items-center justify-center">
                        <button
                            onClick={createNewWorkflow}
                            className="inline-flex items-center gap-1.5 text-[13px] text-muted-foreground/60 hover:text-foreground/80 transition-colors duration-200 py-1 px-2 rounded-md hover:bg-muted/30"
                        >
                            <Plus className="w-3.5 h-3.5" />
                            <span>or start with a blank workflow</span>
                        </button>
                    </div>
                </div>
            </section>

            <div className="px-4 md:px-6 pb-10 space-y-10">
                {/* error state */}
                {error && (
                    <div className="bg-destructive/10 text-destructive text-[13px] px-3 py-2 rounded-md">{error}</div>
                )}

                {/* recent section */}
                {isLoading ? (
                    <div className="flex items-center justify-center py-12">
                        <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
                    </div>
                ) : hasWorkflows && (
                    <section>
                        <div className="flex items-center justify-between mb-4">
                            <div>
                                <h2 className="text-sm font-semibold tracking-tight text-foreground/80">Recents</h2>
                            </div>
                            <Button
                                onClick={createNewWorkflow}
                                size="sm"
                                className="h-8 px-3 text-[13px] font-medium shadow-sm"
                            >
                                <Plus className="mr-1.5 h-3.5 w-3.5" /> New Workflow
                            </Button>
                        </div>

                        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
                            {workflows.map((workflow) => (
                                <div key={workflow.id} className="group relative">
                                    <Link
                                        href={{ pathname: "/dashboard/workflow", query: { id: workflow.id } }}
                                        className="block"
                                    >
                                        <div className="relative aspect-[4/3] rounded-lg border border-border/60 bg-card overflow-hidden transition-all duration-200 hover:border-border hover:shadow-sm hover:shadow-primary/5">
                                            {/* Thumbnail or gradient placeholder */}
                                            {workflow.thumbnail_url ? (
                                                <Image
                                                    src={workflow.thumbnail_url}
                                                    alt={workflow.name}
                                                    className="absolute inset-0 w-full h-full object-cover"
                                                    fill
                                                    unoptimized
                                                />
                                            ) : (
                                                <div className="absolute inset-0 bg-[hsl(220,15%,8%)]">
                                                    <div className="absolute inset-0 flex items-center justify-center">
                                                        <Film className="w-8 h-8 text-muted-foreground/20" />
                                                    </div>
                                                </div>
                                            )}

                                            {/* Status badge */}
                                            {workflow.status && workflow.status !== 'draft' && (
                                                <div className={cn(
                                                    "absolute top-1.5 left-1.5 px-1.5 py-0.5 rounded text-[10px] font-medium flex items-center gap-1 backdrop-blur-sm",
                                                    workflow.status === 'ready' && "bg-green-500/20 text-green-400 border border-green-500/20",
                                                    workflow.status === 'generating' && "bg-amber-500/20 text-amber-400 border border-amber-500/20",
                                                    workflow.status === 'failed' && "bg-red-500/20 text-red-400 border border-red-500/20",
                                                )}
                                                >
                                                    {workflow.status === 'ready' && <><Sparkles className="w-2.5 h-2.5" /> Ready</>}
                                                    {workflow.status === 'generating' && <><Loader2 className="w-2.5 h-2.5 animate-spin" /> Generating</>}
                                                    {workflow.status === 'failed' && <><AlertCircle className="w-2.5 h-2.5" /> Failed</>}
                                                </div>
                                            )}

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

                            {/* create new placeholder card */}
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
                    </section>
                )}

                {/* ─── Inspirations Section ─── */}
                {!isLoading && (
                    <section>
                        <div className="mb-4">
                            <h2 className="text-sm font-semibold tracking-tight text-foreground/80">
                                {hasWorkflows ? "Inspirations" : "Or start from an inspiration"}
                            </h2>
                        </div>

                        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
                            {workflowInspirations.map((template) => (
                                <button
                                    key={template.id}
                                    onClick={() => createFromInspiration(template)}
                                    disabled={!!creatingInspirationId}
                                    className="group/tpl text-left transition-all duration-200 focus:outline-none disabled:opacity-70"
                                >
                                    {/* Thumbnail */}
                                    <div className={cn(
                                        "relative aspect-[16/10] rounded-lg border overflow-hidden transition-all duration-200",
                                        "border-border/40 bg-[hsl(220,15%,8%)]",
                                        "group-hover/tpl:border-border/80 group-hover/tpl:shadow-md group-hover/tpl:shadow-primary/5",
                                        "group-focus-visible/tpl:border-primary/40 group-focus-visible/tpl:ring-1 group-focus-visible/tpl:ring-primary/20",
                                        creatingInspirationId === template.id && "border-primary/40"
                                    )}>
                                        <WorkflowPreview
                                            nodes={template.nodes.map(n => ({
                                                id: n.id,
                                                type: n.type,
                                                position: n.position,
                                            }))}
                                            edges={template.edges.map(e => ({
                                                id: e.id,
                                                source: e.source,
                                                target: e.target,
                                            }))}
                                        />

                                        {/* Loading overlay */}
                                        {creatingInspirationId === template.id && (
                                            <div className="absolute inset-0 bg-background/60 backdrop-blur-sm flex items-center justify-center">
                                                <Loader2 className="w-5 h-5 animate-spin text-primary" />
                                            </div>
                                        )}
                                    </div>

                                    <div className="mt-2.5 px-0.5 min-w-0">
                                        <h3 className="text-[13px] font-medium text-foreground/85 group-hover/tpl:text-foreground transition-colors truncate">
                                            {template.name}
                                        </h3>
                                        <p className="text-[11px] text-muted-foreground/50 mt-0.5 line-clamp-2 leading-relaxed">
                                            {template.description}
                                        </p>
                                        {template.insight && (
                                            <p className="text-[10px] text-muted-foreground/45 mt-1 font-medium truncate">
                                                {template.insight}
                                            </p>
                                        )}
                                    </div>
                                </button>
                            ))}
                        </div>
                    </section>
                )}
            </div>

            {/* close menu when clicking outsie */}
            {menuOpenId && (
                <div className="fixed inset-0 z-40" onClick={() => setMenuOpenId(null)} />
            )}
        </div>
    )
}
