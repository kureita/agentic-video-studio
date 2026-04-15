"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import {
    FolderOpen,
    FolderClosed,
    Image as ImageIcon,
    Video,
    Music,
    Upload,
    Film,
    ChevronRight,
    X,
    Loader2,
    ExternalLink,
    Copy,
    Check,
    Package,
    Trash2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import { S3Image } from "@/components/ui/s3-image";
import { motion, AnimatePresence } from "framer-motion";
import Link from "next/link";
import { toast } from "sonner";

// ── Types ────────────────────────────────────────────────────────────

interface AssetItem {
    node_id: string;
    node_type: string;
    asset_category: string;
    url: string;
    presigned_url: string;
    node_data?: Record<string, unknown> | null;
}

interface WorkflowAssets {
    workflow_id: string;
    workflow_name: string;
    updated_at: string;
    assets: AssetItem[];
}

interface UserAssetsResponse {
    workspaces: WorkflowAssets[];
    total_assets: number;
}

// ── Category config ──────────────────────────────────────────────────

const CATEGORY_CONFIG: Record<string, { label: string; icon: React.ReactNode; color: string; bgColor: string }> = {
    generated_image: {
        label: "Generated Images",
        icon: <ImageIcon className="w-3.5 h-3.5" />,
        color: "text-emerald-400",
        bgColor: "bg-emerald-500/10",
    },
    generated_video: {
        label: "Generated Videos",
        icon: <Video className="w-3.5 h-3.5" />,
        color: "text-purple-400",
        bgColor: "bg-purple-500/10",
    },
    generated_audio: {
        label: "Generated Audio",
        icon: <Music className="w-3.5 h-3.5" />,
        color: "text-blue-400",
        bgColor: "bg-blue-500/10",
    },
    uploaded: {
        label: "Uploaded Assets",
        icon: <Upload className="w-3.5 h-3.5" />,
        color: "text-amber-400",
        bgColor: "bg-amber-500/10",
    },
    rendered_video: {
        label: "Rendered Videos",
        icon: <Film className="w-3.5 h-3.5" />,
        color: "text-rose-400",
        bgColor: "bg-rose-500/10",
    },
};

const KNOWN_CATEGORIES = new Set(Object.keys(CATEGORY_CONFIG));
const CATEGORY_ORDER = ["generated_image", "generated_video", "generated_audio", "uploaded", "rendered_video"];

// ── Asset Thumbnail ──────────────────────────────────────────────────

function AssetThumbnail({ asset, onClick }: { asset: AssetItem; onClick: () => void }) {
    const isImage =
        asset.asset_category === "generated_image" ||
        (asset.asset_category === "uploaded" && asset.presigned_url.match(/\.(jpg|jpeg|png|webp|gif)/i));
    const isVideo =
        asset.asset_category === "generated_video" ||
        asset.asset_category === "rendered_video" ||
        (asset.asset_category === "uploaded" && asset.presigned_url.match(/\.(mp4|mov|webm)/i));
    const isAudio =
        asset.asset_category === "generated_audio" ||
        (asset.asset_category === "uploaded" && asset.presigned_url.match(/\.(mp3|wav|ogg|flac)/i));

    const cat = CATEGORY_CONFIG[asset.asset_category];
    if (!cat) return null;

    return (
        <button
            onClick={onClick}
            draggable
            onDragStart={(e) => {
                e.dataTransfer.setData("text/plain", asset.url);
                e.dataTransfer.setData("application/kureita-asset", JSON.stringify({
                    type: "asset",
                    url: asset.url,
                    presigned_url: asset.presigned_url,
                    asset_category: asset.asset_category,
                    node_type: asset.node_type,
                    node_data: asset.node_data || {},
                }));
                e.dataTransfer.effectAllowed = "copy";
            }}
            className="group relative aspect-square rounded-lg overflow-hidden border border-border/40 bg-muted/20 hover:border-border/70 hover:bg-muted/40 transition-all duration-200 cursor-pointer focus:outline-none focus-visible:ring-1 focus-visible:ring-primary/40"
        >
            {isImage ? (
                <S3Image src={asset.url} alt="Asset" fill className="object-cover" unoptimized />
            ) : isVideo ? (
                <div className="absolute inset-0 flex items-center justify-center bg-black/40">
                    <div className={cn("w-8 h-8 rounded-full flex items-center justify-center", cat.bgColor)}>
                        <Video className={cn("w-4 h-4", cat.color)} />
                    </div>
                </div>
            ) : isAudio ? (
                <div className="absolute inset-0 flex items-center justify-center bg-black/20">
                    <div className={cn("w-8 h-8 rounded-full flex items-center justify-center", cat.bgColor)}>
                        <Music className={cn("w-4 h-4", cat.color)} />
                    </div>
                </div>
            ) : (
                <div className="absolute inset-0 flex items-center justify-center bg-muted/30">
                    <div className={cn("w-8 h-8 rounded-full flex items-center justify-center", cat.bgColor)}>
                        {cat.icon}
                    </div>
                </div>
            )}
            <div className="absolute bottom-1 left-1 px-1.5 py-0.5 rounded bg-black/60 backdrop-blur-sm text-[9px] font-medium text-white/80 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <span className={cat.color}>{cat.icon}</span>
            </div>
        </button>
    );
}

// ── Asset Preview Modal ──────────────────────────────────────────────

function AssetPreviewModal({ asset, onClose, onDeleteSuccess }: { asset: AssetItem; onClose: () => void; onDeleteSuccess?: () => void }) {
    const [copied, setCopied] = useState(false);
    const [isDeleting, setIsDeleting] = useState(false);

    const handleCopy = () => {
        navigator.clipboard.writeText(asset.presigned_url);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    const handleDelete = async () => {
        if (!confirm("Are you sure you want to permanently delete this asset from S3? This cannot be undone.")) return;
        setIsDeleting(true);
        try {
            await api.delete("/api/user-assets", { data: { url: asset.url } });
            toast.success("Asset deleted permanently");
            onDeleteSuccess?.();
            onClose();
        } catch {
            toast.error("Failed to delete asset");
        } finally {
            setIsDeleting(false);
        }
    };

    const isImage =
        asset.asset_category === "generated_image" ||
        (asset.asset_category === "uploaded" && asset.presigned_url.match(/\.(jpg|jpeg|png|webp|gif)/i));
    const isVideo =
        asset.asset_category === "generated_video" ||
        asset.asset_category === "rendered_video" ||
        (asset.asset_category === "uploaded" && asset.presigned_url.match(/\.(mp4|mov|webm)/i));
    const isAudio =
        asset.asset_category === "generated_audio" ||
        (asset.asset_category === "uploaded" && asset.presigned_url.match(/\.(mp3|wav|ogg|flac)/i));

    const cat = CATEGORY_CONFIG[asset.asset_category] || {
        label: "Asset", icon: <Package className="w-3.5 h-3.5" />, color: "text-zinc-400", bgColor: "bg-zinc-500/10",
    };

    return (
        <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[200] flex items-center justify-center bg-black/70 backdrop-blur-sm"
            onClick={onClose}
        >
            <motion.div
                initial={{ scale: 0.92, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                exit={{ scale: 0.92, opacity: 0 }}
                transition={{ duration: 0.15 }}
                className="relative max-w-2xl max-h-[80vh] w-full mx-4 rounded-xl border border-border/60 bg-popover shadow-2xl overflow-hidden"
                onClick={(e) => e.stopPropagation()}
            >
                <button onClick={onClose} className="absolute top-3 right-3 z-10 w-8 h-8 rounded-full bg-black/50 hover:bg-black/70 flex items-center justify-center text-white/80 hover:text-white transition-colors cursor-pointer">
                    <X className="w-4 h-4" />
                </button>
                <div className="bg-black/40 flex items-center justify-center min-h-[200px] max-h-[60vh]">
                    {isImage ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img src={asset.presigned_url} alt="Asset preview" className="max-w-full max-h-[60vh] object-contain" />
                    ) : isVideo ? (
                        <video src={asset.presigned_url} controls autoPlay className="max-w-full max-h-[60vh]" />
                    ) : isAudio ? (
                        <div className="p-8 flex flex-col items-center gap-4">
                            <div className={cn("w-16 h-16 rounded-full flex items-center justify-center", cat.bgColor)}>
                                <Music className={cn("w-8 h-8", cat.color)} />
                            </div>
                            <audio src={asset.presigned_url} controls className="w-full max-w-md" />
                        </div>
                    ) : (
                        <div className="p-8 text-center text-muted-foreground text-sm">Preview not available</div>
                    )}
                </div>
                <div className="px-4 py-3 border-t border-border/40 flex items-center justify-between gap-2 bg-popover">
                    <span className={cn("flex items-center gap-1 text-xs font-medium", cat.color)}>
                        {cat.icon} {cat.label}
                    </span>
                    <div className="flex items-center gap-2 shrink-0">
                        <button onClick={handleDelete} disabled={isDeleting} className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium text-red-500 hover:bg-red-500/10 hover:text-red-600 transition-colors cursor-pointer">
                            {isDeleting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />} 
                            {isDeleting ? "Deleting..." : "Delete"}
                        </button>
                        <button onClick={handleCopy} className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-muted/60 transition-colors cursor-pointer">
                            {copied ? <Check className="w-3.5 h-3.5 text-green-500" /> : <Copy className="w-3.5 h-3.5" />}
                            {copied ? "Copied" : "Copy URL"}
                        </button>
                        <a href={asset.presigned_url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium bg-primary text-primary-foreground hover:bg-primary/90 transition-colors">
                            <ExternalLink className="w-3.5 h-3.5" /> Open
                        </a>
                    </div>
                </div>
            </motion.div>
        </motion.div>
    );
}

// ── Category Folder (inside a workflow) ──────────────────────────────

function CategoryFolder({
    category,
    assets,
    defaultOpen,
    onDeleteSuccess,
}: {
    category: string;
    assets: AssetItem[];
    defaultOpen: boolean;
    onDeleteSuccess?: () => void;
}) {
    const [isExpanded, setIsExpanded] = useState(defaultOpen);
    const [previewAsset, setPreviewAsset] = useState<AssetItem | null>(null);

    const config = CATEGORY_CONFIG[category];
    if (!config) return null;

    return (
        <>
            <button
                onClick={() => setIsExpanded(!isExpanded)}
                className="w-full flex items-center gap-2 px-2 py-1.5 text-left hover:bg-muted/30 rounded-md transition-colors cursor-pointer"
            >
                <ChevronRight className={cn("w-3 h-3 text-muted-foreground/40 transition-transform duration-150 shrink-0", isExpanded && "rotate-90")} />
                <span className={cn("shrink-0", config.color)}>{config.icon}</span>
                <span className="text-[12px] text-muted-foreground/80 font-medium truncate flex-1">{config.label}</span>
                <span className="text-[10px] text-muted-foreground/40 font-mono shrink-0">{assets.length}</span>
            </button>

            <AnimatePresence>
                {isExpanded && (
                    <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: "auto", opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.12 }}
                        className="overflow-hidden"
                    >
                        <div className="grid grid-cols-3 gap-1.5 pl-7 pr-2 py-1.5">
                            {assets.map((asset) => (
                                <AssetThumbnail key={asset.url} asset={asset} onClick={() => setPreviewAsset(asset)} />
                            ))}
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>

            <AnimatePresence>
                {previewAsset && <AssetPreviewModal asset={previewAsset} onClose={() => setPreviewAsset(null)} onDeleteSuccess={onDeleteSuccess} />}
            </AnimatePresence>
        </>
    );
}

// ── Workflow Folder ──────────────────────────────────────────────────

function WorkflowFolder({
    workflow,
    defaultOpen,
    isCurrent,
    onDeleteSuccess,
}: {
    workflow: WorkflowAssets;
    defaultOpen: boolean;
    isCurrent: boolean;
    onDeleteSuccess?: () => void;
}) {
    const [isOpen, setIsOpen] = useState(defaultOpen);

    // Group assets by category, skip unknown
    const grouped = workflow.assets.reduce<Record<string, AssetItem[]>>((acc, asset) => {
        if (!KNOWN_CATEGORIES.has(asset.asset_category)) return acc;
        if (!acc[asset.asset_category]) acc[asset.asset_category] = [];
        acc[asset.asset_category].push(asset);
        return acc;
    }, {});

    const orderedCategories = CATEGORY_ORDER.filter(cat => grouped[cat]?.length > 0);

    return (
        <div>
            {/* Workflow row */}
            <button
                onClick={() => setIsOpen(!isOpen)}
                className={cn(
                    "w-full flex items-center gap-2 px-3 py-2 text-left transition-colors hover:bg-muted/40 rounded-lg group cursor-pointer",
                    isOpen && "bg-muted/20",
                )}
            >
                <ChevronRight className={cn("w-3.5 h-3.5 text-muted-foreground/50 transition-transform duration-200 shrink-0", isOpen && "rotate-90")} />
                {isOpen
                    ? <FolderOpen className="w-4 h-4 text-amber-400/80 shrink-0" />
                    : <FolderClosed className="w-4 h-4 text-amber-400/60 shrink-0" />
                }
                <span className="text-[13px] font-medium text-foreground/85 truncate flex-1">
                    {workflow.workflow_name}
                </span>
                {isCurrent && (
                    <span className="text-[9px] font-semibold uppercase tracking-wider text-primary/80 bg-primary/10 px-1.5 py-0.5 rounded shrink-0">
                        Current
                    </span>
                )}
                <span className="text-[11px] text-muted-foreground/50 font-mono shrink-0">{workflow.assets.length}</span>
            </button>

            {/* Category subfolders */}
            <AnimatePresence>
                {isOpen && (
                    <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: "auto", opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.15 }}
                        className="overflow-hidden"
                    >
                        <div className="pl-5 pr-1 pb-1 space-y-0.5">
                            {orderedCategories.map((cat) => (
                                <CategoryFolder
                                    key={cat}
                                    category={cat}
                                    assets={grouped[cat]}
                                    defaultOpen={isCurrent}
                                    onDeleteSuccess={onDeleteSuccess}
                                />
                            ))}

                            {/* Quick link to open workflow */}
                            {!isCurrent && (
                                <Link
                                    href={`/dashboard/workflow?id=${workflow.workflow_id}`}
                                    className="flex items-center gap-2 px-2 py-1.5 text-[11px] text-muted-foreground/50 hover:text-muted-foreground/80 hover:bg-muted/30 rounded-md transition-colors"
                                >
                                    <ExternalLink className="w-3 h-3" />
                                    Open workflow
                                </Link>
                            )}
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
}

// ── Main Panel ───────────────────────────────────────────────────────

export function YourStuffPanel({
    isOpen,
    onClose,
    currentWorkflowId,
}: {
    isOpen: boolean;
    onClose: () => void;
    currentWorkflowId?: string | null;
}) {
    const [data, setData] = useState<UserAssetsResponse | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const panelRef = useRef<HTMLDivElement>(null);

    const fetchAssets = useCallback(async () => {
        setIsLoading(true);
        try {
            const params: Record<string, string> = {};
            if (currentWorkflowId) params.current_workflow_id = currentWorkflowId;
            const res = await api.get<UserAssetsResponse>("/api/user-assets", { params });
            setData(res.data);
        } catch (err) {
            console.error("[YourStuff] Failed to load assets:", err);
        } finally {
            setIsLoading(false);
        }
    }, [currentWorkflowId]);

    useEffect(() => {
        if (isOpen) fetchAssets();
    }, [isOpen, fetchAssets]);

    // Close on click outside
    useEffect(() => {
        if (!isOpen) return;
        const handler = (e: MouseEvent) => {
            if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
                onClose();
            }
        };
        const tid = setTimeout(() => document.addEventListener("mousedown", handler), 100);
        return () => { clearTimeout(tid); document.removeEventListener("mousedown", handler); };
    }, [isOpen, onClose]);

    const workspaces = data?.workspaces || [];

    return (
        <AnimatePresence>
            {isOpen && (
                <>
                    {/* Backdrop */}
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="fixed inset-0 bg-black/30 z-[90] pointer-events-none"
                    />

                    {/* Slide-out Panel — from RIGHT */}
                    <motion.div
                        ref={panelRef}
                        initial={{ x: 340, opacity: 0 }}
                        animate={{ x: 0, opacity: 1 }}
                        exit={{ x: 340, opacity: 0 }}
                        transition={{ type: "spring", damping: 28, stiffness: 350 }}
                        className="fixed right-0 top-0 bottom-0 w-[340px] max-w-[85vw] bg-popover border-l border-border/60 shadow-2xl shadow-black/40 z-[100] flex flex-col"
                    >
                        {/* Header */}
                        <div className="flex items-center justify-between px-4 py-3 border-b border-border/40">
                            <div className="flex items-center gap-2.5">
                                <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-primary/20 to-primary/5 flex items-center justify-center">
                                    <Package className="w-4 h-4 text-primary" />
                                </div>
                                <div>
                                    <h2 className="text-sm font-semibold text-foreground">Your Stuff</h2>
                                    {data && (
                                        <p className="text-[10px] text-muted-foreground/60">
                                            {data.total_assets} asset{data.total_assets !== 1 ? "s" : ""} across {workspaces.length} workflow{workspaces.length !== 1 ? "s" : ""}
                                        </p>
                                    )}
                                </div>
                            </div>
                            <button
                                onClick={onClose}
                                className="w-7 h-7 rounded-md hover:bg-muted/60 flex items-center justify-center text-muted-foreground/50 hover:text-muted-foreground transition-colors cursor-pointer"
                            >
                                <X className="w-4 h-4" />
                            </button>
                        </div>

                        {/* Content */}
                        <div className="flex-1 overflow-y-auto px-2 py-2">
                            {isLoading ? (
                                <div className="flex items-center justify-center py-16">
                                    <Loader2 className="w-5 h-5 animate-spin text-muted-foreground/50" />
                                </div>
                            ) : workspaces.length === 0 ? (
                                <div className="flex flex-col items-center justify-center py-16 text-center">
                                    <div className="w-12 h-12 rounded-full bg-muted/30 flex items-center justify-center mb-3">
                                        <Package className="w-6 h-6 text-muted-foreground/30" />
                                    </div>
                                    <p className="text-sm text-muted-foreground/60 font-medium">No assets yet</p>
                                    <p className="text-[11px] text-muted-foreground/40 mt-1 max-w-[200px]">
                                        Generated images, videos, and uploaded media will appear here.
                                    </p>
                                </div>
                            ) : (
                                <div className="space-y-0.5">
                                    {/* Workspace root folder label */}
                                    <div className="flex items-center gap-2 px-3 py-2 rounded-lg">
                                        <FolderOpen className="w-4 h-4 text-muted-foreground/50" />
                                        <span className="text-[12px] font-semibold text-muted-foreground/70 uppercase tracking-wider">
                                            Workspace
                                        </span>
                                    </div>

                                    {/* Workflow folders */}
                                    <div className="pl-2 space-y-0.5">
                                        {workspaces.map((ws) => (
                                            <WorkflowFolder
                                                key={ws.workflow_id}
                                                workflow={ws}
                                                defaultOpen={ws.workflow_id === currentWorkflowId}
                                                isCurrent={ws.workflow_id === currentWorkflowId}
                                                onDeleteSuccess={fetchAssets}
                                            />
                                        ))}
                                    </div>
                                </div>
                            )}
                        </div>

                        {/* Footer */}
                        <div className="px-4 py-2.5 border-t border-border/30 text-[10px] text-muted-foreground/40 flex items-center justify-between">
                            <span>Assets stored securely in S3</span>
                            <button
                                onClick={fetchAssets}
                                disabled={isLoading}
                                className="text-muted-foreground/50 hover:text-muted-foreground/80 transition-colors cursor-pointer disabled:opacity-30"
                            >
                                Refresh
                            </button>
                        </div>
                    </motion.div>
                </>
            )}
        </AnimatePresence>
    );
}
