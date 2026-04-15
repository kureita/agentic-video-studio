"use client";

import { useState, useRef, useEffect } from "react";
import {
    Loader2,
    ChevronDown,
    Paperclip,
    X,
    AtSign,
    ArrowUp,
    Image as ImageIcon,
    Video,
    Type,
    Eye,
    Clapperboard,
    Upload,
    Music,
    Workflow,
} from "lucide-react";

import { cn, ALLOWED_MEDIA_TYPES } from "@/lib/utils";
import Image from "next/image";
import { S3Image } from "@/components/ui/s3-image";
import { useWorkflowStore } from "@/lib/workflow-store";
import { ChatAttachment, ChatMessage } from "@/lib/workflow-api";
import { api } from "@/lib/api";
import { AgentModel, useAgentModels } from "@/lib/agent-models";
import { motion, AnimatePresence } from "framer-motion";
import { ChatMessageItem, TypingIndicator } from "@/components/workflow/chat-messages";
import { toast } from "sonner";
import { AddCreditsModal } from "@/components/billing/add-credits-modal";
import { useAuth0 } from "@auth0/auth0-react";
import { useMobileTab } from "@/components/workflow/mobile-tab-context";
import { useRouter } from "next/navigation";


// ============================================
// Cursor-style Input Component
// ============================================

// Helper to get node type icon
function getNodeTypeIcon(type: string) {
    switch (type) {
        case 'text': return <Type className="w-3 h-3" />;
        case 'imageGen': return <ImageIcon className="w-3 h-3" />;
        case 'videoGen': return <Video className="w-3 h-3" />;
        case 'assistant': return <Eye className="w-3 h-3" />;
        case 'vision': return <Eye className="w-3 h-3" />;
        case 'editorAgent': return <Clapperboard className="w-3 h-3" />;
        case 'mediaUpload': return <Upload className="w-3 h-3" />;
        case 'audioGen': return <Music className="w-3 h-3" />;
        default: return <Type className="w-3 h-3" />;
    }
}

function getNodeTypeLabel(type: string) {
    switch (type) {
        case 'text': return 'Text';
        case 'imageGen': return 'Image Gen';
        case 'videoGen': return 'Video Gen';
        case 'assistant': return 'Media Assistant';
        case 'vision': return 'Media Assistant';
        case 'editorAgent': return 'Editor Agent';
        case 'mediaUpload': return 'Media Upload';
        case 'audioGen': return 'Audio Gen';
        default: return type;
    }
}

interface Attachment extends ChatAttachment {
    file?: File;
}

function CursorInput({
    value,
    onChange,
    onSubmit,
    isLoading,
    pendingAttachments,
    onRemoveAttachment,
    onFileUpload,
    isUploading,
    selectedModel,
    onModelSelect,
    modelOptions,
}: {
    value: string;
    onChange: (val: string) => void;
    onSubmit: () => void;
    isLoading: boolean;
    pendingAttachments: Attachment[];
    onRemoveAttachment: (index: number) => void;
    onFileUpload: (files: FileList | null) => void;
    isUploading: boolean;
    selectedModel: string;
    onModelSelect: (model: string) => void;
    modelOptions: AgentModel[];
}) {
    const textareaRef = useRef<HTMLTextAreaElement>(null);
    const [showContextMenu, setShowContextMenu] = useState(false);
    const [showModelMenu, setShowModelMenu] = useState(false);
    const [isDragging, setIsDragging] = useState(false);
    const contextMenuRef = useRef<HTMLDivElement>(null);
    const modelMenuRef = useRef<HTMLDivElement>(null);
    const nodes = useWorkflowStore((state) => state.nodes);

    // Auto-resize textarea
    useEffect(() => {
        const textarea = textareaRef.current;
        if (textarea) {
            textarea.style.height = "0";
            const scrollHeight = Math.min(textarea.scrollHeight, 160);
            textarea.style.height = `${scrollHeight}px`;
        }
    }, [value]);

    // Close menus when clicking outside
    useEffect(() => {
        const handleClickOutside = (e: MouseEvent) => {
            if (contextMenuRef.current && !contextMenuRef.current.contains(e.target as Node)) {
                setShowContextMenu(false);
            }
            if (modelMenuRef.current && !modelMenuRef.current.contains(e.target as Node)) {
                setShowModelMenu(false);
            }
        };
        if (showContextMenu || showModelMenu) {
            document.addEventListener('mousedown', handleClickOutside);
            return () => document.removeEventListener('mousedown', handleClickOutside);
        }
    }, [showContextMenu, showModelMenu]);

    const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            if (value.trim() || pendingAttachments.length > 0) {
                onSubmit();
            }
        }
    };

    const hasAttachments = pendingAttachments.length > 0;

    // Drag and drop handlers
    const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
        e.preventDefault();
        e.stopPropagation();
        if (!isDragging) setIsDragging(true);
    };

    const handleDragEnter = (e: React.DragEvent<HTMLDivElement>) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragging(true);
    };

    const handleDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
        e.preventDefault();
        e.stopPropagation();
        // Only set false if we are actually leaving the container, not just entering child elements
        if (!e.currentTarget.contains(e.relatedTarget as Node)) {
            setIsDragging(false);
        }
    };

    const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragging(false);
        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            onFileUpload(e.dataTransfer.files);
        }
    };

    // Insert node reference into the textarea
    const insertNodeReference = (nodeType: string, nodeIndex: number, nodeLabel: string) => {
        const ref = `@${nodeLabel}`;
        const textarea = textareaRef.current;
        if (textarea) {
            const cursor = textarea.selectionStart;
            const before = value.slice(0, cursor);
            const after = value.slice(cursor);
            const needsSpace = before.length > 0 && !before.endsWith(' ') && !before.endsWith('\n');
            const newValue = before + (needsSpace ? ' ' : '') + ref + ' ' + after;
            onChange(newValue);
            setTimeout(() => {
                textarea.focus();
                const newCursor = cursor + (needsSpace ? 1 : 0) + ref.length + 1;
                textarea.setSelectionRange(newCursor, newCursor);
            }, 0);
        } else {
            onChange(value + (value ? ' ' : '') + ref + ' ');
        }
        setShowContextMenu(false);
    };

    // Group nodes by type for display
    const groupedNodes = nodes.reduce((acc, node, idx) => {
        const type = node.type || 'unknown';
        if (!acc[type]) acc[type] = [];
        // Calculate the type-specific index
        const typeIndex = nodes.filter(n => n.type === type).indexOf(node) + 1;
        const label = `${getNodeTypeLabel(type)} #${typeIndex}`;
        acc[type].push({ id: node.id, label, typeIndex, globalIndex: idx });
        return acc;
    }, {} as Record<string, { id: string; label: string; typeIndex: number; globalIndex: number }[]>);

    return (
        <div className="p-3">
            {/* Main Input Container - Cursor-style */}
            <div
                onDragOver={handleDragOver}
                onDragEnter={handleDragEnter}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                className={cn(
                    "relative rounded-xl border transition-all duration-200",
                    "bg-muted/30 border-border/50",
                    "focus-within:border-primary/40 focus-within:bg-muted/50",
                    "shadow-sm focus-within:shadow-md focus-within:shadow-primary/5",
                    isDragging && "border-primary bg-primary/5 shadow-md ring-2 ring-primary/20"
                )}
            >
                {/* Drag Overlay */}
                <AnimatePresence>
                    {isDragging && (
                        <motion.div
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            transition={{ duration: 0.15 }}
                            className="absolute inset-0 z-50 flex flex-col items-center justify-center bg-background/80 backdrop-blur-[2px] border border-dashed border-primary/40 rounded-xl pointer-events-none overflow-hidden"
                        >
                            <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center mb-1.5">
                                <Upload className="w-4 h-4 text-primary" />
                            </div>
                            <p className="text-xs font-medium text-foreground">Drop images or videos here</p>
                            <p className="text-[10px] text-muted-foreground mt-0.5">Files will be added as attachments</p>
                        </motion.div>
                    )}
                </AnimatePresence>

                {/* Inline Attachment Previews */}
                <AnimatePresence>
                    {hasAttachments && (
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
                                                    onClick={() => onRemoveAttachment(idx)}
                                                    className="absolute -top-1.5 -right-1.5 w-4 h-4 rounded-full bg-destructive text-destructive-foreground flex items-center justify-center opacity-0 group-hover/att:opacity-100 transition-opacity cursor-pointer shadow-sm z-10"
                                                >
                                                    <X className="w-2.5 h-2.5" />
                                                </button>
                                            </div>
                                        ) : att.type.startsWith("video") ? (
                                            <div className="relative">
                                                <div className="h-14 w-20 rounded-lg overflow-hidden border border-border/40 bg-muted/40 relative">
                                                    <video src={att.url} className="h-full w-full object-cover" />
                                                    <div className="absolute inset-0 flex items-center justify-center bg-black/20">
                                                        <Video className="w-4 h-4 text-white/80" />
                                                    </div>
                                                </div>
                                                <button
                                                    onClick={() => onRemoveAttachment(idx)}
                                                    className="absolute -top-1.5 -right-1.5 w-4 h-4 rounded-full bg-destructive text-destructive-foreground flex items-center justify-center opacity-0 group-hover/att:opacity-100 transition-opacity cursor-pointer shadow-sm z-10"
                                                >
                                                    <X className="w-2.5 h-2.5" />
                                                </button>
                                            </div>
                                        ) : (
                                            <div className="relative flex items-center gap-1.5 h-8 px-2.5 rounded-lg border border-border/40 bg-muted/40">
                                                <Paperclip className="w-3 h-3 text-muted-foreground/60" />
                                                <span className="text-[11px] text-muted-foreground truncate max-w-[80px]">{att.filename}</span>
                                                <button
                                                    onClick={() => onRemoveAttachment(idx)}
                                                    className="p-0.5 rounded hover:bg-muted text-muted-foreground/40 hover:text-muted-foreground transition-colors cursor-pointer"
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
                                <p className="text-[10px] text-muted-foreground leading-tight">
                                    Upload media to use it in chat or in your workflow.
                                </p>
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>

                {/* Textarea */}
                <textarea
                    ref={textareaRef}
                    value={value}
                    onChange={(e) => onChange(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="Plan, search, build anything"
                    disabled={isLoading}
                    rows={1}
                    className={cn(
                        "w-full resize-none bg-transparent px-3.5 pt-3 pb-1 text-[13px] placeholder:text-muted-foreground/40",
                        "focus:outline-none leading-relaxed",
                        "min-h-[36px] max-h-[160px]",
                        isLoading && "opacity-50 cursor-not-allowed"
                    )}
                />

                {/* Bottom bar with actions */}
                <div className="flex items-center justify-between px-2.5 pb-2 pt-0.5">
                    {/* Left side actions */}
                    <div className="flex items-center gap-1 relative" ref={contextMenuRef}>
                        {/* Context / Add button */}
                        <button
                            onClick={() => setShowContextMenu(!showContextMenu)}
                            className={cn(
                                "flex items-center gap-1.5 px-2 py-1 rounded-md text-[11px] transition-colors cursor-pointer",
                                "text-muted-foreground/50 hover:text-muted-foreground hover:bg-muted/60",
                                showContextMenu && "text-muted-foreground bg-muted/60",
                                isLoading && "opacity-50 cursor-not-allowed"
                            )}
                            disabled={isLoading}
                        >
                            <AtSign className="w-3 h-3" />
                            <span>Add context</span>
                        </button>

                        {/* Context Menu Dropdown */}
                        <AnimatePresence>
                            {showContextMenu && (
                                <motion.div
                                    initial={{ opacity: 0, y: 4, scale: 0.96 }}
                                    animate={{ opacity: 1, y: 0, scale: 1 }}
                                    exit={{ opacity: 0, y: 4, scale: 0.96 }}
                                    transition={{ duration: 0.12 }}
                                    className="absolute bottom-full left-0 mb-2 w-56 bg-popover text-popover-foreground rounded-lg border shadow-xl overflow-hidden z-50"
                                >
                                    <div className="px-3 py-2 text-[11px] font-semibold text-muted-foreground/70 uppercase tracking-wider bg-muted/30 border-b">
                                        Reference Nodes
                                    </div>
                                    <div className="max-h-[200px] overflow-y-auto p-1">
                                        {Object.keys(groupedNodes).length === 0 ? (
                                            <div className="px-3 py-2 text-xs text-muted-foreground/50 italic">No nodes in workflow</div>
                                        ) : (
                                            Object.entries(groupedNodes).map(([type, items]) => (
                                                <div key={type}>
                                                    {items.map((node) => (
                                                        <button
                                                            key={node.id}
                                                            className="w-full text-left px-2.5 py-1.5 text-xs rounded-md hover:bg-accent hover:text-accent-foreground cursor-pointer flex items-center gap-2 transition-colors"
                                                            onClick={() => insertNodeReference(type, node.typeIndex, node.label)}
                                                        >
                                                            <span className="text-muted-foreground/60">{getNodeTypeIcon(type)}</span>
                                                            <span className="font-medium">{node.label}</span>
                                                        </button>
                                                    ))}
                                                </div>
                                            ))
                                        )}
                                    </div>
                                </motion.div>
                            )}
                        </AnimatePresence>
                    </div>

                    {/* Right side */}
                    <div className="flex items-center gap-1.5">
                        {/* Model selector */}
                        <div className="relative" ref={modelMenuRef}>
                            <button
                                onClick={() => setShowModelMenu(!showModelMenu)}
                                className={cn(
                                    "flex items-center gap-1.5 px-2 py-1 rounded-md text-[11px] transition-colors cursor-pointer",
                                    "text-muted-foreground/50 hover:text-muted-foreground hover:bg-muted/60",
                                    showModelMenu && "text-muted-foreground bg-muted/60",
                                    isLoading && "opacity-50 cursor-not-allowed"
                                )}
                                disabled={isLoading}
                            >
                                <ChevronDown className="w-3.5 h-3.5" />
                                <span>{selectedModel}</span>
                            </button>

                            {/* Model Menu Dropdown */}
                            <AnimatePresence>
                                {showModelMenu && (
                                    <motion.div
                                        initial={{ opacity: 0, y: 4, scale: 0.96 }}
                                        animate={{ opacity: 1, y: 0, scale: 1 }}
                                        exit={{ opacity: 0, y: 4, scale: 0.96 }}
                                        transition={{ duration: 0.12 }}
                                        className="absolute bottom-full right-0 mb-2 w-64 bg-popover text-popover-foreground rounded-lg border shadow-xl overflow-hidden z-50"
                                    >
                                        <div className="px-3 py-2 text-[11px] text-muted-foreground border-b border-border/50">
                                            Model
                                        </div>
                                        <div className="max-h-[240px] overflow-y-auto flex flex-col">
                                            {modelOptions.map((model) => (
                                                <button
                                                    key={model.display_name}
                                                    onClick={() => {
                                                        onModelSelect(model.display_name);
                                                        setShowModelMenu(false);
                                                    }}
                                                    className={cn(
                                                        "w-full text-left px-2 py-2 text-[11px] hover:bg-accent/80 hover:text-accent-foreground cursor-pointer flex items-start justify-between gap-2",
                                                        selectedModel === model.display_name && "bg-accent/60 text-accent-foreground font-medium"
                                                    )}
                                                >
                                                    <div className="min-w-0">
                                                        <div className={cn(selectedModel !== model.display_name && "text-muted-foreground/90")}>
                                                            {model.display_name}
                                                        </div>
                                                        {model.input_modalities.filter((modality) => modality !== "text").length > 0 && (
                                                            <div className="text-[10px] text-muted-foreground/60 mt-0.5">
                                                                {model.input_modalities.filter((modality) => modality !== "text").join(" • ")}
                                                            </div>
                                                        )}
                                                    </div>
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
                                (isUploading || isLoading) && "opacity-50 cursor-not-allowed"
                            )}
                        >
                            <Paperclip className="w-3.5 h-3.5" />
                            <input
                                type="file"
                                className="hidden"
                                onChange={(e) => onFileUpload(e.target.files)}
                                disabled={isUploading || isLoading}
                                accept="image/*,video/*,audio/*"
                                multiple
                            />
                        </label>

                        {/* Submit button */}
                        <button
                            onClick={() => onSubmit()}
                            disabled={(!value.trim() && pendingAttachments.length === 0) || isLoading || isUploading}
                            className={cn(
                                "p-1.5 rounded-lg transition-all duration-200 cursor-pointer",
                                value.trim() || pendingAttachments.length > 0
                                    ? "bg-primary text-primary-foreground shadow-sm hover:shadow-md hover:bg-primary/90"
                                    : "bg-muted/60 text-muted-foreground/30 cursor-not-allowed"
                            )}
                        >
                            {isLoading ? (
                                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                            ) : (
                                <ArrowUp className="w-3.5 h-3.5" />
                            )}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}

// ============================================
// Mobile Tab Switch Buttons
// ============================================

function MobileSwitchToCanvas() {
    const { setActiveTab } = useMobileTab();
    return (
        <button
            onClick={() => setActiveTab("canvas")}
            className="md:hidden flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-muted/60 transition-colors cursor-pointer"
            title="Switch to Canvas"
        >
            <Workflow className="w-4 h-4" />
            <span>Canvas</span>
        </button>
    );
}

// ============================================
// Main Agent Sidebar
// ============================================

export function AgentSidebar() {
    const router = useRouter();
    const { chatHistory, addChatMessage, setNodes, setEdges, nodes, edges, name: workflowName, setName: setWorkflowName } = useWorkflowStore();
    const { getAccessTokenSilently } = useAuth0();
    const { models: agentModels } = useAgentModels();
    const storeId = useWorkflowStore((state) => state.id);
    const [input, setInput] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const [isUploading, setIsUploading] = useState(false);
    const [selectedModel, setSelectedModel] = useState("Gemini 3.1 Pro Preview (High)");
    const [pendingAttachments, setPendingAttachments] = useState<Attachment[]>([]);
    const [isCreditsModalOpen, setIsCreditsModalOpen] = useState(false);
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const autoPromptSent = useRef(false);

    // Resizable sidebar state
    const [sidebarWidth, setSidebarWidth] = useState(420);
    const [isResizing, setIsResizing] = useState(false);
    const sidebarRef = useRef<HTMLDivElement>(null);

    const MIN_WIDTH = 280;
    const MAX_WIDTH = 600;

    // Handle resize drag
    useEffect(() => {
        if (!isResizing) return;

        const handleMouseMove = (e: MouseEvent) => {
            const newWidth = Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, e.clientX));
            setSidebarWidth(newWidth);
        };

        const handleMouseUp = () => {
            setIsResizing(false);
        };

        document.addEventListener("mousemove", handleMouseMove);
        document.addEventListener("mouseup", handleMouseUp);
        document.body.style.cursor = "col-resize";
        document.body.style.userSelect = "none";

        return () => {
            document.removeEventListener("mousemove", handleMouseMove);
            document.removeEventListener("mouseup", handleMouseUp);
            document.body.style.cursor = "";
            document.body.style.userSelect = "";
        };
    }, [isResizing]);

    // Auto-scroll to bottom when messages change
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [chatHistory, isLoading]);

    useEffect(() => {
        if (!agentModels.length) return;
        if (!agentModels.some((model) => model.display_name === selectedModel)) {
            setSelectedModel(agentModels[0].display_name);
        }
    }, [agentModels, selectedModel]);

    const handleFileUpload = async (files: FileList | null) => {
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
        // Note: we can't easily reset the input generic value here unless we ref it, 
        // but for drag&drop and controlled inputs it's usually fine.
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

    // Show welcome message if no chat history
    const displayMessages: ChatMessage[] =
        chatHistory.length === 0
            ? [
                {
                    role: "assistant" as const,
                    content:
                        "Hello! I'm your AI creative assistant. Tell me what you want to create, and I can either build the workflow or analyze attached media directly in chat.",
                },
            ]
            : chatHistory;

    const handleSubmit = async (overrideMessage?: string | unknown) => {
        let userMessage: string;
        const finalAttachments = [...pendingAttachments];
        const typedPrompt = typeof overrideMessage === "string" ? overrideMessage : input.trim();

        if (overrideMessage && typeof overrideMessage === 'string') {
            // Auto-prompt: use the override directly
            userMessage = overrideMessage;
        } else {
            // Manual submit: build from input + attachments
            if ((!input.trim() && pendingAttachments.length === 0) || isLoading || isUploading) return;

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
                            if (storeId) {
                                formData.append("workflow_id", storeId);
                            }
                            if (workflowName) {
                                formData.append("workflow_name", workflowName);
                            }
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
                    return;
                }
                setIsUploading(false);
            }

            userMessage = input.trim();
            setInput("");
            setPendingAttachments([]);
        }

        if ((!userMessage && finalAttachments.length === 0) || isLoading) return;

        addChatMessage({
            role: "user",
            content: userMessage,
            attachments: finalAttachments.map(({ filename, type, url }) => ({ filename, type, url })),
        });
        setIsLoading(true);

        try {
            // Sanitize chatHistory to plain {role, content} objects before sending to backend
            // to avoid circular JSON errors from SDK objects in the store
            const sanitizedHistory = chatHistory.map((m) => ({
                role: m.role,
                content: [
                    typeof m.content === 'string' ? m.content : JSON.stringify(m.content),
                    ...(Array.isArray(m.attachments)
                        ? m.attachments.map((attachment) => `[Attached: ${attachment.filename}] (${attachment.type})`)
                        : []),
                ].filter(Boolean).join('\n'),
            }));

            const token = await getAccessTokenSilently();
            const response = await api.post("/api/agent/flow", {
                prompt: typedPrompt || (finalAttachments.length > 0 ? "Please analyze the attached media." : userMessage),
                model: selectedModel,
                current_nodes: nodes,
                current_edges: edges,
                chat_history: sanitizedHistory,
                attachments: finalAttachments.map((attachment) => ({
                    filename: attachment.filename,
                    type: attachment.type,
                    url: attachment.url,
                })),
            }, {
                headers: { Authorization: `Bearer ${token}` }
            });

            const initialResult = response.data;
            if (!initialResult.job_id) {
                throw new Error("Failed to start workflow generation job");
            }

            // Poll for completion
            let result;
            while (true) {
                await new Promise(resolve => setTimeout(resolve, 3000));
                const statusRes = await api.get(`/api/agent/flow/status/${initialResult.job_id}`, {
                    headers: { Authorization: `Bearer ${token}` }
                });

                if (statusRes.data.status === "completed" || statusRes.data.status === "failed") {
                    result = {
                        success: statusRes.data.status === "completed",
                        message: statusRes.data.result?.message,
                        nodes: statusRes.data.result?.nodes,
                        edges: statusRes.data.result?.edges,
                        thinking: statusRes.data.result?.thinking,
                        thinking_duration_ms: statusRes.data.result?.thinking_duration_ms,
                        action: statusRes.data.result?.action,
                        apply_workflow: statusRes.data.result?.apply_workflow,
                        tool_calls: statusRes.data.result?.tool_calls,
                        suggested_name: statusRes.data.result?.suggested_name,
                        error: statusRes.data.error,
                    };
                    break;
                }
            }

            if (result.success) {
                if (result.suggested_name && workflowName.startsWith("Untitled Workflow")) {
                    setWorkflowName(result.suggested_name);
                }

                const hasNodeArray = Array.isArray(result.nodes);
                const hasEdgeArray = Array.isArray(result.edges);
                const hasAnyElement =
                    (hasNodeArray && result.nodes.length > 0) ||
                    (hasEdgeArray && result.edges.length > 0);
                const indicatesWorkflowAction = result.action === "replace_all" || result.action === "update";
                const shouldApplyWorkflow =
                    result.apply_workflow ??
                    (
                        (hasNodeArray || hasEdgeArray) &&
                        (hasAnyElement || indicatesWorkflowAction)
                    );

                let appliedWorkflow = false;
                if (shouldApplyWorkflow && hasNodeArray) {
                    setNodes(result.nodes);
                    interface AgentEdge {
                        id?: string;
                        source?: string;
                        target?: string;
                        sourceHandle?: string;
                        source_handle?: string;
                        targetHandle?: string;
                        target_handle?: string;
                        [key: string]: unknown;
                    }
                    const edgeList = hasEdgeArray ? result.edges : [];
                    const validEdges = edgeList.map((e: AgentEdge | unknown) => {
                        const safeE = e as AgentEdge;
                        return {
                            ...safeE,
                            id: safeE.id || `${safeE.source}-${safeE.target}`,
                            sourceHandle: safeE.sourceHandle || safeE.source_handle || undefined,
                            targetHandle: safeE.targetHandle || safeE.target_handle || undefined,
                        };
                    });
                    setEdges(validEdges);
                    appliedWorkflow = true;

                    // Make newly generated workflows immediately visible on canvas.
                    if (typeof window !== "undefined") {
                        window.setTimeout(() => {
                            window.dispatchEvent(new CustomEvent("kureita:fit-workflow-view", {
                                detail: { workflowId: storeId || undefined },
                            }));
                        }, 40);
                    }
                }

                const likelyWorkflowRequest = /\b(create|build|make|generate|workflow|scene|node|ad|edit|modify|update|connect)\b/i
                    .test(typedPrompt || "");
                const assistantContent = likelyWorkflowRequest && !appliedWorkflow
                    ? `${result.message || "I processed your request."}\n\nI couldn't apply workflow changes because no valid node payload was returned. Please retry and I’ll regenerate the nodes.`
                    : (result.message || "I've updated the workflow based on your request.");

                addChatMessage({
                    role: "assistant",
                    content: assistantContent,
                    thinking: result.thinking || undefined,
                    thinking_duration_ms: result.thinking_duration_ms || undefined,
                    tool_calls: result.tool_calls || undefined,
                });
            } else {
                addChatMessage({
                    role: "assistant",
                    content: result.message || "Sorry, I encountered an error creating the workflow.",
                    thinking: result.thinking || undefined,
                    thinking_duration_ms: result.thinking_duration_ms || undefined,
                });
            }
        } catch (error: unknown) {
            console.error("Agent error:", error);

            interface ErrorResponse {
                response?: {
                    status?: number;
                    data?: {
                        detail?: string;
                    };
                };
            }
            const typedError = error as ErrorResponse;
            const status = typedError.response?.status;
            const detail = typedError.response?.data?.detail;

            if (status === 402 || (typeof detail === 'string' && detail.toLowerCase().includes("insufficient"))) {
                toast.error("Insufficient balance. Please add funds to continue.", {
                    action: {
                        label: "Billing",
                        onClick: () => window.location.href = "/usage"
                    }
                });

                addChatMessage({
                    role: "assistant",
                    content: "You do not have enough balance to perform this generative action. Please add more funds on the [Billing & Usage](/usage) page to continue building!",
                });

                // Automatically open the modal for convenience
                setIsCreditsModalOpen(true);
            } else {
                toast.error("AI service error. Please try again.");
                addChatMessage({
                    role: "assistant",
                    content: "Sorry, something went wrong with the AI service.",
                });
            }
        } finally {
            setIsLoading(false);
        }
    };

    // -- Auto-send initial prompt from dashboard --
    const handleSubmitRef = useRef(handleSubmit);
    handleSubmitRef.current = handleSubmit;

    useEffect(() => {
        if (storeId && !autoPromptSent.current) {
            const initialModel = sessionStorage.getItem("kureita_initial_model");
            if (initialModel) {
                setSelectedModel(initialModel);
                sessionStorage.removeItem("kureita_initial_model");
            }

            const prompt = sessionStorage.getItem("kureita_initial_prompt");
            if (prompt) {
                autoPromptSent.current = true;
                sessionStorage.removeItem("kureita_initial_prompt");
                // small delay to ensure the workflow is fully loaded and UI is ready
                const timer = setTimeout(() => {
                    handleSubmitRef.current(prompt);
                }, 600);
                return () => clearTimeout(timer);
            }
        }
    }, [storeId]);

    return (
        <div
            ref={sidebarRef}
            className="border-r h-screen bg-card flex flex-col shadow-xl z-20 shrink-0 sticky top-0 relative"
            style={{ width: `${sidebarWidth}px` }}
        >
            {/* Header */}
            <div className="px-4 py-3 flex flex-col gap-2 z-10 shadow-[0_4px_20px_-4px_rgba(0,0,0,0.1)]">
                <div className="flex items-center justify-between">
                    <button
                        onClick={() => router.push("/dashboard")}
                        className="flex items-center gap-2.5 cursor-pointer hover:opacity-80 transition-opacity"
                        title="Go to Dashboard"
                    >
                        <div className="w-6 h-6 rounded-lg bg-gradient-to-br from-violet-500/20 to-blue-500/20 flex items-center justify-center">
                            <Image src="/kureita_logo.png" alt="Kureita" width={24} height={24} className="w-6 h-6" unoptimized />
                        </div>
                        <div className="flex-1 text-left">
                            <h2 className="font-semibold text-sm">Kureita</h2>
                            <p className="text-[10px] text-muted-foreground/60">AI Workflow Builder</p>
                        </div>
                    </button>

                    <AddCreditsModal
                        open={isCreditsModalOpen}
                        onOpenChange={setIsCreditsModalOpen}
                    />

                    {/* Mobile: Switch to Canvas */}
                    <MobileSwitchToCanvas />
                </div>

            </div>

            {/* Messages Area */}
            <div className="flex-1 overflow-y-auto px-4 py-4">
                {displayMessages.map((msg, i) => (
                    <ChatMessageItem
                        key={`${i}-${msg.role}-${(typeof msg.content === 'string' ? msg.content : JSON.stringify(msg.content)).substring(0, 20)}`}
                        message={msg}
                    />
                ))}

                {/* Live typing indicator */}
                {isLoading && <TypingIndicator />}

                <div ref={messagesEndRef} />
            </div>

            {/* Cursor-style Input */}
            <CursorInput
                value={input}
                onChange={setInput}
                onSubmit={handleSubmit}
                isLoading={isLoading}
                pendingAttachments={pendingAttachments}
                onRemoveAttachment={handleRemoveAttachment}
                onFileUpload={handleFileUpload}
                isUploading={isUploading}
                selectedModel={selectedModel}
                onModelSelect={setSelectedModel}
                modelOptions={agentModels}
            />

            {/* Resize Handle */}
            <div
                className={cn(
                    "sidebar-resize-handle absolute top-0 right-0 w-1 h-full cursor-col-resize z-30 group",
                    "hover:bg-primary/30 active:bg-primary/50 transition-colors duration-150",
                    isResizing && "bg-primary/50"
                )}
                onMouseDown={(e) => {
                    e.preventDefault();
                    setIsResizing(true);
                }}
            >
                {/* Visual indicator line */}
                <div className={cn(
                    "absolute top-1/2 -translate-y-1/2 right-0 w-[3px] h-8 rounded-full transition-opacity duration-150",
                    "bg-muted-foreground/20 group-hover:bg-primary/40",
                    isResizing ? "opacity-100 bg-primary/60" : "opacity-0 group-hover:opacity-100"
                )} />
            </div>

            {/* Overlay to prevent iframe/canvas interference during resize */}
            {isResizing && (
                <div className="fixed inset-0 z-20 cursor-col-resize" />
            )}
        </div>
    );
}
