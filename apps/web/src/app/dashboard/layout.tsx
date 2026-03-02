"use client";

import { useState, createContext, useContext } from "react";
import { usePathname } from "next/navigation";
import { DashboardHeader } from "@/components/dashboard-header";
import { AgentSidebar } from "@/components/workflow/agent-sidebar";
import { AuthGuard } from "@/components/auth/auth-guard";

// ============================================
// Mobile Tab Context
// ============================================
interface MobileTabContextType {
    activeTab: "chat" | "canvas";
    setActiveTab: (tab: "chat" | "canvas") => void;
}

export const MobileTabContext = createContext<MobileTabContextType>({
    activeTab: "chat",
    setActiveTab: () => { },
});

export function useMobileTab() {
    return useContext(MobileTabContext);
}

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
    /* Override the sidebar's inner div inline width */
    .wf-sidebar > div {
        width: 100% !important;
        height: 100% !important;
        border-right: none !important;
        position: static !important;
        max-width: 100% !important;
    }
    /* Hide the resize handle */
    .wf-sidebar .sidebar-resize-handle {
        display: none !important;
    }
    .wf-canvas {
        flex: 1 1 0% !important;
        width: 100% !important;
        min-width: 0 !important;
        overflow: auto !important;
    }
    /* On mobile: hide non-active tab */
    .wf-sidebar.wf-hidden,
    .wf-canvas.wf-hidden {
        display: none !important;
    }
}
@media (min-width: 768px) {
    /* Desktop: never apply wf-hidden, both panels visible */
    .wf-sidebar.wf-hidden,
    .wf-canvas.wf-hidden {
        display: block !important;
    }
}
`;

function WorkflowLayout({ children }: { children: React.ReactNode }) {
    const [activeTab, setActiveTab] = useState<"chat" | "canvas">("chat");

    return (
        <MobileTabContext.Provider value={{ activeTab, setActiveTab }}>
            <style dangerouslySetInnerHTML={{ __html: MOBILE_STYLES }} />

            <div className="wf-root flex min-h-screen bg-background text-foreground">
                {/* Sidebar */}
                <div className={`wf-sidebar${activeTab !== "chat" ? " wf-hidden" : ""}`}>
                    <AgentSidebar />
                </div>

                {/* Canvas */}
                <div className={`wf-canvas flex-1 overflow-auto${activeTab !== "canvas" ? " wf-hidden" : ""}`}>
                    {children}
                </div>
            </div>
        </MobileTabContext.Provider>
    );
}

export default function DashboardLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    const pathname = usePathname();
    const isWorkflowPage = pathname === "/dashboard/workflow" || pathname === "/dashboard/workflow/";

    if (isWorkflowPage) {
        return (
            <AuthGuard>
                <WorkflowLayout>{children}</WorkflowLayout>
            </AuthGuard>
        );
    }

    return (
        <AuthGuard>
            <div className="flex flex-col min-h-screen bg-background text-foreground">
                <DashboardHeader />
                <main className="flex-1 overflow-auto">
                    {children}
                </main>
            </div>
        </AuthGuard>
    );
}
