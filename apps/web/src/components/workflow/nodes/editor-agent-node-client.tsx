import { memo, useState, useRef, useMemo, ChangeEvent, useEffect } from "react";
import { NodeProps, useReactFlow } from "@xyflow/react";
import { Clapperboard, Loader2, Download, Play } from "lucide-react";
import { NodeWrapper } from "@/components/workflow/node-wrapper";
import { HighlightedTextarea } from "@/components/workflow/nodes/highlighted-textarea";
import { useWorkflowStore } from "@/lib/workflow-store";
import { RemotionVideoPlayer } from "@/components/video/RemotionVideoPlayer";
import { getNodeReferenceLabel, getNodeReferenceLabelById } from "@/lib/node-references";

interface VideoClip {
    url: string;
    startTime: number;
    duration: number;
    transition?: "fade" | "slide" | "cut";
}

const normalizeMediaUrl = (url: string): string => {
    if (!url) return url;
    try {
        const parsed = new URL(url);
        if (parsed.searchParams.has("X-Amz-Algorithm")) {
            parsed.search = "";
            return parsed.toString();
        }
    } catch {
        // Keep non-URL values untouched.
    }
    return url;
};

export const EditorAgentNodeClient = memo(({ id, selected, data }: NodeProps) => {
    const { deleteElements, updateNodeData } = useReactFlow();
    const { nodes, edges, runNode, clearNodeOutput, outputs, runningNodeId } = useWorkflowStore();

    const isRunning = runningNodeId === id;
    const [showPreview, setShowPreview] = useState(false);
    const [videoClips, setVideoClips] = useState<VideoClip[]>([]);
    const [audioUrl, setAudioUrl] = useState<string | undefined>();

    // Get connected inputs
    const connectedInputs = useMemo(() => {
        const inputs: { videos: string[]; audio?: string; images: string[] } = {
            videos: [],
            images: [],
        };

        edges.forEach((edge) => {
            if (edge.target === id) {
                const sourceOutput = outputs[edge.source];
                const targetHandle = edge.targetHandle || "";

                if (targetHandle.includes("ref_videos") && sourceOutput) {
                    if (Array.isArray(sourceOutput)) {
                        inputs.videos.push(...sourceOutput.map((value) => normalizeMediaUrl(String(value))));
                    } else if (typeof sourceOutput === "string") {
                        inputs.videos.push(normalizeMediaUrl(sourceOutput));
                    }
                } else if (targetHandle.includes("audio") && sourceOutput) {
                    inputs.audio = normalizeMediaUrl(sourceOutput as string);
                } else if (targetHandle.includes("ref_images") && sourceOutput) {
                    if (Array.isArray(sourceOutput)) {
                        inputs.images.push(...sourceOutput.map((value) => normalizeMediaUrl(String(value))));
                    } else if (typeof sourceOutput === "string") {
                        inputs.images.push(normalizeMediaUrl(sourceOutput));
                    }
                }
            }
        });

        return inputs;
    }, [edges, id, outputs]);

    const connectedInputSignature = useMemo(
        () => JSON.stringify({
            videos: connectedInputs.videos,
            audio: connectedInputs.audio || "",
            images: connectedInputs.images,
        }),
        [connectedInputs]
    );
    const previousInputSignatureRef = useRef<string | null>(null);

    // Update video clips only when effective connected inputs changed
    useEffect(() => {
        if (previousInputSignatureRef.current === connectedInputSignature) {
            return;
        }
        previousInputSignatureRef.current = connectedInputSignature;

        if (connectedInputs.videos.length > 0) {
            const clips: VideoClip[] = connectedInputs.videos.map((url, index) => ({
                url,
                startTime: index * 4, // 4 seconds per clip by default
                duration: 4,
                transition: "fade",
            }));
            setVideoClips(clips);
            setAudioUrl(connectedInputs.audio);
            setShowPreview(true);
        } else {
            setVideoClips([]);
            setShowPreview(false);
        }
    }, [connectedInputSignature, connectedInputs]);

    const [showSuggestions, setShowSuggestions] = useState(false);
    const [filterText, setFilterText] = useState("");
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    const textNodes = useMemo(() =>
        nodes
            .filter(n => n.type === 'text')
            .map((n) => ({ id: n.id, label: getNodeReferenceLabel(n), content: (n.data.text as string) || "" })),
        [nodes]
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

    const handleExport = async () => {
        // TODO: Implement export to file
        // This could call the server-side Remotion renderer for high-quality export
        console.log("Export video", { videoClips, audioUrl });
    };

    return (
        <NodeWrapper
            nodeId={id}
            title={`${useWorkflowStore((state) => getNodeReferenceLabelById(state.nodes, id) || "Editor Agent #?")} (Client)`}
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
            onClear={() => {
                clearNodeOutput(id);
                setShowPreview(false);
            }}
            isRunning={isRunning}
            executionStatus={data.executionStatus as "queued" | "running" | "completed" | "failed" | null}
            executionError={(data.executionError as string | null | undefined) ?? null}
        >
            <div className="relative bg-muted/30 group/editor transition-all duration-300 ease-in-out overflow-hidden w-[400px]">

                {/* Top Section: Video Player */}
                <div className="relative h-[225px] flex items-center justify-center bg-black">
                    {showPreview && videoClips.length > 0 ? (
                        <div className="relative w-full h-full">
                            <RemotionVideoPlayer
                                clips={videoClips}
                                audio={audioUrl}
                                width={1920}
                                height={1080}
                                fps={30}
                                controls
                                className="w-full h-full"
                            />

                            {/* Export button */}
                            <button
                                onClick={handleExport}
                                className="absolute top-3 right-3 w-8 h-8 bg-black/60 backdrop-blur-md border border-white/10 rounded-full flex items-center justify-center text-white/90 hover:bg-black/80 hover:text-white transition-all z-30"
                                title="Export video"
                            >
                                <Download className="w-4 h-4" />
                            </button>
                        </div>
                    ) : isRunning ? (
                        <div className="flex flex-col items-center justify-center text-center">
                            <div className="w-12 h-12 rounded-full bg-purple-500/10 flex items-center justify-center mb-3 text-purple-500">
                                <Loader2 className="w-6 h-6 animate-spin" />
                            </div>
                            <p className="text-xs font-medium text-muted-foreground">Processing...</p>
                        </div>
                    ) : (
                        <div className="flex flex-col items-center justify-center text-center text-muted-foreground/50">
                            <Play className="w-12 h-12 mb-2" />
                            <p className="text-xs">Connect videos to preview</p>
                            <p className="text-[10px] mt-1 opacity-70">Real-time client-side rendering</p>
                        </div>
                    )}
                </div>

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

EditorAgentNodeClient.displayName = "EditorAgentNodeClient";
