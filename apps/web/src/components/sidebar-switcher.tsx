"use client";

import { usePathname } from "next/navigation";
import { Sidebar } from "@/components/sidebar";
import { AgentSidebar } from "@/components/workflow/agent-sidebar";

export function SidebarSwitcher() {
    const pathname = usePathname();
    // Check for exact match or trailing slash
    const isWorkflowPage = pathname === "/dashboard/workflow" || pathname === "/dashboard/workflow/";

    if (isWorkflowPage) {
        return <AgentSidebar />;
    }

    return <Sidebar />;
}
