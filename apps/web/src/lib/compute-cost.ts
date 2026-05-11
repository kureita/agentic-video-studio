import { Model } from "./api";

type CostedModelType = "image" | "video" | "audio";
const EDITOR_AGENT_DEFAULT_ESTIMATE_USD = 0.5;
export interface CostNode {
    id: string;
    type?: string;
    data?: Record<string, unknown>;
}

export interface CostEdge {
    source: string;
    target: string;
}

const NODE_TYPE_TO_MODEL_TYPE: Record<string, CostedModelType | undefined> = {
    image: "image",
    imageGen: "image",
    video: "video",
    videoGen: "video",
    audio: "audio",
    audioGen: "audio",
};

const AUDIO_TYPE_TO_CATEGORY: Record<string, string> = {
    voice_design: "voice_design",
    voice_clone: "voice_clone",
    music: "music",
    sfx: "sfx",
};

const getModelTypeForNode = (node: Pick<CostNode, "type">): CostedModelType | undefined =>
    node.type ? NODE_TYPE_TO_MODEL_TYPE[node.type] : undefined;

const parseDuration = (duration: unknown, fallback = 5): number => {
    if (typeof duration === "number") return duration;
    if (typeof duration === "string") {
        return parseFloat(duration.replace(/s$/i, "")) || fallback;
    }
    return fallback;
};

const findModelForNode = (
    node: CostNode,
    modelType: CostedModelType,
    models: Model[]
): Model | undefined => {
    const modelId = typeof node.data?.model === "string" ? node.data.model : undefined;
    if (modelId) {
        return models.find(
            (m) => m.type === modelType && (m.id === modelId || m.name === modelId)
        );
    }

    if (modelType === "audio") {
        const rawAudioType = typeof node.data?.audioType === "string" ? node.data.audioType : "";
        const category = AUDIO_TYPE_TO_CATEGORY[rawAudioType] || "voice_design";
        return models.find((m) => m.type === "audio" && m.category === category && !m.coming_soon)
            || models.find((m) => m.type === "audio" && m.category === category);
    }

    return models.find((m) => m.type === modelType && !m.coming_soon)
        || models.find((m) => m.type === modelType);
};

export function estimateVideoModelCost(
    model: Model,
    resolution: string,
    duration: number
): number {
    for (const cfg of model.configs) {
        if (cfg.resolution === resolution && cfg.duration === duration) {
            return cfg.est_price_usd ?? 0;
        }
    }

    const pricedDurationConfigs = model.configs
        .filter((cfg) =>
            cfg.resolution === resolution
            && typeof cfg.duration === "number"
            && typeof cfg.est_price_usd === "number"
            && cfg.duration > 0
            && cfg.est_price_usd > 0
        )
        .sort((a, b) => Math.abs((a.duration ?? 0) - duration) - Math.abs((b.duration ?? 0) - duration));

    if (pricedDurationConfigs.length > 0) {
        const nearest = pricedDurationConfigs[0];
        return ((nearest.est_price_usd ?? 0) / (nearest.duration ?? duration)) * duration;
    }

    const anyPricedDurationConfig = model.configs
        .filter((cfg) =>
            typeof cfg.duration === "number"
            && typeof cfg.est_price_usd === "number"
            && cfg.duration > 0
            && cfg.est_price_usd > 0
        )
        .sort((a, b) => Math.abs((a.duration ?? 0) - duration) - Math.abs((b.duration ?? 0) - duration))[0];

    if (anyPricedDurationConfig) {
        return ((anyPricedDurationConfig.est_price_usd ?? 0) / (anyPricedDurationConfig.duration ?? duration)) * duration;
    }

    return 0;
}

export function formatEstimatedUsd(cost: number): string {
    if (cost > 0 && cost < 0.01) return "<$0.01";
    return `$${cost.toFixed(2)}`;
}

export function isPinnedAssetNode(node: CostNode): boolean {
    const data = node.data as Record<string, unknown> | undefined;
    return !!(data?.isPinnedAsset && typeof data.output === "string");
}

export function hasUnavailableCostEstimate(node: CostNode, models?: Model[]): boolean {
    if (node.type === "__unavailable_cost_estimate__") return true;

    if (models) {
        const modelType = getModelTypeForNode(node);
        if (modelType) {
            const model = findModelForNode(node, modelType, models);
            // Avatar / lipsync models bill per second of input audio. Without
            // the audio attached we have no way to estimate the run cost — the
            // UI must say "unavailable" rather than quote the registry's
            // single-second default.
            if (model?.requires_input_duration) return true;
        }
    }

    return false;
}

/**
 * Estimate USD cost for a single node.
 *
 * Returns `null` when the node CAN'T be honestly estimated — i.e. its cost
 * depends on a required input that hasn't been provided (e.g. avatar / lipsync
 * models bill per second of the attached audio, so without an audio length we
 * can't quote a dollar amount). Callers must distinguish `null` (unknown) from
 * `0` (definitely free) so the pre-run confirm dialog and balance check don't
 * silently under-estimate.
 */
export function computeNodeCost(node: CostNode, models: Model[]): number | null {
    if (node.type === "editorAgent") return EDITOR_AGENT_DEFAULT_ESTIMATE_USD;

    const modelType = getModelTypeForNode(node);
    if (!modelType) return 0;

    const model = findModelForNode(node, modelType, models);
    if (!model || !model.configs || model.configs.length === 0) return 0;

    // Audio-driven video models (avatar, lipsync): output duration = attached
    // audio duration, and we have no way to probe that ahead of time. Treat the
    // estimate as unavailable so aggregates flag it instead of pretending $0.
    if (model.requires_input_duration) return null;

    if (modelType === "video") {
        const resolution = (node.data?.resolution as string) || "720p";
        const duration = parseDuration(node.data?.duration);
        const videoCost = estimateVideoModelCost(model, resolution, duration);
        if (videoCost > 0) return videoCost;
    } else if (modelType === "image") {
        let ratio = node.data?.ratio as string | undefined;
        if (!ratio && typeof node.data?.width === "number" && typeof node.data?.height === "number") {
            const w = node.data.width as number;
            const h = node.data.height as number;
            const r = w / h;
            if (Math.abs(r - 16 / 9) < 0.1) ratio = "16:9";
            else if (Math.abs(r - 9 / 16) < 0.1) ratio = "9:16";
            else if (Math.abs(r - 4 / 3) < 0.1) ratio = "4:3";
            else if (Math.abs(r - 3 / 4) < 0.1) ratio = "3:4";
            else ratio = "1:1";
        }
        ratio = ratio || "1:1";
        
        for (const cfg of model.configs) {
            if (cfg.id === ratio) {
                return cfg.est_price_usd ?? 0;
            }
        }
    } else if (modelType === "audio") {
        const defaultCfg = model.configs.find(c => c.id === model.default_config_id) || model.configs[0];
        if (defaultCfg?.est_price_usd_per_min) {
            if (node.data?.duration == null || node.data.duration === "") return 0;
            const duration = parseDuration(node.data.duration, 0);
            if (duration <= 0) return 0;
            return defaultCfg.est_price_usd_per_min * (duration / 60);
        }
    }

    // Fallback: use default config or first config
    const defaultCfg = model.configs.find(c => c.id === model.default_config_id);
    return (defaultCfg?.est_price_usd ?? model.configs[0]?.est_price_usd) ?? 0;
}

/**
 * Sum of known per-node costs across a workflow. `cost` is just the known
 * portion (excludes nodes whose estimate is unavailable); `hasUnavailable`
 * tells the caller whether the real total may be higher.
 */
export interface WorkflowCostEstimate {
    cost: number;
    hasUnavailable: boolean;
}

export function computeWorkflowCost(nodes: CostNode[], models: Model[]): WorkflowCostEstimate {
    let cost = 0;
    let hasUnavailable = false;
    for (const node of nodes) {
        if (isPinnedAssetNode(node)) continue;
        const nodeCost = computeNodeCost(node, models);
        if (nodeCost == null) {
            hasUnavailable = true;
            continue;
        }
        cost += nodeCost;
    }
    return { cost, hasUnavailable };
}

export interface NodeRunEstimate {
    cost: number;
    hasUnavailable: boolean;
    nodeIds: string[];
    billableNodeIds: string[];
    billableNodeCount: number;
}

export function getNodeIdsNeededForRun(
    nodeId: string,
    nodes: CostNode[],
    edges: CostEdge[],
    outputs: Record<string, unknown>
): string[] {
    const nodeById = new Map(nodes.map((node) => [node.id, node]));
    const needed = new Set<string>();

    const visit = (currentId: string, visited = new Set<string>()) => {
        if (visited.has(currentId)) return;
        visited.add(currentId);
        needed.add(currentId);

        const dependencies = edges
            .filter((edge) => edge.target === currentId)
            .map((edge) => edge.source);

        for (const sourceId of dependencies) {
            const sourceNode = nodeById.get(sourceId);
            const sourceData = sourceNode?.data as Record<string, unknown> | undefined;
            const hasStoreOutput = typeof outputs[sourceId] === "string" && outputs[sourceId].length > 0;
            const hasDataOutput = !!sourceData?.output;
            if (!hasStoreOutput && !hasDataOutput && !sourceData?.isPinnedAsset) {
                visit(sourceId, visited);
            }
        }
    };

    visit(nodeId);
    return Array.from(needed);
}

export function computeNodeRunEstimate(args: {
    nodeId: string;
    nodes: CostNode[];
    edges: CostEdge[];
    outputs: Record<string, unknown>;
    models: Model[];
    currentNodeEstimatedCost?: number | null;
}): NodeRunEstimate {
    const { nodeId, nodes, edges, outputs, models, currentNodeEstimatedCost } = args;
    const nodeById = new Map(nodes.map((node) => [node.id, node]));
    const nodeIds = getNodeIdsNeededForRun(nodeId, nodes, edges, outputs);
    let cost = 0;
    let hasUnavailable = false;
    const billableNodeIds: string[] = [];

    for (const id of nodeIds) {
        const node = nodeById.get(id);
        if (!node || isPinnedAssetNode(node)) continue;

        const nodeCost = id === nodeId && currentNodeEstimatedCost !== undefined
            ? currentNodeEstimatedCost
            : computeNodeCost(node, models);
        if (nodeCost == null) {
            hasUnavailable = true;
            continue;
        }
        cost += nodeCost;
        if (nodeCost > 0) billableNodeIds.push(id);
    }

    return { cost, hasUnavailable, nodeIds, billableNodeIds, billableNodeCount: billableNodeIds.length };
}
