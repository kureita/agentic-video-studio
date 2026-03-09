import { memo, useState, useRef, useMemo, ChangeEvent, useCallback, useEffect } from "react";
import { NodeProps, useReactFlow } from "@xyflow/react";
import { Video, Clock, ChevronDown, Square, Loader2, Download, Monitor, MoreVertical } from "lucide-react";
import { NodeWrapper } from "@/components/workflow/node-wrapper";
import { HighlightedTextarea } from "@/components/workflow/nodes/highlighted-textarea";
import { usePresignedUrl } from "@/lib/use-presigned-url";
import { workflowApi } from "@/lib/workflow-api";
import { useWorkflowStore } from "@/lib/workflow-store";
import { toast } from "sonner";
import { extractFrameFromVideo } from "@/lib/video-utils";

const MODEL_CONFIGS: Record<string, { durations: string[], inputs: { id: string, label: string, type: "text" | "image" | "video" | "audio" }[] }> = {
    "Veo 3.1": { durations: ["8s"], inputs: [{ id: "text", label: "Text/Prompt", type: "text" }, { id: "start_image", label: "Start Image", type: "image" }, { id: "end_image", label: "End Image", type: "image" }] },
    "Veo 3.1 Fast": { durations: ["8s"], inputs: [{ id: "text", label: "Text/Prompt", type: "text" }, { id: "start_image", label: "Start Image", type: "image" }, { id: "end_image", label: "End Image", type: "image" }] },
    "Veo 3": { durations: ["8s"], inputs: [{ id: "text", label: "Text/Prompt", type: "text" }, { id: "start_image", label: "Start Image", type: "image" }] },
    "Veo 3 Fast": { durations: ["8s"], inputs: [{ id: "text", label: "Text/Prompt", type: "text" }, { id: "start_image", label: "Start Image", type: "image" }, { id: "end_image", label: "End Image", type: "image" }] },
    "Veo 2": { durations: ["5s", "6s", "7s", "8s"], inputs: [{ id: "text", label: "Text/Prompt", type: "text" }, { id: "start_image", label: "Start Image", type: "image" }, { id: "end_image", label: "End Image", type: "image" }] },
    "Kling 3.0 Standard": { durations: ["5s", "10s"], inputs: [{ id: "text", label: "Text/Prompt", type: "text" }, { id: "start_image", label: "Start Image", type: "image" }, { id: "end_image", label: "End Image", type: "image" }] },
    "Kling 3.0 Pro": { durations: ["5s", "10s"], inputs: [{ id: "text", label: "Text/Prompt", type: "text" }, { id: "start_image", label: "Start Image", type: "image" }, { id: "end_image", label: "End Image", type: "image" }] },
    "Kling 2.1 Master": { durations: ["5s", "10s"], inputs: [{ id: "text", label: "Text/Prompt", type: "text" }, { id: "start_image", label: "Start Image", type: "image" }, { id: "end_image", label: "End Image", type: "image" }] },
    "Kling Lip Sync": { durations: ["5s", "10s"], inputs: [{ id: "text", label: "Text/Prompt", type: "text" }, { id: "start_image", label: "Video", type: "video" }, { id: "audio", label: "Audio", type: "audio" }] },
    "Runway Gen-4.5": { durations: ["5s", "8s", "10s"], inputs: [{ id: "text", label: "Text/Prompt", type: "text" }, { id: "start_image", label: "Start Image", type: "image" }] },
    "Runway Gen-4 Turbo": { durations: ["2s", "5s", "10s"], inputs: [{ id: "text", label: "Text/Prompt", type: "text" }, { id: "start_image", label: "Start Image", type: "image" }] },
    "Seedance 1.5 Pro": { durations: ["4s", "5s", "8s", "10s", "12s"], inputs: [{ id: "text", label: "Text/Prompt", type: "text" }, { id: "start_image", label: "Start Image", type: "image" }, { id: "end_image", label: "End Image", type: "image" }] },
    "Seedance 1.0 Pro": { durations: ["5s", "8s", "10s", "12s"], inputs: [{ id: "text", label: "Text/Prompt", type: "text" }, { id: "start_image", label: "Start Image", type: "image" }, { id: "end_image", label: "End Image", type: "image" }] },
    "Seedance 1.0 Pro Fast": { durations: ["5s", "8s", "10s", "12s"], inputs: [{ id: "text", label: "Text/Prompt", type: "text" }, { id: "start_image", label: "Start Image", type: "image" }] },
    "Seedance 1.0 Lite": { durations: ["5s", "8s", "10s", "12s"], inputs: [{ id: "text", label: "Text/Prompt", type: "text" }, { id: "start_image", label: "Start Image", type: "image" }, { id: "end_image", label: "End Image", type: "image" }] },
    "Wan2.6": { durations: ["5s", "10s", "15s"], inputs: [{ id: "text", label: "Text/Prompt", type: "text" }, { id: "start_image", label: "Start Image", type: "image" }] },
    "Wan2.6 Flash": { durations: ["3s", "5s", "10s"], inputs: [{ id: "text", label: "Text/Prompt", type: "text" }, { id: "start_image", label: "Start Image", type: "image" }] },
    "Hailuo 2.3": { durations: ["6s", "10s"], inputs: [{ id: "text", label: "Text/Prompt", type: "text" }, { id: "start_image", label: "Start Image", type: "image" }] },
    "Hailuo 2.3 Fast": { durations: ["6s", "10s"], inputs: [{ id: "text", label: "Text/Prompt", type: "text" }, { id: "start_image", label: "Start Image", type: "image" }] },
    "PixVerse V5.6": { durations: ["5s", "8s", "10s"], inputs: [{ id: "text", label: "Text/Prompt", type: "text" }, { id: "start_image", label: "Start Image", type: "image" }, { id: "end_image", label: "End Image", type: "image" }] },
};

export const VideoGenNode = memo(({ id, selected, data }: NodeProps) => {
    const { deleteElements, updateNodeData } = useReactFlow();
    const { nodes, setNodes, runNode, clearNodeOutput, outputs, runningNodeId, setRawOutput } = useWorkflowStore();

    // Derive workflowId from the URL query param: /dashboard/workflow?id=<workflowId>
    const workflowId = useMemo(() => new URLSearchParams(window.location.search).get('id') || '', []);

    const [extractingHandle, setExtractingHandle] = useState<string | null>(null);
    const [extractionError, setExtractionError] = useState<string | null>(null);
    const [menuOpen, setMenuOpen] = useState(false);
    const menuRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
                setMenuOpen(false);
            }
        };
        if (menuOpen) {
            document.addEventListener("mousedown", handleClickOutside);
        }
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, [menuOpen]);

    const isRunning = runningNodeId === id;
    const rawOutput = (outputs[id] as string | undefined) || (data.output as string | undefined);

    // Get presigned URL for S3 video assets
    const { url: presignedOutput } = usePresignedUrl(rawOutput);
    const output = presignedOutput || rawOutput;

    const handleExtractFrames = useCallback(async (handleId: string) => {
        if (!workflowId || extractingHandle || !output) return;
        console.log('[ExtractFrames] Starting client-side extraction for node', id, 'workflow', workflowId, 'handle', handleId);
        setExtractingHandle(handleId);
        setExtractionError(null);
        try {
            const timeRatio = handleId === 'end_frame' ? 1 : 0;
            const base64Image = await extractFrameFromVideo(output, timeRatio);

            const startFramePayload = handleId === 'start_frame' ? base64Image : undefined;
            const endFramePayload = handleId === 'end_frame' ? base64Image : undefined;

            const res = await workflowApi.extractFrames(workflowId, id, startFramePayload, endFramePayload);
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
    }, [workflowId, id, extractingHandle, output, setRawOutput]);

    // Automatically extract frames whenever a new video is generated
    useEffect(() => {
        if (!workflowId || !output || !output.startsWith('http')) return;

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
                        setRawOutput(`${id}__start_frame`, startFramePayload);
                    }

                    if (!hasEndFrame) {
                        endFramePayload = await extractFrameFromVideo(output, 1);
                        setRawOutput(`${id}__end_frame`, endFramePayload);
                    }

                    if (startFramePayload || endFramePayload) {
                        await workflowApi.extractFrames(workflowId, id, startFramePayload, endFramePayload);
                        console.log(`[VideoNode ${id}] Auto-extraction complete and saved to backend.`);
                    }
                } catch (err) {
                    console.error(`[VideoNode ${id}] Auto-extraction failed:`, err);
                }
            }, 1000);
            return () => clearTimeout(timer);
        }
    }, [workflowId, id, output, outputs, setRawOutput]);


    // Sync node data to workflow store
    const updateData = (updates: Record<string, unknown>) => {
        updateNodeData(id, updates);
        setNodes(
            nodes.map((n) =>
                n.id === id ? { ...n, data: { ...n.data, ...updates } } : n
            )
        );
    };

    const currentModel = (typeof data.model === 'string' ? data.model : "Kling 3.0 Standard");
    // Ensure the current model exists in configs, fallback to default
    const config = MODEL_CONFIGS[currentModel] || MODEL_CONFIGS["Kling 3.0 Standard"];

    // Check if the current duration is valid for the model, otherwise update to default for model.
    // However, during render we cannot safely update state synchronously without warnings, 
    // so we just define the effective duration. The actual data sync happens on selection change.
    const validDurations = config.durations;
    const effectiveDuration = validDurations.includes(typeof data.duration === 'string' ? data.duration : "4s")
        ? (data.duration as string || validDurations[0])
        : validDurations[0];

    const handleModelChange = (newModel: string) => {
        const newConfig = MODEL_CONFIGS[newModel] || MODEL_CONFIGS["Kling 3.0 Standard"];
        const currentDur = data.duration as string || "4s";
        let newDuration = currentDur;
        if (!newConfig.durations.includes(currentDur)) {
            newDuration = newConfig.durations[0];
        }
        updateData({ model: newModel, duration: newDuration });
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

    const ratio = (data.ratio as string) || "16:9";
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

        updateNodeData(id, { prompt: val });

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
            updateNodeData(id, { prompt: newVal });
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
    const startFramePreview = (outputs[`${id}__start_frame`] as string | undefined) || undefined;
    const endFramePreview = (outputs[`${id}__end_frame`] as string | undefined) || undefined;
    const hasVideoOutput = !!output;

    return (
        <NodeWrapper
            title={`Video Generator #${useWorkflowStore((state) =>
                state.nodes
                    .filter(n => n.type === 'videoGen')
                    .findIndex(n => n.id === id) + 1
            )}`}
            icon={<Video className="w-4 h-4" />}
            selected={selected}
            inputs={config.inputs}
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
            contentClassName="p-0 overflow-hidden isolate"
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
                            className="absolute inset-0 w-full h-full object-cover z-0"
                            controls={!showSuggestions} // Disable controls when typing? Or keep enabled.
                            playsInline
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
                        <div className="absolute inset-0 bg-black/40 z-0 pointer-events-none transition-opacity duration-300" />

                        {/* Download button */}
                        <button
                            onClick={handleDownload}
                            className="absolute top-3 right-3 w-8 h-8 bg-black/60 backdrop-blur-md border border-white/10 rounded-full flex items-center justify-center text-white/90 hover:bg-black/80 hover:text-white transition-all z-30 opacity-0 group-hover/video:opacity-100"
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
                <div className={`relative z-10 h-full flex flex-col justify-end pb-12 pointer-events-none transition-all duration-300 ${output ? "opacity-0 group-hover/video:opacity-100 focus-within:opacity-100" : ""}`}>
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
                <div className="absolute bottom-3 left-3 right-3 flex items-center gap-1 opacity-0 group-hover/video:opacity-100 transition-all duration-300 translate-y-2 group-hover/video:translate-y-0 z-20">
                    {/* Duration Pill */}
                    <div className="relative h-7 flex items-center gap-1.5 bg-black/60 backdrop-blur-md border border-white/10 rounded-full px-2 text-white/90 hover:bg-black/70 transition-colors flex-shrink-0">
                        <Clock className="w-2.5 h-2.5 text-white/70 flex-shrink-0" />
                        <span className="text-[10px] font-medium whitespace-nowrap">{effectiveDuration}</span>
                        <ChevronDown className="w-2.5 h-2.5 text-white/50 flex-shrink-0" />
                        <select
                            className="absolute inset-0 opacity-0 cursor-pointer"
                            value={effectiveDuration}
                            onChange={(e) => updateData({ duration: e.target.value })}
                        >
                            {validDurations.map(d => (
                                <option key={d} value={d}>{d}</option>
                            ))}
                        </select>
                    </div>

                    {/* Model Pill */}
                    <div className="relative h-7 flex items-center gap-1.5 bg-black/60 backdrop-blur-md border border-white/10 rounded-full px-2 text-white/90 hover:bg-black/70 transition-colors min-w-0 flex-grow">
                        <span className="text-[10px] font-medium truncate flex-grow text-left">{currentModel}</span>
                        <ChevronDown className="w-2.5 h-2.5 text-white/50 flex-shrink-0" />
                        <select
                            className="absolute inset-0 opacity-0 cursor-pointer"
                            value={currentModel}
                            onChange={(e) => handleModelChange(e.target.value)}
                        >
                            <option value="Veo 3.1">Veo 3.1</option>
                            <option value="Veo 3.1 Fast">Veo 3.1 Fast</option>
                            <option value="Veo 3">Veo 3</option>
                            <option value="Veo 3 Fast">Veo 3 Fast</option>
                            <option value="Veo 2">Veo 2</option>
                            <option value="Kling 3.0 Standard">Kling 3.0 Standard</option>
                            <option value="Kling 3.0 Pro">Kling 3.0 Pro</option>
                            <option value="Kling 2.1 Master">Kling 2.1 Master</option>
                            <option value="Kling Lip Sync">Kling Lip Sync</option>
                            <option value="Runway Gen-4.5">Runway Gen-4.5</option>
                            <option value="Runway Gen-4 Turbo">Runway Gen-4 Turbo</option>
                            <option value="Seedance 1.5 Pro">Seedance 1.5 Pro</option>
                            <option value="Seedance 1.0 Pro">Seedance 1.0 Pro</option>
                            <option value="Seedance 1.0 Pro Fast">Seedance 1.0 Pro Fast</option>
                            <option value="Seedance 1.0 Lite">Seedance 1.0 Lite</option>
                            <option value="Wan2.6">Wan2.6</option>
                            <option value="Wan2.6 Flash">Wan2.6 Flash</option>
                            <option value="Hailuo 2.3">Hailuo 2.3</option>
                            <option value="Hailuo 2.3 Fast">Hailuo 2.3 Fast</option>
                            <option value="PixVerse V5.6">PixVerse V5.6</option>
                        </select>
                    </div>

                    {/* Kebab Menu for Settings */}
                    <div
                        className="relative flex-shrink-0"
                        ref={menuRef}
                    >
                        <button
                            className="h-7 w-7 flex items-center justify-center bg-black/60 backdrop-blur-md border border-white/10 rounded-full text-white/90 hover:bg-black/70 transition-colors"
                            onClick={(e) => {
                                e.stopPropagation();
                                setMenuOpen(!menuOpen);
                            }}
                        >
                            <MoreVertical className="w-3.5 h-3.5" />
                        </button>

                        {menuOpen && (
                            <div className="absolute bottom-full right-0 mb-2 w-32 bg-black/80 backdrop-blur-md border border-white/10 rounded-lg p-2 flex flex-col gap-2.5 z-50 shadow-xl pointer-events-auto">
                                <div className="text-[10px] font-medium text-white/50 uppercase tracking-wider px-1">Settings</div>

                                {/* Ratio Dropdown in Menu */}
                                <div className="flex flex-col gap-1.5">
                                    <label className="text-[10px] text-white/70 flex items-center gap-1.5 px-1">
                                        <Square className="w-3 h-3" /> Ratio
                                    </label>
                                    <select
                                        className="bg-black/60 text-white/90 text-[10px] rounded border border-white/10 p-1.5 outline-none cursor-pointer w-full"
                                        value={typeof data.ratio === 'string' ? data.ratio : "16:9"}
                                        onChange={(e) => updateData({ ratio: e.target.value })}
                                        onClick={(e) => e.stopPropagation()}
                                    >
                                        <option value="16:9">16:9</option>
                                        <option value="9:16">9:16</option>
                                        <option value="1:1">1:1</option>
                                    </select>
                                </div>

                                {/* Resolution Dropdown in Menu */}
                                <div className="flex flex-col gap-1.5">
                                    <label className="text-[10px] text-white/70 flex items-center gap-1.5 px-1">
                                        <Monitor className="w-3 h-3" /> Resolution
                                    </label>
                                    <select
                                        className="bg-black/60 text-white/90 text-[10px] rounded border border-white/10 p-1.5 outline-none cursor-pointer w-full"
                                        value={typeof data.resolution === 'string' ? data.resolution : "720p"}
                                        onChange={(e) => updateData({ resolution: e.target.value })}
                                        onClick={(e) => e.stopPropagation()}
                                    >
                                        <option value="720p">720p</option>
                                        <option value="1080p">1080p</option>
                                    </select>
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </NodeWrapper>
    );
});

VideoGenNode.displayName = "VideoGenNode";
