export type WorkflowConnectionType = "audio" | "image" | "video" | "text" | "any";

const FALLBACK_CONNECTION_TYPE: WorkflowConnectionType = "any";

export const WORKFLOW_CONNECTION_COLORS: Record<WorkflowConnectionType, string> = {
    audio: "#ec4899",
    image: "#38bdf8",
    video: "#a855f7",
    text: "#22c55e",
    any: "#6b7280",
};

export const WORKFLOW_CONNECTION_SURFACE_COLORS: Record<WorkflowConnectionType, string> = {
    audio: "rgba(236, 72, 153, 0.14)",
    image: "rgba(56, 189, 248, 0.14)",
    video: "rgba(168, 85, 247, 0.14)",
    text: "rgba(34, 197, 94, 0.14)",
    any: "rgba(107, 114, 128, 0.14)",
};

export function normalizeWorkflowConnectionType(type?: string | null): WorkflowConnectionType {
    const normalized = String(type || "").toLowerCase();
    if (normalized === "audio" || normalized === "image" || normalized === "video" || normalized === "text") {
        return normalized;
    }
    return FALLBACK_CONNECTION_TYPE;
}

export function getWorkflowConnectionTypeFromHandle(handleId?: string | null): WorkflowConnectionType {
    const [rawType] = String(handleId || "").split("|");
    return normalizeWorkflowConnectionType(rawType);
}

export function getWorkflowConnectionColor(type?: string | null): string {
    return WORKFLOW_CONNECTION_COLORS[normalizeWorkflowConnectionType(type)];
}

export function getWorkflowConnectionSurfaceColor(type?: string | null): string {
    return WORKFLOW_CONNECTION_SURFACE_COLORS[normalizeWorkflowConnectionType(type)];
}

export function getWorkflowEdgeConnectionType(edge: {
    sourceHandle?: string | null;
    targetHandle?: string | null;
}): WorkflowConnectionType {
    const sourceType = getWorkflowConnectionTypeFromHandle(edge.sourceHandle);
    if (sourceType !== FALLBACK_CONNECTION_TYPE) return sourceType;
    return getWorkflowConnectionTypeFromHandle(edge.targetHandle);
}
