"use client";

import { usePathname } from "next/navigation";
import { DashboardHeader } from "@/components/dashboard-header";
import { AgentSidebar } from "@/components/workflow/agent-sidebar";
import { AuthGuard } from "@/components/auth/auth-guard";

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
                <div className="flex min-h-screen bg-background text-foreground">
                    <AgentSidebar />
                    <main className="flex-1 overflow-auto">
                        {children}
                    </main>
                </div>
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
