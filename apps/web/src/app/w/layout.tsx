"use client";

import { useState, Suspense } from "react";
import { PublicViewProvider } from "@/lib/public-view-context";
import { PublicAgentSidebar } from "@/components/workflow/public-agent-sidebar";
import { PublicMobileTabContext } from "@/lib/public-mobile-tab-context";

const MOBILE_STYLES = `
@media (max-width: 767px) {
    .wf-root {
        flex-direction: column !important;
        height: 100dvh !important;
        overflow: hidden !important;
        min-height: auto !important;
    }
    .wf-sidebar {
        flex: 1 1 0% !important;
        width: 100% !important;
        min-width: 0 !important;
        max-width: 100% !important;
        overflow: hidden !important;
    }
    .wf-sidebar > div {
        width: 100% !important;
        height: 100% !important;
        border-right: none !important;
        position: static !important;
        max-width: 100% !important;
    }
    .wf-sidebar .sidebar-resize-handle {
        display: none !important;
    }
    .wf-canvas {
        flex: 1 1 0% !important;
        width: 100% !important;
        min-width: 0 !important;
        overflow: auto !important;
    }
    .wf-sidebar.wf-hidden,
    .wf-canvas.wf-hidden {
        display: none !important;
    }
}
@media (min-width: 768px) {
    .wf-sidebar.wf-hidden,
    .wf-canvas.wf-hidden {
        display: block !important;
    }
}
`;

export default function PublicWorkflowLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    const [activeTab, setActiveTab] = useState<"chat" | "canvas">("canvas");

    return (
        <PublicViewProvider>
            <PublicMobileTabContext.Provider value={{ activeTab, setActiveTab }}>
                <style dangerouslySetInnerHTML={{ __html: MOBILE_STYLES }} />

                <div className="wf-root flex min-h-screen bg-background text-foreground">
                    <div className={`wf-sidebar${activeTab !== "chat" ? " wf-hidden" : ""}`}>
                        <Suspense>
                            <PublicAgentSidebar />
                        </Suspense>
                    </div>

                    <div className={`wf-canvas flex-1 overflow-auto${activeTab !== "canvas" ? " wf-hidden" : ""}`}>
                        {children}
                    </div>
                </div>
            </PublicMobileTabContext.Provider>
        </PublicViewProvider>
    );
}
