"use client";

import { createContext, useContext } from "react";

export interface MobileTabContextType {
    activeTab: "chat" | "canvas";
    setActiveTab: (tab: "chat" | "canvas") => void;
}

export const MobileTabContext = createContext<MobileTabContextType>({
    activeTab: "chat",
    setActiveTab: () => { },
});

export function useMobileTab() {
    return useContext(MobileTabContext);
}
