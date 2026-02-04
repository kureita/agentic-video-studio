import { memo } from "react";
import { NodeProps, useReactFlow } from "@xyflow/react";
import { Bot, Sparkles } from "lucide-react";
import { NodeWrapper } from "@/components/workflow/node-wrapper";

export const AssistantNode = memo(({ id, selected, data }: NodeProps) => {
    const { deleteElements } = useReactFlow();

    return (
        <NodeWrapper
            title="Assistant"
            icon={<Bot className="w-4 h-4" />}
            selected={selected}
            inputs={[
                { id: "input", label: "Input", type: "text" },
                { id: "context", label: "Context", type: "text" }
            ]}
            outputs={[{ id: "output", label: "Output", type: "text" }]}
            color="bg-emerald-500"
            onDelete={() => deleteElements({ nodes: [{ id }] })}
        >
            <div className="flex flex-col gap-2">
                <textarea
                    className="w-full min-h-[80px] rounded-md border-none bg-transparent px-1 py-1 text-sm placeholder:text-muted-foreground/50 focus-visible:outline-none resize-none leading-relaxed"
                    placeholder="Describe how to modify the content..."
                    defaultValue={typeof data.instruction === 'string' ? data.instruction : ''}
                />

                <div className="flex items-center justify-between pt-2 border-t border-border/10">
                    <div className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-emerald-500/10 border border-emerald-500/20 text-[10px] font-medium text-emerald-600 dark:text-emerald-400">
                        <Sparkles className="w-3 h-3" />
                        <span>Gemini 1.5 Pro</span>
                    </div>
                </div>
            </div>
        </NodeWrapper>
    );
});

AssistantNode.displayName = "AssistantNode";
