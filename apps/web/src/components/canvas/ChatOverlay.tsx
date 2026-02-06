"use client";

import { useState, useRef, useEffect } from "react";
import { Send, Bot, Sparkles, ChevronDown } from "lucide-react";
import { Button, Textarea } from "@/components/ui";
import { cn } from "@/lib/utils";
import * as Popover from "@radix-ui/react-popover";

interface ChatOverlayProps {
    onPlanReceived: (plan: any) => void;
}

type ModelType = "openai" | "anthropic" | "gemini";

const models: { id: ModelType; label: string }[] = [
    { id: "openai", label: "GPT-4o" },
    { id: "anthropic", label: "Claude 3.5 Sonnet" },
    { id: "gemini", label: "Gemini 1.5 Pro" },
];

export function ChatOverlay({ onPlanReceived }: ChatOverlayProps) {
    const [messages, setMessages] = useState<{ role: "user" | "assistant"; content: string }[]>([]);
    const [prompt, setPrompt] = useState("");
    const [isThinking, setIsThinking] = useState(false);
    const [selectedModel, setSelectedModel] = useState<ModelType>("openai");

    // Ref for auto-scrolling
    const scrollRef = useRef<HTMLDivElement>(null);

    const activeModel = models.find(m => m.id === selectedModel);

    // Auto-scroll to bottom when messages change
    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [messages, isThinking]);

    const handleSubmit = async () => {
        if (!prompt.trim()) return;

        const newMessages = [...messages, { role: "user" as const, content: prompt.trim() }];
        setMessages(newMessages);
        setPrompt("");
        setIsThinking(true);

        try {
            const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/director/plan`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ messages: newMessages, model: selectedModel }),
            });

            if (!response.ok) throw new Error("Failed to get plan");

            const plan = await response.json();
            console.log("Received Plan:", plan);
            onPlanReceived(plan);

            // Add helpful assistant response based on the plan narrative
            setMessages(prev => [...prev, {
                role: "assistant",
                content: plan.narrative || "I've updated the workflow based on your request."
            }]);

        } catch (error) {
            console.error("Director Error:", error);
            setMessages(prev => [...prev, {
                role: "assistant",
                content: "Sorry, I encountered an error while building that plan. Please try again."
            }]);
        } finally {
            setIsThinking(false);
        }
    };

    return (
        <div className="flex flex-col h-full bg-background border-l border-border/60">

            {/* Header */}
            <div className="flex justify-between items-center px-4 py-3 border-b border-border/50 bg-background-secondary/10 shrink-0">
                <div className="flex items-center gap-2.5">
                    <div>
                        <h3 className="font-semibold text-sm leading-none mb-0.5">AI Director</h3>
                        <p className="text-[9px] text-foreground-muted uppercase tracking-wider font-medium">Assistant</p>
                    </div>
                </div>

                {/* Model Selector - Compact */}
                <Popover.Root>
                    <Popover.Trigger asChild>
                        <button className="flex items-center gap-1.5 px-2 py-1 rounded-md hover:bg-background-secondary transition-all text-[10px] font-medium text-foreground-muted hover:text-foreground border border-transparent hover:border-border/50">
                            <div className="flex items-center gap-1.5 opacity-80">
                                <span>{activeModel?.label}</span>
                            </div>
                            <ChevronDown className="w-2.5 h-2.5 opacity-30" />
                        </button>
                    </Popover.Trigger>
                    <Popover.Portal>
                        <Popover.Content
                            className="w-48 bg-popover border border-border rounded-lg shadow-xl p-1 z-[60] flex flex-col gap-0.5 animate-in fade-in zoom-in-95 duration-100"
                            side="bottom"
                            align="end"
                            sideOffset={5}
                        >
                            {models.map((m) => (
                                <button
                                    key={m.id}
                                    onClick={() => setSelectedModel(m.id)}
                                    className={cn(
                                        "flex items-center gap-3 px-3 py-2 rounded-md text-xs text-left transition-colors relative",
                                        selectedModel === m.id
                                            ? "bg-indigo-50/50 text-indigo-700 font-medium"
                                            : "hover:bg-accent/50 text-foreground"
                                    )}
                                >
                                    <span>{m.label}</span>
                                    {selectedModel === m.id && (
                                        <div className="absolute right-2 w-1.5 h-1.5 rounded-full bg-indigo-600" />
                                    )}
                                </button>
                            ))}
                        </Popover.Content>
                    </Popover.Portal>
                </Popover.Root>
            </div>

            {/* Messages Area */}
            <div
                ref={scrollRef}
                className="flex-1 overflow-y-auto p-4 space-y-4 bg-background/30"
            >
                {messages.length === 0 && (
                    <div className="h-full flex flex-col items-center justify-center text-center text-foreground-muted p-4 opacity-40">
                        <Bot className="w-10 h-10 mb-3 opacity-20" />
                        <p className="text-sm font-medium mb-1">How can I help you?</p>
                        <p className="text-xs max-w-[180px]">Describe a workflow, and I'll build it.</p>
                    </div>
                )}

                {messages.map((msg, idx) => (
                    <div key={idx} className={cn("flex w-full animate-in fade-in slide-in-from-bottom-2 duration-300", msg.role === "user" ? "justify-end" : "justify-start")}>
                        <div className={cn(
                            "max-w-[90%] rounded-xl px-3.5 py-2 text-xs leading-relaxed shadow-sm",
                            msg.role === "user"
                                ? "bg-indigo-600 text-white rounded-br-none"
                                : "bg-background-secondary/50 border border-border text-foreground rounded-bl-none shadow-none"
                        )}>
                            {msg.content}
                        </div>
                    </div>
                ))}

                {isThinking && (
                    <div className="flex justify-start animate-in fade-in zoom-in-90 duration-300">
                        <div className="bg-background-secondary/30 border border-border/50 text-foreground rounded-xl rounded-bl-none px-3 py-2 text-xs flex items-center gap-2 shadow-sm">
                            <Sparkles className="w-3 h-3 animate-spin text-indigo-500" />
                            <span className="font-medium opacity-70">Thinking...</span>
                        </div>
                    </div>
                )}
            </div>

            {/* Input Area */}
            <div className="p-3 bg-background border-t border-border/50 shrink-0">
                <div className="relative group">
                    <Textarea
                        placeholder="Type a message..."
                        className="min-h-[50px] max-h-[140px] py-3 px-4 text-xs resize-none bg-background-secondary/30 border-border focus:bg-background focus:ring-1 focus:ring-indigo-500/20 transition-all rounded-xl"
                        value={prompt}
                        onChange={(e) => setPrompt(e.target.value)}
                        onKeyDown={(e) => {
                            if (e.key === "Enter" && !e.shiftKey) {
                                e.preventDefault();
                                handleSubmit();
                            }
                        }}
                    />
                    <div className="absolute right-2 bottom-2">
                        <Button
                            size="icon"
                            className="h-7 w-7 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white shadow-sm transition-transform active:scale-95"
                            onClick={handleSubmit}
                            disabled={!prompt.trim() || isThinking}
                        >
                            <Send className="w-3.5 h-3.5" />
                        </Button>
                    </div>
                </div>
                <div className="flex justify-center mt-2">
                    <span className="text-[9px] text-foreground-muted opacity-50">AI can make mistakes. Check generated graphs.</span>
                </div>
            </div>

        </div>
    );
}
