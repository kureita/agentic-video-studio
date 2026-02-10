import { memo, useState, useRef, useMemo, ChangeEvent } from "react";
import { NodeProps, useReactFlow } from "@xyflow/react";
import { Clapperboard, Loader2, Download } from "lucide-react";
import { NodeWrapper } from "@/components/workflow/node-wrapper";
import { useWorkflowStore } from "@/lib/workflow-store";

export const EditorAgentNode = memo(({ id, selected, data }: NodeProps) => {
    const { deleteElements, updateNodeData } = useReactFlow();
    const { runNode, clearNodeOutput, outputs, runningNodeId } = useWorkflowStore();

    const isRunning = runningNodeId === id;
    const output = (outputs[id] as string | undefined) || (data.output as string | undefined);

    const handleDownload = () => {
        if (output) {
            const link = document.createElement('a');
            link.href = output;
            link.download = `edited-video-${Date.now()}.mp4`;
            link.target = '_blank';
            link.click();
        }
    };

    const [showSuggestions, setShowSuggestions] = useState(false);
    const [filterText, setFilterText] = useState("");
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    // Get only connected text nodes for suggestions
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

        // Check for trigger character @
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

    return (
        <NodeWrapper
            title={`Editor Agent #${useWorkflowStore((state) =>
                state.nodes
                    .filter(n => n.type === 'editorAgent')
                    .findIndex(n => n.id === id) + 1
            )}`}
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
            onClear={output ? () => clearNodeOutput(id) : undefined}
            isRunning={isRunning}
        >
            <div className="relative bg-muted/30 group/editor transition-all duration-300 ease-in-out overflow-hidden w-[400px]">

                {/* Top Section: Video Player */}
                <div className="relative h-[225px] flex items-center justify-center">
                    {output && !isRunning ? (
                        <>
                            <video
                                src={output}
                                className="absolute inset-0 w-full h-full object-cover"
                                controls
                                playsInline
                            />

                            {/* Download button */}
                            <button
                                onClick={handleDownload}
                                className="absolute top-3 right-3 w-8 h-8 bg-black/60 backdrop-blur-md border border-white/10 rounded-full flex items-center justify-center text-white/90 hover:bg-black/80 hover:text-white transition-all z-30"
                            >
                                <Download className="w-4 h-4" />
                            </button>
                        </>
                    ) : isRunning ? (
                        <div className="flex flex-col items-center justify-center text-center">
                            <div className="w-12 h-12 rounded-full bg-purple-500/10 flex items-center justify-center mb-3 text-purple-500">
                                <Loader2 className="w-6 h-6 animate-spin" />
                            </div>
                            <p className="text-xs font-medium text-muted-foreground">Editing video...</p>
                        </div>
                    ) : (
                        <div className="flex flex-col items-center justify-center text-center text-muted-foreground/50">
                            <Clapperboard className="w-12 h-12 mb-2" />
                            <p className="text-xs">Edited video will appear here</p>
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
                    <textarea
                        ref={textareaRef}
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
