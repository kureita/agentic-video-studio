"use client";

import { useState } from "react";
import { Sparkles, Send, Loader2, Bot } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { useWorkflowStore } from "@/lib/workflow-store";
import { api } from "@/lib/api";

interface Message {
    role: "user" | "assistant";
    content: string;
}

export function AgentSidebar() {
    const { chatHistory, addChatMessage, setNodes, setEdges, nodes, edges } = useWorkflowStore();
    const [input, setInput] = useState("");
    const [isLoading, setIsLoading] = useState(false);

    // Show welcome message if no chat history
    const displayMessages = chatHistory.length === 0 
        ? [{
            role: "assistant" as const,
            content: "Hello! I'm your AI creative assistant using Gemini. Tell me what video you want to create, and I'll build the workflow for you."
        }]
        : chatHistory;

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!input.trim() || isLoading) return;

        const userMessage = input.trim();
        setInput("");
        addChatMessage({ role: "user", content: userMessage });
        setIsLoading(true);

        try {
            // Call the agent API
            const response = await api.post("/api/agent/flow", {
                prompt: userMessage,
                current_nodes: nodes,
                current_edges: edges
            });

            const result = response.data;

            if (result.success) {
                // Update the workflow with generated nodes/edges
                if (result.nodes && result.nodes.length > 0) {
                    setNodes(result.nodes);
                    setEdges(result.edges || []);

                    addChatMessage({
                        role: "assistant",
                        content: result.message || "I've updated the workflow based on your request."
                    });
                } else {
                    addChatMessage({
                        role: "assistant",
                        content: result.message || "I couldn't generate a workflow for that request. Please try again."
                    });
                }
            } else {
                addChatMessage({
                    role: "assistant",
                    content: "Sorry, I encountered an error creating the workflow."
                });
            }
        } catch (error) {
            console.error("Agent error:", error);
            addChatMessage({
                role: "assistant",
                content: "Sorry, something went wrong with the AI service."
            });
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="w-96 border-r h-screen bg-card flex flex-col shadow-xl z-20 shrink-0 sticky top-0">
            {/* Header */}
            <div className="p-4 flex items-center gap-2 bg-accent/5">
                <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
                    <Bot className="w-4 h-4 text-primary" />
                </div>
                <div>
                    <h2 className="font-semibold text-sm">Kureita</h2>
                    <p className="text-xs text-muted-foreground">AI Workflow Builder</p>
                </div>
            </div>

            {/* Messages Area */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {displayMessages.map((msg, i) => (
                    <div
                        key={`${i}-${msg.role}-${msg.content.substring(0, 20)}`}
                        className={cn(
                            "flex flex-col gap-1 max-w-[90%]",
                            msg.role === "user" ? "ml-auto items-end" : "mr-auto items-start"
                        )}
                    >
                        <div
                            className={cn(
                                "rounded-lg px-3 py-2 text-sm",
                                msg.role === "user"
                                    ? "bg-primary text-primary-foreground"
                                    : "bg-muted text-foreground"
                            )}
                        >
                            {msg.content}
                        </div>
                    </div>
                ))}
                {isLoading && (
                    <div className="flex items-center gap-2 text-xs text-muted-foreground ml-1">
                        <Loader2 className="w-3 h-3 animate-spin" />
                        Thinking...
                    </div>
                )}
            </div>

            {/* Input Area */}
            <div className="p-4 border-t bg-background">
                <form onSubmit={handleSubmit} className="relative">
                    <input
                        type="text"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        placeholder="Describe what you want me to do..."
                        className="w-full bg-muted/50 border border-input rounded-md pl-3 pr-10 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
                        disabled={isLoading}
                    />
                    <Button
                        type="submit"
                        size="icon"
                        className="absolute right-1 top-1 h-7 w-7"
                        disabled={!input.trim() || isLoading}
                    >
                        <Send className="w-3 h-3" />
                    </Button>
                </form>
            </div>
        </div>
    );
}
