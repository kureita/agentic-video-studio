"use client";

import { useState, useRef, useEffect } from "react";
import { useAuth0 } from "@auth0/auth0-react";
import { LifeBuoy, LogOut, User, ChevronDown, Package } from "lucide-react";
import { cn } from "@/lib/utils";
import Image from "next/image";
import Link from "next/link";
import { YourStuffPanel } from "@/components/your-stuff-panel";

const SUPPORT_MAILTO = (() => {
    const body = [
        "Hi Kureita support,",
        "",
        "I need help with:",
        "",
        "[Please describe your issue here]",
        "",
        "Thanks,",
    ].join("\n");
    // encodeURIComponent uses %20 for spaces; URLSearchParams uses + which many mail apps show literally.
    const cc = encodeURIComponent("rishav@kureita.com,abhishek@kureita.com");
    const subject = encodeURIComponent("Kureita support request");
    const bodyQ = encodeURIComponent(body);
    return `mailto:help@kureita.com?cc=${cc}&subject=${subject}&body=${bodyQ}`;
})();

export function DashboardHeader() {
    const { user, logout } = useAuth0();
    const [isDropdownOpen, setIsDropdownOpen] = useState(false);
    const [isYourStuffOpen, setIsYourStuffOpen] = useState(false);
    const dropdownRef = useRef<HTMLDivElement>(null);

    // Close dropdown when clicking outside
    useEffect(() => {
        function handleClickOutside(event: MouseEvent) {
            if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
                setIsDropdownOpen(false);
            }
        }
        document.addEventListener("mousedown", handleClickOutside);
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, []);

    return (
        <>
            <header className="h-14 border-b border-border/50 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 flex items-center justify-between px-4 md:px-6 sticky top-0 z-50">
                {/* Logo */}
                <Link href="/dashboard" className="flex items-center gap-2.5 cursor-pointer hover:opacity-80 transition-opacity">
                    <Image src="/kureita_logo.png" alt="Kureita" width={24} height={24} className="h-6 w-auto" unoptimized />
                </Link>

                {/* User Dropdown */}
                <div className="relative" ref={dropdownRef}>
                    <button
                        onClick={() => setIsDropdownOpen(!isDropdownOpen)}
                        className={cn(
                            "flex items-center gap-2 rounded-full py-1 pl-1 pr-2.5 transition-colors",
                            "hover:bg-accent/80",
                            isDropdownOpen && "bg-accent/80"
                        )}
                    >
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
                        <ChevronDown className={cn(
                            "w-3 h-3 text-muted-foreground transition-transform duration-200",
                            isDropdownOpen && "rotate-180"
                        )} />
                    </button>

                    {/* Dropdown Menu */}
                    {isDropdownOpen && (
                        <div className="absolute right-0 top-full mt-1.5 w-56 bg-popover border border-border/60 rounded-lg shadow-lg shadow-black/20 py-1 z-50 animate-fade-in">
                            {/* User Info */}
                            <div className="px-3 py-2.5 border-b border-border/40">
                                <p className="text-[13px] font-medium text-foreground truncate">
                                    {user?.name || "User"}
                                </p>
                                <p className="text-[11px] text-muted-foreground/70 truncate mt-0.5">
                                    {user?.email || ""}
                                </p>
                            </div>

                            <div className="py-1 border-b border-border/40">
                                {/* Your Stuff */}
                                <button
                                    onClick={() => {
                                        setIsDropdownOpen(false);
                                        setIsYourStuffOpen(true);
                                    }}
                                    className="flex items-center gap-2 w-full px-3 py-1.5 text-[13px] font-medium text-muted-foreground hover:bg-accent/80 hover:text-accent-foreground transition-colors cursor-pointer"
                                >
                                    <Package className="h-3.5 w-3.5 shrink-0" />
                                    Your Stuff
                                </button>
                                {/* Billing & Usage */}
                                <a
                                    href="/usage"
                                    className="flex items-center gap-2 w-full px-3 py-1.5 text-[13px] font-medium text-muted-foreground hover:bg-accent/80 hover:text-accent-foreground transition-colors"
                                >
                                    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="lucide lucide-credit-card"><rect width="20" height="14" x="2" y="5" rx="2" /><line x1="2" x2="22" y1="10" y2="10" /></svg>
                                    Billing & Usage
                                </a>
                                <a
                                    href={SUPPORT_MAILTO}
                                    onClick={() => setIsDropdownOpen(false)}
                                    className="flex items-center gap-2 w-full px-3 py-1.5 text-[13px] font-medium text-muted-foreground hover:bg-accent/80 hover:text-accent-foreground transition-colors"
                                >
                                    <LifeBuoy className="h-3.5 w-3.5 shrink-0" />
                                    Support
                                </a>
                            </div>

                            {/* Sign Out */}
                            <div className="py-1">
                                <button
                                    onClick={() => logout({ logoutParams: { returnTo: window.location.origin } })}
                                    className="flex items-center gap-2 w-full px-3 py-1.5 text-[13px] font-medium text-muted-foreground hover:bg-accent/80 hover:text-destructive transition-colors"
                                >
                                    <LogOut className="h-3.5 w-3.5" />
                                    Sign Out
                                </button>
                            </div>
                        </div>
                    )}
                </div>
            </header>

            {/* Your Stuff Panel */}
            <YourStuffPanel
                isOpen={isYourStuffOpen}
                onClose={() => setIsYourStuffOpen(false)}
            />
        </>
    );
}
