"use client";

import { useEffect, useRef } from "react";
import { useAuth0 } from "@auth0/auth0-react";
import { Loader2, AlertTriangle, Mail } from "lucide-react";
import Link from "next/link";

/**
 * AuthGuard — wraps protected pages.
 * If the user is not authenticated, triggers an Auth0 login redirect.
 * Handles Auth0 errors (e.g. misconfigured audience) to prevent infinite loops.
 * Enforces email verification for authenticated users.
 */
export function AuthGuard({ children }: { children: React.ReactNode }) {
    const { isAuthenticated, isLoading, error, loginWithRedirect, user, logout } =
        useAuth0();
    const hasRedirected = useRef(false);

    useEffect(() => {
        // Only redirect if: not loading, not authenticated, no error, and haven't already redirected
        if (!isLoading && !isAuthenticated && !error && !hasRedirected.current) {
            hasRedirected.current = true;
            loginWithRedirect();
        }
    }, [isLoading, isAuthenticated, error, loginWithRedirect]);

    if (isLoading) {
        return (
            <div className="flex items-center justify-center min-h-screen bg-background">
                <div className="flex flex-col items-center gap-4">
                    <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
                    <p className="text-sm text-muted-foreground">Loading...</p>
                </div>
            </div>
        );
    }

    // Show Auth0 errors instead of looping
    if (error) {
        return (
            <div className="flex items-center justify-center min-h-screen bg-background">
                <div className="flex flex-col items-center gap-4 max-w-md text-center px-6">
                    <AlertTriangle className="w-10 h-10 text-destructive" />
                    <h2 className="text-lg font-semibold">Authentication Error</h2>
                    <p className="text-sm text-muted-foreground">{error.message}</p>
                    <div className="flex gap-3 mt-2">
                        <button
                            onClick={() => {
                                hasRedirected.current = false;
                                loginWithRedirect();
                            }}
                            className="px-4 py-2 text-sm font-medium rounded-md bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
                        >
                            Try Again
                        </button>
                        <Link
                            href="/"
                            className="px-4 py-2 text-sm font-medium rounded-md border border-border hover:bg-accent transition-colors"
                        >
                            Go Home
                        </Link>
                    </div>
                </div>
            </div>
        );
    }

    if (!isAuthenticated) {
        return (
            <div className="flex items-center justify-center min-h-screen bg-background">
                <div className="flex flex-col items-center gap-4">
                    <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
                    <p className="text-sm text-muted-foreground">
                        Redirecting to login...
                    </p>
                </div>
            </div>
        );
    }

    // Enforce Email Verification
    // We check explicitly for false (it might be undefined for some social providers that don't return it, though usually they return true/false)
    if (user?.email_verified === false) {
        return (
            <div className="flex items-center justify-center min-h-screen bg-background px-4">
                <div className="flex flex-col items-center gap-6 max-w-md text-center px-8 py-12 rounded-xl border bg-card shadow-sm animate-in fade-in zoom-in duration-300">
                    <div className="p-4 rounded-full bg-primary/10 text-primary">
                        <Mail className="w-8 h-8" />
                    </div>
                    <div className="space-y-2">
                        <h2 className="text-xl font-semibold">Verify your email</h2>
                        <p className="text-sm text-muted-foreground">
                            We've sent a verification link to{" "}
                            <span className="font-medium text-foreground">
                                {user.email}
                            </span>
                            . Please check your inbox to continue.
                        </p>
                    </div>

                    <div className="flex flex-col gap-3 w-full mt-2">
                        <button
                            onClick={() => loginWithRedirect()}
                            className="w-full px-4 py-2.5 text-sm font-medium rounded-md bg-primary text-primary-foreground hover:bg-primary/90 transition-colors shadow-sm"
                        >
                            I've Verified My Email
                        </button>
                        <button
                            onClick={() =>
                                logout({
                                    logoutParams: { returnTo: window.location.origin },
                                })
                            }
                            className="text-sm text-muted-foreground hover:text-foreground transition-colors"
                        >
                            Log out
                        </button>
                    </div>
                </div>
            </div>
        );
    }

    return <>{children}</>;
}
