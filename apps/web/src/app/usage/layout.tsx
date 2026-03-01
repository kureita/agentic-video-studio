"use client";

import { DashboardHeader } from "@/components/dashboard-header";
import { AuthGuard } from "@/components/auth/auth-guard";

export default function UsageLayout({
    children,
}: {
    children: React.ReactNode;
}) {
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
