import { memo, useState, useRef, useMemo, ChangeEvent, useCallback, useEffect } from "react";
import { NodeProps, useReactFlow, useUpdateNodeInternals, type Edge } from "@xyflow/react";
import { Video, Clock, ChevronDown, Square, Loader2, Download, Monitor, MoreVertical } from "lucide-react";
import { NodeWrapper } from "@/components/workflow/node-wrapper";
import { HighlightedTextarea } from "@/components/workflow/nodes/highlighted-textarea";
import { usePresignedUrl } from "@/lib/use-presigned-url";
import { workflowApi } from "@/lib/workflow-api";
import { useWorkflowStore } from "@/lib/workflow-store";
import { useModels } from "@/lib/use-models";
import type { Model } from "@/lib/api";
import { toast } from "sonner";
import { extractFrameFromVideo } from "@/lib/video-utils";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";

type InputMode = "t2v" | "i2v" | "reference" | "elements" | "v2v";
type PersistedVideoNodeSettings = {
    model?: string;
    duration?: string;
    resolution?: string;
    inputMode?: string;
    generateAudio?: boolean;
    ratio?: string;
    updatedAt?: number;
};

const DEFAULT_DURATIONS = ["4s", "5s", "6s", "8s", "10s"];
const DEFAULT_RESOLUTIONS = ["720p", "1080p", "4k"];
const DEFAULT_INPUT_MODES: InputMode[] = ["t2v"];
const INPUT_MODE_PRIORITY: InputMode[] = ["i2v", "reference", "elements", "v2v", "t2v"];
const ALL_INPUT_MODES: InputMode[] = ["t2v", "i2v", "reference", "elements", "v2v"];
const LOCAL_PERSIST_KEYS = ["model", "duration", "resolution", "inputMode", "ratio", "generateAudio"] as const;

const sortDurationOptions = (durations: string[]) => {
    return [...durations].sort((a, b) => {
        const aNum = parseInt(a.replace("s", ""), 10);
        const bNum = parseInt(b.replace("s", ""), 10);
        if (Number.isNaN(aNum) || Number.isNaN(bNum)) return a.localeCompare(b);
        return aNum - bNum;
    });
};

const getModelDurations = (model?: Model, resolution?: string) => {
    if (!model) return DEFAULT_DURATIONS;

    const min = typeof model.duration_min === "number" ? model.duration_min : undefined;
    const max = typeof model.duration_max === "number" ? model.duration_max : undefined;
    const step = typeof model.duration_step === "number" && model.duration_step > 0 ? model.duration_step : 1;

    const matchingConfigDurations = Array.from(
        new Set(
            (model.configs || [])
                .filter((c) => !resolution || c.resolution === resolution)
                .map((c) => (c.duration ? `${c.duration}s` : null))
                .filter(Boolean) as string[]
        )
    );
    if (matchingConfigDurations.length > 0 && !(typeof min === "number" && typeof max === "number" && max >= min)) {
        return sortDurationOptions(matchingConfigDurations);
    }

    if (typeof min === "number" && typeof max === "number" && max >= min) {
        const values: string[] = [];
        for (let s = min; s <= max; s += step) {
            values.push(`${s}s`);
        }
        if (values.length > 0) return values;
    }

    return DEFAULT_DURATIONS;
};

const getModelResolutions = (model?: Model) => {
    if (!model) return DEFAULT_RESOLUTIONS;
    const resolutions = Array.from(new Set((model.configs || []).map((c) => c.resolution).filter(Boolean) as string[]));
    return resolutions.length > 0 ? resolutions : DEFAULT_RESOLUTIONS;
};

const getFrameImagesMax = (model?: Model) => {
    const max = typeof model?.frame_images_max === "number" ? model.frame_images_max : 2;
    return max > 0 ? max : 1;
};

const getReferenceImageBounds = (model?: Model) => {
    const min = typeof model?.reference_images_min === "number" ? model.reference_images_min : 1;
    const max = typeof model?.reference_images_max === "number" ? model.reference_images_max : 1;
    return { min, max: Math.max(min, max) };
};

const isInputMode = (value: string): value is InputMode =>
    ALL_INPUT_MODES.includes(value as InputMode);

const getModelInputModes = (model?: Model): InputMode[] => {
    if (!model) return DEFAULT_INPUT_MODES;

    const declaredModes = (model.input_modes || [])
        .map((mode) => mode.toLowerCase())
        .filter(isInputMode);

    if (declaredModes.length > 0) {
        return Array.from(new Set(declaredModes));
    }

    const caps = new Set((model.capabilities || []).map((cap) => cap.toLowerCase()));
    const inferred: InputMode[] = [];
    if (caps.has("i2v")) inferred.push("i2v");
    if (caps.has("reference")) inferred.push("reference");
    if (caps.has("elements")) inferred.push("elements");
    if (caps.has("v2v")) inferred.push("v2v");
    if (caps.has("t2v") || inferred.length === 0) inferred.push("t2v");
    return Array.from(new Set(inferred));
};

const sortInputModes = (modes: InputMode[]) => {
    const unique = Array.from(new Set(modes.filter((mode) => isInputMode(mode))));
    return unique.sort((a, b) => INPUT_MODE_PRIORITY.indexOf(a) - INPUT_MODE_PRIORITY.indexOf(b));
};

const getInputModeLabel = (mode: InputMode) => {
    switch (mode) {
        case "i2v":
            return "Start/End Frame";
        case "reference":
            return "Reference";
        case "elements":
            return "Elements";
        case "v2v":
            return "Video Extend";
        case "t2v":
        default:
            return "Text to Video";
    }
};

// Ordered preference of which image handle to reuse in each input mode.
// The first entry that's available in the new mode wins.
const IMAGE_REMAP_PRIORITY: Record<InputMode, string[]> = {
    t2v: [],
    i2v: ["start_image", "end_image"],
    reference: ["reference_image", "reference_images"],
    elements: ["elements_image"],
    v2v: [],
};

const VIDEO_REMAP_PRIORITY: Record<InputMode, string[]> = {
    t2v: [],
    i2v: [],
    reference: [],
    elements: ["elements_video"],
    v2v: ["reference_video"],
};

const AUDIO_REMAP_PRIORITY: Record<InputMode, string[]> = {
    t2v: ["audio"],
    i2v: ["audio"],
    reference: ["audio"],
    elements: ["elements_audio"],
    v2v: ["audio"],
};

const getNativeAudioDefault = (model?: Model) => {
    const hasAudioCapability = !!model?.capabilities?.some((c) => c.toLowerCase() === "audio");
    if (!hasAudioCapability) return false;
    if (typeof model?.native_audio_default === "boolean") return model.native_audio_default;
    return true;
};

const getCapabilitiesLabel = (capabilities: string[] = []) => {
    const hasI2V = !!capabilities.find(c => c.toLowerCase() === "i2v");
    const hasReference = !!capabilities.find(c => c.toLowerCase() === "reference");
    const hasElements = !!capabilities.find(c => c.toLowerCase() === "elements");
    const hasV2V = !!capabilities.find(c => c.toLowerCase() === "v2v");
    const hasAudio = !!capabilities.find(c => c.toLowerCase() === "audio");

    let label = "";
    if (hasI2V) label = "Image-to-Video";
    if (hasReference) label += (label ? " + " : "") + "Reference";
    if (hasElements) label += (label ? " + " : "") + "Elements";
    if (hasV2V) label += (label ? " + " : "") + "Video Extend";

    if (hasAudio) {
        label += label ? " + Audio" : "Audio Generation";
    }

    return label;
};

export const VideoGenNode = memo(({ id, selected, data }: NodeProps) => {
    const { deleteElements } = useReactFlow();
    const updateNodeInternals = useUpdateNodeInternals();
    const { nodes, setNodes, setEdges: setGlobalEdges, runNode, clearNodeOutput, outputs, runningNodeId, setRawOutput } = useWorkflowStore();

    const { models, isLoading: isModelsLoading } = useModels();
    const videoModels = models.filter(m => m.type === "video");

    // Derive workflowId from the URL query param: /dashboard/workflow?id=<workflowId>
    const workflowId = useMemo(() => new URLSearchParams(window.location.search).get('id') || '', []);
    const settingsStorageKey = useMemo(
        () => `video_gen_node:${workflowId || "unknown"}:${id}`,
        [workflowId, id]
    );

    const [extractingHandle, setExtractingHandle] = useState<string | null>(null);
    const [extractionError, setExtractionError] = useState<string | null>(null);
    const [menuOpen, setMenuOpen] = useState(false);
    const menuRef = useRef<HTMLDivElement>(null);

    const [showModelMenu, setShowModelMenu] = useState(false);
    const [showDurationMenu, setShowDurationMenu] = useState(false);
    const [showInputModeMenu, setShowInputModeMenu] = useState(false);
    const [hasCompletedInitialHydration, setHasCompletedInitialHydration] = useState(false);
    const saveTimerRef = useRef<number | null>(null);
    const hydratedSettingsKeyRef = useRef<string | null>(null);
    const modelMenuRef = useRef<HTMLDivElement>(null);
    const durationMenuRef = useRef<HTMLDivElement>(null);
    const inputModeMenuRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
                setMenuOpen(false);
            }
            if (modelMenuRef.current && !modelMenuRef.current.contains(event.target as Node)) {
                setShowModelMenu(false);
            }
            if (durationMenuRef.current && !durationMenuRef.current.contains(event.target as Node)) {
                setShowDurationMenu(false);
            }
            if (inputModeMenuRef.current && !inputModeMenuRef.current.contains(event.target as Node)) {
                setShowInputModeMenu(false);
            }
        };
        if (menuOpen || showModelMenu || showDurationMenu || showInputModeMenu) {
            document.addEventListener("mousedown", handleClickOutside);
        }
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, [menuOpen, showModelMenu, showDurationMenu, showInputModeMenu]);

    const isRunning = runningNodeId === id;
    const rawOutput = (outputs[id] as string | undefined) || (data.output as string | undefined);

    // Get presigned URL for S3 video assets
    const { url: presignedOutput } = usePresignedUrl(rawOutput);
    const output = presignedOutput || rawOutput;

    const isCurrentSourceOutput = useCallback((expectedOutput?: string) => {
        if (!expectedOutput) return false;

        const state = useWorkflowStore.getState();
        const currentNode = state.nodes.find((node) => node.id === id);
        const latestOutput = (state.outputs[id] as string | undefined) || (currentNode?.data?.output as string | undefined);
        return latestOutput === expectedOutput;
    }, [id]);

    const handleExtractFrames = useCallback(async (handleId: string) => {
        const sourceOutput = rawOutput;
        if (!workflowId || extractingHandle || !output || !sourceOutput) return;
        console.log('[ExtractFrames] Starting client-side extraction for node', id, 'workflow', workflowId, 'handle', handleId);
        setExtractingHandle(handleId);
        setExtractionError(null);
        try {
            const timeRatio = handleId === 'end_frame' ? 1 : 0;
            const base64Image = await extractFrameFromVideo(output, timeRatio);
            if (!isCurrentSourceOutput(sourceOutput)) return;

            const startFramePayload = handleId === 'start_frame' ? base64Image : undefined;
            const endFramePayload = handleId === 'end_frame' ? base64Image : undefined;

            const res = await workflowApi.extractFrames(workflowId, id, startFramePayload, endFramePayload);
            if (!isCurrentSourceOutput(sourceOutput)) return;
            console.log('[ExtractFrames] Save Response:', res.data);

            setRawOutput(`${id}__${handleId}`, base64Image);
        } catch (err: unknown) {
            console.error('[ExtractFrames] Error:', err);
            const msg = err instanceof Error ? err.message : 'Could not extract frame from video element (CORS or timeout)';
            setExtractionError(msg);
            toast.error(msg);
        } finally {
            setExtractingHandle(null);
        }
    }, [workflowId, id, extractingHandle, output, rawOutput, setRawOutput, isCurrentSourceOutput]);

    // Automatically extract frames whenever a new video is generated
    useEffect(() => {
        const sourceOutput = rawOutput;
        if (!workflowId || !output || !sourceOutput || !output.startsWith('http')) return;

        // Check if we already have frames for this video to avoid endless extraction loops
        const hasStartFrame = outputs[`${id}__start_frame`];
        const hasEndFrame = outputs[`${id}__end_frame`];

        if (!hasStartFrame || !hasEndFrame) {
            console.log(`[VideoNode ${id}] New output detected, auto-extracting frames...`);
            // We give the video a tiny delay to ensure the browser has loaded the blob URL metadata
            const timer = setTimeout(async () => {
                try {
                    let startFramePayload = undefined;
                    let endFramePayload = undefined;

                    if (!hasStartFrame) {
                        startFramePayload = await extractFrameFromVideo(output, 0);
                        if (!isCurrentSourceOutput(sourceOutput)) return;
                        setRawOutput(`${id}__start_frame`, startFramePayload);
                    }

                    if (!hasEndFrame) {
                        endFramePayload = await extractFrameFromVideo(output, 1);
                        if (!isCurrentSourceOutput(sourceOutput)) return;
                        setRawOutput(`${id}__end_frame`, endFramePayload);
                    }

                    if ((startFramePayload || endFramePayload) && isCurrentSourceOutput(sourceOutput)) {
                        await workflowApi.extractFrames(workflowId, id, startFramePayload, endFramePayload);
                        console.log(`[VideoNode ${id}] Auto-extraction complete and saved to backend.`);
                    }
                } catch (err) {
                    console.error(`[VideoNode ${id}] Auto-extraction failed:`, err);
                }
            }, 1000);
            return () => clearTimeout(timer);
        }
    }, [workflowId, id, output, rawOutput, outputs, setRawOutput, isCurrentSourceOutput]);


    const schedulePersistSettings = useCallback((updates: Record<string, unknown>) => {
        const shouldPersistNow = LOCAL_PERSIST_KEYS
            .some((key) => key in updates);
        if (!shouldPersistNow) return;

        if (saveTimerRef.current !== null) {
            window.clearTimeout(saveTimerRef.current);
        }

        saveTimerRef.current = window.setTimeout(() => {
            const state = useWorkflowStore.getState();
            if (state.id && !state.isPublicView && state.isDirty && !state.isSaving) {
                void state.saveWorkflow();
            }
            saveTimerRef.current = null;
        }, 500);
    }, []);

    useEffect(() => {
        return () => {
            if (saveTimerRef.current !== null) {
                window.clearTimeout(saveTimerRef.current);
                saveTimerRef.current = null;
                const state = useWorkflowStore.getState();
                if (state.id && !state.isPublicView && state.isDirty && !state.isSaving) {
                    void state.saveWorkflow();
                }
            }
        };
    }, []);

    const persistLocalSettingsPatch = useCallback((updates: Record<string, unknown>) => {
        if (!hasCompletedInitialHydration) return;

        const localPatch: Record<string, unknown> = {};
        for (const key of LOCAL_PERSIST_KEYS) {
            if (key in updates) {
                localPatch[key] = updates[key];
            }
        }

        if (Object.keys(localPatch).length === 0) return;

        try {
            const existingRaw = localStorage.getItem(settingsStorageKey);
            const existing = existingRaw ? JSON.parse(existingRaw) as PersistedVideoNodeSettings : {};
            localStorage.setItem(
                settingsStorageKey,
                JSON.stringify({
                    ...existing,
                    ...localPatch,
                    updatedAt: Date.now(),
                })
            );
        } catch (err) {
            console.warn("[VideoNode] Failed to persist local settings patch", err);
        }
    }, [hasCompletedInitialHydration, settingsStorageKey]);

    // Sync node data to workflow store
    const updateData = useCallback((updates: Record<string, unknown>) => {
        const state = useWorkflowStore.getState();
        const currentNode = state.nodes.find((n) => n.id === id);
        if (!currentNode) return;

        const hasRealChange = Object.entries(updates).some(([key, value]) => !Object.is(currentNode.data?.[key], value));
        if (!hasRealChange) {
            return;
        }

        setNodes(
            state.nodes.map((n) =>
                n.id === id ? { ...n, data: { ...n.data, ...updates } } : n
            )
        );
        persistLocalSettingsPatch(updates);
        schedulePersistSettings(updates);
    }, [id, setNodes, persistLocalSettingsPatch, schedulePersistSettings]);

    const currentModelId = typeof data.model === "string"
        ? data.model
        : (videoModels.length > 0 ? videoModels[0].id : "kling-video-3-standard");
    const currentModelEntry = videoModels.find((m) => m.id === currentModelId) || videoModels.find((m) => m.name === currentModelId);
    const currentModelDisplayName = currentModelEntry?.name || currentModelId;

    const selectedModelData = currentModelEntry;
    const validResolutions = useMemo(() => getModelResolutions(selectedModelData), [selectedModelData]);
    const effectiveResolution = validResolutions.includes(typeof data.resolution === "string" ? data.resolution : "")
        ? (data.resolution as string || validResolutions[0])
        : validResolutions[0];
    const validDurations = useMemo(
        () => getModelDurations(selectedModelData, effectiveResolution),
        [selectedModelData, effectiveResolution]
    );
    const availableInputModes = useMemo(
        () => sortInputModes(getModelInputModes(selectedModelData)),
        [selectedModelData]
    );
    const frameImagesMax = useMemo(() => getFrameImagesMax(selectedModelData), [selectedModelData]);
    const referenceBounds = useMemo(() => getReferenceImageBounds(selectedModelData), [selectedModelData]);
    const nativeAudioDefault = useMemo(() => getNativeAudioDefault(selectedModelData), [selectedModelData]);

    const selectableInputModes = useMemo(
        () => selectedModelData ? availableInputModes : [],
        [availableInputModes, selectedModelData]
    );
    const requestedInputMode = useMemo(() => {
        if (typeof data.inputMode !== "string") return undefined;
        const normalized = data.inputMode.toLowerCase();
        if (normalized === "auto") return "t2v";
        return isInputMode(normalized) ? normalized : undefined;
    }, [data.inputMode]);
    const defaultInputMode = selectableInputModes.includes("t2v") ? "t2v" : (selectableInputModes[0] || "t2v");
    const inputMode = selectedModelData
        ? ((requestedInputMode
            && selectableInputModes.includes(requestedInputMode))
            ? requestedInputMode
            : defaultInputMode)
        : (requestedInputMode || "t2v");

    useEffect(() => {
        if (!selectedModelData) return;

        if (requestedInputMode !== inputMode) {
            updateData({ inputMode });
        }
    }, [selectedModelData, requestedInputMode, inputMode, updateData]);

    // ONE-SHOT drift correction: if the workflow loaded with edges targeting
    // handles that the saved `inputMode` doesn't expose (e.g. edges on
    // `reference_images` but mode stored as `t2v`), flip mode exactly once so
    // the handles appear. After this runs we never touch the mode again — the
    // user and the remap effect own mode from that point on. This avoids any
    // possibility of an inference-vs-remap oscillation.
    const didRunInitialInferenceRef = useRef(false);
    useEffect(() => {
        if (didRunInitialInferenceRef.current) return;
        if (!selectedModelData) return;

        const state = useWorkflowStore.getState();
        const incoming = state.edges.filter((e) => e.target === id);
        if (incoming.length === 0) {
            // Nothing to infer from — mark done so we don't keep retrying.
            didRunInitialInferenceRef.current = true;
            return;
        }

        const handleIds = new Set<string>();
        for (const e of incoming) {
            const h = e.targetHandle?.split("|")[1] ?? "";
            if (h) handleIds.add(h);
        }

        let desiredMode: InputMode | null = null;
        if (handleIds.has("elements_image") || handleIds.has("elements_video") || handleIds.has("elements_audio")) {
            desiredMode = "elements";
        } else if (handleIds.has("reference_video")) {
            desiredMode = "v2v";
        } else if (handleIds.has("reference_image") || handleIds.has("reference_images")) {
            desiredMode = "reference";
        } else if (handleIds.has("start_image") || handleIds.has("end_image")) {
            desiredMode = "i2v";
        }

        didRunInitialInferenceRef.current = true;

        if (!desiredMode || desiredMode === inputMode) return;
        if (!selectableInputModes.includes(desiredMode)) return;

        updateData({ inputMode: desiredMode });
    }, [selectedModelData, selectableInputModes, inputMode, id, updateData]);

    const configInputs = useMemo(() => {
        const inputs: { id: string, label: string, type: "text" | "image" | "video" | "audio" }[] = [
            { id: "text", label: "Text/Prompt", type: "text" }
        ];

        if (inputMode === "i2v") {
            inputs.push({ id: "start_image", label: "Start Image", type: "image" });
            if (frameImagesMax > 1) {
                inputs.push({ id: "end_image", label: "End Image", type: "image" });
            }
        } else if (inputMode === "reference") {
            const referenceHandleId = referenceBounds.max <= 1 ? "reference_image" : "reference_images";
            const referenceLabel = referenceBounds.max <= 1 ? "Reference Image" : "Reference Images";
            inputs.push({ id: referenceHandleId, label: referenceLabel, type: "image" });
        } else if (inputMode === "elements") {
            inputs.push({ id: "elements_image", label: "Element Image", type: "image" });
            inputs.push({ id: "elements_video", label: "Element Video", type: "video" });
            inputs.push({ id: "elements_audio", label: "Element Audio", type: "audio" });
        } else if (inputMode === "v2v") {
            inputs.push({ id: "reference_video", label: "Reference Video", type: "video" });
        }

        // Show external audio input connection ONLY for models that explicitly support it.
        // Kling 3.0 uses native audio provider settings and should not expose an audio input handle.
        const supportsExternalAudioInput = !!currentModelEntry?.capabilities?.some(
            (c: string) => c.toLowerCase() === "audio_input"
        );
        const isKlingVideo3 = typeof currentModelEntry?.id === "string" && currentModelEntry.id.startsWith("kling-video-3-");
        if (supportsExternalAudioInput && !isKlingVideo3 && inputMode !== "elements") {
            inputs.push({ id: "audio", label: "Audio", type: "audio" });
        }

        return inputs;
    }, [
        inputMode,
        currentModelEntry,
        frameImagesMax,
        referenceBounds.max,
    ]);

    // Notify React Flow that this node's handles changed so it recomputes edge
    // endpoints immediately. Without this, edges keep rendering against the
    // OLD handle positions (stale handle-bounds cache) until the page is
    // refreshed.
    const handleSignature = useMemo(
        () => configInputs.map((h) => h.id).sort().join("|"),
        [configInputs]
    );
    useEffect(() => {
        updateNodeInternals(id);
    }, [handleSignature, id, updateNodeInternals]);

    // When the set of available input handles actually changes (the user flipped
    // mode or picked a new model), reconcile existing edges:
    //   * edges still on a valid handle within capacity → keep as-is
    //   * edges whose handle vanished but have a compatible replacement in the
    //     new mode → remap onto that handle
    //   * edges whose handle vanished and have no compatible replacement → DROP
    //
    // Dropping (rather than preserving silently) is deliberate: users expect a
    // mode switch to reshape the node; connections that don't fit the new mode
    // must not silently resurface when switching back. First render and no-op
    // re-renders are skipped so saved workflows aren't wiped on load.
    const previousHandleKeyRef = useRef<string | null>(null);
    useEffect(() => {
        if (!selectedModelData) return;

        const handlesById = new Map(configInputs.map((h) => [h.id, h] as const));
        const newKey = [...handlesById.keys()].sort().join("|");
        const prevKey = previousHandleKeyRef.current;
        previousHandleKeyRef.current = newKey;

        // Skip first render (saved state hydration) and no-op re-renders.
        if (prevKey === null || prevKey === newKey) return;

        const state = useWorkflowStore.getState();
        const currentEdges = state.edges;
        const edgesToThisNode = currentEdges.filter((e) => e.target === id);
        if (edgesToThisNode.length === 0) return;

        const imagePool = configInputs.filter((h) => h.type === "image");
        const videoPool = configInputs.filter((h) => h.type === "video");
        const audioPool = configInputs.filter((h) => h.type === "audio");

        const capacityOf = (handleId: string): number => {
            if (handleId === "start_image" || handleId === "end_image") return 1;
            if (handleId === "reference_image") return 1;
            if (handleId === "reference_video") return 1;
            if (handleId === "reference_images") return Math.max(1, referenceBounds.max);
            if (handleId.startsWith("elements_")) {
                const elementsMax = (selectedModelData?.elements_max ?? 4);
                return Math.max(1, elementsMax);
            }
            if (handleId === "audio") return 1;
            if (handleId === "text") return Infinity;
            return 1;
        };

        const usageCount = new Map<string, number>();
        const pickHandle = (
            pool: { id: string; type: string }[],
            priority: string[]
        ): string | null => {
            for (const pid of priority) {
                const handle = pool.find((h) => h.id === pid);
                if (!handle) continue;
                const used = usageCount.get(handle.id) ?? 0;
                if (used < capacityOf(handle.id)) return handle.id;
            }
            for (const handle of pool) {
                const used = usageCount.get(handle.id) ?? 0;
                if (used < capacityOf(handle.id)) return handle.id;
            }
            return null;
        };

        // Seed usage from edges already on handles that still exist, dropping
        // any that exceed the (possibly smaller) capacity for that handle.
        const droppedEdgeIds = new Set<string>();
        let didChange = false;
        for (const edge of edgesToThisNode) {
            const existingHandleId = edge.targetHandle?.split("|")[1] ?? "";
            if (!handlesById.has(existingHandleId)) continue;
            const cap = capacityOf(existingHandleId);
            const used = usageCount.get(existingHandleId) ?? 0;
            if (used >= cap) {
                droppedEdgeIds.add(edge.id);
                didChange = true;
                continue;
            }
            usageCount.set(existingHandleId, used + 1);
        }

        const updatedEdges = currentEdges.map((edge) => {
            if (edge.target !== id) return edge;
            if (droppedEdgeIds.has(edge.id)) return edge;

            const [sourceType = ""] = (edge.sourceHandle ?? "").split("|");
            const [, existingHandleId = ""] = (edge.targetHandle ?? "").split("|");

            // Still on a valid handle and within capacity — keep as-is.
            if (handlesById.has(existingHandleId)) return edge;

            const pool = sourceType === "image"
                ? imagePool
                : sourceType === "video"
                    ? videoPool
                    : sourceType === "audio"
                        ? audioPool
                        : sourceType === "text"
                            ? configInputs.filter((h) => h.type === "text")
                            : [];
            const priority = sourceType === "image"
                ? IMAGE_REMAP_PRIORITY[inputMode]
                : sourceType === "video"
                    ? VIDEO_REMAP_PRIORITY[inputMode]
                    : sourceType === "audio"
                        ? AUDIO_REMAP_PRIORITY[inputMode]
                        : [];
            const nextHandleId = pool.length > 0 ? pickHandle(pool, priority) : null;

            // No compatible handle in the new mode → DROP the edge so it can't
            // silently reappear if the user switches modes again.
            if (!nextHandleId) {
                droppedEdgeIds.add(edge.id);
                didChange = true;
                return edge;
            }

            usageCount.set(nextHandleId, (usageCount.get(nextHandleId) ?? 0) + 1);
            didChange = true;
            return {
                ...edge,
                targetHandle: `${sourceType}|${nextHandleId}`,
            } as Edge;
        }).filter((edge) => !droppedEdgeIds.has(edge.id));

        if (didChange) {
            setGlobalEdges(updatedEdges);
        }
    }, [configInputs, inputMode, selectedModelData, referenceBounds.max, id, setGlobalEdges]);

    const hasNativeAudioCapability = !!selectedModelData?.capabilities?.some(
        (c) => c.toLowerCase() === "audio"
    );
    const rawGenerateAudio = typeof data.generateAudio === "boolean" ? data.generateAudio : nativeAudioDefault;
    const generateAudio = hasNativeAudioCapability ? rawGenerateAudio : false;
    const ratio = (data.ratio as string) || "16:9";

    // Keep node data capability-consistent when model/audio defaults drift.
    useEffect(() => {
        if (!selectedModelData) return;

        if (!hasNativeAudioCapability) {
            if (typeof data.generateAudio === "boolean" && data.generateAudio) {
                updateData({ generateAudio: false });
            }
            return;
        }

        if (typeof data.generateAudio !== "boolean") {
            updateData({ generateAudio: nativeAudioDefault });
        }
    }, [selectedModelData, hasNativeAudioCapability, data.generateAudio, nativeAudioDefault, updateData]);

    const effectiveDuration = validDurations.includes(typeof data.duration === "string" ? data.duration : "")
        ? (data.duration as string || validDurations[0])
        : validDurations[0];

    useEffect(() => {
        if (!selectedModelData) return;

        if (typeof data.resolution !== "string" || data.resolution !== effectiveResolution) {
            updateData({ resolution: effectiveResolution });
        }
    }, [selectedModelData, data.resolution, effectiveResolution, updateData]);

    useEffect(() => {
        if (!selectedModelData) return;

        if (typeof data.duration !== "string" || data.duration !== effectiveDuration) {
            updateData({ duration: effectiveDuration });
        }
    }, [selectedModelData, data.duration, effectiveDuration, updateData]);

    useEffect(() => {
        hydratedSettingsKeyRef.current = null;
        setHasCompletedInitialHydration(false);
    }, [settingsStorageKey]);

    // Persist critical settings locally so refresh never loses unsynced choices.
    useEffect(() => {
        if (hydratedSettingsKeyRef.current === settingsStorageKey) {
            return;
        }

        hydratedSettingsKeyRef.current = settingsStorageKey;

        try {
            const stored = localStorage.getItem(settingsStorageKey);
            if (stored) {
                const parsed = JSON.parse(stored) as PersistedVideoNodeSettings;
                const patch: Record<string, unknown> = {};

                const rawModel = typeof data.model === "string" ? data.model : undefined;
                const rawDuration = typeof data.duration === "string" ? data.duration : undefined;
                const rawResolution = typeof data.resolution === "string" ? data.resolution : undefined;
                const rawInputMode = typeof data.inputMode === "string"
                    ? (data.inputMode.toLowerCase() === "auto" ? "t2v" : data.inputMode.toLowerCase())
                    : undefined;
                const rawRatio = typeof data.ratio === "string" ? data.ratio : undefined;
                const rawGenerateAudio = typeof data.generateAudio === "boolean" ? data.generateAudio : undefined;

                if (typeof parsed.model === "string" && parsed.model !== rawModel) patch.model = parsed.model;
                if (typeof parsed.duration === "string" && parsed.duration !== rawDuration) patch.duration = parsed.duration;
                if (typeof parsed.resolution === "string" && parsed.resolution !== rawResolution) patch.resolution = parsed.resolution;
                if (typeof parsed.inputMode === "string") {
                    const normalizedInputMode = parsed.inputMode.toLowerCase() === "auto" ? "t2v" : parsed.inputMode.toLowerCase();
                    if (isInputMode(normalizedInputMode) && normalizedInputMode !== rawInputMode) {
                        patch.inputMode = normalizedInputMode;
                    }
                }
                if (typeof parsed.generateAudio === "boolean" && parsed.generateAudio !== rawGenerateAudio) patch.generateAudio = parsed.generateAudio;
                if (typeof parsed.ratio === "string" && parsed.ratio !== rawRatio) patch.ratio = parsed.ratio;

                if (Object.keys(patch).length > 0) {
                    updateData(patch);
                }
            }
        } catch (err) {
            console.warn("[VideoNode] Failed to restore local settings", err);
        } finally {
            setHasCompletedInitialHydration(true);
        }
    }, [
        settingsStorageKey,
        data.model,
        data.duration,
        data.resolution,
        data.inputMode,
        data.generateAudio,
        data.ratio,
        updateData,
    ]);

    useEffect(() => {
        if (!hasCompletedInitialHydration) return;
        if (isModelsLoading) return;

        try {
            const snapshot = {
                model: currentModelId,
                duration: effectiveDuration,
                resolution: effectiveResolution,
                inputMode,
                generateAudio,
                ratio,
                updatedAt: Date.now(),
            };
            localStorage.setItem(settingsStorageKey, JSON.stringify(snapshot));
        } catch (err) {
            console.warn("[VideoNode] Failed to persist local settings", err);
        }
    }, [hasCompletedInitialHydration, isModelsLoading, settingsStorageKey, currentModelId, effectiveDuration, effectiveResolution, inputMode, generateAudio, ratio]);

    const handleModelChange = (newModelId: string) => {
        const newModelData = videoModels.find((m) => m.id === newModelId);
        const newValidResolutions = getModelResolutions(newModelData);
        const newInputModes = sortInputModes(getModelInputModes(newModelData));
        const newModelHasAudio = !!newModelData?.capabilities?.some((c) => c.toLowerCase() === "audio");
        const newModelAudioDefault = getNativeAudioDefault(newModelData);

        const currentRes = typeof data.resolution === "string" ? data.resolution : "720p";
        const newResolution = newValidResolutions.includes(currentRes) ? currentRes : newValidResolutions[0];
        const newValidDurations = getModelDurations(newModelData, newResolution);

        const currentDur = typeof data.duration === "string" ? data.duration : "4s";
        const newDuration = newValidDurations.includes(currentDur) ? currentDur : newValidDurations[0];

        const rawInputMode = typeof data.inputMode === "string" ? data.inputMode.toLowerCase() : "";
        const currentInputMode = rawInputMode === "auto" ? "t2v" : rawInputMode;
        const newInputMode = (isInputMode(currentInputMode) && newInputModes.includes(currentInputMode))
            ? currentInputMode
            : (newInputModes.includes("t2v") ? "t2v" : (newInputModes[0] || "t2v"));

        updateData({
            model: newModelId,
            duration: newDuration,
            resolution: newResolution,
            inputMode: newInputMode,
            generateAudio: newModelHasAudio ? newModelAudioDefault : false,
        });
    };

    const handleDownload = () => {
        if (output) {
            const link = document.createElement('a');
            link.href = output;
            link.download = `generated-video-${Date.now()}.mp4`;
            link.target = '_blank';
            link.click();
        }
    };

    const BASE_DIM = 300;

    const getDimensions = (r: string) => {
        const [w, h] = r.split(':').map(Number);
        if (!w || !h) return { width: BASE_DIM, height: BASE_DIM };

        if (w > h) {
            return { width: BASE_DIM * (w / h), height: BASE_DIM };
        } else if (h > w) {
            return { width: BASE_DIM, height: BASE_DIM * (h / w) };
        }
        return { width: BASE_DIM, height: BASE_DIM };
    };

    const styles = getDimensions(ratio);

    const [showSuggestions, setShowSuggestions] = useState(false);
    const [filterText, setFilterText] = useState("");
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    const edges = useWorkflowStore((state) => state.edges);
    const connectedTextNodeIds = useMemo(() => new Set(
        edges.filter(e => e.target === id).map(e => e.source)
    ), [edges, id]);
    const allTextNodes = useMemo(() =>
        nodes.filter(n => n.type === 'text').map((n, i) => ({ id: n.id, label: `Text #${i + 1}`, content: (n.data.text as string) || "" })),
        [nodes]
    );
    const textNodes = useMemo(() =>
        allTextNodes.filter(n => connectedTextNodeIds.has(n.id)),
        [allTextNodes, connectedTextNodeIds]
    );

    const handleTextChange = (e: ChangeEvent<HTMLTextAreaElement>) => {
        const val = e.target.value;
        const cursor = e.target.selectionStart;

        updateData({ prompt: val });

        const textBeforeCursor = val.slice(0, cursor);
        const lastAt = textBeforeCursor.lastIndexOf('@');

        if (lastAt !== -1) {
            const textAfterAt = textBeforeCursor.slice(lastAt + 1);
            if (!textAfterAt.includes('\n') && !textAfterAt.includes(' ') && textAfterAt.length < 20) {
                setShowSuggestions(true);
                setFilterText(textAfterAt.toLowerCase());
                return;
            }
        }
        setShowSuggestions(false);
    };

    const insertSuggestion = (label: string) => {
        const val = (typeof data.prompt === 'string' ? data.prompt : '');
        const cursor = textareaRef.current?.selectionStart || val.length;

        const textBeforeCursor = val.slice(0, cursor);
        const lastAt = textBeforeCursor.lastIndexOf('@');

        if (lastAt !== -1) {
            const newVal = val.slice(0, lastAt) + `@${label} ` + val.slice(cursor);
            updateData({ prompt: newVal });
            setShowSuggestions(false);

            setTimeout(() => {
                if (textareaRef.current) {
                    textareaRef.current.focus();
                    const newCursor = lastAt + label.length + 2;
                    textareaRef.current.setSelectionRange(newCursor, newCursor);
                }
            }, 0);
        }
    };

    // Frame previews extracted by the backend after video generation
    const hasVideoOutput = !!output;
    const startFramePreview = hasVideoOutput ? ((outputs[`${id}__start_frame`] as string | undefined) || undefined) : undefined;
    const endFramePreview = hasVideoOutput ? ((outputs[`${id}__end_frame`] as string | undefined) || undefined) : undefined;
    const showPromptOverlay = !output;
    const showSettingsBar = !output || selected || showDurationMenu || showModelMenu || showInputModeMenu || menuOpen;

    return (
        <NodeWrapper
            nodeId={id}
            title={`Video Generator #${useWorkflowStore((state) =>
                state.nodes
                    .filter(n => n.type === 'videoGen')
                    .findIndex(n => n.id === id) + 1
            )}`}
            icon={<Video className="w-4 h-4" />}
            selected={selected}
            inputs={configInputs}
            outputs={[
                { id: "video", label: "Video", type: "video" },
                {
                    id: "start_frame", label: "Start Frame", type: "image",
                    framePreview: startFramePreview,
                    hasVideoOutput,
                    onExtractFrames: () => handleExtractFrames('start_frame'),
                    isExtractingFrames: extractingHandle === 'start_frame',
                    extractionError: extractionError || undefined,
                },
                {
                    id: "end_frame", label: "End Frame", type: "image",
                    framePreview: endFramePreview,
                    hasVideoOutput,
                    onExtractFrames: () => handleExtractFrames('end_frame'),
                    isExtractingFrames: extractingHandle === 'end_frame',
                    extractionError: extractionError || undefined,
                },
            ]}
            contentClassName="p-0 bg-black overflow-hidden isolate"
            onDelete={() => deleteElements({ nodes: [{ id }] })}
            onRun={() => runNode(id)}
            onClear={output ? () => clearNodeOutput(id) : undefined}
            isRunning={isRunning}
            executionStatus={data.executionStatus as "queued" | "running" | "completed" | "failed" | null}
        >
            <div
                className="relative bg-muted/30 group/video transition-all duration-300 ease-in-out overflow-hidden"
                style={{
                    width: styles.width,
                    height: styles.height
                }}
            >
                {/* 1. Background Video (Output) */}
                {output && !isRunning && (
                    <>
                        <video
                            src={output}
                            className="absolute inset-0 w-full h-full object-cover z-0 select-none nodrag nopan nowheel"
                            preload="metadata"
                            playsInline
                            controls
                            onPointerDown={(e) => e.stopPropagation()}
                            onDoubleClick={(e) => e.stopPropagation()}
                            onLoadedMetadata={(e) => {
                                const video = e.currentTarget;
                                const w = video.videoWidth;
                                const h = video.videoHeight;
                                if (!w || !h) return;

                                const currentRatio = (data.ratio as string) || "16:9";
                                const videoRatio = w / h;
                                const standards = {
                                    "1:1": 1,
                                    "16:9": 16 / 9,
                                    "9:16": 9 / 16,
                                    "4:3": 4 / 3,
                                    "3:4": 3 / 4
                                };
                                let closest = "16:9";
                                let minDiff = Infinity;
                                Object.entries(standards).forEach(([key, val]) => {
                                    const diff = Math.abs(videoRatio - val);
                                    if (diff < minDiff) {
                                        minDiff = diff;
                                        closest = key;
                                    }
                                });
                                if (closest !== currentRatio && minDiff < 0.1) {
                                    updateData({ ratio: closest });
                                }
                            }}
                        />

                        {/* Download button */}
                        <button
                            onClick={handleDownload}
                            className="absolute top-3 right-3 w-8 h-8 bg-black/60 backdrop-blur-md border border-white/10 rounded-full flex items-center justify-center text-white/90 hover:bg-black/80 hover:text-white transition-all z-30 opacity-100 md:opacity-0 md:group-hover/video:opacity-100 nodrag nopan nowheel"
                        >
                            <Download className="w-4 h-4" />
                        </button>
                    </>
                )}

                {/* 2. Loading Overlay */}
                {isRunning && (
                    <div className="absolute inset-0 z-50 flex flex-col items-center justify-center p-6 text-center bg-background/90 backdrop-blur-sm">
                        <div className="w-12 h-12 rounded-full bg-rose-500/10 flex items-center justify-center mb-3 text-rose-500">
                            <Loader2 className="w-6 h-6 animate-spin" />
                        </div>
                        <p className="text-xs font-medium text-muted-foreground">Generating video...</p>
                    </div>
                )}

                {/* 3. Text Input Layer (Always Visible) */}
                <div className={cn(
                    "relative z-10 h-full flex flex-col justify-end pb-12 pointer-events-none transition-all duration-300",
                    showPromptOverlay ? "opacity-100 visible" : "opacity-0 invisible"
                )}>
                    {/* Suggestions Popup */}
                    {showSuggestions && textNodes.length > 0 && (
                        <div className="absolute bottom-12 left-2 z-50 w-48 bg-popover text-popover-foreground rounded-md border shadow-md overflow-hidden animate-in fade-in zoom-in-95 duration-100 pointer-events-auto">
                            <div className="px-2 py-1.5 text-xs font-semibold text-muted-foreground bg-muted/50 border-b">
                                Suggested Inputs
                            </div>
                            <div className="max-h-[120px] overflow-y-auto p-1">
                                {textNodes
                                    .filter(n => n.label.toLowerCase().includes(filterText) || n.content.toLowerCase().includes(filterText))
                                    .map((node) => (
                                        <button
                                            key={node.id}
                                            className="w-full text-left px-2 py-1.5 text-xs rounded-sm hover:bg-accent hover:text-accent-foreground cursor-pointer flex items-center justify-between group/item"
                                            onClick={() => insertSuggestion(node.label)}
                                        >
                                            <span className="font-medium text-primary">{node.label}</span>
                                            <span className="text-[10px] text-muted-foreground truncate max-w-[80px] opacity-70 group-hover/item:opacity-100">
                                                {node.content.slice(0, 15)}...
                                            </span>
                                        </button>
                                    ))}
                                {textNodes.length === 0 && (
                                    <div className="px-2 py-1.5 text-xs text-muted-foreground italic">No text nodes found</div>
                                )}
                            </div>
                        </div>
                    )}

                    <HighlightedTextarea
                        textareaRef={textareaRef}
                        className="w-full min-h-[80px] bg-transparent border-none px-4 pb-2 pt-4 text-sm font-medium placeholder:text-white/50 focus-visible:outline-none resize-y overflow-y-auto leading-relaxed text-white nodrag nowheel pointer-events-auto drop-shadow-md shadow-black/50"
                        placeholder="Describe the video you want to generate..."
                        value={typeof data.prompt === 'string' ? data.prompt : ''}
                        onChange={handleTextChange}
                        onKeyDown={(e) => e.stopPropagation()}
                    />
                </div>

                {/* Controls Bar */}
                <div className={cn(
                    "absolute left-3 flex items-center gap-1 transition-all duration-300 z-20",
                    output
                        ? (showSettingsBar
                            ? "bottom-12 right-3 opacity-100 translate-y-0"
                            : "bottom-12 right-3 opacity-0 translate-y-2 pointer-events-none")
                        : "bottom-3 right-3 opacity-0 group-hover/video:opacity-100 translate-y-2 group-hover/video:translate-y-0"
                )}>
                    {/* Duration Pill */}
                    <div className="relative flex-shrink-0" ref={durationMenuRef}>
                        <button
                            onClick={() => {
                                setShowDurationMenu(!showDurationMenu);
                                setShowModelMenu(false);
                                setShowInputModeMenu(false);
                                setMenuOpen(false);
                            }}
                            className={cn(
                                "flex items-center gap-1.5 h-7 bg-black/60 backdrop-blur-md border border-white/10 rounded-full px-2 text-white/90 hover:bg-black/70 transition-colors cursor-pointer",
                                showDurationMenu && "bg-black/80 border-white/20"
                            )}
                        >
                            <Clock className="w-2.5 h-2.5 text-white/70 flex-shrink-0" />
                            <span className="text-[10px] font-medium whitespace-nowrap">{effectiveDuration}</span>
                            <ChevronDown className="w-2.5 h-2.5 text-white/50 flex-shrink-0" />
                        </button>

                        <AnimatePresence>
                            {showDurationMenu && (
                                <motion.div
                                    initial={{ opacity: 0, y: 4, scale: 0.96 }}
                                    animate={{ opacity: 1, y: 0, scale: 1 }}
                                    exit={{ opacity: 0, y: 4, scale: 0.96 }}
                                    transition={{ duration: 0.12 }}
                                    className="absolute bottom-full left-0 mb-2 w-24 bg-black/90 backdrop-blur-xl border border-white/10 rounded-xl shadow-2xl overflow-hidden z-50 pointer-events-auto flex flex-col"
                                >
                                    <div className="px-3 py-2 text-[10px] font-semibold text-white/50 uppercase tracking-wider border-b border-white/10 bg-black/40">
                                        Duration
                                    </div>
                                    <div className="max-h-[180px] overflow-y-auto flex flex-col p-1 nodrag nowheel">
                                        {validDurations.map(d => (
                                            <button
                                                key={d}
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    updateData({ duration: d });
                                                    setShowDurationMenu(false);
                                                }}
                                                className={cn(
                                                    "w-full text-left px-2.5 py-1.5 text-[11px] rounded-lg hover:bg-white/10 cursor-pointer transition-colors",
                                                    effectiveDuration === d && "bg-white/15 text-white font-medium"
                                                )}
                                            >
                                                <span className={cn(effectiveDuration !== d && "text-white/80")}>
                                                    {d}
                                                </span>
                                            </button>
                                        ))}
                                    </div>
                                </motion.div>
                            )}
                        </AnimatePresence>
                    </div>

                    {/* Model Pill */}
                    <div className="relative flex-grow min-w-0" ref={modelMenuRef}>
                        <button
                            onClick={() => {
                                setShowModelMenu(!showModelMenu);
                                setShowDurationMenu(false);
                                setShowInputModeMenu(false);
                                setMenuOpen(false);
                            }}
                            className={cn(
                                "flex items-center gap-1.5 h-7 w-full bg-black/60 backdrop-blur-md border border-white/10 rounded-full px-2 text-white/90 hover:bg-black/70 transition-colors cursor-pointer",
                                showModelMenu && "bg-black/80 border-white/20"
                            )}
                        >
                            <span className="text-[10px] font-medium truncate flex-grow text-left">{currentModelDisplayName}</span>
                            <ChevronDown className="w-2.5 h-2.5 text-white/50 flex-shrink-0" />
                        </button>

                        <AnimatePresence>
                            {showModelMenu && (
                                <motion.div
                                    initial={{ opacity: 0, y: 4, scale: 0.96 }}
                                    animate={{ opacity: 1, y: 0, scale: 1 }}
                                    exit={{ opacity: 0, y: 4, scale: 0.96 }}
                                    transition={{ duration: 0.12 }}
                                    className="absolute bottom-full left-0 mb-2 w-48 bg-black/90 backdrop-blur-xl border border-white/10 rounded-xl shadow-2xl overflow-hidden z-50 pointer-events-auto flex flex-col"
                                >
                                    <div className="px-3 py-2 text-[10px] font-semibold text-white/50 uppercase tracking-wider border-b border-white/10 bg-black/40">
                                        Model
                                    </div>
                                    <div className="max-h-[180px] overflow-y-auto flex flex-col p-1 nodrag nowheel">
                                        {videoModels.map(m => (
                                            <button
                                                key={m.id}
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    handleModelChange(m.id);
                                                    setShowModelMenu(false);
                                                }}
                                                className={cn(
                                                    "w-full text-left px-2.5 py-1.5 rounded-lg hover:bg-white/10 cursor-pointer flex items-center justify-between transition-colors",
                                                    currentModelId === m.id && "bg-white/15 text-white"
                                                )}
                                            >
                                                <div className="flex flex-col gap-0.5">
                                                    <span className={cn("text-[11px] font-medium", currentModelId !== m.id && "text-white/80")}>
                                                        {m.name}
                                                    </span>
                                                    {getCapabilitiesLabel(m.capabilities) && (
                                                        <span className="text-white/40 text-[9px] leading-tight">
                                                            {getCapabilitiesLabel(m.capabilities)}
                                                        </span>
                                                    )}
                                                </div>
                                            </button>
                                        ))}
                                        {videoModels.length === 0 && (
                                            <div className="px-3 py-2 text-[11px] text-white/50 italic">No models available</div>
                                        )}
                                    </div>
                                </motion.div>
                            )}
                        </AnimatePresence>
                    </div>

                    {/* Input Mode Pill */}
                    {selectableInputModes.length > 0 && (
                    <div className="relative flex-shrink-0 min-w-0 max-w-[110px]" ref={inputModeMenuRef}>
                        <button
                            onClick={(e) => {
                                e.stopPropagation();
                                setShowInputModeMenu(!showInputModeMenu);
                                setShowModelMenu(false);
                                setShowDurationMenu(false);
                                setMenuOpen(false);
                            }}
                            className={cn(
                                "flex items-center gap-1.5 h-7 w-full bg-black/60 backdrop-blur-md border border-white/10 rounded-full px-2 text-white/90 hover:bg-black/70 transition-colors cursor-pointer",
                                showInputModeMenu && "bg-black/80 border-white/20"
                            )}
                        >
                            <span className="text-[10px] font-medium truncate flex-grow text-left">
                                {getInputModeLabel(inputMode)}
                            </span>
                            <ChevronDown className="w-2.5 h-2.5 text-white/50 flex-shrink-0" />
                        </button>
                        
                        <AnimatePresence>
                            {showInputModeMenu && (
                                <motion.div
                                    initial={{ opacity: 0, y: 4, scale: 0.96 }}
                                    animate={{ opacity: 1, y: 0, scale: 1 }}
                                    exit={{ opacity: 0, y: 4, scale: 0.96 }}
                                    transition={{ duration: 0.12 }}
                                    className="absolute bottom-full right-0 mb-2 w-32 bg-black/90 backdrop-blur-xl border border-white/10 rounded-xl shadow-2xl overflow-hidden z-50 pointer-events-auto flex flex-col"
                                >
                                    <div className="px-3 py-2 text-[10px] font-semibold text-white/50 uppercase tracking-wider border-b border-white/10 bg-black/40">
                                        Input Mode
                                    </div>
                                    <div className="max-h-[180px] overflow-y-auto flex flex-col p-1 nodrag nowheel">
                                        {selectableInputModes.map((mode) => {
                                            const label = getInputModeLabel(mode);

                                            return (
                                            <button
                                                key={mode}
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    updateData({ inputMode: mode });
                                                    setShowInputModeMenu(false);
                                                }}
                                                className={cn(
                                                    "w-full text-left px-2.5 py-1.5 text-[11px] rounded-lg hover:bg-white/10 cursor-pointer transition-colors",
                                                    inputMode === mode && "bg-white/15 text-white font-medium"
                                                )}
                                            >
                                                <span className={cn(inputMode !== mode && "text-white/80")}>
                                                    {label}
                                                </span>
                                            </button>
                                            );
                                        })}
                                    </div>
                                </motion.div>
                            )}
                        </AnimatePresence>
                    </div>
                    )}

                    {/* Kebab Menu for Settings */}
                    <div
                        className="relative flex-shrink-0"
                        ref={menuRef}
                    >
                        <button
                            className={cn(
                                "h-7 w-7 flex items-center justify-center bg-black/60 backdrop-blur-md border border-white/10 rounded-full text-white/90 hover:bg-black/70 transition-colors cursor-pointer",
                                menuOpen && "bg-black/80 border-white/20"
                            )}
                            onClick={(e) => {
                                e.stopPropagation();
                                setMenuOpen(!menuOpen);
                                setShowModelMenu(false);
                                setShowInputModeMenu(false);
                                setShowDurationMenu(false);
                            }}
                        >
                            <MoreVertical className="w-3.5 h-3.5" />
                        </button>

                        <AnimatePresence>
                            {menuOpen && (
                                <motion.div
                                    initial={{ opacity: 0, y: 4, scale: 0.96 }}
                                    animate={{ opacity: 1, y: 0, scale: 1 }}
                                    exit={{ opacity: 0, y: 4, scale: 0.96 }}
                                    transition={{ duration: 0.12 }}
                                    className="absolute bottom-full right-0 mb-2 w-40 max-h-[230px] overflow-y-auto bg-black/90 backdrop-blur-xl border border-white/10 rounded-xl shadow-2xl z-50 pointer-events-auto flex flex-col p-2 gap-3 nodrag nowheel"
                                >
                                    <div className="text-[10px] font-medium text-white/50 uppercase tracking-wider px-1">Settings</div>

                                    {/* Ratio Dropdown in Menu */}
                                    <div className="flex flex-col gap-1.5 nodrag nowheel">
                                        <label className="text-[10px] text-white/70 flex items-center gap-1.5 px-1">
                                            <Square className="w-3 h-3" /> Ratio
                                        </label>
                                        <div className="flex flex-wrap gap-1">
                                            {["16:9", "9:16", "1:1"].map((r) => (
                                                <button
                                                    key={r}
                                                    onClick={(e) => {
                                                        e.stopPropagation();
                                                        updateData({ ratio: r });
                                                    }}
                                                    className={cn(
                                                        "px-2 py-1 text-[10px] rounded border transition-colors cursor-pointer flex-grow text-center",
                                                        (typeof data.ratio === 'string' ? data.ratio : "16:9") === r
                                                            ? "bg-white/20 border-white/30 text-white"
                                                            : "bg-black/40 border-white/10 text-white/70 hover:bg-white/10"
                                                    )}
                                                >
                                                    {r}
                                                </button>
                                            ))}
                                        </div>
                                    </div>

                                    {/* Resolution Dropdown in Menu */}
                                    <div className="flex flex-col gap-1.5 nodrag nowheel">
                                        <label className="text-[10px] text-white/70 flex items-center gap-1.5 px-1">
                                            <Monitor className="w-3 h-3" /> Resolution
                                        </label>
                                        <div className="flex flex-wrap gap-1">
                                            {validResolutions.map(r => (
                                                <button
                                                    key={r}
                                                    onClick={(e) => {
                                                        e.stopPropagation();
                                                        const nextDurations = getModelDurations(selectedModelData, r);
                                                        const nextDuration = nextDurations.includes(effectiveDuration)
                                                            ? effectiveDuration
                                                            : nextDurations[0];
                                                        updateData({ resolution: r, duration: nextDuration });
                                                    }}
                                                    className={cn(
                                                        "px-2 py-1 text-[10px] rounded border transition-colors cursor-pointer flex-grow text-center",
                                                        effectiveResolution === r
                                                            ? "bg-white/20 border-white/30 text-white"
                                                            : "bg-black/40 border-white/10 text-white/70 hover:bg-white/10"
                                                    )}
                                                >
                                                    {r}
                                                </button>
                                            ))}
                                        </div>
                                    </div>

                                    {/* Native Audio Toggle */}
                                    <div className="flex flex-col gap-1.5 nodrag nowheel">
                                        <label className="text-[10px] text-white/70 px-1">Native Audio</label>
                                        <div className="flex items-center justify-between px-1">
                                            <span className="text-[10px] text-white/90">{generateAudio ? "On" : "Off"}</span>
                                            <button
                                                type="button"
                                                role="switch"
                                                aria-label="Toggle native audio"
                                                aria-checked={generateAudio}
                                                disabled={!hasNativeAudioCapability}
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    if (!hasNativeAudioCapability) return;
                                                    updateData({ generateAudio: !generateAudio });
                                                }}
                                                className={cn(
                                                    "relative inline-flex h-5 w-9 items-center rounded-full border transition-colors cursor-pointer",
                                                    generateAudio
                                                        ? "bg-emerald-400/80 border-emerald-200/50"
                                                        : "bg-white/20 border-white/20",
                                                    !hasNativeAudioCapability && "opacity-50 cursor-not-allowed"
                                                )}
                                            >
                                                <span
                                                    className={cn(
                                                        "inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform",
                                                        generateAudio ? "translate-x-4.5" : "translate-x-0.5"
                                                    )}
                                                />
                                            </button>
                                        </div>
                                        <p className="text-[9px] text-white/40 px-1">
                                            {hasNativeAudioCapability
                                                ? "Creates model-native audio in the generated clip."
                                                : "Selected model has no native audio capability."}
                                        </p>
                                    </div>
                                </motion.div>
                            )}
                        </AnimatePresence>
                    </div>
                </div>
            </div>
        </NodeWrapper>
    );
});

VideoGenNode.displayName = "VideoGenNode";
