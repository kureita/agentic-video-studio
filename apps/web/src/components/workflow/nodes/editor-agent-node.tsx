import { memo, useState, useRef, useMemo, useCallback, useEffect, ChangeEvent } from "react";
import { NodeProps, useReactFlow } from "@xyflow/react";
import { Clapperboard, Loader2, Download, Play, Code2, AlertTriangle, X, ChevronDown } from "lucide-react";
import { NodeWrapper } from "@/components/workflow/node-wrapper";
import { HighlightedTextarea } from "@/components/workflow/nodes/highlighted-textarea";
import { useWorkflowStore } from "@/lib/workflow-store";
import { useClientRender } from "@/lib/remotion/useClientRender";
import { workflowApi } from "@/lib/workflow-api";
import { canExtractFramesClientSide, extractFrameFromVideo } from "@/lib/video-utils";
import { usePresignedUrl } from "@/lib/use-presigned-url";
import { getNodeReferenceLabel, getNodeReferenceLabelById } from "@/lib/node-references";

/** Check if a string is a *video* URL (NOT audio/image) rather than TSX code.
 * Inspects the path extension before the query string so .mp3/.wav/.m4a/etc.
 * don't get treated as video — otherwise audio outputs would be loaded into
 * a <video crossOrigin="anonymous"> element and trip CORS on signed S3 URLs.
 */
function isVideoUrl(s: string): boolean {
    if (!s) return false;
    const trimmed = s.trim();
    if (!trimmed.startsWith('http') || trimmed.includes('\n')) return false;

    let pathname: string;
    try {
        pathname = new URL(trimmed).pathname.toLowerCase();
    } catch {
        return false;
    }

    const VIDEO_EXTS = ['.mp4', '.webm', '.mov', '.m4v', '.mkv'];
    const AUDIO_EXTS = ['.mp3', '.wav', '.m4a', '.ogg', '.opus', '.flac', '.aac'];
    const IMAGE_EXTS = ['.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp', '.avif'];

    if (VIDEO_EXTS.some((ext) => pathname.endsWith(ext))) return true;
    if (AUDIO_EXTS.some((ext) => pathname.endsWith(ext))) return false;
    if (IMAGE_EXTS.some((ext) => pathname.endsWith(ext))) return false;

    // No recognized extension — only treat as video if the path strongly hints
    // at one (e.g. "/video/" or "generated_video_..."). This is the path that
    // covers legacy outputs without a file extension.
    return pathname.includes('video');
}

/** Cheap, stable fingerprint of TSX so we can compare composition identity across
 * remounts without storing the full code string twice. djb2 hash is enough — we
 * only need equality, not cryptographic strength. */
function fingerprintCode(code: string): string {
    let hash = 5381;
    for (let i = 0; i < code.length; i++) {
        hash = ((hash << 5) + hash + code.charCodeAt(i)) | 0;
    }
    return `${code.length}:${hash >>> 0}`;
}

export const EditorAgentNode = memo(({ id, selected, data }: NodeProps) => {
    const { deleteElements, updateNodeData } = useReactFlow();
    const { runNode, clearNodeOutput, outputs, runningNodeId, uploadRenderedVideo, setRawOutput } = useWorkflowStore();

    const isRunning = runningNodeId === id;
    const workflowId = typeof window !== "undefined" ? new URLSearchParams(window.location.search).get("id") || "" : "";
    const [extractingHandle, setExtractingHandle] = useState<string | null>(null);
    const [extractionError, setExtractionError] = useState<string | null>(null);

    // The output from the backend — could be raw TSX, JSON-wrapped scene/compositor, or a video URL
    const storeOutput = (outputs[id] as string | undefined) || (data.output as string | undefined) || null;
    const rawStoredVideoUrl = (storeOutput && isVideoUrl(storeOutput)) ? storeOutput : null;
    const { url: presignedStoredVideoUrl } = usePresignedUrl(rawStoredVideoUrl);
    const storedVideoUrl = rawStoredVideoUrl ? (presignedStoredVideoUrl || rawStoredVideoUrl) : null;

    // If the output got overwritten with a video URL (from upload-render), ignore it
    // and use the preserved TSX code instead.
    const preservedCodeRef = useRef<string | null>(null);
    const rawOutput = (storeOutput && isVideoUrl(storeOutput))
        ? preservedCodeRef.current   // Fall back to preserved TSX
        : storeOutput;

    // Parse scene/compositor metadata from JSON output
    const parsedOutput = useMemo(() => {
        if (!rawOutput) return null;
        try {
            const parsed = JSON.parse(rawOutput);
            if (parsed.type === 'scene' || parsed.type === 'compositor') {
                return parsed as { type: 'scene' | 'compositor'; code: string; sceneConfig?: { durationFrames: number; label: string } };
            }
        } catch {
            // Not JSON — raw TSX (default/legacy mode)
        }
        return { type: 'default' as const, code: rawOutput };
    }, [rawOutput]);

    const compositionCode = parsedOutput?.code || null;
    const outputMode = parsedOutput?.type || null;
    const isScene = outputMode === 'scene';
    const isCompositor = outputMode === 'compositor';

    // Client-side render hook
    const { state: renderState, renderFromCode, cancel, download, clear: clearRender } = useClientRender();

    // Auto-render & auto-upload guards.
    //
    // Three distinct refs because the lifecycle has multiple boundaries:
    //  - lastRenderedCodeRef: the code we *attempted* to render (set as soon
    //    as renderFromCode is called). Prevents the render effect from
    //    re-firing while the same code is still in-flight or just finished.
    //  - lastUploadedFingerprintRef: fingerprint of the code that's been
    //    successfully uploaded to S3. Persisted via `${id}__rendered_fp` so
    //    it survives remounts. Prevents re-uploading an identical render
    //    and (together with `${id}__rendered_url`) short-circuits the
    //    auto-render effect when the backend echoes back a TSX we've
    //    already turned into an MP4.
    //  - lastUploadedUrlRef: S3 URL of the uploaded MP4 for the above
    //    fingerprint. Used to restore `outputs[id]` when the backend
    //    re-runs and overwrites the URL with the same TSX.
    const lastRenderedCodeRef = useRef<string | null>(null);
    const hasUploadedRef = useRef<boolean>(false);
    const persistedRenderedFp = (outputs[`${id}__rendered_fp`] as string | undefined) || null;
    const persistedRenderedUrl = (outputs[`${id}__rendered_url`] as string | undefined) || null;
    const lastUploadedFingerprintRef = useRef<string | null>(persistedRenderedFp);
    const lastUploadedUrlRef = useRef<string | null>(persistedRenderedUrl);
    // Re-sync the in-memory refs if the persisted values change from
    // elsewhere (e.g. clearNodeOutput resetting the slots).
    useEffect(() => {
        lastUploadedFingerprintRef.current = persistedRenderedFp;
    }, [persistedRenderedFp]);
    useEffect(() => {
        lastUploadedUrlRef.current = persistedRenderedUrl;
    }, [persistedRenderedUrl]);

    const compositionFingerprint = useMemo(
        () => (compositionCode ? fingerprintCode(compositionCode) : null),
        [compositionCode],
    );

    // True when the current composition has already been rendered AND
    // uploaded — possibly in a prior run/session. Detected via fingerprint
    // identity. When this is true the render is "already done" — no
    // auto-render, no auto-upload, and we restore outputs[id] back to the
    // saved URL so the user keeps seeing the existing MP4 instead of an
    // empty player while the backend was overwriting outputs[id] with TSX.
    const alreadyRenderedAndUploaded =
        !!compositionFingerprint &&
        lastUploadedFingerprintRef.current === compositionFingerprint &&
        !!lastUploadedUrlRef.current;

    useEffect(() => {
        if (!compositionCode || isScene) return;
        if (renderState.isRendering) return;
        if (compositionCode === lastRenderedCodeRef.current) return;

        // Backend echoed back a TSX we already rendered & uploaded. Skip
        // the render entirely and restore the previously uploaded URL so
        // the user keeps seeing the same MP4 they already produced.
        if (alreadyRenderedAndUploaded) {
            lastRenderedCodeRef.current = compositionCode;
            preservedCodeRef.current = compositionCode;
            hasUploadedRef.current = true;
            const savedUrl = lastUploadedUrlRef.current;
            if (savedUrl && storeOutput !== savedUrl) {
                setRawOutput(id, savedUrl);
            }
            return;
        }

        lastRenderedCodeRef.current = compositionCode;
        preservedCodeRef.current = compositionCode;
        hasUploadedRef.current = false;
        renderFromCode(compositionCode);
    }, [compositionCode, isScene, renderState.isRendering, renderFromCode, alreadyRenderedAndUploaded, id, setRawOutput, storeOutput]);

    // Automatically upload rendered MP4 to S3 when done — but only once per
    // distinct composition. The persisted fingerprint+URL pair survives
    // remounts so a reload won't re-upload the same render.
    useEffect(() => {
        if (!renderState.blobUrl || renderState.isRendering) return;
        if (isScene) return;
        if (hasUploadedRef.current) return;

        const codeAtUploadTime = preservedCodeRef.current;
        if (!codeAtUploadTime) return;

        const fp = fingerprintCode(codeAtUploadTime);
        if (lastUploadedFingerprintRef.current === fp && lastUploadedUrlRef.current) {
            // We've already uploaded this exact composition; flip the
            // flag and skip. Avoids hammering S3 when the same code is
            // re-rendered (e.g. after a manual cache miss or remount).
            hasUploadedRef.current = true;
            return;
        }

        const upload = async () => {
            hasUploadedRef.current = true;
            try {
                const res = await fetch(renderState.blobUrl!);
                const blob = await res.blob();

                const file = new File([blob], `render_${id}.mp4`, { type: 'video/mp4' });

                // Pass fp through so the backend persists (fp, url) and a
                // future reload sees the existing render is "ours".
                const uploadedUrl = await uploadRenderedVideo(id, file, fp);
                if (uploadedUrl) {
                    lastUploadedFingerprintRef.current = fp;
                    lastUploadedUrlRef.current = uploadedUrl;
                    setRawOutput(id, uploadedUrl);
                    // Mirror in client outputs map so the in-session dedup
                    // (auto-render and auto-upload guards) sees the new fp+url
                    // even before the next workflow load.
                    setRawOutput(`${id}__rendered_fp`, fp);
                    setRawOutput(`${id}__rendered_url`, uploadedUrl);
                }
            } catch (err) {
                console.error("Failed to auto-upload rendered video:", err);
                hasUploadedRef.current = false;
            }
        };
        upload();
    }, [renderState.blobUrl, renderState.isRendering, isScene, id, uploadRenderedVideo, setRawOutput]);

    const handleExtractFrames = useCallback(async (handleId: string) => {
        const sourceVideo = renderState.blobUrl || storedVideoUrl || null;
        if (!sourceVideo || extractingHandle) return;

        setExtractingHandle(handleId);
        setExtractionError(null);

        try {
            if (!canExtractFramesClientSide(sourceVideo)) {
                if (!workflowId) return;
                const response = await workflowApi.extractFrames(workflowId, id, undefined, undefined, sourceVideo);
                const frame = handleId === "start_frame" ? response.data.start_frame : response.data.end_frame;
                if (frame) {
                    setRawOutput(`${id}__${handleId}`, frame);
                }
                return;
            }

            const timeRatio = handleId === "end_frame" ? 1 : 0;
            const frame = await extractFrameFromVideo(sourceVideo, timeRatio);
            const startFramePayload = handleId === "start_frame" ? frame : undefined;
            const endFramePayload = handleId === "end_frame" ? frame : undefined;

            if (workflowId) {
                await workflowApi.extractFrames(workflowId, id, startFramePayload, endFramePayload);
            }

            setRawOutput(`${id}__${handleId}`, frame);
        } catch (err) {
            console.error("[EditorNode] Frame extraction failed:", err);
            setExtractionError(err instanceof Error ? err.message : "Could not extract frame");
        } finally {
            setExtractingHandle(null);
        }
    }, [extractingHandle, id, renderState.blobUrl, setRawOutput, storedVideoUrl, workflowId]);

    const autoExtractionAttemptedRef = useRef<string | null>(null);

    useEffect(() => {
        const sourceVideo = renderState.blobUrl || storedVideoUrl || null;
        if (!sourceVideo || !workflowId) return;

        const hasStartFrame = outputs[`${id}__start_frame`];
        const hasEndFrame = outputs[`${id}__end_frame`];
        if (hasStartFrame && hasEndFrame) return;

        if (autoExtractionAttemptedRef.current === sourceVideo) return;

        if (!canExtractFramesClientSide(sourceVideo)) {
            autoExtractionAttemptedRef.current = sourceVideo;
            void workflowApi.extractFrames(workflowId, id, undefined, undefined, sourceVideo)
                .then((res) => {
                    if (res.data.start_frame) setRawOutput(`${id}__start_frame`, res.data.start_frame);
                    if (res.data.end_frame) setRawOutput(`${id}__end_frame`, res.data.end_frame);
                })
                .catch((err) => {
                    const msg = err instanceof Error ? err.message : "server extraction failed";
                    console.warn("[EditorNode] Auto frame extraction skipped:", msg);
                });
            return;
        }

        const timer = setTimeout(async () => {
            autoExtractionAttemptedRef.current = sourceVideo;
            try {
                let startFramePayload: string | undefined;
                let endFramePayload: string | undefined;

                if (!hasStartFrame) {
                    startFramePayload = await extractFrameFromVideo(sourceVideo, 0);
                    setRawOutput(`${id}__start_frame`, startFramePayload);
                }

                if (!hasEndFrame) {
                    endFramePayload = await extractFrameFromVideo(sourceVideo, 1);
                    setRawOutput(`${id}__end_frame`, endFramePayload);
                }

                if (startFramePayload || endFramePayload) {
                    await workflowApi.extractFrames(workflowId, id, startFramePayload, endFramePayload);
                }
            } catch (err) {
                // Surface as warn (not error) — usually CORS on signed S3 URLs.
                // The per-handle UI shows the user a Retry button.
                const msg = err instanceof Error ? err.message : "frame extraction failed";
                console.warn("[EditorNode] Auto frame extraction skipped:", msg);
            }
        }, 1000);

        return () => clearTimeout(timer);
    }, [workflowId, id, outputs, renderState.blobUrl, setRawOutput, storedVideoUrl]);

    // Manual re-render — explicit user action, so reset the dedup guards and
    // force both a render and a fresh S3 upload of the result.
    const handleReRender = useCallback(async () => {
        if (!compositionCode) return;
        lastRenderedCodeRef.current = compositionCode;
        preservedCodeRef.current = compositionCode;
        lastUploadedFingerprintRef.current = null;
        lastUploadedUrlRef.current = null;
        hasUploadedRef.current = false;
        await renderFromCode(compositionCode);
    }, [compositionCode, renderFromCode]);

    // Show/hide generated code
    const [showCode, setShowCode] = useState(false);

    // Text input / suggestions
    const [showSuggestions, setShowSuggestions] = useState(false);
    const [filterText, setFilterText] = useState("");
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    const nodes = useWorkflowStore((state) => state.nodes);
    const edges = useWorkflowStore((state) => state.edges);
    const connectedTextNodeIds = useMemo(() => new Set(
        edges.filter(e => e.target === id).map(e => e.source)
    ), [edges, id]);
    const allTextNodes = useMemo(() =>
        nodes.filter(n => n.type === 'text').map((n) => ({ id: n.id, label: getNodeReferenceLabel(n), content: (n.data.text as string) || "" })),
        [nodes]
    );
    const textNodes = useMemo(() =>
        allTextNodes.filter(n => connectedTextNodeIds.has(n.id)),
        [allTextNodes, connectedTextNodeIds]
    );

    const handleTextChange = (e: ChangeEvent<HTMLTextAreaElement>) => {
        const val = e.target.value;
        const cursor = e.target.selectionStart;

        updateNodeData(id, { instruction: val });

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
        const val = (typeof data.instruction === 'string' ? data.instruction : '');
        const cursor = textareaRef.current?.selectionStart || val.length;

        const textBeforeCursor = val.slice(0, cursor);
        const lastAt = textBeforeCursor.lastIndexOf('@');

        if (lastAt !== -1) {
            const newVal = val.slice(0, lastAt) + `@${label} ` + val.slice(cursor);
            updateNodeData(id, { instruction: newVal });
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

    // Determine what to show in the video area
    const videoSrc = renderState.blobUrl || storedVideoUrl || null;
    const hasVideo = !!videoSrc;
    const isCompiling = renderState.phase === "compiling";
    const isRendering = renderState.phase === "rendering";
    const hasError = renderState.phase === "error";
    const startFramePreview = (outputs[`${id}__start_frame`] as string | undefined) || undefined;
    const endFramePreview = (outputs[`${id}__end_frame`] as string | undefined) || undefined;

    const ratio = (data.ratio as string) || "16:9";

    const getLayout = (r: string) => {
        const [w, h] = r.split(':').map(Number);

        if (!w || !h || w > h) {
            return { width: 400, videoHeight: 400 * (9 / 16) }; // Default / Landscape (400x225)
        } else if (w === h) {
            return { width: 320, videoHeight: 320 }; // Square (320x320)
        } else {
            // Portrait: minimum width is 300px based on NodeWrapper, scale height accordingly
            return { width: 300, videoHeight: 300 * (h / w) }; // e.g. 9:16 -> 300x533
        }
    };

    const layout = getLayout(ratio);

    return (
        <NodeWrapper
            nodeId={id}
            title={`${useWorkflowStore((state) => getNodeReferenceLabelById(state.nodes, id) || "Editor Agent #?")}${isScene ? ' (Scene)' : isCompositor ? ' (Final)' : ''}`}
            icon={<Clapperboard className="w-4 h-4" />}
            selected={selected}
            inputs={[
                { id: "text", label: "Text", type: "text", style: { bottom: '20px' } },
                { id: "audio", label: "Audio", type: "audio", style: { bottom: '60px' } },
                { id: "ref_images", label: "Ref Images", type: "image", style: { bottom: '100px' } },
                { id: "ref_videos", label: "Ref Videos", type: "video", style: { bottom: '140px' } }
            ]}
            outputs={[
                { id: "output", label: "Video", type: "video" },
                { id: "audio", label: "Embedded Audio", type: "audio" },
                {
                    id: "start_frame", label: "Start Frame", type: "image",
                    framePreview: startFramePreview,
                    hasVideoOutput: hasVideo,
                    onExtractFrames: () => handleExtractFrames("start_frame"),
                    isExtractingFrames: extractingHandle === "start_frame",
                    extractionError: extractionError || undefined,
                },
                {
                    id: "end_frame", label: "End Frame", type: "image",
                    framePreview: endFramePreview,
                    hasVideoOutput: hasVideo,
                    onExtractFrames: () => handleExtractFrames("end_frame"),
                    isExtractingFrames: extractingHandle === "end_frame",
                    extractionError: extractionError || undefined,
                },
            ]}
            color="bg-purple-500"
            contentClassName="relative bg-black"
            onDelete={() => deleteElements({ nodes: [{ id }] })}
            onRun={() => runNode(id)}
            onClear={compositionCode ? () => {
                clearNodeOutput(id);
                clearRender();
                lastRenderedCodeRef.current = null;
                preservedCodeRef.current = null;
                lastUploadedFingerprintRef.current = null;
                lastUploadedUrlRef.current = null;
                hasUploadedRef.current = false;
            } : undefined}
            isRunning={isRunning}
            executionStatus={data.executionStatus as "queued" | "running" | "completed" | "failed" | null}
            executionError={(data.executionError as string | null | undefined) ?? null}
        >
            <div
                className="relative bg-muted/30 group/editor transition-all duration-300 ease-in-out overflow-hidden"
                style={{
                    width: layout.width
                }}
            >

                {/* Top Section: Rendered Video */}
                <div
                    className="relative flex items-center justify-center bg-transparent"
                    style={{
                        height: layout.videoHeight
                    }}
                >
                    {hasVideo ? (
                        <div className="relative w-full h-full">
                            <video
                                src={videoSrc!}
                                className="w-full h-full object-cover select-none nodrag nopan nowheel"
                                controls
                                preload="metadata"
                                playsInline
                                crossOrigin="anonymous"
                                onPointerDown={(e) => e.stopPropagation()}
                                onMouseDown={(e) => e.stopPropagation()}
                                onClick={(e) => e.stopPropagation()}
                                onDoubleClick={(e) => e.stopPropagation()}
                            />

                            {/* Action buttons overlay */}
                            <div className="absolute top-3 right-3 flex gap-1.5 z-30">
                                {/* Show code button */}
                                <button
                                    onClick={() => setShowCode(!showCode)}
                                    className={`w-7 h-7 backdrop-blur-md border border-white/10 rounded-full flex items-center justify-center text-white/80 hover:text-white transition-all ${showCode ? 'bg-purple-600/80' : 'bg-black/60 hover:bg-black/80'}`}
                                    title="View generated code"
                                >
                                    <Code2 className="w-3.5 h-3.5" />
                                </button>

                                {/* Re-render button */}
                                <button
                                    onClick={handleReRender}
                                    className="w-7 h-7 bg-black/60 backdrop-blur-md border border-white/10 rounded-full flex items-center justify-center text-white/80 hover:bg-black/80 hover:text-white transition-all"
                                    title="Re-render"
                                >
                                    <Play className="w-3.5 h-3.5" />
                                </button>

                                {/* Download button */}
                                <button
                                    onClick={() => download()}
                                    className="w-7 h-7 bg-green-600/80 backdrop-blur-md border border-white/10 rounded-full flex items-center justify-center text-white hover:bg-green-600 transition-all"
                                    title="Download MP4"
                                >
                                    <Download className="w-3.5 h-3.5" />
                                </button>
                            </div>
                        </div>
                    ) : isScene && compositionCode ? (
                        /* Scene preview — no render, just show code info */
                        <div className="flex flex-col items-center justify-center text-center">
                            <div className="w-12 h-12 rounded-full bg-purple-500/10 flex items-center justify-center mb-3">
                                <Code2 className="w-6 h-6 text-purple-500" />
                            </div>
                            <p className="text-xs font-medium text-muted-foreground">Scene Component Ready</p>
                            <p className="text-[10px] text-muted-foreground/60 mt-1">
                                {parsedOutput?.type === 'scene' && parsedOutput.sceneConfig
                                    ? `${parsedOutput.sceneConfig.label} · ${Math.round((parsedOutput.sceneConfig.durationFrames || 90) / 30)}s`
                                    : 'Connect to a compositor to render'
                                }
                            </p>
                            <button
                                onClick={() => setShowCode(!showCode)}
                                className="mt-2 px-3 py-1 text-[10px] bg-white/10 rounded-full text-white/80 hover:bg-white/20 transition-colors"
                            >
                                {showCode ? 'Hide Code' : 'View Code'}
                            </button>
                        </div>
                    ) : (isCompiling || isRendering) ? (
                        <div className="flex flex-col items-center justify-center text-center">
                            <div className="w-12 h-12 rounded-full bg-purple-500/10 flex items-center justify-center mb-3 text-purple-500">
                                <Loader2 className="w-6 h-6 animate-spin" />
                            </div>
                            <p className="text-xs font-medium text-muted-foreground">
                                {isCompiling ? "Compiling composition..." : `Rendering... ${renderState.progress}%`}
                            </p>
                            {isRendering && (
                                <>
                                    <div className="w-48 h-1.5 bg-white/10 rounded-full mt-2 overflow-hidden">
                                        <div
                                            className="h-full bg-purple-500 rounded-full transition-all duration-300"
                                            style={{ width: `${renderState.progress}%` }}
                                        />
                                    </div>
                                    <button
                                        onClick={cancel}
                                        className="mt-2 text-[10px] text-red-400 hover:text-red-300 transition-colors"
                                    >
                                        Cancel
                                    </button>
                                </>
                            )}
                        </div>
                    ) : isRunning ? (
                        <div className="flex flex-col items-center justify-center text-center">
                            <div className="w-12 h-12 rounded-full bg-purple-500/10 flex items-center justify-center mb-3 text-purple-500">
                                <Loader2 className="w-6 h-6 animate-spin" />
                            </div>
                            <p className="text-xs font-medium text-muted-foreground">AI is writing composition code...</p>
                        </div>
                    ) : hasError ? (
                        <div className="flex flex-col items-center justify-center text-center px-4">
                            <AlertTriangle className="w-8 h-8 text-red-400 mb-2" />
                            <p className="text-xs text-red-400 font-medium">Render Error</p>
                            <p className="text-[10px] text-red-400/70 mt-1 max-w-[300px] break-words">
                                {renderState.error}
                            </p>
                            {compositionCode && (
                                <button
                                    onClick={handleReRender}
                                    className="mt-3 px-3 py-1 text-[10px] bg-white/10 rounded-full text-white/80 hover:bg-white/20 transition-colors"
                                >
                                    Retry
                                </button>
                            )}
                        </div>
                    ) : (
                        <div className="flex flex-col items-center justify-center text-center text-muted-foreground/50">
                            <Clapperboard className="w-12 h-12 mb-2" />
                            <p className="text-xs">Rendered video will appear here</p>
                            <p className="text-[10px] mt-1 opacity-70">Client-Side Rendering. Keep the Browser Focused.</p>
                        </div>
                    )}

                    {/* Render warning */}
                    {isRendering && (
                        <div className="absolute bottom-0 left-0 right-0 bg-amber-500/90 text-black px-3 py-1.5 text-[10px] font-medium flex items-center gap-1.5">
                            <AlertTriangle className="w-3 h-3" />
                            Keep this tab focused while rendering
                        </div>
                    )}
                </div>

                {/* Code viewer (collapsible) */}
                {showCode && compositionCode && (
                    <div className="relative bg-zinc-900 border-t border-white/10">
                        <div className="flex items-center justify-between px-3 py-1.5 bg-zinc-800/80">
                            <span className="text-[10px] text-white/50 font-mono">Generated Remotion TSX</span>
                            <button onClick={() => setShowCode(false)} className="text-white/40 hover:text-white/70">
                                <X className="w-3 h-3" />
                            </button>
                        </div>
                        <pre className="text-[10px] text-green-300/80 font-mono px-3 py-2 overflow-auto max-h-[160px] leading-relaxed nodrag nowheel">
                            {compositionCode}
                        </pre>
                    </div>
                )}

                {/* Divider Line */}
                <div className="h-px bg-gradient-to-r from-transparent via-white/20 to-transparent" />

                {/* Bottom Section: Text Input */}
                <div className="relative bg-transparent">
                    {/* Suggestions Popup */}
                    {showSuggestions && textNodes.length > 0 && (
                        <div className="absolute bottom-full left-4 mb-2 z-50 w-48 bg-popover text-popover-foreground rounded-md border shadow-md overflow-hidden animate-in fade-in zoom-in-95 duration-100">
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
                            </div>
                        </div>
                    )}

                    {/* Text Input */}
                    <HighlightedTextarea
                        textareaRef={textareaRef}
                        className="w-full min-h-[120px] bg-transparent border-none px-4 py-3 pb-8 text-sm font-medium placeholder:text-white/50 focus-visible:outline-none resize-none overflow-y-auto leading-relaxed text-white nodrag nowheel"
                        placeholder="Describe the editing task (e.g., stitch videos, add transitions, apply effects)..."
                        value={typeof data.instruction === 'string' ? data.instruction : ''}
                        onChange={handleTextChange}
                        onKeyDown={(e) => e.stopPropagation()}
                    />

                    {/* Controls Bar */}
                    <div className="absolute bottom-2 right-2 flex items-center gap-1 opacity-100 transition-all duration-300 z-20">
                        {/* Ratio Pill */}
                        <div className="relative h-6 flex items-center gap-1.5 bg-black/60 backdrop-blur-md border border-white/10 rounded-full px-2 text-white/90 hover:bg-black/70 transition-colors flex-shrink-0">
                            <span className="text-[10px] font-medium">{typeof data.ratio === 'string' ? data.ratio : "16:9"}</span>
                            <ChevronDown className="w-2.5 h-2.5 text-white/50 flex-shrink-0" />
                            <select
                                className="absolute inset-0 opacity-0 cursor-pointer"
                                value={typeof data.ratio === 'string' ? data.ratio : "16:9"}
                                onChange={(e) => updateNodeData(id, { ratio: e.target.value })}
                            >
                                <option value="16:9">16:9</option>
                                <option value="9:16">9:16</option>
                                <option value="1:1">1:1</option>
                            </select>
                        </div>
                    </div>
                </div>
            </div>
        </NodeWrapper>
    );
});

EditorAgentNode.displayName = "EditorAgentNode";
