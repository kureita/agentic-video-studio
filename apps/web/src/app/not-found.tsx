"use client";

import Link from "next/link";

export default function NotFound() {
    return (
        <div className="flex items-center justify-center min-h-screen bg-background px-4">
            <div className="flex flex-col items-center gap-6 max-w-md text-center">
                {/* Animated 404 */}
                <div className="relative">
                    <h1 className="text-[120px] font-extrabold leading-none tracking-tighter text-foreground/5 select-none">
                        404
                    </h1>
                    <div className="absolute inset-0 flex items-center justify-center">
                        <span className="text-5xl font-bold tracking-tight text-foreground">
                            404
                        </span>
                    </div>
                </div>

                {/* Message */}
                <div className="space-y-2">
                    <h2 className="text-xl font-semibold text-foreground">
                        Page not found
                    </h2>
                    <p className="text-sm text-muted-foreground leading-relaxed">
                        The page you&apos;re looking for doesn&apos;t exist or has been
                        moved. Let&apos;s get you back on track.
                    </p>
                </div>

                {/* Actions */}
                <div className="flex gap-3 mt-2">
                    <Link
                        href="/dashboard/"
                        className="px-5 py-2.5 text-sm font-medium rounded-md bg-primary text-primary-foreground hover:bg-primary/90 transition-colors shadow-sm"
                    >
                        Go to Dashboard
                    </Link>
                    <button
                        onClick={() => window.history.back()}
                        className="px-5 py-2.5 text-sm font-medium rounded-md border border-border text-foreground hover:bg-accent transition-colors"
                    >
                        Go Back
                    </button>
                </div>
            </div>
        </div>
    );
}
