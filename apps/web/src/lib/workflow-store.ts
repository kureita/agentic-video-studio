import { create } from "zustand";
import { Node, Edge } from "@xyflow/react";
import { workflowApi, Workflow, ChatMessage, WorkflowNode, NodeState, WorkflowRunStatus } from "./workflow-api";
import { toast } from "sonner";

// ============================================
// Types
// ============================================

interface WorkflowState {
    // Workflow data
    id: string | null;
    name: string;
    nodes: Node[];
    edges: Edge[];

    // Async execution state (polling-based Run All)
    nodeExecutionStates: Record<string, NodeState>;
    executionProgress: { current: number; total: number } | null;
    outputs: Record<string, string>; // nodeId -> output URL
    chatHistory: ChatMessage[];

    // Loading states
    isLoading: boolean;
    isSaving: boolean;
    isRunning: boolean;
    runningNodeId: string | null;

    // Error state
    error: string | null;

    // Dirty tracking
    isDirty: boolean;
    isRunningAsync: boolean;

    // Actions
    setWorkflow: (workflow: Workflow) => void;
    setName: (name: string) => void;
    setNodes: (nodes: Node[]) => void;
    setEdges: (edges: Edge[]) => void;
    setNodeOutput: (nodeId: string, output: string) => void;
    clearNodeOutput: (nodeId: string) => void;
    addChatMessage: (message: ChatMessage) => void;
    setChatHistory: (messages: ChatMessage[]) => void;
    saveChatHistory: () => Promise<void>;
    markDirty: () => void;
    markClean: () => void;

    // API actions
    createWorkflow: (name?: string) => Promise<string | null>;
    loadWorkflow: (id: string) => Promise<void>;
    saveWorkflow: () => Promise<void>;
    runWorkflow: () => Promise<void>;
    runWorkflowAsync: () => Promise<void>;
    runNode: (nodeId: string) => Promise<void>;
    clearExecutionStates: () => void;

    // Reset
    reset: () => void;
}

const initialState = {
    id: null,
    name: "Untitled Workflow",
    nodes: [],
    edges: [],
    outputs: {},
    chatHistory: [],
    isLoading: false,
    isSaving: false,
    isRunning: false,
    isRunningAsync: false,
    runningNodeId: null,
    nodeExecutionStates: {} as Record<string, NodeState>,
    executionProgress: null as { current: number; total: number } | null,
    error: null,
    isDirty: false,
};

// ============================================
// Store
// ============================================

interface RawEdge {
    id?: string;
    source?: string;
    target?: string;
    sourceHandle?: string;
    source_handle?: string;
    targetHandle?: string;
    target_handle?: string;
    [key: string]: unknown;
}

// Helper to infer missing handles for older workflows
function inferMissingHandles(edge: RawEdge, nodes: Node[]) {
    let sourceHandle = edge.sourceHandle || edge.source_handle;
    let targetHandle = edge.targetHandle || edge.target_handle;

    if (sourceHandle && targetHandle) return { sourceHandle, targetHandle };

    const sourceNode = nodes.find((n: Node) => n.id === edge.source);
    const targetNode = nodes.find((n: Node) => n.id === edge.target);

    if (!sourceNode || !targetNode) return { sourceHandle, targetHandle };

    if (!sourceHandle) {
        switch (sourceNode.type) {
            case 'text': sourceHandle = 'text|text'; break;
            case 'imageGen': sourceHandle = 'image|image'; break;
            case 'videoGen': sourceHandle = 'video|video'; break;
            case 'audioGen': sourceHandle = 'audio|audio'; break;
            case 'mediaUpload': sourceHandle = 'image|output'; break;
            default: sourceHandle = 'any|output';
        }
    }

    if (!targetHandle) {
        switch (targetNode.type) {
            case 'imageGen':
                targetHandle = sourceNode.type === 'text' ? 'text|prompt' : 'image|image';
                break;
            case 'videoGen':
                targetHandle = sourceNode.type === 'text' ? 'text|text' : 'image|start_image';
                break;
            case 'editorAgent':
                if (sourceNode.type === 'videoGen') targetHandle = 'video|ref_videos';
                else if (sourceNode.type === 'imageGen') targetHandle = 'image|ref_images';
                else if (sourceNode.type === 'audioGen') targetHandle = 'audio|audio';
                else targetHandle = 'text|text';
                break;
            default:
                targetHandle = 'any|input';
        }
    }

    return { sourceHandle, targetHandle };
}

export const useWorkflowStore = create<WorkflowState>((set, get) => ({
    ...initialState,

    // Basic setters
    setWorkflow: (workflow: Workflow) => {
        // Ensure nodes and edges are properly formatted arrays
        const nodes = Array.isArray(workflow.nodes) ? workflow.nodes : [];
        const edges = Array.isArray(workflow.edges) ? workflow.edges : [];
        const chatHistory = Array.isArray(workflow.chat_history) ? workflow.chat_history : [];

        // Validate and sanitize nodes
        const validNodes = nodes.map((node: WorkflowNode) => ({
            id: node.id || String(Math.random()),
            type: node.type || 'default',
            position: node.position || { x: 0, y: 0 },
            data: node.data || {},
        })) as Node[];

        // Validate and sanitize edges
        const validEdges = edges.map((edge: RawEdge | unknown) => {
            const safeEdge = edge as RawEdge;
            const { sourceHandle, targetHandle } = inferMissingHandles(safeEdge, validNodes);
            return {
                id: safeEdge.id || `${safeEdge.source}-${safeEdge.target}`,
                source: safeEdge.source,
                target: safeEdge.target,
                sourceHandle,
                targetHandle,
            };
        }) as Edge[];

        set({
            id: workflow.id,
            name: workflow.name,
            nodes: validNodes,
            edges: validEdges,
            outputs: workflow.outputs || {},
            chatHistory: chatHistory,
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
        set((state) => {
            const newOutputs = { ...state.outputs, [nodeId]: output };

            // Also update the node's data.output for persistence
            const newNodes = state.nodes.map((node) => {
                if (node.id === nodeId) {
                    return {
                        ...node,
                        data: { ...node.data, output },
                    };
                }
                return node;
            });

            return {
                outputs: newOutputs,
                nodes: newNodes,
                isDirty: true
            };
        });
    },

    clearNodeOutput: (nodeId: string) => {
        set((state) => {
            const newOutputs = { ...state.outputs };
            delete newOutputs[nodeId];

            // Also clear the node's data.output
            const newNodes = state.nodes.map((node) => {
                if (node.id === nodeId) {
                    const newData = { ...node.data };
                    delete newData.output;
                    return {
                        ...node,
                        data: newData,
                    };
                }
                return node;
            });

            return {
                outputs: newOutputs,
                nodes: newNodes,
                isDirty: true
            };
        });
    },

    addChatMessage: (message: ChatMessage) => {
        set((state) => ({
            chatHistory: [...state.chatHistory, message],
        }));
        // Auto-save chat history immediately
        get().saveChatHistory();
    },

    setChatHistory: (messages: ChatMessage[]) => {
        set({ chatHistory: messages });
    },

    saveChatHistory: async () => {
        const { id, chatHistory } = get();
        if (!id) {
            console.log("[WorkflowStore] No workflow ID to save chat history");
            return;
        }

        try {
            await workflowApi.update(id, {
                chat_history: chatHistory,
            });
            console.log("[WorkflowStore] Chat history saved successfully");
        } catch (error) {
            console.error("[WorkflowStore] Chat history save error:", error);
        }
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
                chatHistory: [],
                isLoading: false,
                isDirty: false,
            });
            return workflow.id;
        } catch (error) {
            console.error("[WorkflowStore] Create error:", error);
            set({ isLoading: false, error: "Failed to create workflow" });
            toast.error("Failed to create workflow");
            return null;
        }
    },

    // Load an existing workflow
    loadWorkflow: async (id: string) => {
        set({ isLoading: true, error: null });
        try {
            const response = await workflowApi.get(id);
            const workflow = response.data;

            // Ensure nodes and edges are properly formatted arrays
            const nodes = Array.isArray(workflow.nodes) ? workflow.nodes : [];
            const edges = Array.isArray(workflow.edges) ? workflow.edges : [];
            const chatHistory = Array.isArray(workflow.chat_history) ? workflow.chat_history : [];

            // Validate and sanitize nodes
            const validNodes = nodes.map((node: WorkflowNode) => ({
                id: node.id || String(Math.random()),
                type: node.type || 'default',
                position: node.position || { x: 0, y: 0 },
                data: node.data || {},
            })) as Node[];

            // Validate and sanitize edges
            const validEdges = edges.map((edge: RawEdge | unknown) => {
                const safeEdge = edge as RawEdge;
                const { sourceHandle, targetHandle } = inferMissingHandles(safeEdge, validNodes);
                return {
                    id: safeEdge.id || `${safeEdge.source}-${safeEdge.target}`,
                    source: safeEdge.source,
                    target: safeEdge.target,
                    sourceHandle,
                    targetHandle,
                };
            }) as Edge[];

            console.log(`[WorkflowStore] Loaded workflow ${id}: ${validNodes.length} nodes, ${validEdges.length} edges`);

            set({
                id: workflow.id,
                name: workflow.name,
                nodes: validNodes,
                edges: validEdges,
                outputs: workflow.outputs || {},
                chatHistory: chatHistory,
                isLoading: false,
                isDirty: false,
            });
        } catch (error) {
            console.error("[WorkflowStore] Load error:", error);
            set({ isLoading: false, error: "Failed to load workflow" });
            toast.error("Failed to load workflow");
            throw error; // Re-throw to allow caller to handle
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
            toast.error("Failed to save workflow");
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
                toast.error(`Workflow completed with errors in ${result.errors.length} node(s)`);
            } else {
                toast.success("Workflow run completed");
            }
        } catch (error) {
            console.error("[WorkflowStore] Run error:", error);
            set({ isRunning: false, error: "Failed to run workflow" });
            toast.error("Failed to run workflow");
        }
    },

    // Run the entire workflow (async + polling for real-time progress)
    runWorkflowAsync: async () => {
        const { id } = get();
        if (!id) {
            console.error("[WorkflowStore] No workflow ID to run");
            return;
        }

        // Save first to ensure latest nodes/edges are persisted
        await get().saveWorkflow();

        set({
            isRunning: true,
            isRunningAsync: true,
            error: null,
            nodeExecutionStates: {},
            executionProgress: null,
        });

        try {
            // Start the async run
            await workflowApi.runWorkflowAsync(id);

            // Poll for status updates
            const finalStatus = await workflowApi.pollWorkflowRun(id, (status: WorkflowRunStatus) => {
                // Update node execution states for real-time visual feedback
                set({
                    nodeExecutionStates: status.node_states,
                    executionProgress: status.progress,
                });

                // Update outputs as they become available
                if (Object.keys(status.outputs).length > 0) {
                    set((state) => ({
                        outputs: { ...state.outputs, ...status.outputs },
                    }));
                }
            });

            // Final update
            set({
                isRunning: false,
                isRunningAsync: false,
                outputs: { ...get().outputs, ...finalStatus.outputs },
                nodeExecutionStates: finalStatus.node_states,
                executionProgress: finalStatus.progress,
            });

            if (finalStatus.status === "failed" && finalStatus.errors.length > 0) {
                console.error("[WorkflowStore] Run errors:", finalStatus.errors);
                set({ error: `Errors in ${finalStatus.errors.length} node(s)` });
                toast.error(`Workflow completed with errors in ${finalStatus.errors.length} node(s)`);
            } else {
                toast.success("Workflow run completed");
            }
        } catch (error) {
            console.error("[WorkflowStore] Async run error:", error);
            set({
                isRunning: false,
                isRunningAsync: false,
                error: "Failed to run workflow",
                nodeExecutionStates: {},
                executionProgress: null,
            });
            toast.error("Failed to run workflow");
        }
    },

    // Clear execution state indicators from all nodes
    clearExecutionStates: () => {
        set({ nodeExecutionStates: {}, executionProgress: null });
    },

    // Run a single node with recursive dependency execution
    runNode: async (nodeId: string) => {
        const store = get();
        const { id, edges } = store;

        if (!id) {
            console.error("[WorkflowStore] No workflow ID to run node");
            return;
        }

        // Save first to ensure latest nodes/edges are persisted
        await store.saveWorkflow();

        // Helper to run a specific node via API
        const executeNodeApi = async (targetId: string): Promise<boolean> => {
            set({ runningNodeId: targetId, error: null });

            // Resolve prompt references if present
            const currentStore = get();
            let inputOverrides: Record<string, unknown> | undefined;
            const targetNode = currentStore.nodes.find(n => n.id === targetId);

            if (targetNode && targetNode.data) {
                // Check for prompt (Image/Video) or instruction (Vision/Editor)
                const textKey = typeof targetNode.data.prompt === 'string' ? 'prompt' :
                    (typeof targetNode.data.instruction === 'string' ? 'instruction' : null);

                if (textKey) {
                    let resolvedText = targetNode.data[textKey] as string;

                    // Find all text nodes to generate the same labels as the UI
                    const textNodes = currentStore.nodes
                        .filter(n => n.type === 'text')
                        .map((n, i) => ({
                            label: `Text #${i + 1}`,
                            content: (n.data.text as string) || ""
                        }))
                        // Sort by length desc to prevent partial replacements
                        .sort((a, b) => b.label.length - a.label.length);

                    let hasReplacements = false;
                    textNodes.forEach(textNode => {
                        const mention = `@${textNode.label}`;
                        if (resolvedText.includes(mention)) {
                            // Global replacement
                            resolvedText = resolvedText.split(mention).join(textNode.content);
                            hasReplacements = true;
                        }
                    });

                    if (hasReplacements) {
                        inputOverrides = { [textKey]: resolvedText };
                    }
                }
            }

            try {
                const response = await workflowApi.runNode(id, targetId, inputOverrides);
                const result = response.data;

                if (result.success && result.output) {
                    const storeOutput = result.output as string;

                    set((state) => {
                        const newOutputs = { ...state.outputs, [targetId]: storeOutput };

                        // Also update node data for persistence
                        const newNodes = state.nodes.map((node) => {
                            if (node.id === targetId) {
                                return {
                                    ...node,
                                    data: { ...node.data, output: storeOutput },
                                };
                            }
                            return node;
                        });

                        return {
                            outputs: newOutputs,
                            nodes: newNodes,
                            runningNodeId: null,
                            isDirty: true // Mark dirty so it gets saved on next manual save or run
                        };
                    });

                    return true;
                } else {
                    set({ runningNodeId: null, error: result.error || "Node execution failed" });
                    return false;
                }
            } catch (error) {
                console.error("[WorkflowStore] Run node error:", error);
                set({ runningNodeId: null, error: "Failed to run node" });
                toast.error("Failed to run node");
                return false;
            }
        };

        // Recursive function to check and run dependencies
        const ensureDependencies = async (targetId: string, visited = new Set<string>()): Promise<boolean> => {
            if (visited.has(targetId)) return true; // Cycle detected or already processed
            visited.add(targetId);

            // Find upstream nodes (dependencies)
            const dependencies = edges
                .filter(e => e.target === targetId)
                .map(e => e.source);

            // Check each dependency
            for (const sourceId of dependencies) {
                // Check if output exists
                const currentOutputs = get().outputs;

                if (!currentOutputs[sourceId]) {
                    console.log(`[Workflow] Dependency ${sourceId} missing output. Recursively running...`);

                    // First ensure ITS dependencies are ready
                    const depsOk = await ensureDependencies(sourceId, visited);
                    if (!depsOk) return false;

                    // Then run the dependency itself
                    const runOk = await executeNodeApi(sourceId);
                    if (!runOk) return false;
                }
            }

            return true;
        };

        // Start execution
        // 1. Ensure all upstream dependencies have outputs
        const dependenciesReady = await ensureDependencies(nodeId);

        // 2. If dependencies ready, run the target node (always run target node when explicitly requested)
        if (dependenciesReady) {
            await executeNodeApi(nodeId);
        }
    },

    // Reset to initial state
    reset: () => set(initialState),
}));
