"use client";

import { useState, useRef, useEffect } from "react";
import { LogIn, MessageSquare, Clapperboard } from "lucide-react";
import { cn } from "@/lib/utils";
import Image from "next/image";
import { useWorkflowStore } from "@/lib/workflow-store";
import { usePublicView } from "@/lib/public-view-context";
import { usePublicMobileTab } from "@/lib/public-mobile-tab-context";
import { ChatMessageItem } from "@/components/workflow/chat-messages";

export function PublicAgentSidebar() {
    const { chatHistory } = useWorkflowStore();
    const { requireLogin } = usePublicView();
    const { setActiveTab } = usePublicMobileTab();
    const messagesEndRef = useRef<HTMLDivElement>(null);

    const [sidebarWidth, setSidebarWidth] = useState(360);
    const [isResizing, setIsResizing] = useState(false);
    const sidebarRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [chatHistory.length]);

    useEffect(() => {
        if (!isResizing) return;
        const handleMouseMove = (e: MouseEvent) => {
            const newWidth = Math.min(Math.max(e.clientX, 280), 600);
            setSidebarWidth(newWidth);
        };
        const handleMouseUp = () => setIsResizing(false);
        window.addEventListener("mousemove", handleMouseMove);
        window.addEventListener("mouseup", handleMouseUp);
        return () => {
            window.removeEventListener("mousemove", handleMouseMove);
            window.removeEventListener("mouseup", handleMouseUp);
        };
    }, [isResizing]);

    return (
        <div
            ref={sidebarRef}
            className="border-r h-screen bg-card flex flex-col shadow-xl z-20 shrink-0 sticky top-0 relative"
            style={{ width: `${sidebarWidth}px` }}
        >
            {/* Header */}
            <div className="px-4 py-3 flex flex-col gap-2 z-10 shadow-[0_4px_20px_-4px_rgba(0,0,0,0.1)]">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2.5">
                        <div className="w-6 h-6 rounded-lg bg-gradient-to-br from-violet-500/20 to-blue-500/20 flex items-center justify-center">
                            <Image src="/kureita_logo.png" alt="Kureita" width={24} height={24} className="w-6 h-6" unoptimized />
                        </div>
                        <div className="flex-1 text-left">
                            <h2 className="font-semibold text-sm">Kureita</h2>
                            <p className="text-[10px] text-muted-foreground/60">AI Workflow Builder</p>
                        </div>
                    </div>

                    {/* Mobile: Switch to Canvas */}
                    <button
                        onClick={() => setActiveTab("canvas")}
                        className="md:hidden flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-muted/60 transition-colors"
                    >
                        <Clapperboard className="w-4 h-4" />
                        <span>Canvas</span>
                    </button>
                </div>
            </div>

            {/* Messages Area */}
            <div className="flex-1 overflow-y-auto px-4 py-4">
                {chatHistory.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-full text-center px-6 gap-4">
                        <MessageSquare className="w-10 h-10 text-muted-foreground/30" />
                        <div>
                            <p className="text-sm font-medium text-muted-foreground">AI Chat History</p>
                            <p className="text-xs text-muted-foreground/60 mt-1">
                                Sign in to chat with the AI assistant and build workflows.
                            </p>
                        </div>
                    </div>
                ) : (
                    chatHistory.map((msg, i) => (
                        <ChatMessageItem key={i} message={msg} />
                    ))
                )}
                <div ref={messagesEndRef} />
            </div>

            {/* Login CTA Input Area */}
            <div className="p-4 border-t border-border">
                <button
                    onClick={() => requireLogin("Sign in to chat with the AI assistant and modify this workflow.")}
                    className="w-full flex items-center gap-3 px-4 py-3 rounded-xl bg-muted/40 border border-border/50 hover:border-primary/30 hover:bg-muted/60 transition-all cursor-pointer group"
                >
                    <div className="flex-1 text-left text-sm text-muted-foreground/60 group-hover:text-muted-foreground transition-colors">
                        Ask AI to modify workflow...
                    </div>
                    <span className="inline-flex items-center h-7 gap-1.5 text-xs font-medium text-muted-foreground">
                        <LogIn className="w-3.5 h-3.5" />
                        Sign in
                    </span>
                </button>
            </div>

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
                <div className={cn(
                    "absolute top-1/2 -translate-y-1/2 right-0 w-[3px] h-8 rounded-full transition-opacity duration-150",
                    "bg-muted-foreground/20 group-hover:bg-primary/40",
                    isResizing ? "opacity-100 bg-primary/60" : "opacity-0 group-hover:opacity-100"
                )} />
            </div>

            {isResizing && (
                <div className="fixed inset-0 z-20 cursor-col-resize" />
            )}
        </div>
    );
}
