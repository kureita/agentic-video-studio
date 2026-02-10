import { memo } from "react";
import { NodeProps, useReactFlow } from "@xyflow/react";
import { Type } from "lucide-react";
import { NodeWrapper } from "@/components/workflow/node-wrapper";
import { useWorkflowStore } from "@/lib/workflow-store";

export const TextNode = memo(({ id, selected, data }: NodeProps) => {
    const { updateNodeData, deleteElements } = useReactFlow();

    return (
        <NodeWrapper
            title={`Text #${useWorkflowStore((state) =>
                state.nodes
                    .filter(n => n.type === 'text')
                    .findIndex(n => n.id === id) + 1
            )}`}
            icon={<Type className="w-4 h-4" />}
            selected={selected}
            contentClassName="p-4"
            outputs={[{ id: "text", label: "Text", type: "text" }]}
            color="bg-blue-500"
            onDelete={() => deleteElements({ nodes: [{ id }] })}
        >
            <textarea
                className="w-full min-h-[120px] bg-transparent border-none p-0 text-sm font-medium placeholder:text-muted-foreground/30 focus-visible:outline-none resize-y overflow-y-auto leading-relaxed nowheel"
                placeholder="Write something..."
                value={typeof data.text === 'string' ? data.text : ''}
                onChange={(evt) => updateNodeData(id, { text: evt.target.value })}
                autoFocus={selected}
            />
        </NodeWrapper>
    );
});

TextNode.displayName = "TextNode";
