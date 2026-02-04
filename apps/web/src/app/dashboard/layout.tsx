import { Sidebar } from "@/components/sidebar";
import { cn } from "@/lib/utils";

export default function DashboardLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return (
        <div className="flex min-h-screen bg-background text-foreground">
            <Sidebar className="hidden lg:block shrink-0" />
            <main className="flex-1 overflow-auto">
                <div className="container h-full py-6 px-4 md:px-8 max-w-7xl mx-auto">
                    {children}
                </div>
            </main>
        </div>
    );
}
