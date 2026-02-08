"use client";

import { useState, useRef, useCallback, useEffect, KeyboardEvent } from "react";
import { Send, X, Sparkles, Check, XCircle, Loader2, ChevronDown, Trash2, StopCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useAgentChat, ModelProvider } from "@/hooks/use-agent-chat";
import { useWorkflowStore, AgentAction } from "@/lib/workflow-store";
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

interface AIPanelProps {
    isOpen: boolean;
    onClose: () => void;
}

const MODEL_OPTIONS: { value: ModelProvider; label: string; icon: string }[] = [
    { value: "openai", label: "GPT-4o", icon: "🟢" },
    { value: "claude", label: "Claude 3.5 Sonnet", icon: "🟠" },
    { value: "gemini", label: "Gemini 2.5 Flash", icon: "🔵" },
];

export function AgentPanel({ isOpen, onClose }: AIPanelProps) {
    console.log("Rendering AgentPanel Premium v3 - FORCE UPDATE");
    const [inputValue, setInputValue] = useState("");
    const [panelWidth, setPanelWidth] = useState(400);
    const [isResizing, setIsResizing] = useState(false);

    const panelRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLTextAreaElement>(null);
    const messagesEndRef = useRef<HTMLDivElement>(null);

    const { nodes, edges, applyAgentActions, setPendingAgentActions } = useWorkflowStore();

    const {
        messages,
        isLoading,
        status,
        thinking,
        pendingActions,
        model,
        setModel,
        sendMessage,
        clearMessages,
        cancelRequest
    } = useAgentChat({
        onAction: (action) => {
            console.log("[AIPanel] Action received:", action);
        },
        onComplete: (response) => {
            if (response.actions && response.actions.length > 0) {
                setPendingAgentActions(response.actions);
            }
        },
    });

    // Auto-scroll
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages, thinking, status]);

    // Handle resize
    const handleResizeStart = useCallback((e: React.MouseEvent) => {
        e.preventDefault();
        setIsResizing(true);
    }, []);

    useEffect(() => {
        const handleMouseMove = (e: MouseEvent) => {
            if (!isResizing || !panelRef.current) return;
            const panelRect = panelRef.current.getBoundingClientRect();
            // Calculate new width: mouse X position relative to panel's left edge
            const newWidth = e.clientX - panelRect.left;
            setPanelWidth(Math.max(320, Math.min(800, newWidth)));
        };
        const handleMouseUp = () => {
            setIsResizing(false);
            document.body.style.cursor = "";
            document.body.style.userSelect = "";
        };

        if (isResizing) {
            document.addEventListener("mousemove", handleMouseMove);
            document.addEventListener("mouseup", handleMouseUp);
            document.body.style.cursor = "col-resize";
            document.body.style.userSelect = "none";
        }
        return () => {
            document.removeEventListener("mousemove", handleMouseMove);
            document.removeEventListener("mouseup", handleMouseUp);
        };
    }, [isResizing]);

    const handleSend = useCallback((text?: string) => {
        const contentToSend = text || inputValue;
        if (!contentToSend.trim() || isLoading) return;
        sendMessage(contentToSend, { nodes, edges });
        setInputValue("");
        if (inputRef.current) inputRef.current.focus();
    }, [inputValue, isLoading, sendMessage, nodes, edges]);

    const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    const handleApplyActions = useCallback(() => {
        if (pendingActions.length > 0) applyAgentActions(pendingActions as AgentAction[]);
    }, [pendingActions, applyAgentActions]);

    const handleRejectActions = useCallback(() => {
        setPendingAgentActions([]);
    }, [setPendingAgentActions]);

    if (!isOpen) return null;

    const selectedModel = MODEL_OPTIONS.find(m => m.value === model) || MODEL_OPTIONS[0];

    return (
        <div
            ref={panelRef}
            className={cn(
                "h-full z-20 flex flex-col bg-card text-card-foreground border-r border-border shadow-xl",
                "animate-in slide-in-from-left duration-200"
            )}
            style={{ width: panelWidth }}
        >
            {/* Minimalist Header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-border/40 select-none bg-blue-950/30 backdrop-blur-sm">
                <div className="flex items-center gap-3 p-1.5 -ml-1.5">
                    <div className="relative flex items-center justify-center w-8 h-8 rounded-xl bg-primary/10 border border-primary/20">
                        <Sparkles className="w-4 h-4 text-primary" />
                        <div className="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full bg-green-500 border-2 border-card" />
                    </div>
                    <div>
                        <h3 className="font-medium text-sm leading-none text-blue-400">Kureita AI V4</h3>
                        <p className="text-[10px] text-muted-foreground mt-0.5 font-medium tracking-wide">
                            AI Assistant
                        </p>
                    </div>
                </div>

                <div className="flex items-center gap-1">
                    <Button variant="ghost" size="icon" onClick={clearMessages} className="h-7 w-7 opacity-50 hover:opacity-100 transition-opacity" title="Clear Chat">
                        <Trash2 className="w-3.5 h-3.5" />
                    </Button>
                    <Button variant="ghost" size="icon" onClick={onClose} className="h-7 w-7 opacity-50 hover:opacity-100 transition-opacity">
                        <X className="w-4 h-4" />
                    </Button>
                </div>
            </div>

            {/* Chat Area */}
            <div className="flex-1 overflow-y-auto px-4 py-4 space-y-6 bg-background/50 scrollbar-thin scrollbar-thumb-border scrollbar-track-transparent">
                {messages.length === 0 && (
                    <div className="flex flex-col items-center justify-center h-full text-center px-6 opacity-40 select-none">
                        <Sparkles className="w-12 h-12 mb-4 text-primary/50" />
                        <p className="text-sm font-medium">How can I help you build today?</p>
                        <div className="mt-6 flex flex-wrap justify-center gap-2">
                            {["Create a promo video", "Build a social media workflow", "Edit this workflow"].map((suggestion, i) => (
                                <button
                                    key={i}
                                    className="px-3 py-1.5 text-xs bg-muted/50 hover:bg-muted border border-border/50 rounded-full transition-colors"
                                    onClick={() => handleSend(suggestion)}
                                >
                                    {suggestion}
                                </button>
                            ))}
                        </div>
                    </div>
                )}

                {messages.map((msg, idx) => (
                    <div
                        key={idx}
                        className={cn(
                            "flex flex-col max-w-[90%]",
                            msg.role === "user" ? "ml-auto items-end" : "mr-auto items-start"
                        )}
                    >
                        <div
                            className={cn(
                                "px-4 py-2.5 text-sm rounded-2xl shadow-sm",
                                msg.role === "user"
                                    ? "bg-primary text-primary-foreground rounded-br-sm"
                                    : "bg-muted/80 text-foreground border border-border/50 rounded-bl-sm"
                            )}
                        >
                            <div className="whitespace-pre-wrap leading-relaxed">{msg.content}</div>
                        </div>

                        {/* Clarifying Questions as Chips */}
                        {msg.role === "assistant" && msg.questions && msg.questions.length > 0 && (
                            <div className="mt-3 flex flex-col gap-2 w-full animate-in fade-in slide-in-from-top-1 duration-300">
                                <span className="text-[10px] font-medium text-muted-foreground ml-1 uppercase tracking-wider">Suggested Responses</span>
                                <div className="flex flex-wrap gap-2">
                                    {msg.questions.map((q, qIdx) => (
                                        <button
                                            key={qIdx}
                                            className="text-left px-3 py-2 text-xs bg-primary/5 hover:bg-primary/10 border border-primary/20 text-primary-foreground hover:text-primary rounded-xl transition-colors cursor-pointer"
                                            onClick={() => handleSend(q)}
                                        >
                                            ↳ {q}
                                        </button>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                ))}

                {/* Thinking Indicator */}
                {isLoading && (
                    <div className="flex flex-col mr-auto max-w-[90%] items-start animate-pulse">
                        <div className="px-4 py-2.5 bg-muted/50 border border-border/30 rounded-2xl rounded-bl-sm flex items-center gap-2">
                            <Loader2 className="w-3.5 h-3.5 animate-spin text-primary" />
                            <span className="text-xs font-medium text-muted-foreground">{status || "Reasoning..."}</span>
                        </div>
                        {thinking && (
                            <div className="mt-2 ml-1 text-xs text-muted-foreground italic max-w-xs truncate">
                                ↳ {thinking}
                            </div>
                        )}
                    </div>
                )}

                {/* Function Call / Action Preview */}
                {pendingActions.length > 0 && !isLoading && (
                    <div className="mx-4 my-2 p-3 bg-gradient-to-r from-primary/5 to-transparent border border-primary/10 rounded-xl animate-in zoom-in-95 duration-200">
                        <div className="flex items-center justify-between mb-2">
                            <span className="text-xs font-medium text-primary flex items-center gap-1.5">
                                <Sparkles className="w-3 h-3" />
                                Proposed Changes ({pendingActions.length})
                            </span>
                        </div>
                        <div className="space-y-1 mb-3">
                            {pendingActions.slice(0, 3).map((a, i) => (
                                <div key={i} className="text-xs text-muted-foreground flex items-center gap-2">
                                    <div className="w-1 h-1 rounded-full bg-primary/50" />
                                    {a.type}: <span className="text-foreground/80">{a.node?.data?.label || a.nodeId || "Workflow"}</span>
                                </div>
                            ))}
                            {pendingActions.length > 3 && (
                                <div className="text-[10px] text-muted-foreground pl-3">+{pendingActions.length - 3} more actions</div>
                            )}
                        </div>
                        <div className="flex gap-2">
                            <Button size="sm" onClick={handleApplyActions} className="h-7 text-xs flex-1 bg-primary/90 hover:bg-primary">
                                <Check className="w-3 h-3 mr-1.5" /> Apply
                            </Button>
                            <Button size="sm" variant="outline" onClick={handleRejectActions} className="h-7 text-xs flex-1 bg-background/50">
                                <XCircle className="w-3 h-3 mr-1.5" /> Discard
                            </Button>
                        </div>
                    </div>
                )}

                <div ref={messagesEndRef} />
            </div>

            {/* Input Area */}
            <div className="p-4 bg-card border-t border-border/50">
                {/* Text Input */}
                <div className="relative">
                    <textarea
                        ref={inputRef}
                        value={inputValue}
                        onChange={(e) => setInputValue(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder="Ask Kureita to create or edit..."
                        className={cn(
                            "w-full min-h-[50px] max-h-[140px] px-4 py-3 pr-12 pb-10", // Added padding bottom for model selector
                            "bg-muted/30 border border-border/50 rounded-xl",
                            "text-sm placeholder:text-muted-foreground/50",
                            "resize-none outline-none focus:ring-1 focus:ring-primary/50 focus:border-primary/50 focus:bg-background transition-all"
                        )}
                        rows={1}
                        disabled={isLoading}
                    />

                    {/* Model Selector in Input Area */}
                    <div className="absolute left-3 bottom-2.5">
                        <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                                <button className="flex items-center gap-1.5 px-2 py-1 rounded-md hover:bg-muted/80 transition-colors text-xs font-medium text-muted-foreground hover:text-foreground outline-none">
                                    <span>{selectedModel.icon}</span>
                                    <span>{selectedModel.label}</span>
                                    <ChevronDown className="w-3 h-3 opacity-50" />
                                </button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="start" className="w-[200px] z-[60]">
                                {MODEL_OPTIONS.map((option) => (
                                    <DropdownMenuItem key={option.value} onClick={() => setModel(option.value)} className="gap-2 cursor-pointer text-xs">
                                        <span className="text-sm">{option.icon}</span>
                                        <span className="font-medium">{option.label}</span>
                                        {model === option.value && <Check className="w-3 h-3 ml-auto text-primary" />}
                                    </DropdownMenuItem>
                                ))}
                            </DropdownMenuContent>
                        </DropdownMenu>
                    </div>

                    <Button
                        onClick={isLoading ? cancelRequest : () => handleSend()}
                        disabled={!inputValue.trim() && !isLoading}
                        size="icon"
                        className={cn(
                            "absolute right-1.5 bottom-1.5 h-8 w-8 rounded-lg transition-all",
                            (!inputValue.trim() && !isLoading) ? "opacity-0 scale-90" : "opacity-100 scale-100",
                            isLoading && "bg-destructive/10 text-destructive hover:bg-destructive/20"
                        )}
                    >
                        {isLoading ? <StopCircle className="w-4 h-4" /> : <Send className="w-4 h-4" />}
                    </Button>
                </div>
            </div>

            {/* Resize Handle - Visible line */}
            <div
                className={cn(
                    "absolute right-0 top-0 bottom-0 w-1 cursor-col-resize z-50 transition-colors",
                    "hover:bg-primary/50 active:bg-primary",
                    "border-r border-border hover:border-primary/50",
                    isResizing && "bg-primary/20"
                )}
                onMouseDown={handleResizeStart}
            />
        </div>
    );
}
