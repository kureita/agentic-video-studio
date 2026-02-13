"use client";

import { Auth0Provider } from "@auth0/auth0-react";
import { useEffect } from "react";
import { useAuth0 } from "@auth0/auth0-react";
import { setAuthTokenGetter } from "@/lib/api";

function AuthTokenSync() {
    const { getAccessTokenSilently, isAuthenticated } = useAuth0();

    useEffect(() => {
        if (isAuthenticated) {
            setAuthTokenGetter(() => getAccessTokenSilently());
        }
    }, [isAuthenticated, getAccessTokenSilently]);

    return null;
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
    const domain = process.env.NEXT_PUBLIC_AUTH0_DOMAIN || "";
    const clientId = process.env.NEXT_PUBLIC_AUTH0_CLIENT_ID || "";
    const audience = process.env.NEXT_PUBLIC_AUTH0_AUDIENCE || "";

    if (!domain || !clientId) {
        // If Auth0 is not configured, render children without auth
        console.warn("Auth0 not configured — running without authentication");
        return <>{children}</>;
    }

    const redirectUri =
        typeof window !== "undefined" ? `${window.location.origin}/dashboard/` : "";

    return (
        <Auth0Provider
            domain={domain}
            clientId={clientId}
            authorizationParams={{
                redirect_uri: redirectUri,
                audience,
            }}
            cacheLocation="localstorage"
            useRefreshTokens={true}
        >
            <AuthTokenSync />
            {children}
        </Auth0Provider>
    );
}
