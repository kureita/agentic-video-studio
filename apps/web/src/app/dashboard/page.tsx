"use client";

import Link from "next/link";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { useEffect, useState, useCallback, useRef } from "react";
import { Plus, MoreHorizontal, Clock, Trash2, Pencil, Loader2, ArrowUp, Sparkles, Film, AlertCircle, ChevronDown, Paperclip, X } from "lucide-react";
import { WorkflowPreview } from "@/components/workflow/workflow-preview";
import { Button } from "@/components/ui/button";
import { S3Image } from "@/components/ui/s3-image";
import { workflowApi, WorkflowListItem } from "@/lib/workflow-api";
import { workflowInspirations, WorkflowInspiration } from "@/lib/inspirations"
import { cn, ALLOWED_MEDIA_TYPES } from "@/lib/utils";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { motion, AnimatePresence } from "framer-motion";

interface Attachment {
    url: string;
    type: string;
    filename: string;
    file?: File;
}

const FORK_SESSION_KEY = "kureita_fork_workflow_id";

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
    const [isUploading, setIsUploading] = useState(false);
    const [pendingAttachments, setPendingAttachments] = useState<Attachment[]>([]);
    const [selectedModel, setSelectedModel] = useState("Gemini 3.1 Pro Preview (High)");
    const [showModelMenu, setShowModelMenu] = useState(false);
    const [creatingInspirationId, setCreatingInspirationId] = useState<string | null>(null);
    const heroInputRef = useRef<HTMLTextAreaElement>(null);
    const modelMenuRef = useRef<HTMLDivElement>(null);

    // Auto-resize textarea
    useEffect(() => {
        if (heroInputRef.current) {
            heroInputRef.current.style.height = "0";
            const scrollHeight = Math.min(heroInputRef.current.scrollHeight, 160);
            heroInputRef.current.style.height = `${scrollHeight}px`;
        }
    }, [heroInput]);

    useEffect(() => {
        const handleClickOutside = (e: MouseEvent) => {
            if (modelMenuRef.current && !modelMenuRef.current.contains(e.target as Node)) {
                setShowModelMenu(false);
            }
        };
        if (showModelMenu) {
            document.addEventListener('mousedown', handleClickOutside);
            return () => document.removeEventListener('mousedown', handleClickOutside);
        }
    }, [showModelMenu]);

    // Check for pending workflow redirect (from public viewer → login → here)
    useEffect(() => {
        const pendingId = sessionStorage.getItem(FORK_SESSION_KEY);
        if (pendingId) {
            sessionStorage.removeItem(FORK_SESSION_KEY);
            router.replace(`/dashboard/workflow/?id=${pendingId}`);
            return;
        }
    }, [router]);

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

    const handleFileUpload = (files: FileList | null) => {
        if (!files || files.length === 0) return;

        const allowedTypes = ALLOWED_MEDIA_TYPES;
        const newAttachments: Attachment[] = [];
        let hasInvalidFiles = false;

        for (const file of Array.from(files)) {
            if (!allowedTypes.includes(file.type)) {
                hasInvalidFiles = true;
                continue;
            }

            newAttachments.push({
                filename: file.name,
                url: URL.createObjectURL(file),
                type: file.type,
                file: file
            });
        }

        if (hasInvalidFiles) {
            toast.error("Format not supported. Please use accepted image, video, or audio formats.");
        }

        if (newAttachments.length > 0) {
            setPendingAttachments((prev) => [...prev, ...newAttachments]);
        }
    };

    const handleRemoveAttachment = (index: number) => {
        setPendingAttachments((prev) => {
            const att = prev[index];
            if (att.url.startsWith('blob:')) {
                URL.revokeObjectURL(att.url);
            }
            return prev.filter((_, i) => i !== index);
        });
    };

    const createFromPrompt = useCallback(async () => {
        let userMessage = heroInput.trim();
        const finalAttachments = [...pendingAttachments];
        if ((!userMessage && finalAttachments.length === 0) || isCreating || isUploading) return;

        setIsCreating(true);

        // Upload pending files first
        const filesToUpload = finalAttachments.filter(a => a.file);
        if (filesToUpload.length > 0) {
            setIsUploading(true);
            try {
                for (let i = 0; i < finalAttachments.length; i++) {
                    const att = finalAttachments[i];
                    if (att.file) {
                        const formData = new FormData();
                        formData.append("file", att.file);
                        const response = await api.post("/api/assets/upload", formData, {
                            headers: { "Content-Type": "multipart/form-data" },
                        });
                        if (response.data.success) {
                            if (att.url.startsWith('blob:')) {
                                URL.revokeObjectURL(att.url);
                            }
                            finalAttachments[i] = {
                                filename: response.data.filename,
                                url: response.data.url,
                                type: response.data.type
                            };
                        } else {
                            throw new Error("Upload failed for " + att.filename);
                        }
                    }
                }
            } catch (error) {
                console.error("Upload error:", error);
                toast.error("Failed to upload attachments");
                setIsUploading(false);
                setIsCreating(false);
                return;
            }
            setIsUploading(false);
        }

        if (finalAttachments.length > 0) {
            const attachmentLines = finalAttachments.map(
                (att) => `[Attached: ${att.filename}] (${att.type}) - URL: ${att.url}`
            );
            userMessage += (userMessage ? '\n' : '') + attachmentLines.join('\n');
        }

        try {
            const response = await workflowApi.create("Untitled Workflow");
            const newWorkflow = response.data;

            // store prompt and model for the agent sidebar to pick up
            sessionStorage.setItem("kureita_initial_prompt", userMessage);
            sessionStorage.setItem("kureita_initial_model", selectedModel);

            router.push(`/dashboard/workflow?id=${newWorkflow.id}`);
        } catch (err) {
            console.error("Failed to create workflow:", err);
            toast.error("Failed to create workflow");
            setIsCreating(false);
        }
    }, [heroInput, isCreating, isUploading, pendingAttachments, selectedModel, router]);

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
                        "relative rounded-xl border transition-all duration-200",
                        "bg-muted/30 border-border/50",
                        "focus-within:border-primary/40 focus-within:bg-muted/50",
                        "shadow-sm focus-within:shadow-md focus-within:shadow-primary/5"
                    )}>
                        {/* Inline Attachment Previews */}
                        <AnimatePresence>
                            {pendingAttachments.length > 0 && (
                                <motion.div
                                    initial={{ height: 0, opacity: 0 }}
                                    animate={{ height: "auto", opacity: 1 }}
                                    exit={{ height: 0, opacity: 0 }}
                                    className="overflow-hidden"
                                >
                                    <div className="flex flex-wrap gap-1.5 px-3 pt-2.5">
                                        {pendingAttachments.map((att, idx) => (
                                            <motion.div
                                                key={`${att.filename}-${idx}`}
                                                initial={{ scale: 0.8, opacity: 0 }}
                                                animate={{ scale: 1, opacity: 1 }}
                                                exit={{ scale: 0.8, opacity: 0 }}
                                                transition={{ duration: 0.15 }}
                                                className="group/att relative"
                                            >
                                                {att.type.startsWith("image") ? (
                                                    <div className="relative">
                                                        <div className="h-14 w-14 rounded-lg overflow-hidden border border-border/40 bg-muted/40">
                                                            {att.url.startsWith('blob:') ? (
                                                                // eslint-disable-next-line @next/next/no-img-element
                                                                <img src={att.url} alt={att.filename} className="w-full h-full object-cover" />
                                                            ) : (
                                                                <S3Image src={att.url} alt={att.filename} fill className="object-cover" unoptimized />
                                                            )}
                                                        </div>
                                                        <button
                                                            onClick={() => handleRemoveAttachment(idx)}
                                                            className="absolute -top-1.5 -right-1.5 w-4 h-4 rounded-full bg-destructive text-destructive-foreground flex items-center justify-center opacity-0 group-hover/att:opacity-100 transition-opacity cursor-pointer shadow-sm z-10"
                                                        >
                                                            <X className="w-2.5 h-2.5" />
                                                        </button>
                                                    </div>
                                                ) : (
                                                    <div className="relative flex items-center gap-1.5 h-8 px-2.5 rounded-lg border border-border/40 bg-muted/40 text-left">
                                                        <Paperclip className="w-3 h-3 text-muted-foreground/60 shrink-0" />
                                                        <span className="text-[11px] text-muted-foreground truncate max-w-[80px]">{att.filename}</span>
                                                        <button
                                                            onClick={() => handleRemoveAttachment(idx)}
                                                            className="p-0.5 rounded hover:bg-muted text-muted-foreground/40 hover:text-muted-foreground transition-colors cursor-pointer shrink-0"
                                                        >
                                                            <X className="w-3 h-3" />
                                                        </button>
                                                    </div>
                                                )}
                                            </motion.div>
                                        ))}
                                        {isUploading && (
                                            <div className="h-14 w-14 rounded-lg border border-border/40 bg-muted/40 flex items-center justify-center">
                                                <Loader2 className="w-4 h-4 animate-spin text-muted-foreground/50" />
                                            </div>
                                        )}
                                    </div>
                                    <div className="px-4 pb-2 pt-1 flex items-start gap-1.5 opacity-60">
                                        <div className="mt-[4px] w-1 h-1 rounded-full bg-muted-foreground"></div>
                                        <p className="text-[10px] text-muted-foreground leading-tight text-left">
                                            Media assets are routed directly to your workflow. AI analysis for images and videos is coming soon, we&apos;re working hard on it!
                                        </p>
                                    </div>
                                </motion.div>
                            )}
                        </AnimatePresence>

                        <textarea
                            ref={heroInputRef}
                            rows={1}
                            value={heroInput}
                            onChange={(e) => setHeroInput(e.target.value)}
                            onKeyDown={(e) => {
                                if (e.key === "Enter" && !e.shiftKey) {
                                    e.preventDefault();
                                    if (heroInput.trim() || pendingAttachments.length > 0) {
                                        createFromPrompt();
                                    }
                                }
                            }}
                            placeholder="Describe your video idea..."
                            disabled={isCreating}
                            className={cn(
                                "w-full resize-none bg-transparent px-3.5 pt-3 pb-1 text-[13px] placeholder:text-muted-foreground/40",
                                "focus:outline-none leading-relaxed",
                                "min-h-[60px] max-h-[160px]",
                                isCreating && "opacity-50 cursor-not-allowed"
                            )}
                        />
                        <div className="flex items-center justify-end gap-1.5 px-2.5 pb-2 pt-0.5">
                            {/* Right actions: Model select + Upload + Submit */}
                            {/* Model selector */}
                            <div className="relative" ref={modelMenuRef}>
                                <button
                                    onClick={() => setShowModelMenu(!showModelMenu)}
                                    className={cn(
                                        "flex items-center gap-1.5 px-2 py-1 rounded-md text-[11px] transition-colors cursor-pointer",
                                        "text-muted-foreground/50 hover:text-muted-foreground hover:bg-muted/60",
                                        showModelMenu && "text-muted-foreground bg-muted/60",
                                        isCreating && "opacity-50 cursor-not-allowed"
                                    )}
                                    disabled={isCreating || isUploading}
                                >
                                    <ChevronDown className="w-3.5 h-3.5" />
                                    <span>{selectedModel}</span>
                                </button>

                                {/* Model Menu Dropdown */}
                                <AnimatePresence>
                                    {showModelMenu && (
                                        <motion.div
                                            initial={{ opacity: 0, y: -4, scale: 0.96 }}
                                            animate={{ opacity: 1, y: 0, scale: 1 }}
                                            exit={{ opacity: 0, y: -4, scale: 0.96 }}
                                            transition={{ duration: 0.12 }}
                                            className="absolute top-full right-0 mt-2 w-64 bg-popover text-popover-foreground rounded-lg border shadow-xl overflow-hidden z-[100] text-left"
                                        >
                                            <div className="px-3 py-2 text-[11px] text-muted-foreground border-b border-border/50">
                                                Model
                                            </div>
                                            <div className="max-h-[240px] overflow-y-auto flex flex-col">
                                                {[
                                                    "Gemini 3.1 Pro Preview (High)",
                                                    "Gemini 3.1 Flash Lite Preview (Low)",
                                                    "Claude 4.6 Opus (High)",
                                                    "Claude 4.6 Sonnet (Medium)",
                                                    "Claude 4.5 Haiku (Low)",
                                                    "GPT-5.4 Pro (High)",
                                                    "GPT-5 Mini (Medium)",
                                                    "GPT-5 Nano (Low)"
                                                ].map((modelName) => (
                                                    <button
                                                        key={modelName}
                                                        onClick={() => {
                                                            setSelectedModel(modelName);
                                                            setShowModelMenu(false);
                                                        }}
                                                        className={cn(
                                                            "w-full text-left px-2 py-2 text-[11px] hover:bg-accent/80 hover:text-accent-foreground cursor-pointer flex items-center justify-between",
                                                            selectedModel === modelName && "bg-accent/60 text-accent-foreground font-medium"
                                                        )}
                                                    >
                                                        <span className={cn(selectedModel !== modelName && "text-muted-foreground/90")}>{modelName}</span>
                                                    </button>
                                                ))}
                                            </div>
                                        </motion.div>
                                    )}
                                </AnimatePresence>
                            </div>

                            {/* Attachment button */}
                            <label
                                className={cn(
                                    "p-1.5 rounded-md transition-colors cursor-pointer",
                                    "text-muted-foreground/40 hover:text-muted-foreground hover:bg-muted/60",
                                    (isUploading || isCreating) && "opacity-50 cursor-not-allowed"
                                )}
                            >
                                <Paperclip className="w-3.5 h-3.5" />
                                <input
                                    type="file"
                                    className="hidden"
                                    onChange={(e) => handleFileUpload(e.target.files)}
                                    disabled={isUploading || isCreating}
                                    accept="image/*,video/*,audio/*"
                                    multiple
                                />
                            </label>

                            <button
                                onClick={createFromPrompt}
                                disabled={(!heroInput.trim() && pendingAttachments.length === 0) || isCreating || isUploading}
                                className={cn(
                                    "p-1.5 rounded-lg transition-all duration-200 cursor-pointer",
                                    heroInput.trim() || pendingAttachments.length > 0
                                        ? "bg-primary text-primary-foreground shadow-sm hover:shadow-md hover:bg-primary/90"
                                        : "bg-muted/60 text-muted-foreground/30 cursor-not-allowed"
                                )}
                            >
                                {isCreating || isUploading ? (
                                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                                ) : (
                                    <ArrowUp className="w-3.5 h-3.5" />
                                )}
                            </button>
                        </div>
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
                ) : (
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
                                            {/* Thumbnail or nodes preview or gradient placeholder */}
                                            {workflow.thumbnail_url ? (
                                                <S3Image
                                                    src={workflow.thumbnail_url}
                                                    alt={workflow.name}
                                                    className="absolute inset-0 w-full h-full object-cover"
                                                    fill
                                                    unoptimized
                                                />
                                            ) : (workflow.nodes && workflow.nodes.length > 0) ? (
                                                <div className="absolute inset-0 bg-muted/40 pointer-events-none">
                                                    <WorkflowPreview
                                                        nodes={workflow.nodes.map(n => ({
                                                            id: n.id,
                                                            type: n.type,
                                                            position: n.position,
                                                        }))}
                                                        edges={(workflow.edges || []).map(e => ({
                                                            id: e.id,
                                                            source: e.source,
                                                            target: e.target,
                                                        }))}
                                                    />
                                                </div>
                                            ) : (
                                                <div className="absolute inset-0 bg-muted/40">
                                                    <div className="absolute inset-0 flex items-center justify-center">
                                                        <Image src="/kureita_logo.svg" alt="Workflow" width={32} height={32} className="w-8 h-8 opacity-40 invert mix-blend-screen" unoptimized />
                                                    </div>
                                                </div>
                                            )}

                                            {/* Status badge */}
                                            {workflow.status && workflow.status !== 'draft' && workflow.status !== 'ready' && (
                                                <div className={cn(
                                                    "absolute top-1.5 left-1.5 px-1.5 py-0.5 rounded text-[10px] font-medium flex items-center gap-1 backdrop-blur-sm",
                                                    workflow.status === 'generating' && "bg-amber-500/20 text-amber-400 border border-amber-500/20",
                                                    workflow.status === 'failed' && "bg-red-500/20 text-red-400 border border-red-500/20",
                                                )}
                                                >
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
                                        "border-border/40 bg-muted/40",
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
