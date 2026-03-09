"use client";

import { Suspense } from "react";
import { useEffect, useRef } from "react";
import { useAuth0 } from "@auth0/auth0-react";
import { useSearchParams } from "next/navigation";
import { Loader2 } from "lucide-react";

function LoginContent() {
    const { isAuthenticated, isLoading, loginWithRedirect } = useAuth0();
    const searchParams = useSearchParams();
    const hasRedirected = useRef(false);

    useEffect(() => {
        if (isLoading) return;

        // Already logged in → go to dashboard
        if (isAuthenticated) {
            window.location.replace("/dashboard/");
            return;
        }

        // Not authenticated → trigger Auth0 login (only once)
        if (!hasRedirected.current) {
            hasRedirected.current = true;

            const loginHint = searchParams.get("login_hint");

            loginWithRedirect({
                authorizationParams: {
                    ...(loginHint ? { login_hint: loginHint } : {}),
                },
            });
        }
    }, [isLoading, isAuthenticated, loginWithRedirect, searchParams]);

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

/**
 * /login page — handles Auth0 Third-Party Initiated Login.
 *
 * When Auth0 redirects to /login?iss=<domain>, this page triggers
 * loginWithRedirect() to start the authorization flow.
 * If the user is already authenticated, redirects to /dashboard/.
 */
export default function LoginPage() {
    return (
        <Suspense
            fallback={
                <div className="flex items-center justify-center min-h-screen bg-background">
                    <div className="flex flex-col items-center gap-4">
                        <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
                        <p className="text-sm text-muted-foreground">Loading...</p>
                    </div>
                </div>
            }
        >
            <LoginContent />
        </Suspense>
    );
}
