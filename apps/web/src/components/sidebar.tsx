"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { useAuth0 } from "@auth0/auth0-react";
import { cn } from "@/lib/utils";
import {
    Home,
    Layers,
    Settings,
    LogOut,
    User,
} from "lucide-react";

type SidebarProps = React.HTMLAttributes<HTMLDivElement>;

export function Sidebar({ className }: SidebarProps) {
    const pathname = usePathname();
    const { user, logout } = useAuth0();

    return (
        <div className={cn("w-56 border-r border-border/50 min-h-screen bg-card/80 flex flex-col", className)}>
            <div className="space-y-3 py-3 flex-1">
                <div className="px-3 py-1.5">
                    <div className="flex items-center gap-2 px-3 mb-6">
                        <Image src="/kureita_logo.png" alt="Kureita" width={24} height={24} className="h-6 w-auto" unoptimized />
                    </div>

                    <div className="space-y-0.5">
                        <h3 className="mb-2 px-3 text-[10px] font-semibold tracking-widest text-muted-foreground/70 uppercase">
                            Platform
                        </h3>
                        <Link href="/dashboard">
                            <span className={cn(
                                "group flex items-center rounded-md px-3 py-1.5 text-[13px] font-medium transition-colors hover:bg-accent/80 hover:text-accent-foreground",
                                pathname === "/dashboard" ? "bg-accent/80 text-accent-foreground" : "transparent text-muted-foreground"
                            )}>
                                <Home className="mr-2 h-3.5 w-3.5" />
                                Home
                            </span>
                        </Link>
                        <Link href="/dashboard/workflows">
                            <span className={cn(
                                "group flex items-center rounded-md px-3 py-1.5 text-[13px] font-medium transition-colors hover:bg-accent/80 hover:text-accent-foreground",
                                pathname.includes("/dashboard/workflows") ? "bg-accent/80 text-accent-foreground" : "transparent text-muted-foreground"
                            )}>
                                <Layers className="mr-2 h-3.5 w-3.5" />
                                Workflows
                            </span>
                        </Link>
                        <Link href="/dashboard/settings">
                            <span className={cn(
                                "group flex items-center rounded-md px-3 py-1.5 text-[13px] font-medium transition-colors hover:bg-accent/80 hover:text-accent-foreground",
                                pathname === "/dashboard/settings" ? "bg-accent/80 text-accent-foreground" : "transparent text-muted-foreground"
                            )}>
                                <Settings className="mr-2 h-3.5 w-3.5" />
                                Settings
                            </span>
                        </Link>
                    </div>
                </div>
            </div>

            {/* User section */}
            <div className="border-t border-border/50 px-3 py-3">
                <div className="flex items-center gap-2.5 px-3 mb-2">
                    {user?.picture ? (
                        <Image
                            src={user.picture}
                            alt={user.name || "User"}
                            width={28}
                            height={28}
                            className="w-7 h-7 rounded-full ring-1 ring-border/50"
                            unoptimized
                        />
                    ) : (
                        <div className="w-7 h-7 rounded-full bg-muted/60 flex items-center justify-center">
                            <User className="w-3.5 h-3.5 text-muted-foreground" />
                        </div>
                    )}
                    <div className="flex-1 min-w-0">
                        <p className="text-[13px] font-medium truncate">{user?.name || "User"}</p>
                        <p className="text-[11px] text-muted-foreground/70 truncate">{user?.email || ""}</p>
                    </div>
                </div>
                <button
                    onClick={() => logout({ logoutParams: { returnTo: window.location.origin } })}
                    className="flex items-center gap-2 w-full rounded-md px-3 py-1.5 text-[13px] font-medium text-muted-foreground/70 hover:bg-accent/80 hover:text-accent-foreground transition-colors"
                >
                    <LogOut className="h-3.5 w-3.5" />
                    Sign Out
                </button>
            </div>
        </div>
    );
}
