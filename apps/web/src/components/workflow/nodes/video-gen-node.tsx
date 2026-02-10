import { memo, useState, useRef, useMemo, ChangeEvent } from "react";
import { NodeProps, useReactFlow } from "@xyflow/react";
import { Video, Clock, ChevronDown, Square, Loader2, Download, Monitor } from "lucide-react";
import { NodeWrapper } from "@/components/workflow/node-wrapper";

import { useWorkflowStore } from "@/lib/workflow-store";

export const VideoGenNode = memo(({ id, selected, data }: NodeProps) => {
    const { deleteElements, updateNodeData } = useReactFlow();
    const { nodes, setNodes, runNode, clearNodeOutput, outputs, runningNodeId } = useWorkflowStore();

    // Sync node data to workflow store
    const updateData = (updates: Record<string, unknown>) => {
        updateNodeData(id, updates);
        setNodes(
            nodes.map((n) =>
                n.id === id ? { ...n, data: { ...n.data, ...updates } } : n
            )
        );
    };

    const isRunning = runningNodeId === id;
    const output = (outputs[id] as string | undefined) || (data.output as string | undefined);

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

    return (
        <NodeWrapper
            title={`Video Generator #${useWorkflowStore((state) =>
                state.nodes
                    .filter(n => n.type === 'videoGen')
                    .findIndex(n => n.id === id) + 1
            )}`}
            icon={<Video className="w-4 h-4" />}
            selected={selected}
            inputs={[
                { id: "text", label: "Text/Prompt", type: "text" },
                { id: "start_image", label: "Start Image", type: "image" },
                { id: "end_image", label: "End Image", type: "image" },
                { id: "reference_images", label: "Ref Images", type: "image" },
                { id: "reference_video", label: "Ref Video", type: "video" }
            ]}
            outputs={[{ id: "video", label: "Video", type: "video" }]}
            contentClassName="p-0 overflow-hidden isolate"
            onDelete={() => deleteElements({ nodes: [{ id }] })}
            onRun={() => runNode(id)}
            onClear={output ? () => clearNodeOutput(id) : undefined}
            isRunning={isRunning}
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

                    <textarea
                        ref={textareaRef}
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
                    <div className="relative h-7 flex items-center gap-1.5 bg-black/60 backdrop-blur-md border border-white/10 rounded-full px-2 text-white/90 hover:bg-black/70 transition-colors">
                        <Clock className="w-2.5 h-2.5 text-white/70 flex-shrink-0" />
                        <span className="text-[10px] font-medium truncate">{typeof data.duration === 'string' ? data.duration : "4s"}</span>
                        <ChevronDown className="w-2.5 h-2.5 text-white/50 flex-shrink-0" />
                        <select
                            className="absolute inset-0 opacity-0 cursor-pointer"
                            value={typeof data.duration === 'string' ? data.duration : "4s"}
                            onChange={(e) => updateData({ duration: e.target.value })}
                        >
                            <option value="4s">4s</option>
                            <option value="6s">6s</option>
                            <option value="8s">8s</option>
                        </select>
                    </div>

                    {/* Model Pill */}
                    <div className="relative h-7 flex items-center gap-1.5 bg-black/60 backdrop-blur-md border border-white/10 rounded-full px-2 text-white/90 hover:bg-black/70 transition-colors min-w-0 flex-grow max-w-[100px]">
                        <span className="text-[10px] font-medium truncate">{typeof data.model === 'string' ? data.model : "Google Veo"}</span>
                        <ChevronDown className="w-2.5 h-2.5 text-white/50 flex-shrink-0" />
                        <select
                            className="absolute inset-0 opacity-0 cursor-pointer"
                            value={typeof data.model === 'string' ? data.model : "Veo 3.1"}
                            onChange={(e) => updateData({ model: e.target.value })}
                        >
                            <option value="Veo 3.1">Veo 3.1</option>
                            <option value="Veo 3.1 Fast">Veo 3.1 Fast</option>
                        </select>
                    </div>

                    {/* Ratio Pill */}
                    <div className="relative h-7 flex items-center gap-1.5 bg-black/60 backdrop-blur-md border border-white/10 rounded-full px-2 text-white/90 hover:bg-black/70 transition-colors flex-shrink-0">
                        <Square className="w-2.5 h-2.5 text-white/70 flex-shrink-0" />
                        <span className="text-[10px] font-medium">{typeof data.ratio === 'string' ? data.ratio : "16:9"}</span>
                        <ChevronDown className="w-2.5 h-2.5 text-white/50 flex-shrink-0" />
                        <select
                            className="absolute inset-0 opacity-0 cursor-pointer"
                            value={typeof data.ratio === 'string' ? data.ratio : "16:9"}
                            onChange={(e) => updateData({ ratio: e.target.value })}
                        >
                            <option value="16:9">16:9</option>
                            <option value="9:16">9:16</option>
                            <option value="1:1">1:1</option>
                        </select>
                    </div>

                    {/* Resolution Pill */}
                    <div className="relative h-7 flex items-center gap-1.5 bg-black/60 backdrop-blur-md border border-white/10 rounded-full px-2 text-white/90 hover:bg-black/70 transition-colors flex-shrink-0">
                        <Monitor className="w-2.5 h-2.5 text-white/70 flex-shrink-0" />
                        <span className="text-[10px] font-medium">{typeof data.resolution === 'string' ? data.resolution : "720p"}</span>
                        <ChevronDown className="w-2.5 h-2.5 text-white/50 flex-shrink-0" />
                        <select
                            className="absolute inset-0 opacity-0 cursor-pointer"
                            value={typeof data.resolution === 'string' ? data.resolution : "720p"}
                            onChange={(e) => updateData({ resolution: e.target.value })}
                        >
                            <option value="720p">720p</option>
                            <option value="1080p">1080p</option>
                        </select>
                    </div>
                </div>
            </div>
        </NodeWrapper>
    );
});

VideoGenNode.displayName = "VideoGenNode";
