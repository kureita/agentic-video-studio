import { memo } from "react";
import { NodeProps } from "@xyflow/react";
import { Maximize, ArrowUpRight } from "lucide-react";
import { NodeWrapper } from "@/components/workflow/node-wrapper";

export const UpscalerNode = memo(({ id, selected, data }: NodeProps) => {
    return (
        <NodeWrapper
            title="Upscaler"
            icon={<Maximize className="w-4 h-4" />}
            selected={selected}
            inputs={[
                { id: "image", label: "Image", type: "image" }
            ]}
            outputs={[{ id: "image", label: "Upscaled", type: "image" }]}
            color="bg-pink-500"
            contentClassName="p-0 overflow-hidden isolate"
        >
            <div className="relative w-full aspect-square bg-muted/30 group/upscaler">
                {data.output ? (
                    <>
                        <img
                            src={data.output as string}
                            alt="Upscaled"
                            className="w-full h-full object-cover transition-transform duration-700 group-hover/upscaler:scale-105"
                        />
                        <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent opacity-0 group-hover/upscaler:opacity-100 transition-opacity duration-300 pointer-events-none" />
                    </>
                ) : (
                    <div className="h-full flex flex-col items-center justify-center p-6 text-center bg-gradient-to-br from-pink-500/5 to-muted/10">
                        <div className="w-12 h-12 rounded-full bg-pink-500/10 flex items-center justify-center mb-3 text-pink-500 animate-pulse">
                            <Maximize className="w-6 h-6" />
                        </div>
                        <p className="text-xs font-medium text-muted-foreground">Waiting for input...</p>
                    </div>
                )}

                {/* Scale Control Overlay */}
                <div className="absolute inset-x-0 bottom-0 p-3 opacity-0 group-hover/upscaler:opacity-100 transition-all duration-300 translate-y-2 group-hover/upscaler:translate-y-0">
                    <div className="flex items-center justify-center gap-1 bg-background/90 backdrop-blur-md p-1 rounded-lg border border-border shadow-lg w-fit mx-auto">
                        <button className="px-3 py-1 rounded text-xs font-medium bg-primary text-primary-foreground shadow-sm">2x</button>
                        <button className="px-3 py-1 rounded text-xs font-medium hover:bg-muted/50 transition-colors">4x</button>
                    </div>
                </div>

                <div className="absolute top-3 right-3 opacity-0 group-hover/upscaler:opacity-100 transition-opacity">
                    <div className="px-2 py-1 rounded-md bg-black/40 backdrop-blur-md border border-white/10 text-[10px] font-medium text-white shadow-sm flex items-center gap-1">
                        <ArrowUpRight className="w-3 h-3" />
                        Upscale
                    </div>
                </div>
            </div>
        </NodeWrapper>
    );
});

UpscalerNode.displayName = "UpscalerNode";
