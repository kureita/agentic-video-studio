"use client";

import { useState } from "react";
import { Sparkles, Send, Loader2, Bot, Paperclip, X } from "lucide-react";
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
    const [isUploading, setIsUploading] = useState(false);
    const [pendingAttachment, setPendingAttachment] = useState<{ url: string, type: string, filename: string } | null>(null);

    const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;

        setIsUploading(true);
        try {
            const formData = new FormData();
            formData.append("file", file);

            const response = await api.post("/api/assets/upload", formData, {
                headers: { "Content-Type": "multipart/form-data" },
            });

            if (response.data.success) {
                const { filename, url, type } = response.data;
                setPendingAttachment({ filename, url, type });
            }
        } catch (error) {
            console.error("Upload error:", error);
            // Optional: Show error toast or temporary message
        } finally {
            setIsUploading(false);
            // Reset input
            e.target.value = "";
        }
    };

    // Show welcome message if no chat history
    const displayMessages = chatHistory.length === 0
        ? [{
            role: "assistant" as const,
            content: "Hello! I'm your AI creative assistant using Gemini. Tell me what video you want to create, and I'll build the workflow for you."
        }]
        : chatHistory;

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if ((!input.trim() && !pendingAttachment) || isLoading) return;

        let userMessage = input.trim();
        if (pendingAttachment) {
            userMessage += `\n[Attached: ${pendingAttachment.filename}] (${pendingAttachment.type}) - URL: ${pendingAttachment.url}`;
        }

        setInput("");
        setPendingAttachment(null);
        addChatMessage({ role: "user", content: userMessage });
        setIsLoading(true);

        try {
            // Call the agent API
            const response = await api.post("/api/agent/flow", {
                prompt: userMessage,
                current_nodes: nodes,
                current_edges: edges,
                chat_history: chatHistory
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
                            {(() => {
                                // Check for attachment
                                const attachmentMatch = msg.content.match(/\[Attached: (.*?)\] \((.*?)\) - URL: (.*?)$/);
                                if (attachmentMatch) {
                                    const [_, filename, type, url] = attachmentMatch;
                                    const cleanContent = msg.content.replace(attachmentMatch[0], "").trim();
                                    const isImage = type.startsWith("image");
                                    const isVideo = type.startsWith("video");

                                    return (
                                        <div className="flex flex-col gap-2">
                                            {cleanContent && <p>{cleanContent}</p>}
                                            <div className="mt-1 rounded-md overflow-hidden border bg-background/50 max-w-[200px]">
                                                {isImage && <img src={url} alt={filename} className="w-full h-auto object-cover" />}
                                                {isVideo && <video src={url} className="w-full h-auto" controls />}
                                                {!isImage && !isVideo && (
                                                    <div className="p-2 text-xs flex items-center gap-1">
                                                        <Paperclip className="w-3 h-3" />
                                                        <span className="truncate">{filename}</span>
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    );
                                }
                                return msg.content;
                            })()}
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
                {pendingAttachment && (
                    <div className="mb-2 p-2 bg-muted rounded-md flex items-center justify-between">
                        <div className="flex items-center gap-2 overflow-hidden">
                            {pendingAttachment.type.startsWith("image") ? (
                                <img src={pendingAttachment.url} alt="Preview" className="h-8 w-8 object-cover rounded" />
                            ) : (
                                <div className="h-8 w-8 bg-background rounded flex items-center justify-center">
                                    <Paperclip className="w-4 h-4" />
                                </div>
                            )}
                            <span className="text-xs truncate max-w-[150px]">{pendingAttachment.filename}</span>
                        </div>
                        <Button
                            variant="ghost"
                            size="icon"
                            className="h-6 w-6"
                            onClick={() => setPendingAttachment(null)}
                        >
                            <X className="w-3 h-3" />
                        </Button>
                    </div>
                )}
                <form onSubmit={handleSubmit} className="relative flex items-center gap-2">
                    <label className={cn(
                        "cursor-pointer hover:bg-muted p-2 rounded-md transition-colors",
                        isUploading ? "opacity-50 cursor-not-allowed" : ""
                    )}>
                        <Paperclip className="w-4 h-4 text-muted-foreground" />
                        <input
                            type="file"
                            className="hidden"
                            onChange={handleFileUpload}
                            disabled={isUploading || isLoading}
                        />
                    </label>
                    <div className="relative flex-1">
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
                            disabled={(!input.trim() && !pendingAttachment) || isLoading}
                        >
                            <Send className="w-3 h-3" />
                        </Button>
                    </div>
                </form>
            </div>
        </div>
    );
}
