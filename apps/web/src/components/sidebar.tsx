"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
    Home,
    Layers,
    Settings,
    Sparkles,
    Plus,
    Image as ImageIcon,
    Video,
    Bot
} from "lucide-react";

interface SidebarProps extends React.HTMLAttributes<HTMLDivElement> { }

export function Sidebar({ className }: SidebarProps) {
    const pathname = usePathname();

    return (
        <div className={cn("pb-12 w-64 border-r min-h-screen bg-card", className)}>
            <div className="space-y-4 py-4">
                <div className="px-3 py-2">
                    <div className="flex items-center gap-2 px-4 mb-8">
                        <img src="/kureita_logo.png" alt="Kureita" className="h-8" />
                    </div>

                    <div className="space-y-1">
                        <h3 className="mb-2 px-4 text-xs font-semibold tracking-tight text-muted-foreground uppercase">
                            Platform
                        </h3>
                        <Link href="/dashboard">
                            <span className={cn(
                                "group flex items-center rounded-md px-4 py-2 text-sm font-medium hover:bg-accent hover:text-accent-foreground",
                                pathname === "/dashboard" ? "bg-accent text-accent-foreground" : "transparent"
                            )}>
                                <Home className="mr-2 h-4 w-4" />
                                Home
                            </span>
                        </Link>
                        <Link href="/dashboard/workflows">
                            <span className={cn(
                                "group flex items-center rounded-md px-4 py-2 text-sm font-medium hover:bg-accent hover:text-accent-foreground",
                                pathname.includes("/dashboard/workflows") ? "bg-accent text-accent-foreground" : "transparent"
                            )}>
                                <Layers className="mr-2 h-4 w-4" />
                                Workflows
                            </span>
                        </Link>
                        <Link href="/dashboard/settings">
                            <span className={cn(
                                "group flex items-center rounded-md px-4 py-2 text-sm font-medium hover:bg-accent hover:text-accent-foreground",
                                pathname === "/dashboard/settings" ? "bg-accent text-accent-foreground" : "transparent"
                            )}>
                                <Settings className="mr-2 h-4 w-4" />
                                Settings
                            </span>
                        </Link>
                    </div>
                </div>

                <div className="px-3 py-2">
                    <h3 className="mb-2 px-4 text-xs font-semibold tracking-tight text-muted-foreground uppercase">
                        Tools
                    </h3>
                    <div className="space-y-1">
                        <div className="group flex items-center rounded-md px-4 py-2 text-sm font-medium text-muted-foreground cursor-not-allowed opacity-70">
                            <ImageIcon className="mr-2 h-4 w-4" />
                            Image Gen
                        </div>
                        <div className="group flex items-center rounded-md px-4 py-2 text-sm font-medium text-muted-foreground cursor-not-allowed opacity-70">
                            <Video className="mr-2 h-4 w-4" />
                            Video Gen
                        </div>
                        <div className="group flex items-center rounded-md px-4 py-2 text-sm font-medium text-muted-foreground cursor-not-allowed opacity-70">
                            <Bot className="mr-2 h-4 w-4" />
                            Assistant
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
