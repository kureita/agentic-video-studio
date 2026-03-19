"use client";

import { createContext, useContext, useState, useCallback, ReactNode } from "react";
import { LoginPromptDialog } from "@/components/ui/login-prompt-dialog";

interface PublicViewContextType {
    isPublicView: boolean;
    /** Call this to gate any action that requires auth. Shows login dialog and returns false. */
    requireLogin: (reason?: string) => boolean;
}

const PublicViewContext = createContext<PublicViewContextType>({
    isPublicView: false,
    requireLogin: () => true,
});

export function usePublicView() {
    return useContext(PublicViewContext);
}

export function PublicViewProvider({ children }: { children: ReactNode }) {
    const [showLoginDialog, setShowLoginDialog] = useState(false);
    const [loginReason, setLoginReason] = useState<string | undefined>();

    const requireLogin = useCallback((reason?: string) => {
        setLoginReason(reason);
        setShowLoginDialog(true);
        return false;
    }, []);

    return (
        <PublicViewContext.Provider value={{ isPublicView: true, requireLogin }}>
            {children}
            <LoginPromptDialog
                open={showLoginDialog}
                onOpenChange={setShowLoginDialog}
                reason={loginReason}
            />
        </PublicViewContext.Provider>
    );
}

export function AuthenticatedViewProvider({ children }: { children: ReactNode }) {
    return (
        <PublicViewContext.Provider value={{ isPublicView: false, requireLogin: () => true }}>
            {children}
        </PublicViewContext.Provider>
    );
}
