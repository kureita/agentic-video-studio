import { memo, useState, useRef, useMemo, ChangeEvent, useCallback, useEffect } from "react";
import { NodeProps, useReactFlow } from "@xyflow/react";
import { Video, Clock, ChevronDown, Square, Loader2, Download, Monitor, MoreVertical } from "lucide-react";
import { NodeWrapper } from "@/components/workflow/node-wrapper";
import { HighlightedTextarea } from "@/components/workflow/nodes/highlighted-textarea";
import { usePresignedUrl } from "@/lib/use-presigned-url";
import { workflowApi } from "@/lib/workflow-api";
import { useWorkflowStore } from "@/lib/workflow-store";
import { useModels } from "@/lib/use-models";
import { toast } from "sonner";
import { extractFrameFromVideo } from "@/lib/video-utils";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";

const DEFAULT_INPUTS: { id: string, label: string, type: "text" | "image" | "video" | "audio" }[] = [
    { id: "text", label: "Text/Prompt", type: "text" },
    { id: "start_image", label: "Start Image", type: "image" },
    { id: "end_image", label: "End Image", type: "image" }
];

const getCapabilitiesLabel = (capabilities: string[] = []) => {
    const hasT2V = !!capabilities.find(c => c.toLowerCase() === "t2v");
    const hasI2V = !!capabilities.find(c => c.toLowerCase() === "i2v");
    const hasAudio = !!capabilities.find(c => c.toLowerCase() === "audio");

    let label = "";
    if (hasT2V && hasI2V) label = "Text to Video & Image to Video";
    else if (hasI2V) label = "Image to Video";
    else if (hasT2V) label = "Text to Video";

    if (hasAudio) {
        label += label ? " + Audio" : "Audio Generation";
    }

    return label;
};

export const VideoGenNode = memo(({ id, selected, data }: NodeProps) => {
    const { deleteElements, updateNodeData } = useReactFlow();
    const { nodes, setNodes, runNode, clearNodeOutput, outputs, runningNodeId, setRawOutput } = useWorkflowStore();

    const { models } = useModels();
    const videoModels = models.filter(m => m.type === "video");

    // Derive workflowId from the URL query param: /dashboard/workflow?id=<workflowId>
    const workflowId = useMemo(() => new URLSearchParams(window.location.search).get('id') || '', []);

    const [extractingHandle, setExtractingHandle] = useState<string | null>(null);
    const [extractionError, setExtractionError] = useState<string | null>(null);
    const [menuOpen, setMenuOpen] = useState(false);
    const menuRef = useRef<HTMLDivElement>(null);

    const [showModelMenu, setShowModelMenu] = useState(false);
    const [showDurationMenu, setShowDurationMenu] = useState(false);
    const modelMenuRef = useRef<HTMLDivElement>(null);
    const durationMenuRef = useRef<HTMLDivElement>(null);

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
        };
        if (menuOpen || showModelMenu || showDurationMenu) {
            document.addEventListener("mousedown", handleClickOutside);
        }
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, [menuOpen, showModelMenu, showDurationMenu]);

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

    const currentModel = (typeof data.model === 'string' ? data.model : (videoModels.length > 0 ? videoModels[0].name : "Google Veo 3.1"));
    const configInputs = DEFAULT_INPUTS;

    const selectedModelData = videoModels.find(m => m.name === currentModel);
    let validDurations = ["5s", "8s", "10s"];
    let validResolutions = ["720p", "1080p"];
    if (selectedModelData && selectedModelData.configs) {
        const d = Array.from(new Set(selectedModelData.configs.map(c => c.duration ? `${c.duration}s` : null).filter(Boolean)));
        if (d.length > 0) validDurations = d as string[];

        const r = Array.from(new Set(selectedModelData.configs.map(c => c.resolution).filter(Boolean)));
        if (r.length > 0) validResolutions = r as string[];
    }

    const effectiveDuration = validDurations.includes(typeof data.duration === 'string' ? data.duration : "")
        ? (data.duration as string || validDurations[0])
        : validDurations[0];

    const effectiveResolution = validResolutions.includes(typeof data.resolution === 'string' ? data.resolution : "")
        ? (data.resolution as string || validResolutions[0])
        : validResolutions[0];

    const handleModelChange = (newModel: string) => {
        const newModelData = videoModels.find(m => m.name === newModel);
        let newValidDurations = ["5s", "8s", "10s"];
        let newValidResolutions = ["720p", "1080p"];

        if (newModelData && newModelData.configs) {
            const d = Array.from(new Set(newModelData.configs.map(c => c.duration ? `${c.duration}s` : null).filter(Boolean)));
            if (d.length > 0) newValidDurations = d as string[];

            const r = Array.from(new Set(newModelData.configs.map(c => c.resolution).filter(Boolean)));
            if (r.length > 0) newValidResolutions = r as string[];
        }

        const currentDur = data.duration as string || "4s";
        let newDuration = currentDur;
        if (!newValidDurations.includes(currentDur)) {
            newDuration = newValidDurations[0];
        }

        const currentRes = data.resolution as string || "720p";
        let newResolution = currentRes;
        if (!newValidResolutions.includes(currentRes)) {
            newResolution = newValidResolutions[0];
        }

        updateData({ model: newModel, duration: newDuration, resolution: newResolution });
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
                    <div className="relative flex-shrink-0" ref={durationMenuRef}>
                        <button
                            onClick={() => {
                                setShowDurationMenu(!showDurationMenu);
                                setShowModelMenu(false);
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
                                    <div className="flex flex-col p-1 nodrag nowheel">
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
                                setMenuOpen(false);
                            }}
                            className={cn(
                                "flex items-center gap-1.5 h-7 w-full bg-black/60 backdrop-blur-md border border-white/10 rounded-full px-2 text-white/90 hover:bg-black/70 transition-colors cursor-pointer",
                                showModelMenu && "bg-black/80 border-white/20"
                            )}
                        >
                            <span className="text-[10px] font-medium truncate flex-grow text-left">{currentModel}</span>
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
                                    <div className="max-h-[160px] overflow-y-auto flex flex-col p-1 nodrag nowheel">
                                        {videoModels.map(m => (
                                            <button
                                                key={m.id}
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    handleModelChange(m.name);
                                                    setShowModelMenu(false);
                                                }}
                                                className={cn(
                                                    "w-full text-left px-2.5 py-1.5 rounded-lg hover:bg-white/10 cursor-pointer flex items-center justify-between transition-colors",
                                                    currentModel === m.name && "bg-white/15 text-white"
                                                )}
                                            >
                                                <div className="flex flex-col gap-0.5">
                                                    <span className={cn("text-[11px] font-medium", currentModel !== m.name && "text-white/80")}>
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
                                    className="absolute bottom-full right-0 mb-2 w-40 bg-black/90 backdrop-blur-xl border border-white/10 rounded-xl shadow-2xl overflow-hidden z-50 pointer-events-auto flex flex-col p-2 gap-3"
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
                                                        updateData({ resolution: r });
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
