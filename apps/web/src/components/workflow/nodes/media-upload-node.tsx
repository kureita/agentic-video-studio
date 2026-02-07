import { memo, useState } from "react";
import { NodeProps, useReactFlow } from "@xyflow/react";
import { Upload, Image as ImageIcon, Video } from "lucide-react";
import { NodeWrapper } from "@/components/workflow/node-wrapper";
import { useWorkflowStore } from "@/lib/workflow-store";

export const MediaUploadNode = memo(({ id, selected, data }: NodeProps) => {
    const { deleteElements } = useReactFlow();
    const { runNode, clearNodeOutput, outputs, runningNodeId } = useWorkflowStore();

    const isRunning = runningNodeId === id;
    const output = (outputs[id] as string | undefined) || (data.output as string | undefined);

    // Determine media type from data or current output
    const mediaType = data.mediaType || (output ? (output.toString().includes('.mp4') || output.toString().includes('video') ? 'video' : 'image') : null);

    // Output handle changes based on media type
    const nodeHandles = [{
        id: "output",
        label: mediaType === 'video' ? 'Video' : mediaType === 'image' ? 'Image' : 'Media',
        type: (mediaType || 'any') as any
    }];

    return (
        <NodeWrapper
            title="Media Upload"
            icon={<Upload className="w-4 h-4" />}
            selected={selected}
            outputs={nodeHandles}
            contentClassName="p-0"
            onDelete={() => deleteElements({ nodes: [{ id }] })}
            onRun={() => runNode(id)}
            onClear={output ? () => clearNodeOutput(id) : undefined}
            isRunning={isRunning}
        >
            <div className="min-h-[200px] flex flex-col">
                {/* Preview Area */}
                {output ? (
                    <div className="relative w-full aspect-video bg-black overflow-hidden">
                        {mediaType === 'video' ? (
                            <video
                                src={output as string}
                                controls
                                className="w-full h-full object-contain"
                            />
                        ) : (
                            <img
                                src={output as string}
                                alt="Uploaded media"
                                className="w-full h-full object-contain"
                            />
                        )}

                        {/* Media Type Badge */}
                        <div className="absolute top-2 left-2 px-2 py-1 rounded-md bg-black/60 backdrop-blur-sm border border-white/10 text-[10px] font-medium text-white shadow-sm flex items-center gap-1">
                            {mediaType === 'video' ? (
                                <>
                                    <Video className="w-3 h-3" />
                                    <span>Video</span>
                                </>
                            ) : (
                                <>
                                    <ImageIcon className="w-3 h-3" />
                                    <span>Image</span>
                                </>
                            )}
                        </div>
                    </div>
                ) : (
                    <div className="h-[200px] flex flex-col items-center justify-center p-4 bg-muted/20 hover:bg-muted/40 transition-colors cursor-pointer group/upload relative overflow-hidden">
                        <div className="absolute inset-0 border-2 border-dashed border-muted-foreground/20 group-hover/upload:border-primary/50 transition-colors m-2 rounded-lg" />

                        <div className="relative z-10 flex flex-col items-center animate-in fade-in zoom-in duration-500">
                            <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-blue-500/20 to-blue-500/5 flex items-center justify-center mb-3 shadow-inner group-hover/upload:scale-110 transition-transform duration-300">
                                <Upload className="w-5 h-5 text-blue-500" />
                            </div>
                            <p className="text-xs font-medium text-foreground mb-1">Upload Image or Video</p>
                            <p className="text-[10px] text-muted-foreground text-center max-w-[160px]">
                                Drag & drop or click to browse
                            </p>
                            <div className="flex items-center gap-2 mt-3">
                                <div className="flex items-center gap-1 px-2 py-1 rounded bg-muted/50 text-[9px] text-muted-foreground">
                                    <ImageIcon className="w-2.5 h-2.5" />
                                    <span>JPG, PNG</span>
                                </div>
                                <div className="flex items-center gap-1 px-2 py-1 rounded bg-muted/50 text-[9px] text-muted-foreground">
                                    <Video className="w-2.5 h-2.5" />
                                    <span>MP4, MOV</span>
                                </div>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </NodeWrapper>
    );
});

MediaUploadNode.displayName = "MediaUploadNode";
