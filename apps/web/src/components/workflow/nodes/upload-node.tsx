import { memo } from "react";
import { NodeProps, useReactFlow } from "@xyflow/react";
import { Upload, Image as ImageIcon } from "lucide-react";
import { NodeWrapper } from "@/components/workflow/node-wrapper";
import { useWorkflowStore } from "@/lib/workflow-store";

export const UploadNode = memo(({ id, selected, data }: NodeProps) => {
    const { deleteElements } = useReactFlow();

    return (
        <NodeWrapper
            title={`Upload #${useWorkflowStore((state) =>
                state.nodes
                    .filter(n => n.type === 'upload')
                    .findIndex(n => n.id === id) + 1
            )}`}
            icon={<Upload className="w-4 h-4" />}
            selected={selected}
            outputs={[{ id: "media", label: "Media", type: "image" }]}
            contentClassName="p-0"
            onDelete={() => deleteElements({ nodes: [{ id }] })}
        >
            <div className="h-40 flex flex-col items-center justify-center p-4 bg-muted/20 hover:bg-muted/40 transition-colors cursor-pointer group/upload relative overflow-hidden">
                <div className="absolute inset-0 border-2 border-dashed border-muted-foreground/20 group-hover/upload:border-primary/50 transition-colors m-2 rounded-lg" />

                <div className="relative z-10 flex flex-col items-center animate-in fade-in zoom-in duration-500">
                    <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-orange-500/20 to-orange-500/5 flex items-center justify-center mb-3 shadow-inner group-hover/upload:scale-110 transition-transform duration-300">
                        <Upload className="w-5 h-5 text-orange-500" />
                    </div>
                    <p className="text-xs font-medium text-foreground mb-1">Upload Media</p>
                    <p className="text-[10px] text-muted-foreground text-center max-w-[120px]">
                        Drag & drop or click to browse
                    </p>
                </div>
            </div>
        </NodeWrapper>
    );
});

UploadNode.displayName = "UploadNode";
