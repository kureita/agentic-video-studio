import { memo, useState, useRef, useMemo, ChangeEvent } from "react";
import { NodeProps, useReactFlow } from "@xyflow/react";
import { Eye, Sparkles } from "lucide-react";
import { NodeWrapper } from "@/components/workflow/node-wrapper";
import { useWorkflowStore } from "@/lib/workflow-store";

export const VisionNode = memo(({ id, selected, data }: NodeProps) => {
    const { deleteElements, updateNodeData } = useReactFlow();
    const { runNode, clearNodeOutput, outputs, runningNodeId } = useWorkflowStore();

    const isRunning = runningNodeId === id;
    const output = (outputs[id] as string | undefined) || (data.output as string | undefined);


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
            title={`Vision #${useWorkflowStore((state) =>
                state.nodes
                    .filter(n => n.type === 'vision')
                    .findIndex(n => n.id === id) + 1
            )}`}
            icon={<Eye className="w-4 h-4" />}
            selected={selected}
            inputs={[
                { id: "text", label: "Text", type: "text" },
                { id: "ref_images", label: "Ref Images", type: "image" },
                { id: "ref_videos", label: "Ref Videos", type: "video" }
            ]}
            outputs={[{ id: "output", label: "Output", type: "text" }]}
            color="bg-emerald-500"
            onDelete={() => deleteElements({ nodes: [{ id }] })}
            onRun={() => runNode(id)}
            onClear={output ? () => clearNodeOutput(id) : undefined}
            isRunning={isRunning}
        >
            <div className="flex flex-col h-[280px] w-[320px]">
                {/* Output Area - Read Only (Top 2/3) */}
                <div className="flex-[2] p-3 bg-muted/20 overflow-y-auto overflow-x-hidden">
                    <div className="text-xs text-muted-foreground/70 leading-relaxed whitespace-pre-wrap break-words">
                        {output || "Output will appear here after running..."}
                    </div>
                </div>

                {/* Divider */}
                <div className="h-[2px] bg-border/50" />

                {/* Instruction Area - Editable (Bottom 1/3) */}
                <div className="relative flex-1 flex flex-col">
                    {/* Suggestions Popup */}
                    {showSuggestions && textNodes.length > 0 && (
                        <div className="absolute bottom-12 left-2 z-50 w-48 bg-popover text-popover-foreground rounded-md border shadow-md overflow-hidden animate-in fade-in zoom-in-95 duration-100">
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
                        className="flex-1 w-full rounded-none border-none bg-transparent px-3 py-2 text-sm placeholder:text-muted-foreground/50 focus-visible:outline-none resize-none leading-relaxed overflow-y-auto nowheel"
                        placeholder="Enter your instruction..."
                        value={typeof data.instruction === 'string' ? data.instruction : ''}
                        onChange={handleTextChange}
                        onKeyDown={(e) => e.stopPropagation()}
                    />

                    <div className="flex items-center justify-between px-3 pb-2 pt-1">
                        <div className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-emerald-500/10 border border-emerald-500/20 text-[10px] font-medium text-emerald-600 dark:text-emerald-400">
                            <Sparkles className="w-3 h-3" />
                            <span>Gemini 2.0 Flash</span>
                        </div>
                    </div>
                </div>
            </div>
        </NodeWrapper>
    );
});

VisionNode.displayName = "VisionNode";
