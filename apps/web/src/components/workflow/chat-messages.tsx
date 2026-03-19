"use client";

import { useState, useCallback } from "react";
import {
    Loader2,
    ChevronDown,
    ChevronRight,
    Paperclip,
    X,
    Check,
    Copy,
    Wrench,
    Brain,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { S3Image } from "@/components/ui/s3-image";
import { ChatMessage, ToolCall } from "@/lib/workflow-api";
import { motion, AnimatePresence } from "framer-motion";
import { MarkdownContent, HighlightedReferences } from "@/components/workflow/markdown-content";

// ============================================
// Thinking Block
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
// Tool Call Badge
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
// Message Actions (copy)
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
// Typing Indicator
// ============================================

export function TypingIndicator() {
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
// Chat Message Item
// ============================================

export function ChatMessageItem({ message }: { message: ChatMessage }) {
    const isUser = message.role === "user";

    if (isUser) {
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
            <div className="flex justify-end mb-5 mt-2">
                <div className="max-w-[88%]">
                    <div className="rounded-2xl rounded-br-[4px] px-4 py-2.5 text-[13.5px] bg-muted/80 text-foreground/90 border border-border/40 shadow-sm leading-relaxed">
                        {cleanContent && <div className="whitespace-pre-wrap"><HighlightedReferences text={cleanContent} /></div>}
                        {attachments.length > 0 && (
                            <div className={`flex flex-wrap gap-1.5 ${cleanContent ? 'mt-3' : ''}`}>
                                {attachments.map((att, idx) => (
                                    <div key={idx} className="rounded-lg overflow-hidden border border-border/50 bg-muted/40 max-w-[120px] shadow-sm">
                                        {att.type.startsWith("image") && (
                                            <S3Image src={att.url} alt={att.filename} width={200} height={200} className="w-full h-auto object-cover" unoptimized />
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

    return (
        <div className="mb-5 group/msg">
            <div className="max-w-full">
                <ThinkingBlock
                    thinking={message.thinking}
                    durationMs={message.thinking_duration_ms}
                />

                {message.tool_calls && message.tool_calls.length > 0 && (
                    <div className="mb-2 space-y-0.5">
                        {message.tool_calls.map((tc, idx) => (
                            <ToolCallBadge key={idx} toolCall={tc} />
                        ))}
                    </div>
                )}

                <div className="text-foreground/90">
                    <MarkdownContent content={message.content} size="sm" />
                </div>

                <MessageActions content={message.content} />
            </div>
        </div>
    );
}
