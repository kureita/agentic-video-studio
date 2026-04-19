import { memo, useRef, useCallback, useEffect } from "react";
import { NodeProps, useReactFlow } from "@xyflow/react";
import { Type } from "lucide-react";
import { NodeWrapper } from "@/components/workflow/node-wrapper";
import { useWorkflowStore } from "@/lib/workflow-store";

export const TextNode = memo(({ id, selected, data }: NodeProps) => {
    const { updateNodeData, deleteElements } = useReactFlow();
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    const savedHeight = typeof data.height === 'number' ? data.height : undefined;

    const handleResize = useCallback(() => {
        const el = textareaRef.current;
        if (!el) return;
        const h = el.offsetHeight;
        if (h > 0 && h !== data.height) {
            updateNodeData(id, { height: h });
        }
    }, [id, data.height, updateNodeData]);

    useEffect(() => {
        const el = textareaRef.current;
        if (!el) return;
        const observer = new ResizeObserver(handleResize);
        observer.observe(el);
        return () => observer.disconnect();
    }, [handleResize]);

    return (
        <NodeWrapper
            nodeId={id}
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
                ref={textareaRef}
                className="w-full min-h-[120px] bg-transparent border-none p-0 text-sm font-medium placeholder:text-muted-foreground/30 focus-visible:outline-none resize-y overflow-y-auto leading-relaxed nowheel nodrag"
                placeholder="Write something..."
                value={typeof data.text === 'string' ? data.text : ''}
                onChange={(evt) => updateNodeData(id, { text: evt.target.value })}
                autoFocus={selected}
                style={savedHeight ? { height: savedHeight } : undefined}
            />
        </NodeWrapper>
    );
});

TextNode.displayName = "TextNode";
