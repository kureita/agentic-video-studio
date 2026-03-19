"use client";

import { createContext, useContext } from "react";

interface MobileTabContextType {
    activeTab: "chat" | "canvas";
    setActiveTab: (tab: "chat" | "canvas") => void;
}

export const PublicMobileTabContext = createContext<MobileTabContextType>({
    activeTab: "canvas",
    setActiveTab: () => {},
});

export function usePublicMobileTab() {
    return useContext(PublicMobileTabContext);
}
