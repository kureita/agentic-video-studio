"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import {
    Loader2,
    ChevronDown,
    ChevronRight,
    Paperclip,
    X,
    Check,
    Copy,
    RotateCcw,
    Wrench,
    Brain,
    AtSign,
    ArrowUp,
    Cpu,
    Image as ImageIcon,
    Video,
    Type,
    Eye,
    Clapperboard,
    Upload,
    Music,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useWorkflowStore } from "@/lib/workflow-store";
import { ChatMessage, ToolCall } from "@/lib/workflow-api";
import { api } from "@/lib/api";
import { motion, AnimatePresence } from "framer-motion";
import { MarkdownContent, HighlightedReferences } from "@/components/workflow/markdown-content";

// ============================================
// Thinking Block Component
// ============================================

function ThinkingBlock({
    thinking,
    durationMs,
    isLive,
}: {
    thinking?: string;
    durationMs?: number;
    isLive?: boolean;
}) {
    const [isExpanded, setIsExpanded] = useState(false);

    if (!thinking && !isLive) return null;

    const durationLabel = isLive
        ? "Thinking..."
        : durationMs
            ? `Thought for ${(durationMs / 1000).toFixed(1)}s`
            : "Thought process";

    return (
        <div className="mb-2">
            <button
                onClick={() => setIsExpanded(!isExpanded)}
                className="flex items-center gap-1.5 text-[11px] text-muted-foreground/70 hover:text-muted-foreground transition-colors group cursor-pointer"
            >
                {isLive ? (
                    <motion.div
                        animate={{ rotate: 360 }}
                        transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
                    >
                        <Brain className="w-3 h-3 text-violet-400" />
                    </motion.div>
                ) : (
                    <Brain className="w-3 h-3 text-violet-400/60" />
                )}
                <span className={cn(isLive && "text-violet-400")}>{durationLabel}</span>
                {thinking && (
                    <ChevronDown
                        className={cn(
                            "w-3 h-3 transition-transform duration-200",
                            !isExpanded && "-rotate-90"
                        )}
                    />
                )}
            </button>

            <AnimatePresence>
                {isExpanded && thinking && (
                    <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: "auto", opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.2, ease: "easeOut" }}
                        className="overflow-hidden"
                    >
                        <div className="mt-1.5 pl-4 border-l-2 border-violet-500/20 text-muted-foreground/60">
                            <MarkdownContent content={thinking} size="xs" />
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
}

// ============================================
// Tool Call Badge Component
// ============================================

function ToolCallBadge({ toolCall }: { toolCall: ToolCall }) {
    const [isExpanded, setIsExpanded] = useState(false);

    const statusIcon =
        toolCall.status === "running" ? (
            <Loader2 className="w-3 h-3 animate-spin text-blue-400" />
        ) : toolCall.status === "completed" ? (
            <Check className="w-3 h-3 text-emerald-400" />
        ) : (
            <X className="w-3 h-3 text-red-400" />
        );

    return (
        <div className="mb-1.5">
            <button
                onClick={() => setIsExpanded(!isExpanded)}
                className={cn(
                    "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-medium transition-all duration-150 cursor-pointer",
                    "bg-muted/60 hover:bg-muted text-muted-foreground border border-transparent hover:border-border/50"
                )}
            >
                {isExpanded ? (
                    <ChevronDown className="w-3 h-3" />
                ) : (
                    <ChevronRight className="w-3 h-3" />
                )}
                <Wrench className="w-3 h-3 text-blue-400/70" />
                <span className="text-foreground/80">{toolCall.name}</span>
                {statusIcon}
            </button>

            <AnimatePresence>
                {isExpanded && (
                    <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: "auto", opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.15 }}
                        className="overflow-hidden"
                    >
                        <div className="mt-1 ml-2 p-2 rounded-md bg-muted/30 border border-border/30">
                            {toolCall.args && (
                                <div className="mb-1.5">
                                    <span className="text-[10px] text-muted-foreground/50 uppercase tracking-wider font-semibold">
                                        Input
                                    </span>
                                    <pre className="text-[10px] text-muted-foreground/70 mt-0.5 whitespace-pre-wrap break-all font-mono">
                                        {JSON.stringify(toolCall.args, null, 2)}
                                    </pre>
                                </div>
                            )}
                            {toolCall.result && (
                                <div>
                                    <span className="text-[10px] text-muted-foreground/50 uppercase tracking-wider font-semibold">
                                        Output
                                    </span>
                                    <pre className="text-[10px] text-muted-foreground/70 mt-0.5 whitespace-pre-wrap break-all font-mono">
                                        {toolCall.result}
                                    </pre>
                                </div>
                            )}
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
}

// ============================================
// Message Actions Component  
// ============================================

function MessageActions({ content }: { content: string }) {
    const [copied, setCopied] = useState(false);

    const handleCopy = useCallback(() => {
        navigator.clipboard.writeText(content);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    }, [content]);

    return (
        <div className="flex items-center gap-0.5 mt-1.5 opacity-0 group-hover/msg:opacity-100 transition-opacity duration-150">
            <button
                onClick={handleCopy}
                className="p-1 rounded hover:bg-muted/60 text-muted-foreground/40 hover:text-muted-foreground/70 transition-colors cursor-pointer"
                title="Copy"
            >
                {copied ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
            </button>
        </div>
    );
}

// ============================================
// Typing Indicator Component
// ============================================

function TypingIndicator() {
    return (
        <div className="flex items-center gap-2 py-2 px-1">
            <div className="flex items-center gap-1.5">
                <Loader2 className="w-3.5 h-3.5 text-violet-400 animate-spin" />
                <span className="text-xs text-muted-foreground/60">
                    Kureita is thinking
                </span>
                <div className="flex gap-0.5 items-center">
                    {[0, 1, 2].map((i) => (
                        <motion.span
                            key={i}
                            animate={{ opacity: [0.2, 1, 0.2] }}
                            transition={{
                                duration: 1.2,
                                repeat: Infinity,
                                delay: i * 0.2,
                            }}
                            className="w-1 h-1 rounded-full bg-violet-400"
                        />
                    ))}
                </div>
            </div>
        </div>
    );
}

// ============================================
// Message Component
// ============================================

function ChatMessageItem({ message }: { message: ChatMessage }) {
    const isUser = message.role === "user";

    if (isUser) {
        // Parse multiple attachments
        const attachmentRegex = /\[Attached: (.*?)\] \((.*?)\) - URL: (.*?)$/gm;
        let cleanContent = message.content;
        const attachments: { filename: string; type: string; url: string }[] = [];

        let match;
        while ((match = attachmentRegex.exec(message.content)) !== null) {
            attachments.push({
                filename: match[1],
                type: match[2],
                url: match[3],
            });
            cleanContent = cleanContent.replace(match[0], "");
        }
        cleanContent = cleanContent.trim();

        return (
            <div className="flex justify-end mb-4">
                <div className="max-w-[85%]">
                    <div className="rounded-2xl rounded-br-md px-3.5 py-2 text-[13px] bg-primary text-primary-foreground leading-relaxed">
                        {cleanContent && <p><HighlightedReferences text={cleanContent} /></p>}
                        {attachments.length > 0 && (
                            <div className={`flex flex-wrap gap-1.5 ${cleanContent ? 'mt-1.5' : ''}`}>
                                {attachments.map((att, idx) => (
                                    <div key={idx} className="rounded-lg overflow-hidden border border-primary-foreground/20 max-w-[120px]">
                                        {att.type.startsWith("image") && (
                                            <img src={att.url} alt={att.filename} className="w-full h-auto object-cover" />
                                        )}
                                        {att.type.startsWith("video") && (
                                            <video src={att.url} className="w-full h-auto" controls />
                                        )}
                                        {!att.type.startsWith("image") && !att.type.startsWith("video") && (
                                            <div className="p-2 text-xs flex items-center gap-1">
                                                <Paperclip className="w-3 h-3" />
                                                <span className="truncate">{att.filename}</span>
                                            </div>
                                        )}
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </div>
            </div>
        );
    }

    // Assistant message with rich rendering
    return (
        <div className="mb-5 group/msg">
            <div className="max-w-full">
                {/* Thinking block */}
                <ThinkingBlock
                    thinking={message.thinking}
                    durationMs={message.thinking_duration_ms}
                />

                {/* Tool calls */}
                {message.tool_calls && message.tool_calls.length > 0 && (
                    <div className="mb-2 space-y-0.5">
                        {message.tool_calls.map((tc, idx) => (
                            <ToolCallBadge key={idx} toolCall={tc} />
                        ))}
                    </div>
                )}

                {/* Main content */}
                <div className="text-foreground/90">
                    <MarkdownContent content={message.content} size="sm" />
                </div>

                {/* Actions */}
                <MessageActions content={message.content} />
            </div>
        </div>
    );
}

// ============================================
// Cursor-style Input Component
// ============================================

// Helper to get node type icon
function getNodeTypeIcon(type: string) {
    switch (type) {
        case 'text': return <Type className="w-3 h-3" />;
        case 'imageGen': return <ImageIcon className="w-3 h-3" />;
        case 'videoGen': return <Video className="w-3 h-3" />;
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
        case 'vision': return 'Vision';
        case 'editorAgent': return 'Editor Agent';
        case 'mediaUpload': return 'Media Upload';
        case 'audioGen': return 'Audio Gen';
        default: return type;
    }
}

interface Attachment {
    url: string;
    type: string;
    filename: string;
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
}: {
    value: string;
    onChange: (val: string) => void;
    onSubmit: () => void;
    isLoading: boolean;
    pendingAttachments: Attachment[];
    onRemoveAttachment: (index: number) => void;
    onFileUpload: (e: React.ChangeEvent<HTMLInputElement>) => void;
    isUploading: boolean;
}) {
    const textareaRef = useRef<HTMLTextAreaElement>(null);
    const [showContextMenu, setShowContextMenu] = useState(false);
    const contextMenuRef = useRef<HTMLDivElement>(null);
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

    // Close context menu when clicking outside
    useEffect(() => {
        const handleClickOutside = (e: MouseEvent) => {
            if (contextMenuRef.current && !contextMenuRef.current.contains(e.target as Node)) {
                setShowContextMenu(false);
            }
        };
        if (showContextMenu) {
            document.addEventListener('mousedown', handleClickOutside);
            return () => document.removeEventListener('mousedown', handleClickOutside);
        }
    }, [showContextMenu]);

    const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            if (value.trim() || pendingAttachments.length > 0) {
                onSubmit();
            }
        }
    };

    const hasAttachments = pendingAttachments.length > 0;

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
                className={cn(
                    "relative rounded-xl border transition-all duration-200",
                    "bg-muted/30 border-border/50",
                    "focus-within:border-primary/40 focus-within:bg-muted/50",
                    "shadow-sm focus-within:shadow-md focus-within:shadow-primary/5"
                )}
            >
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
                                            <div className="relative h-14 w-14 rounded-lg overflow-hidden border border-border/40 bg-muted/40">
                                                <img src={att.url} alt={att.filename} className="h-full w-full object-cover" />
                                                <button
                                                    onClick={() => onRemoveAttachment(idx)}
                                                    className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-destructive text-destructive-foreground flex items-center justify-center opacity-0 group-hover/att:opacity-100 transition-opacity cursor-pointer shadow-sm"
                                                >
                                                    <X className="w-2.5 h-2.5" />
                                                </button>
                                            </div>
                                        ) : att.type.startsWith("video") ? (
                                            <div className="relative h-14 w-20 rounded-lg overflow-hidden border border-border/40 bg-muted/40">
                                                <video src={att.url} className="h-full w-full object-cover" />
                                                <div className="absolute inset-0 flex items-center justify-center bg-black/20">
                                                    <Video className="w-4 h-4 text-white/80" />
                                                </div>
                                                <button
                                                    onClick={() => onRemoveAttachment(idx)}
                                                    className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-destructive text-destructive-foreground flex items-center justify-center opacity-0 group-hover/att:opacity-100 transition-opacity cursor-pointer shadow-sm"
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
                        <div className="flex items-center gap-1 px-2 py-1 rounded-md text-[11px] text-muted-foreground/50">
                            <Cpu className="w-3 h-3 text-violet-400/50" />
                            <span>gemini-2.5-flash</span>
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
                                onChange={onFileUpload}
                                disabled={isUploading || isLoading}
                                accept="image/*,video/*"
                                multiple
                            />
                        </label>

                        {/* Submit button */}
                        <button
                            onClick={onSubmit}
                            disabled={(!value.trim() && pendingAttachments.length === 0) || isLoading}
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
// Main Agent Sidebar
// ============================================

export function AgentSidebar() {
    const { chatHistory, addChatMessage, setNodes, setEdges, nodes, edges } = useWorkflowStore();
    const [input, setInput] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const [isUploading, setIsUploading] = useState(false);
    const [pendingAttachments, setPendingAttachments] = useState<Attachment[]>([]);
    const messagesEndRef = useRef<HTMLDivElement>(null);

    // Auto-scroll to bottom when messages change
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [chatHistory, isLoading]);

    const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const files = e.target.files;
        if (!files || files.length === 0) return;

        setIsUploading(true);
        try {
            for (const file of Array.from(files)) {
                const formData = new FormData();
                formData.append("file", file);

                const response = await api.post("/api/assets/upload", formData, {
                    headers: { "Content-Type": "multipart/form-data" },
                });

                if (response.data.success) {
                    const { filename, url, type } = response.data;
                    setPendingAttachments((prev) => [...prev, { filename, url, type }]);
                }
            }
        } catch (error) {
            console.error("Upload error:", error);
        } finally {
            setIsUploading(false);
            e.target.value = "";
        }
    };

    const handleRemoveAttachment = (index: number) => {
        setPendingAttachments((prev) => prev.filter((_, i) => i !== index));
    };

    // Show welcome message if no chat history
    const displayMessages: ChatMessage[] =
        chatHistory.length === 0
            ? [
                {
                    role: "assistant" as const,
                    content:
                        "Hello! I'm your AI creative assistant powered by Gemini. Tell me what video you want to create, and I'll build the workflow for you.",
                },
            ]
            : chatHistory;

    const handleSubmit = async () => {
        if ((!input.trim() && pendingAttachments.length === 0) || isLoading) return;

        let userMessage = input.trim();
        if (pendingAttachments.length > 0) {
            const attachmentLines = pendingAttachments.map(
                (att) => `[Attached: ${att.filename}] (${att.type}) - URL: ${att.url}`
            );
            userMessage += '\n' + attachmentLines.join('\n');
        }

        setInput("");
        setPendingAttachments([]);
        addChatMessage({ role: "user", content: userMessage });
        setIsLoading(true);

        try {
            const response = await api.post("/api/agent/flow", {
                prompt: userMessage,
                current_nodes: nodes,
                current_edges: edges,
                chat_history: chatHistory,
            });

            const result = response.data;

            if (result.success) {
                if (result.nodes && result.nodes.length > 0) {
                    setNodes(result.nodes);
                    setEdges(result.edges || []);
                }

                addChatMessage({
                    role: "assistant",
                    content: result.message || "I've updated the workflow based on your request.",
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
        } catch (error) {
            console.error("Agent error:", error);
            addChatMessage({
                role: "assistant",
                content: "Sorry, something went wrong with the AI service.",
            });
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="w-[420px] border-r h-screen bg-card flex flex-col shadow-xl z-20 shrink-0 sticky top-0">
            {/* Header */}
            <div className="px-4 py-3 flex items-center gap-2.5 z-10 shadow-[0_4px_20px_-4px_rgba(0,0,0,0.1)]">
                <div className="w-6 h-6 rounded-lg bg-gradient-to-br from-violet-500/20 to-blue-500/20 flex items-center justify-center">
                    <img src="/kureita_logo.png" alt="Kureita" className="w-6 h-6" />
                </div>
                <div className="flex-1">
                    <h2 className="font-semibold text-sm">Kureita</h2>
                    <p className="text-[10px] text-muted-foreground/60">AI Workflow Builder</p>
                </div>
            </div>

            {/* Messages Area */}
            <div className="flex-1 overflow-y-auto px-4 py-4">
                {displayMessages.map((msg, i) => (
                    <ChatMessageItem
                        key={`${i}-${msg.role}-${msg.content.substring(0, 20)}`}
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
            />
        </div>
    );
}
