import { memo, useState, useRef, useMemo, ChangeEvent } from "react";
import { NodeProps, useReactFlow } from "@xyflow/react";
import { Clapperboard, Sparkles } from "lucide-react";
import { NodeWrapper } from "@/components/workflow/node-wrapper";
import { useWorkflowStore } from "@/lib/workflow-store";

export const EditorAgentNode = memo(({ id, selected, data }: NodeProps) => {
    const { deleteElements, updateNodeData } = useReactFlow();
    const { runNode, clearNodeOutput, outputs, runningNodeId } = useWorkflowStore();

    const isRunning = runningNodeId === id;
    const output = (outputs[id] as string | undefined) || (data.output as string | undefined);

    const [showSuggestions, setShowSuggestions] = useState(false);
    const [filterText, setFilterText] = useState("");
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    // Get all text nodes for suggestions
    const nodes = useWorkflowStore((state) => state.nodes);
    const textNodes = useMemo(() =>
        nodes
            .filter(n => n.type === 'text')
            .map((n, i) => ({ id: n.id, label: `Text #${i + 1}`, content: (n.data.text as string) || "" })),
        [nodes]
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
            title="Editor Agent"
            icon={<Clapperboard className="w-4 h-4" />}
            selected={selected}
            inputs={[
                { id: "text", label: "Text", type: "text" },
                { id: "ref_images", label: "Ref Images", type: "image" },
                { id: "ref_videos", label: "Ref Videos", type: "video" }
            ]}
            outputs={[{ id: "output", label: "Video", type: "video" }]}
            color="bg-purple-500"
            onDelete={() => deleteElements({ nodes: [{ id }] })}
            onRun={() => runNode(id)}
            onClear={output ? () => clearNodeOutput(id) : undefined}
            isRunning={isRunning}
        >
            <div className="flex flex-col gap-3 p-3">
                {/* Video Preview Area */}
                <div className="w-full aspect-video bg-muted/30 rounded-lg overflow-hidden">
                    {output ? (
                        <video
                            src={output as string}
                            controls
                            className="w-full h-full object-cover"
                        />
                    ) : (
                        <div className="h-full flex flex-col items-center justify-center text-center">
                            <div className="w-12 h-12 rounded-full bg-purple-500/10 flex items-center justify-center mb-3 text-purple-500">
                                <Clapperboard className="w-6 h-6" />
                            </div>
                            <p className="text-xs font-medium text-muted-foreground">Video output will appear here</p>
                        </div>
                    )}
                </div>

                {/* Instruction Area */}
                <div className="relative w-full">
                    {/* Suggestions Popup */}
                    {showSuggestions && textNodes.length > 0 && (
                        <div className="absolute bottom-full left-0 mb-1 z-50 w-48 bg-popover text-popover-foreground rounded-md border shadow-md overflow-hidden animate-in fade-in zoom-in-95 duration-100">
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
                        className="w-full min-h-[80px] rounded-md border border-border/50 bg-muted/20 px-3 py-2 text-sm placeholder:text-muted-foreground/50 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary resize-y overflow-y-auto leading-relaxed nowheel"
                        placeholder="Describe the editing task (e.g., stitch videos, add transitions, apply effects)..."
                        value={typeof data.instruction === 'string' ? data.instruction : ''}
                        onChange={handleTextChange}
                        onKeyDown={(e) => e.stopPropagation()}
                    />
                </div>

                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-purple-500/10 border border-purple-500/20 text-[10px] font-medium text-purple-600 dark:text-purple-400">
                        <Sparkles className="w-3 h-3" />
                        <span>Remotion</span>
                    </div>
                </div>
            </div>
        </NodeWrapper>
    );
});

EditorAgentNode.displayName = "EditorAgentNode";
