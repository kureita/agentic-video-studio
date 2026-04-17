import { create } from "zustand";
import { Node, Edge } from "@xyflow/react";
import { workflowApi, publicWorkflowApi, Workflow, ChatMessage, WorkflowNode, NodeState, WorkflowRunStatus, JobStatusResponse, JobTaskStatus } from "./workflow-api";
import { toast } from "sonner";

function taskToNodeState(task: JobTaskStatus): NodeState {
    return {
        status: (task.status === "pending" ? "queued" : task.status) as NodeState["status"],
        started_at: task.started_at,
        completed_at: task.completed_at,
        error: task.error
    }
}

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

    // Job orchestration (Run All)
    activeJobId: string | null;

    // Public view (read-only, no auth required)
    isPublicView: boolean;
    isPublic: boolean; // whether the workflow owner has set it as public

    // Actions
    setWorkflow: (workflow: Workflow) => void;
    setName: (name: string) => void;
    setNodes: (nodes: Node[]) => void;
    setEdges: (edges: Edge[]) => void;
    setNodeOutput: (nodeId: string, output: string) => void;
    setRawOutput: (key: string, value: string) => void;
    clearNodeOutput: (nodeId: string) => void;
    addChatMessage: (message: ChatMessage) => void;
    setChatHistory: (messages: ChatMessage[]) => void;
    saveChatHistory: () => Promise<void>;
    markDirty: () => void;
    markClean: () => void;

    // API actions
    createWorkflow: (name?: string) => Promise<string | null>;
    loadWorkflow: (id: string) => Promise<void>;
    loadPublicWorkflow: (id: string) => Promise<void>;
    saveWorkflow: () => Promise<void>;
    runWorkflow: () => Promise<void>;
    runWorkflowAsync: () => Promise<void>;
    runNode: (nodeId: string) => Promise<void>;
    clearExecutionStates: () => void;
    uploadRenderedVideo: (nodeId: string, file: File) => Promise<string | null>;
    cancelJob: () => Promise<void>;
    checkActiveJob: () => Promise<void>;
    togglePublic: (isPublic: boolean) => Promise<void>;

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
    activeJobId: null,
    isPublicView: false,
    isPublic: false,
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

const FRAME_OUTPUT_HANDLES = ["start_frame", "end_frame"] as const;

const getFrameOutputKeys = (nodeId: string) =>
    FRAME_OUTPUT_HANDLES.map((handle) => `${nodeId}__${handle}`);

const getNodeOutputValue = (state: Pick<WorkflowState, "outputs" | "nodes">, nodeId: string) => {
    const output = state.outputs[nodeId];
    if (typeof output === "string" && output.length > 0) return output;

    const node = state.nodes.find((candidate) => candidate.id === nodeId);
    const dataOutput = node?.data?.output;
    return typeof dataOutput === "string" && dataOutput.length > 0 ? dataOutput : undefined;
};

const syncNodeDataOutput = (
    nodes: Node[],
    outputs: Record<string, string>,
    affectedNodeIds: Set<string>
) => {
    if (affectedNodeIds.size === 0) return nodes;

    return nodes.map((node) => {
        if (!affectedNodeIds.has(node.id)) return node;

        const nextData = { ...(node.data as Record<string, unknown>) };
        const nextOutput = outputs[node.id];
        if (typeof nextOutput === "string" && nextOutput.length > 0) {
            nextData.output = nextOutput;
        } else {
            delete nextData.output;
        }

        return { ...node, data: nextData };
    });
};

const clearNodeOutputArtifacts = (
    state: Pick<WorkflowState, "outputs" | "nodes">,
    nodeId: string
) => {
    const newOutputs = { ...state.outputs };
    delete newOutputs[nodeId];
    getFrameOutputKeys(nodeId).forEach((key) => delete newOutputs[key]);

    const newNodes = syncNodeDataOutput(state.nodes, newOutputs, new Set([nodeId]));
    return { newOutputs, newNodes };
};

const mergeOutputsWithDerivedState = (
    state: Pick<WorkflowState, "outputs" | "nodes" | "edges">,
    incomingOutputs: Record<string, string>
) => {
    const newOutputs = { ...state.outputs };
    const affectedNodeIds = new Set<string>();

    Object.entries(incomingOutputs).forEach(([key, value]) => {
        const isFrameOutput = FRAME_OUTPUT_HANDLES.some((handle) => key.endsWith(`__${handle}`));
        if (isFrameOutput) return;

        if (state.outputs[key] !== value) {
            getFrameOutputKeys(key).forEach((frameKey) => delete newOutputs[frameKey]);
        }

        newOutputs[key] = value;
        affectedNodeIds.add(key);
    });

    Object.entries(incomingOutputs).forEach(([key, value]) => {
        const frameMatch = key.match(/^(.*)__(start_frame|end_frame)$/);
        if (!frameMatch) return;

        newOutputs[key] = value;

        const [, sourceNodeId, frameHandle] = frameMatch;
        state.edges.forEach((edge) => {
            if (edge.source !== sourceNodeId) return;

            const sourceHandle = edge.sourceHandle || "";
            if (!sourceHandle.endsWith(frameHandle)) return;

            const targetNode = state.nodes.find((node) => node.id === edge.target);
            if (targetNode?.type !== "imageGen") return;

            newOutputs[edge.target] = value;
            affectedNodeIds.add(edge.target);
        });
    });

    const newNodes = syncNodeDataOutput(state.nodes, newOutputs, affectedNodeIds);
    return { newOutputs, newNodes };
};

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
            case 'assistant':
            case 'vision': sourceHandle = 'text|output'; break;
            case 'editorAgent': sourceHandle = 'video|output'; break;
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
                if (sourceNode.type === 'text') targetHandle = 'text|text';
                else if (sourceNode.type === 'audioGen') targetHandle = 'audio|audio';
                else targetHandle = 'image|start_image';
                break;
            case 'editorAgent':
                if (sourceNode.type === 'videoGen') targetHandle = 'video|ref_videos';
                else if (sourceNode.type === 'imageGen') targetHandle = 'image|ref_images';
                else if (sourceNode.type === 'audioGen') targetHandle = 'audio|audio';
                else targetHandle = 'text|text';
                break;
            case 'assistant':
            case 'vision':
                if (sourceNode.type === 'text') targetHandle = 'text|text';
                else if (sourceNode.type === 'audioGen') targetHandle = 'audio|audio';
                else if (sourceNode.type === 'editorAgent' || sourceNode.type === 'videoGen') targetHandle = 'video|ref_videos';
                else if (sourceNode.type === 'mediaUpload') {
                    const mediaType = String(sourceNode.data?.mediaType || "").toLowerCase();
                    if (mediaType === 'audio') targetHandle = 'audio|audio';
                    else if (mediaType === 'video') targetHandle = 'video|ref_videos';
                    else targetHandle = 'image|ref_images';
                } else targetHandle = 'image|ref_images';
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
            isPublic: workflow.is_public ?? false,
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
            const { newOutputs, newNodes } = mergeOutputsWithDerivedState(state, { [nodeId]: output });

            return {
                outputs: newOutputs,
                nodes: newNodes,
                isDirty: true
            };
        });
    },

    setRawOutput: (key: string, value: string) => {
        // Write directly to the outputs map without touching node.data.output.
        // Used for auxiliary keys like `{nodeId}__start_frame`.
        set((state) => {
            const frameMatch = key.match(/^(.*)__(start_frame|end_frame)$/);
            if (frameMatch) {
                const [, sourceNodeId] = frameMatch;
                const sourceOutput = getNodeOutputValue(state, sourceNodeId);
                if (!sourceOutput) {
                    return {};
                }
            }

            const { newOutputs, newNodes } = mergeOutputsWithDerivedState(state, { [key]: value });
            return { outputs: newOutputs, nodes: newNodes };
        });
    },

    clearNodeOutput: (nodeId: string) => {
        set((state) => {
            const { newOutputs, newNodes } = clearNodeOutputArtifacts(state, nodeId);

            return {
                outputs: newOutputs,
                nodes: newNodes,
                isDirty: true
            };
        });

        const { id, isPublicView, isSaving } = get();
        if (!id || isPublicView) return;

        void workflowApi.clearNodeOutput(id, nodeId).catch((error) => {
            console.error("[WorkflowStore] Clear node output error:", error);
            toast.error("Failed to clear node output");
        });

        if (!isSaving) {
            void get().saveWorkflow();
        }
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
                isPublic: workflow.is_public ?? false,
                isPublicView: false,
            });

            // Check for an active Run All job and resume polling if found
            get().checkActiveJob();
        } catch (error) {
            console.error("[WorkflowStore] Load error:", error);
            set({ isLoading: false, error: "Failed to load workflow" });
            toast.error("Failed to load workflow");
            throw error; // Re-throw to allow caller to handle
        }
    },

    // Load a public workflow (no auth required, read-only)
    loadPublicWorkflow: async (id: string) => {
        set({ isLoading: true, error: null, isPublicView: true });
        try {
            const response = await publicWorkflowApi.get(id);
            const workflow = response.data;

            const nodes = Array.isArray(workflow.nodes) ? workflow.nodes : [];
            const edges = Array.isArray(workflow.edges) ? workflow.edges : [];
            const chatHistory = Array.isArray(workflow.chat_history) ? workflow.chat_history : [];

            const validNodes = nodes.map((node: WorkflowNode) => ({
                id: node.id || String(Math.random()),
                type: node.type || 'default',
                position: node.position || { x: 0, y: 0 },
                data: node.data || {},
            })) as Node[];

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

            console.log(`[WorkflowStore] Loaded public workflow ${id}: ${validNodes.length} nodes, ${validEdges.length} edges`);

            set({
                id: workflow.id,
                name: workflow.name,
                nodes: validNodes,
                edges: validEdges,
                outputs: workflow.outputs || {},
                chatHistory: chatHistory,
                isLoading: false,
                isDirty: false,
                isPublicView: true,
                isPublic: workflow.is_public,
            });
        } catch (error) {
            console.error("[WorkflowStore] Public load error:", error);
            set({ isLoading: false, error: "Failed to load workflow", isPublicView: true });
            throw error;
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

    // Run the entire workflow via job orchestration (self-chaining lambda)
    runWorkflow: async () => {
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
            activeJobId: null
        });

        try {

            const response = await workflowApi.createJob(id);
            const { job_id } = response.data;
            set({ activeJobId: job_id });

            console.log(`[WorkflowStore] Job Created: ${job_id}`);

            const finalStatus = await workflowApi.pollJob(id, job_id, (status: JobStatusResponse) => {
                // Build nodeExecutionStates from job tasks for visual feedback 
                const nodeStates: Record<string, NodeState> = {};
                for (const task of status.tasks) {
                    nodeStates[task.node_id] = taskToNodeState(task);
                }


                set({
                    nodeExecutionStates: nodeStates,
                    executionProgress: {
                        current: status.current_task_index,
                        total: status.total_tasks
                    },
                });

                if (Object.keys(status.outputs).length > 0) {
                    set((state) => {
                        const { newOutputs, newNodes } = mergeOutputsWithDerivedState(state, status.outputs);
                        return {
                            outputs: newOutputs,
                            nodes: newNodes,
                        };
                    });
                }
            });

            // Final update
            const finalNodeStates: Record<string, NodeState> = {};
            for (const task of finalStatus.tasks) {
                finalNodeStates[task.node_id] = taskToNodeState(task);
            }

            set({
                isRunning: false,
                isRunningAsync: false,
                activeJobId: null,
                ...(() => {
                    const state = get();
                    const { newOutputs, newNodes } = mergeOutputsWithDerivedState(state, finalStatus.outputs);
                    return { outputs: newOutputs, nodes: newNodes };
                })(),
                nodeExecutionStates: finalNodeStates,
                executionProgress: {
                    current: finalStatus.current_task_index,
                    total: finalStatus.total_tasks
                },
            });

            if (finalStatus.status === "failed" && finalStatus.errors.length > 0) {
                console.error("[WorkflowStore] Job errors:", finalStatus.errors);
                set({ error: `Errors in ${finalStatus.errors.length} node(s)` });
                toast.error(`Run completed with errors in ${finalStatus.errors.length} node(s)`);
            }
            else if (finalStatus.status === "cancelled") {
                toast.info("Run cancelled");
            }
            else {
                toast.success("Workflow run completed");
            }
        } catch (error) {
            console.error("[WorkflowStore] Job run error:", error);
            set({
                isRunning: false,
                isRunningAsync: false,
                activeJobId: null,
                error: "Failed to run workflow",
                nodeExecutionStates: {},
                executionProgress: null,
            });
            toast.error("Failed to run workflow");
        }
    },

    // keep for backward compat but now delegates to runWorkflow (which uses jobs)
    runWorkflowAsync: async () => {
        await get().runWorkflow();
    },

    // Cancel a running job
    cancelJob: async () => {
        const { id, activeJobId } = get();
        if (!id || !activeJobId) return;

        try {
            await workflowApi.cancelJob(id, activeJobId);
            toast.info("Cancelling run...")
        } catch (error) {
            console.error("[WorkflowStore] Job cancel error:", error);
            toast.error("Failed to cancel run");
        }
    },

    // Check for an active job on page load (reconnect after refresh)
    checkActiveJob: async () => {
        const { id } = get();
        if (!id) return;

        try {
            const response = await workflowApi.getActiveJob(id);
            const job = response.data;
            if (!job || !job.job_id) return;

            console.log(`[WorkflowStore] Reconnecting to active job: ${job.job_id}`);

            // Hydrate state from the active job
            const nodeStates: Record<string, NodeState> = {};
            for (const task of job.tasks) {
                nodeStates[task.node_id] = taskToNodeState(task)
            }

            set({
                isRunning: true,
                isRunningAsync: true,
                activeJobId: job.job_id,
                nodeExecutionStates: nodeStates,
                executionProgress: {
                    current: job.current_task_index,
                    total: job.total_tasks,
                },
            });

            if (Object.keys(job.outputs).length > 0) {
                set((state) => {
                    const { newOutputs, newNodes } = mergeOutputsWithDerivedState(state, job.outputs);
                    return {
                        outputs: newOutputs,
                        nodes: newNodes,
                    };
                });
            }

            // Resume polling
            const finalStatus = await workflowApi.pollJob(id, job.job_id, (status: JobStatusResponse) => {
                const states: Record<string, NodeState> = {};
                for (const task of status.tasks) {
                    states[task.node_id] = taskToNodeState(task)
                }
                set({
                    nodeExecutionStates: states,
                    executionProgress: {
                        current: status.current_task_index,
                        total: status.total_tasks,
                    },
                });
                if (Object.keys(status.outputs).length > 0) {
                    set((state) => {
                        const { newOutputs, newNodes } = mergeOutputsWithDerivedState(state, status.outputs);
                        return {
                            outputs: newOutputs,
                            nodes: newNodes,
                        };
                    });
                }
            });

            // Finalize
            const finalNodeStates: Record<string, NodeState> = {};
            for (const task of finalStatus.tasks) {
                finalNodeStates[task.node_id] = taskToNodeState(task);
            }
            set({
                isRunning: false,
                isRunningAsync: false,
                activeJobId: null,
                ...(() => {
                    const state = get();
                    const { newOutputs, newNodes } = mergeOutputsWithDerivedState(state, finalStatus.outputs);
                    return { outputs: newOutputs, nodes: newNodes };
                })(),
                nodeExecutionStates: finalNodeStates,
            });

            if (finalStatus.status === "failed" && finalStatus.errors.length > 0) {
                toast.error(`Run completed with errors in ${finalStatus.errors.length} node(s)`);
            } else if (finalStatus.status !== "cancelled") {
                toast.success("Workflow run completed");
            }
        } catch {
            // No active job or network error — silent
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
                // Start async execution
                await workflowApi.runNodeAsync(id, targetId, inputOverrides);

                // Initialize running visual state
                set((state) => ({
                    nodeExecutionStates: {
                        ...state.nodeExecutionStates,
                        [targetId]: { ...state.nodeExecutionStates[targetId], status: "running" }
                    }
                }));

                // Poll until completion for the specific node
                const finalStatus = await workflowApi.pollNodeRun(id, targetId, (status: WorkflowRunStatus) => {
                    set((state) => ({
                        nodeExecutionStates: {
                            ...state.nodeExecutionStates,
                            ...status.node_states
                        },
                    }));

                    if (Object.keys(status.outputs).length > 0) {
                        set((state) => {
                            const { newOutputs, newNodes } = mergeOutputsWithDerivedState(state, status.outputs);
                            return {
                                outputs: newOutputs,
                                nodes: newNodes,
                            };
                        });
                    }
                });

                const nodeState = finalStatus.node_states[targetId];

                if (nodeState && nodeState.status === "completed") {
                    const storeOutput = finalStatus.outputs[targetId];

                    set((state) => {
                        const mergedOutputs = {
                            ...finalStatus.outputs,
                            ...(typeof storeOutput === "string" ? { [targetId]: storeOutput } : {}),
                        };
                        const { newOutputs, newNodes } = mergeOutputsWithDerivedState(state, mergedOutputs);

                        return {
                            outputs: newOutputs,
                            nodes: newNodes,
                            runningNodeId: null,
                            nodeExecutionStates: {
                                ...state.nodeExecutionStates,
                                [targetId]: { ...nodeState }
                            },
                            isDirty: true // Mark dirty so it gets saved on next manual save or run
                        };
                    });

                    return true;
                } else {
                    const finalError = nodeState?.error || "Node execution failed";
                    set((state) => ({
                        runningNodeId: null,
                        error: finalError,
                        nodeExecutionStates: {
                            ...state.nodeExecutionStates,
                            [targetId]: { ...nodeState }
                        }
                    }));
                    return false;
                }
            } catch (error) {
                console.error("[WorkflowStore] Run node error:", error);
                set((state) => ({
                    runningNodeId: null,
                    error: "Failed to run node",
                    nodeExecutionStates: {
                        ...state.nodeExecutionStates,
                        [targetId]: { status: "failed", error: "Network or polling error" }
                    }
                }));
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

    // Upload rendered video to S3 and save to node output
    uploadRenderedVideo: async (nodeId: string, file: File) => {
        const { id } = get();
        if (!id) return null;

        try {
            const res = await workflowApi.uploadRenderedVideo(id, nodeId, file);
            const data = res.data;

            if (data.url) {
                set((state) => {
                    const nextOutput = data.presigned_url || data.url;
                    const { newOutputs, newNodes } = mergeOutputsWithDerivedState(state, { [nodeId]: nextOutput });
                    return {
                        outputs: newOutputs,
                        nodes: newNodes,
                    };
                });
                // Do NOT call setNodeOutput here — that would overwrite the TSX code
                // with a video URL, causing a re-compile attempt on the URL.
                // The video URL is persisted server-side; the local store keeps the TSX
                // so in-browser re-renders keep working.
                return data.presigned_url || data.url;
            }
            return null;
        } catch (error) {
            console.error("[WorkflowStore] Upload rendered video error:", error);
            toast.error("Failed to upload rendered video");
            return null;
        }
    },

    // Toggle public visibility
    togglePublic: async (isPublic: boolean) => {
        const { id } = get();
        if (!id) return;
        try {
            await workflowApi.togglePublic(id, isPublic);
            set({ isPublic });
        } catch (error) {
            console.error("[WorkflowStore] Toggle public error:", error);
            toast.error("Failed to update sharing settings");
        }
    },

    // Reset to initial state
    reset: () => set(initialState),
}));
