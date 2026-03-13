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
    thumbnail_url?: string | null;
    status?: "draft" | "generating" | "ready" | "failed";
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

// --- Async Run Types ---

export interface NodeState {
    status: "queued" | "running" | "completed" | "failed" | "skipped";
    started_at?: string;
    completed_at?: string;
    error?: string;
}

export interface RunWorkflowAsyncResponse {
    run_id: string;
    status: string;
}

export interface WorkflowRunStatus {
    run_id: string;
    status: "running" | "completed" | "failed";
    node_states: Record<string, NodeState>;
    outputs: Record<string, string>;
    errors: Array<{ node_id: string; error: string }>;
    progress: { current: number; total: number };
}

// --- Job Orchestration Types ---

export interface JobTaskStatus {
    node_id: string;
    node_type: string;
    status: "pending" | "running" | "completed" | "failed" | "skipped";
    attempt: number;
    started_at?: string;
    completed_at?: string;
    error?: string;
}

export interface JobStatusResponse {
    job_id: string;
    status: "pending" | "running" | "completed" | "failed" | "cancelled";
    current_task_index: number;
    total_tasks: number;
    tasks: JobTaskStatus[];
    outputs: Record<string, string>;
    errors: Array<{ node_id: string, error: string }>;
}

export interface CreateJobResponse {
    job_id: string;
    status: string;
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
     * Save pre-extracted start/end frames from a video node to the workflow state.
     * Extraction happens on the client via canvas.
     */
    extractFrames: (workflowId: string, nodeId: string, startFrame?: string, endFrame?: string) =>
        api.post<{ success: boolean; start_frame?: string; end_frame?: string; cached: boolean }>(
            `/api/workflows/${workflowId}/nodes/${nodeId}/extract-frames`,
            { start_frame: startFrame, end_frame: endFrame }
        ),

    /**
     * Start async node execution (returns immediately)
     */
    runNodeAsync: (workflowId: string, nodeId: string, inputOverrides?: Record<string, unknown>) =>
        api.post<RunWorkflowAsyncResponse>(`/api/workflows/${workflowId}/nodes/${nodeId}/run-async`, {
            input_overrides: inputOverrides,
        }),


    /**
     * Run the entire workflow (synchronous - blocks until done)
     */
    runWorkflow: (id: string) =>
        api.post<RunWorkflowResponse>(`/api/workflows/${id}/run`),

    /**
     * Start async workflow execution (returns immediately)
     */
    runWorkflowAsync: (id: string) =>
        api.post<RunWorkflowAsyncResponse>(`/api/workflows/${id}/run-async`),

    /**
     * Poll the current execution status of an async workflow run
     */
    getRunStatus: (id: string) =>
        api.get<WorkflowRunStatus>(`/api/workflows/${id}/run-status`),

    /**
     * Upload a client-rendered video blob to S3 via presigned URL, and save to node output.
     * Bypasses the 10MB API Gateway limit.
     */
    uploadRenderedVideo: async (workflowId: string, nodeId: string, file: File) => {
        // 1. Get presigned upload URL
        const presignRes = await api.post<{ upload_url?: string; file_url?: string; is_local?: boolean }>(
            `/api/workflows/${workflowId}/nodes/${nodeId}/upload-render/presign`,
            { filename: file.name, content_type: file.type }
        );

        const data = presignRes.data;

        if (data.is_local) {
            // Local fallback (direct upload to FastAPI, no 10MB limit in dev)
            const formData = new FormData();
            formData.append("file", file);
            return api.post<{ url: string; presigned_url: string }>(
                `/api/workflows/${workflowId}/nodes/${nodeId}/upload-render`,
                formData,
                { headers: { "Content-Type": "multipart/form-data" } }
            );
        }

        // 2. Upload directly to S3 using the presigned URL
        if (!data.upload_url || !data.file_url) throw new Error("Missing upload URL from backend");

        await fetch(data.upload_url, {
            method: "PUT",
            body: file,
            headers: {
                "Content-Type": file.type
            }
        });

        // 3. Confirm upload with the backend so it saves the URL to the DB
        return api.post<{ url: string; presigned_url: string }>(
            `/api/workflows/${workflowId}/nodes/${nodeId}/upload-render/confirm`,
            { file_url: data.file_url }
        );
    },

    /**
     * Poll workflow run status every intervalMs until completion.
     * Calls onUpdate on each poll with the current status.
     * Returns the final status when done.
     */
    pollWorkflowRun: (
        id: string,
        onUpdate: (status: WorkflowRunStatus) => void,
        intervalMs = 2000,
    ): Promise<WorkflowRunStatus> => {
        return new Promise((resolve, reject) => {
            const poll = async () => {
                try {
                    const response = await workflowApi.getRunStatus(id);
                    const status = response.data;
                    onUpdate(status);

                    if (status.status === "running") {
                        setTimeout(poll, intervalMs);
                    } else {
                        resolve(status);
                    }
                } catch (err) {
                    reject(err);
                }
            };
            poll();
        });
    },

    /**
     * Poll node run status specifically for a single node until completion.
     */
    pollNodeRun: (
        workflowId: string,
        nodeId: string,
        onUpdate: (status: WorkflowRunStatus) => void,
        intervalMs = 2000,
    ): Promise<WorkflowRunStatus> => {
        return new Promise((resolve, reject) => {
            const poll = async () => {
                try {
                    const response = await workflowApi.getRunStatus(workflowId);
                    const status = response.data;
                    onUpdate(status);

                    const nodeState = status.node_states[nodeId];
                    if (!nodeState || nodeState.status === "running" || nodeState.status === "queued") {
                        setTimeout(poll, intervalMs);
                    } else {
                        resolve(status);
                    }
                } catch (err) {
                    reject(err);
                }
            };
            poll();
        });
    },

    // -- Job Orchestration (Run All) --

    createJob: (workflowId: string) =>
        api.post<CreateJobResponse>(`/api/workflows/${workflowId}/jobs`),

    getJobStatus: (workflowId: string, jobId: string) =>
        api.get<JobStatusResponse>(`/api/workflow/${workflowId}/jobs/${jobId}/status`),

    getActiveJob: (workflowId: string) =>
        api.get<JobStatusResponse | null>(`/api/workflows/${workflowId}/jobs/active`),

    cancelJob: (workflowId: string, jobId: string) =>
        api.post(`/api/workflows/${workflowId}/jobs/${jobId}/cancel`),

    nudgeJob: (workflowId: string, jobId: string) =>
        api.post(`/api/workflows/${workflowId}/jobs/${jobId}/nudge`),

    pollJob: (
        workflowId: string,
        jobId: string,
        onUpdate: (status: JobStatusResponse) => void,
        intervalMs = 2500,
    ): Promise<JobStatusResponse> => {
        return new Promise((resolve, reject) => {
            let nudgeChecked = false;
            const poll = async () => {
                try {
                    const response = await workflowApi.getJobStatus(workflowId, jobId);
                    const status = response.data;
                    onUpdate(status);

                    if (status.status === "pending" || status.status === "running") {
                        // Client-assisted nudge: if a task has been running for >5 min, nudge
                        if (!nudgeChecked) {
                            const runningTask = status.tasks.find(t => t.status === "running");
                            if (runningTask?.started_at) {
                                const elapsed = Date.now() - new Date(runningTask.started_at).getTime();
                                if (elapsed > 5 * 60 * 1000) {
                                    nudgeChecked = true;
                                    workflowApi.nudgeJob(workflowId, jobId).catch(() => { });
                                }
                            }
                        }
                        setTimeout(poll, intervalMs);
                    } else {
                        resolve(status);
                    }
                } catch (err) {
                    reject(err);
                }
            };
            poll();
        });
    },
};
