"use client";

import { usePathname } from "next/navigation";
import { Sidebar } from "@/components/sidebar";
import { AgentSidebar } from "@/components/workflow/agent-sidebar";

export function SidebarSwitcher() {
    const pathname = usePathname();
    const isWorkflowPage = pathname.includes("/dashboard/workflow/") && !pathname.endsWith("/dashboard/workflow");

    if (isWorkflowPage) {
        return <AgentSidebar />;
    }

    return <Sidebar />;
}
