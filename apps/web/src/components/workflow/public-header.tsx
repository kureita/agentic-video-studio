"use client";

import { LogIn, Play, MessageSquare, Eye } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useWorkflowStore } from "@/lib/workflow-store";
import { usePublicView } from "@/lib/public-view-context";
import { usePublicMobileTab } from "@/lib/public-mobile-tab-context";

export function PublicWorkflowHeader() {
    const { name } = useWorkflowStore();
    const { requireLogin } = usePublicView();
    const { setActiveTab } = usePublicMobileTab();

    return (
        <div className="h-12 md:h-14 border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 flex items-center justify-between px-2 md:px-4 sticky top-0 z-50">
            <div className="flex items-center gap-2 md:gap-4 min-w-0 flex-1">
                <div className="flex items-center gap-2 px-2">
                    <Eye className="w-4 h-4 text-muted-foreground shrink-0" />
                    <span className="text-xs text-muted-foreground font-medium hidden sm:inline">View only</span>
                </div>

                <div className="flex flex-col min-w-0 flex-1">
                    <div className="h-7 md:h-8 flex items-center px-2 font-medium text-xs md:text-sm truncate">
                        {name}
                    </div>
                </div>
            </div>

            <div className="flex items-center gap-2">
                <Button
                    onClick={() => requireLogin("Sign in to run this workflow and generate media.")}
                    className="h-8 shadow-sm gap-2"
                    variant="default"
                >
                    <Play className="w-4 h-4 fill-current" />
                    <span className="hidden sm:inline">Run All</span>
                    <span className="sm:hidden">Run</span>
                </Button>

                <Button
                    variant="outline"
                    size="sm"
                    className="h-8 gap-2"
                    onClick={() => requireLogin("Sign in to create your own workflows.")}
                >
                    <LogIn className="w-4 h-4" />
                    <span className="hidden sm:inline">Sign in</span>
                </Button>

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
    );
}
