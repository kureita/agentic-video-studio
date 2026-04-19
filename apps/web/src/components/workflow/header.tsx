"use client";

import { ArrowLeft, Loader2, CheckCircle2, Cloud, MessageSquare, Play, Square, Share2, Link2, Check, Globe, Lock, Package } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useWorkflowStore } from "@/lib/workflow-store";
import { useRouter } from "next/navigation";
import { useState, useEffect, useCallback } from "react";
import { useMobileTab } from "@/components/workflow/mobile-tab-context";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { YourStuffPanel } from "@/components/your-stuff-panel";

export function WorkflowHeader() {
    const router = useRouter();
    const { id, name, setName, isSaving, isDirty, saveWorkflow, isRunning, runWorkflow, cancelJob, activeJobId, executionProgress, isPublic, togglePublic } = useWorkflowStore();
    const [editingName, setEditingName] = useState(name);
    const { setActiveTab } = useMobileTab();
    const [showShareMenu, setShowShareMenu] = useState(false);
    const [copied, setCopied] = useState(false);
    const [isYourStuffOpen, setIsYourStuffOpen] = useState(false);

    const shareUrl = typeof window !== "undefined" && id ? `${window.location.origin}/w/?id=${id}` : "";

    const handleCopyLink = useCallback(() => {
        if (!shareUrl) return;
        navigator.clipboard.writeText(shareUrl);
        setCopied(true);
        toast.success("Link copied to clipboard");
        setTimeout(() => setCopied(false), 2000);
    }, [shareUrl]);

    const handleTogglePublic = useCallback(async () => {
        const newValue = !isPublic;
        await togglePublic(newValue);
        if (newValue) {
            toast.success("Workflow is now public. Anyone with the link can view it.");
        } else {
            toast.info("Workflow is now private.");
        }
    }, [isPublic, togglePublic]);

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
        <>
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
                {/* Your Stuff */}
                <Button
                    variant="outline"
                    size="sm"
                    className={cn(
                        "h-8 gap-2 hidden sm:flex",
                        isYourStuffOpen && "bg-accent/80"
                    )}
                    onClick={() => setIsYourStuffOpen(!isYourStuffOpen)}
                >
                    <Package className="w-3.5 h-3.5" />
                    <span>Your Stuff</span>
                </Button>
                <Button
                    variant="outline"
                    size="icon"
                    className={cn("h-8 w-8 sm:hidden", isYourStuffOpen && "bg-accent/80")}
                    onClick={() => setIsYourStuffOpen(!isYourStuffOpen)}
                >
                    <Package className="w-4 h-4" />
                </Button>

                {/* Share Button */}
                <div className="relative">
                    <Button
                        variant="outline"
                        size="sm"
                        className="h-8 gap-2 hidden sm:flex"
                        onClick={() => setShowShareMenu(!showShareMenu)}
                    >
                        {isPublic ? <Globe className="w-3.5 h-3.5 text-green-500" /> : <Lock className="w-3.5 h-3.5" />}
                        <span>Share</span>
                    </Button>
                    <Button
                        variant="outline"
                        size="icon"
                        className="h-8 w-8 sm:hidden"
                        onClick={() => setShowShareMenu(!showShareMenu)}
                    >
                        <Share2 className="w-4 h-4" />
                    </Button>

                    {showShareMenu && (
                        <>
                            <div className="fixed inset-0 z-40" onClick={() => setShowShareMenu(false)} />
                            <div className="absolute right-0 top-10 z-50 w-72 bg-popover border border-border rounded-xl shadow-2xl p-4 space-y-3 animate-in fade-in zoom-in-95 duration-150">
                                <div className="flex items-center justify-between">
                                    <span className="text-sm font-medium">Public access</span>
                                    <button
                                        onClick={handleTogglePublic}
                                        className={`relative w-10 h-5 rounded-full transition-colors ${isPublic ? 'bg-green-500' : 'bg-muted-foreground/30'} cursor-pointer`}
                                    >
                                        <span className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white transition-transform ${isPublic ? 'translate-x-5' : ''}`} />
                                    </button>
                                </div>
                                <p className="text-xs text-muted-foreground">
                                    {isPublic
                                        ? "Anyone with the link can view this workflow (read-only)."
                                        : "Only you can access this workflow."}
                                </p>
                                {isPublic && (
                                    <div className="flex gap-2">
                                        <input
                                            readOnly
                                            value={shareUrl}
                                            className="flex-1 h-8 text-xs bg-muted/50 border border-border rounded-lg px-2 truncate"
                                        />
                                        <Button
                                            size="sm"
                                            variant="outline"
                                            className="h-8 gap-1.5 shrink-0"
                                            onClick={handleCopyLink}
                                        >
                                            {copied ? <Check className="w-3.5 h-3.5 text-green-500" /> : <Link2 className="w-3.5 h-3.5" />}
                                            {copied ? "Copied" : "Copy"}
                                        </Button>
                                    </div>
                                )}
                            </div>
                        </>
                    )}
                </div>

                {/* Run All / Cancel Button */}
                {isRunning && activeJobId ? (
                    <div className="flex items-center gap-2">
                        {executionProgress && (
                            <span className="text-[10px] text-muted-foreground font-mono tabular-nums hidden sm:inline">
                                {executionProgress.current}/{executionProgress.total}
                            </span>
                        )}
                        <Button
                            variant="destructive"
                            className="h-8 shadow-sm gap-2"
                            onClick={cancelJob}
                        >
                            <Square className="w-3.5 h-3.5 fill-current" />
                            <span className="hidden sm:inline">Cancel</span>
                        </Button>
                    </div>
                ) : (
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
                )}

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

        {/* Your Stuff Panel */}
        <YourStuffPanel
            isOpen={isYourStuffOpen}
            onClose={() => setIsYourStuffOpen(false)}
            currentWorkflowId={id}
            currentWorkflowName={name}
        />
        </>
    );
}
