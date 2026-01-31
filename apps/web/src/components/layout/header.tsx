"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui";
import { Plus, Sparkles } from "lucide-react";

export function Header() {
  const pathname = usePathname();

  const navItems = [
    { label: "Dashboard", href: "/dashboard" },
    { label: "Projects", href: "/projects" },
    { label: "Canvas", href: "/canvas" },
  ];

  return (
    <header className="sticky top-0 z-50 glass border-b border-border/50">
      <div className="container-wide flex items-center justify-between h-16">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-foreground flex items-center justify-center">
            <Sparkles className="w-4 h-4 text-background" />
          </div>
          <span className="font-display text-xl font-semibold tracking-tight">
            Kureita
          </span>
        </Link>

        {/* Navigation */}
        <nav className="hidden md:flex items-center gap-1">
          {navItems.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "px-4 py-2 text-sm font-medium rounded-lg transition-colors",
                pathname === item.href
                  ? "text-foreground bg-background-secondary"
                  : "text-foreground-muted hover:text-foreground hover:bg-background-secondary/50"
              )}
            >
              {item.label}
            </Link>
          ))}
        </nav>

        {/* Actions */}
        <div className="flex items-center gap-3">
          <Link href="/projects/new">
            <Button size="sm" icon={<Plus className="w-4 h-4" />}>
              New Project
            </Button>
          </Link>
        </div>
      </div>
    </header>
  );
}

