import { memo, useState, useRef, useMemo, useCallback, useEffect, ChangeEvent } from "react";
import { NodeProps, useReactFlow } from "@xyflow/react";
import { Clapperboard, Loader2, Download, Play, Code2, AlertTriangle, X } from "lucide-react";
import { NodeWrapper } from "@/components/workflow/node-wrapper";
import { HighlightedTextarea } from "@/components/workflow/nodes/highlighted-textarea";
import { useWorkflowStore } from "@/lib/workflow-store";
import { useClientRender } from "@/lib/remotion/useClientRender";

export const EditorAgentNode = memo(({ id, selected, data }: NodeProps) => {
    const { deleteElements, updateNodeData } = useReactFlow();
    const { runNode, clearNodeOutput, outputs, runningNodeId } = useWorkflowStore();

    const isRunning = runningNodeId === id;

    // The output from the backend — could be raw TSX or JSON-wrapped scene/compositor
    const rawOutput = (outputs[id] as string | undefined) || (data.output as string | undefined) || null;

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

    // Auto-render when new code arrives — but NOT for scene-only nodes
    const lastRenderedCodeRef = useRef<string | null>(null);
    useEffect(() => {
        if (compositionCode && !isScene && compositionCode !== lastRenderedCodeRef.current && !renderState.isRendering) {
            lastRenderedCodeRef.current = compositionCode;
            renderFromCode(compositionCode);
        }
    }, [compositionCode, isScene, renderState.isRendering, renderFromCode]);

    // Manual re-render
    const handleReRender = useCallback(async () => {
        if (!compositionCode) return;
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
    const hasVideo = !!renderState.blobUrl;
    const isCompiling = renderState.phase === "compiling";
    const isRendering = renderState.phase === "rendering";
    const hasError = renderState.phase === "error";

    return (
        <NodeWrapper
            title={`Editor Agent #${useWorkflowStore((state) =>
                state.nodes
                    .filter(n => n.type === 'editorAgent')
                    .findIndex(n => n.id === id) + 1
            )}${isScene ? ' (Scene)' : isCompositor ? ' (Final)' : ''}`}
            icon={<Clapperboard className="w-4 h-4" />}
            selected={selected}
            inputs={[
                { id: "text", label: "Text", type: "text", style: { bottom: '20px' } },
                { id: "audio", label: "Audio", type: "audio", style: { bottom: '60px' } },
                { id: "ref_images", label: "Ref Images", type: "image", style: { bottom: '100px' } },
                { id: "ref_videos", label: "Ref Videos", type: "video", style: { bottom: '140px' } }
            ]}
            outputs={[{ id: "output", label: "Video", type: "video" }]}
            color="bg-purple-500"
            contentClassName="relative bg-black"
            onDelete={() => deleteElements({ nodes: [{ id }] })}
            onRun={() => runNode(id)}
            onClear={compositionCode ? () => {
                clearNodeOutput(id);
                clearRender();
                lastRenderedCodeRef.current = null;
            } : undefined}
            isRunning={isRunning}
            executionStatus={data.executionStatus as "queued" | "running" | "completed" | "failed" | null}
        >
            <div className="relative bg-muted/30 group/editor transition-all duration-300 ease-in-out overflow-hidden w-[400px]">

                {/* Top Section: Rendered Video */}
                <div className="relative h-[225px] flex items-center justify-center bg-black">
                    {hasVideo ? (
                        <div className="relative w-full h-full">
                            <video
                                src={renderState.blobUrl!}
                                controls
                                className="w-full h-full object-cover"
                                autoPlay
                                loop
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
                            <p className="text-[10px] mt-1 opacity-70">AI writes Remotion code → client-side render</p>
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
                <div className="relative bg-black/20">
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
                        className="w-full min-h-[120px] bg-transparent border-none px-4 py-3 text-sm font-medium placeholder:text-white/50 focus-visible:outline-none resize-none overflow-y-auto leading-relaxed text-white nodrag nowheel"
                        placeholder="Describe the editing task (e.g., stitch videos, add transitions, apply effects)..."
                        value={typeof data.instruction === 'string' ? data.instruction : ''}
                        onChange={handleTextChange}
                        onKeyDown={(e) => e.stopPropagation()}
                    />
                </div>
            </div>
        </NodeWrapper>
    );
});

EditorAgentNode.displayName = "EditorAgentNode";
