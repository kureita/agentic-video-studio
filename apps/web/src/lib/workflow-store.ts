import { create } from "zustand";
import { Node, Edge } from "@xyflow/react";
import { workflowApi, Workflow } from "./workflow-api";

// ============================================
// Types
// ============================================

interface WorkflowState {
    // Workflow data
    id: string | null;
    name: string;
    nodes: Node[];
    edges: Edge[];
    outputs: Record<string, string>; // nodeId -> output URL

    // Loading states
    isLoading: boolean;
    isSaving: boolean;
    isRunning: boolean;
    runningNodeId: string | null;

    // Error state
    error: string | null;

    // Dirty tracking
    isDirty: boolean;

    // Actions
    setWorkflow: (workflow: Workflow) => void;
    setName: (name: string) => void;
    setNodes: (nodes: Node[]) => void;
    setEdges: (edges: Edge[]) => void;
    setNodeOutput: (nodeId: string, output: string) => void;
    markDirty: () => void;
    markClean: () => void;

    // API actions
    createWorkflow: (name?: string) => Promise<string | null>;
    loadWorkflow: (id: string) => Promise<void>;
    saveWorkflow: () => Promise<void>;
    runWorkflow: () => Promise<void>;
    runNode: (nodeId: string) => Promise<void>;

    // Reset
    reset: () => void;
}

const initialState = {
    id: null,
    name: "Untitled Workflow",
    nodes: [],
    edges: [],
    outputs: {},
    isLoading: false,
    isSaving: false,
    isRunning: false,
    runningNodeId: null,
    error: null,
    isDirty: false,
};

// ============================================
// Store
// ============================================

export const useWorkflowStore = create<WorkflowState>((set, get) => ({
    ...initialState,

    // Basic setters
    setWorkflow: (workflow: Workflow) => {
        set({
            id: workflow.id,
            name: workflow.name,
            nodes: workflow.nodes as Node[],
            edges: workflow.edges as Edge[],
            outputs: workflow.outputs || {},
            isDirty: false,
        });
    },

    setName: (name: string) => {
        set({ name, isDirty: true });
    },

    setNodes: (nodes: Node[]) => {
        set({ nodes, isDirty: true });
    },

    setEdges: (edges: Edge[]) => {
        set({ edges, isDirty: true });
    },

    setNodeOutput: (nodeId: string, output: string) => {
        set((state) => ({
            outputs: { ...state.outputs, [nodeId]: output },
        }));
    },

    markDirty: () => set({ isDirty: true }),
    markClean: () => set({ isDirty: false }),

    // Create a new workflow
    createWorkflow: async (name?: string) => {
        set({ isLoading: true, error: null });
        try {
            const response = await workflowApi.create(name);
            const workflow = response.data;
            set({
                id: workflow.id,
                name: workflow.name,
                nodes: [],
                edges: [],
                outputs: {},
                isLoading: false,
                isDirty: false,
            });
            return workflow.id;
        } catch (error) {
            console.error("[WorkflowStore] Create error:", error);
            set({ isLoading: false, error: "Failed to create workflow" });
            return null;
        }
    },

    // Load an existing workflow
    loadWorkflow: async (id: string) => {
        set({ isLoading: true, error: null });
        try {
            const response = await workflowApi.get(id);
            const workflow = response.data;
            set({
                id: workflow.id,
                name: workflow.name,
                nodes: workflow.nodes as Node[],
                edges: workflow.edges as Edge[],
                outputs: workflow.outputs || {},
                isLoading: false,
                isDirty: false,
            });
        } catch (error) {
            console.error("[WorkflowStore] Load error:", error);
            set({ isLoading: false, error: "Failed to load workflow" });
        }
    },

    // Save the current workflow
    saveWorkflow: async () => {
        const { id, name, nodes, edges } = get();
        if (!id) {
            console.error("[WorkflowStore] No workflow ID to save");
            return;
        }

        set({ isSaving: true, error: null });
        try {
            await workflowApi.update(id, {
                name,
                nodes: nodes.map((n) => ({
                    id: n.id,
                    type: n.type || "unknown",
                    position: n.position,
                    data: n.data as Record<string, unknown>,
                })),
                edges: edges.map((e) => ({
                    id: e.id,
                    source: e.source,
                    target: e.target,
                    sourceHandle: e.sourceHandle || undefined,
                    targetHandle: e.targetHandle || undefined,
                })),
            });
            set({ isSaving: false, isDirty: false });
            console.log("[WorkflowStore] Saved successfully");
        } catch (error) {
            console.error("[WorkflowStore] Save error:", error);
            set({ isSaving: false, error: "Failed to save workflow" });
        }
    },

    // Run the entire workflow
    runWorkflow: async () => {
        const { id } = get();
        if (!id) {
            console.error("[WorkflowStore] No workflow ID to run");
            return;
        }

        // Save first to ensure latest nodes/edges are persisted
        await get().saveWorkflow();

        set({ isRunning: true, error: null });
        try {
            const response = await workflowApi.runWorkflow(id);
            const result = response.data;

            // Update outputs from result
            set((state) => ({
                outputs: { ...state.outputs, ...result.outputs },
                isRunning: false,
            }));

            if (!result.success && result.errors.length > 0) {
                console.error("[WorkflowStore] Run errors:", result.errors);
                set({ error: `Errors in ${result.errors.length} node(s)` });
            }
        } catch (error) {
            console.error("[WorkflowStore] Run error:", error);
            set({ isRunning: false, error: "Failed to run workflow" });
        }
    },

    // Run a single node
    runNode: async (nodeId: string) => {
        const { id } = get();
        if (!id) {
            console.error("[WorkflowStore] No workflow ID to run node");
            return;
        }

        // Save first to ensure latest nodes/edges are persisted
        await get().saveWorkflow();

        set({ runningNodeId: nodeId, error: null });
        try {
            const response = await workflowApi.runNode(id, nodeId);
            const result = response.data;

            if (result.success && result.output) {
                set((state) => ({
                    outputs: { ...state.outputs, [nodeId]: result.output as string },
                    runningNodeId: null,
                }));
            } else {
                set({ runningNodeId: null, error: result.error || "Node execution failed" });
            }
        } catch (error) {
            console.error("[WorkflowStore] Run node error:", error);
            set({ runningNodeId: null, error: "Failed to run node" });
        }
    },

    // Reset to initial state
    reset: () => set(initialState),
}));
