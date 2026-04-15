import { memo, useEffect, useMemo, useRef, useState, ChangeEvent } from "react";
import { Node as FlowNode, NodeProps, useReactFlow } from "@xyflow/react";
import { Eye } from "lucide-react";
import { NodeWrapper } from "@/components/workflow/node-wrapper";
import { useWorkflowStore } from "@/lib/workflow-store";

type AssistantNodeData = {
    output?: string;
    instruction?: string;
    model?: string;
    executionStatus?: "queued" | "running" | "completed" | "failed" | null;
};

type AssistantNodeType = FlowNode<AssistantNodeData>;
const FIXED_MODEL = "Gemini 3.1 Pro Preview (High)";

export const AssistantNode = memo(({ id, selected, data }: NodeProps<AssistantNodeType>) => {
    const { deleteElements, updateNodeData } = useReactFlow();
    const { runNode, clearNodeOutput, outputs, runningNodeId } = useWorkflowStore();

    const [showSuggestions, setShowSuggestions] = useState(false);
    const [filterText, setFilterText] = useState("");
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    const isRunning = runningNodeId === id;
    const output = (outputs[id] as string | undefined) || data.output || "";

    const nodes = useWorkflowStore((state) => state.nodes);
    const textNodes = useMemo(() =>
        nodes
            .filter((node) => node.type === "text")
            .map((node, index) => ({ id: node.id, label: `Text #${index + 1}`, content: (node.data.text as string) || "" })),
        [nodes]
    );

    useEffect(() => {
        if (data.model !== FIXED_MODEL) {
            updateNodeData(id, { model: FIXED_MODEL });
        }
    }, [data.model, id, updateNodeData]);

    const handleTextChange = (e: ChangeEvent<HTMLTextAreaElement>) => {
        const val = e.target.value;
        const cursor = e.target.selectionStart;

        updateNodeData(id, { instruction: val });

        const textBeforeCursor = val.slice(0, cursor);
        const lastAt = textBeforeCursor.lastIndexOf("@");

        if (lastAt !== -1) {
            const textAfterAt = textBeforeCursor.slice(lastAt + 1);
            if (!textAfterAt.includes("\n") && !textAfterAt.includes(" ") && textAfterAt.length < 20) {
                setShowSuggestions(true);
                setFilterText(textAfterAt.toLowerCase());
                return;
            }
        }
        setShowSuggestions(false);
    };

    const insertSuggestion = (label: string) => {
        const val = typeof data.instruction === "string" ? data.instruction : "";
        const cursor = textareaRef.current?.selectionStart || val.length;
        const textBeforeCursor = val.slice(0, cursor);
        const lastAt = textBeforeCursor.lastIndexOf("@");

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
            title={`Media Assistant #${useWorkflowStore((state) =>
                state.nodes
                    .filter((node) => node.type === "assistant" || node.type === "vision")
                    .findIndex((node) => node.id === id) + 1
            )}`}
            icon={<Eye className="w-4 h-4" />}
            selected={selected}
            inputs={[
                { id: "text", label: "Text", type: "text" },
                { id: "ref_images", label: "Images", type: "image" },
                { id: "ref_videos", label: "Videos", type: "video" },
                { id: "audio", label: "Audio", type: "audio" },
            ]}
            outputs={[{ id: "output", label: "Analysis", type: "text" }]}
            contentClassName="p-0 overflow-hidden rounded-[17px]"
            onDelete={() => deleteElements({ nodes: [{ id }] })}
            onRun={() => runNode(id)}
            onClear={output ? () => clearNodeOutput(id) : undefined}
            isRunning={isRunning}
            executionStatus={data.executionStatus || null}
        >
            <div className="flex w-[340px] flex-col">
                {/* Output / Results Area */}
                <div className="relative min-h-[200px] max-h-[260px] overflow-y-auto px-4 py-4 [scrollbar-width:thin] [scrollbar-color:rgba(255,255,255,0.08)_transparent]">
                    {output ? (
                        <div className="text-[12.5px] leading-[1.75] text-foreground/80 whitespace-pre-wrap font-[system-ui] selection:bg-foreground/10">
                            {output}
                        </div>
                    ) : (
                        <div className="flex items-center justify-center h-[180px]">
                            <p className="text-[12px] text-muted-foreground/40">No analysis yet</p>
                        </div>
                    )}
                </div>

                {/* Divider */}
                <div className="h-[1px] mx-3 bg-border/40" />

                {/* Input Area — chat-style */}
                <div className="relative px-3 pt-3 pb-2">
                    {/* Suggestions Popup */}
                    {showSuggestions && textNodes.length > 0 && (
                        <div className="absolute bottom-full left-2 right-2 mb-1.5 z-50 overflow-hidden rounded-xl border border-border/60 bg-popover/95 backdrop-blur-xl shadow-2xl">
                            <div className="px-2.5 py-1.5 text-[9px] font-semibold text-muted-foreground/60 uppercase tracking-wider border-b border-border/30">
                                Suggested Inputs
                            </div>
                            <div className="max-h-[120px] overflow-y-auto p-1">
                                {textNodes
                                    .filter((node) => node.label.toLowerCase().includes(filterText) || node.content.toLowerCase().includes(filterText))
                                    .map((node) => (
                                        <button
                                            key={node.id}
                                            className="flex w-full items-center justify-between rounded-lg px-2.5 py-1.5 text-left text-[11px] text-foreground/80 transition-colors hover:bg-muted/60 cursor-pointer"
                                            onClick={() => insertSuggestion(node.label)}
                                        >
                                            <span className="font-medium text-foreground/70">{node.label}</span>
                                            <span className="max-w-[110px] truncate text-[10px] text-muted-foreground/40">
                                                {node.content.slice(0, 28)}
                                            </span>
                                        </button>
                                    ))}
                            </div>
                        </div>
                    )}

                    <textarea
                        ref={textareaRef}
                        rows={2}
                        className="w-full resize-none bg-transparent px-1 py-1 text-[12px] leading-relaxed text-foreground/80 placeholder:text-muted-foreground/30 focus:outline-none transition-colors duration-150 nodrag nowheel"
                        placeholder="Ask about connected media..."
                        value={typeof data.instruction === "string" ? data.instruction : ""}
                        onChange={handleTextChange}
                        onKeyDown={(e) => e.stopPropagation()}
                    />

                    {/* Model tag — bottom right, subtle */}
                    <div className="flex justify-end pb-0.5">
                        <span className="text-[9.5px] text-muted-foreground/35 font-medium tracking-wide">
                            {FIXED_MODEL}
                        </span>
                    </div>
                </div>
            </div>
        </NodeWrapper>
    );
});

AssistantNode.displayName = "AssistantNode";
