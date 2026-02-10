import { api } from "./api";

// ============================================
// Types
// ============================================

export interface WorkflowNode {
    id: string;
    type: string;
    position: { x: number; y: number };
    data: Record<string, unknown>;
}

export interface WorkflowEdge {
    id: string;
    source: string;
    target: string;
    sourceHandle?: string;
    targetHandle?: string;
}

export interface ToolCall {
    name: string;
    status: "running" | "completed" | "failed";
    args?: Record<string, unknown>;
    result?: string;
}

export interface ChatMessage {
    role: "user" | "assistant";
    content: string;
    timestamp?: string;
    // Rich assistant message metadata
    thinking?: string;
    thinking_duration_ms?: number;
    tool_calls?: ToolCall[];
}

export interface Workflow {
    id: string;
    name: string;
    nodes: WorkflowNode[];
    edges: WorkflowEdge[];
    outputs: Record<string, string>;
    chat_history: ChatMessage[];
    created_at: string;
    updated_at: string;
}

export interface WorkflowListItemNode {
    id: string;
    type: string;
    position: { x: number; y: number };
}

export interface WorkflowListItemEdge {
    id: string;
    source: string;
    target: string;
}

export interface WorkflowListItem {
    id: string;
    name: string;
    updated_at: string;
    node_count: number;
    nodes: WorkflowListItemNode[];
    edges: WorkflowListItemEdge[];
}

export interface UpdateWorkflowData {
    name?: string;
    nodes?: WorkflowNode[];
    edges?: WorkflowEdge[];
    chat_history?: ChatMessage[];
}

export interface RunNodeResponse {
    success: boolean;
    node_id: string;
    output?: string;
    error?: string;
}

export interface RunWorkflowResponse {
    success: boolean;
    outputs: Record<string, string>;
    errors: Array<{ node_id: string; error: string }>;
}

// ============================================
// API Client
// ============================================

export const workflowApi = {
    /**
     * Create a new workflow
     */
    create: (name?: string) =>
        api.post<Workflow>("/api/workflows", { name }),

    /**
     * List all workflows
     */
    list: () =>
        api.get<WorkflowListItem[]>("/api/workflows"),

    /**
     * Get a workflow by ID
     */
    get: (id: string) =>
        api.get<Workflow>(`/api/workflows/${id}`),

    /**
     * Update a workflow (name, nodes, edges)
     */
    update: (id: string, data: UpdateWorkflowData) =>
        api.put<Workflow>(`/api/workflows/${id}`, data),

    /**
     * Delete a workflow
     */
    delete: (id: string) =>
        api.delete(`/api/workflows/${id}`),

    /**
     * Run a single node in a workflow
     */
    runNode: (workflowId: string, nodeId: string, inputOverrides?: Record<string, unknown>) =>
        api.post<RunNodeResponse>(`/api/workflows/${workflowId}/nodes/${nodeId}/run`, {
            input_overrides: inputOverrides,
        }),

    /**
     * Run the entire workflow
     */
    runWorkflow: (id: string) =>
        api.post<RunWorkflowResponse>(`/api/workflows/${id}/run`),
};
