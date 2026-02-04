import { memo } from "react";
import { NodeProps, useReactFlow } from "@xyflow/react";
import { Image as ImageIcon, Sparkles, Minus, Plus, ChevronDown, Square, Loader2, Download } from "lucide-react";
import { NodeWrapper } from "@/components/workflow/node-wrapper";

export const ImageGenNode = memo(({ id, selected, data }: NodeProps) => {
    const { deleteElements, updateNodeData } = useReactFlow();

    const isRunning = data.isRunning as boolean;
    const onRun = data.onRun as (() => void) | undefined;
    const output = data.output as string | undefined;

    const handleDownload = () => {
        if (output) {
            const link = document.createElement('a');
            link.href = output;
            link.download = `generated-image-${Date.now()}.png`;
            link.target = '_blank';
            link.click();
        }
    };

    return (
        <NodeWrapper
            title="Image Generator"
            icon={<ImageIcon className="w-4 h-4" />}
            selected={selected}
            inputs={[
                { id: "prompt", label: "Prompt", type: "text" },
                { id: "image", label: "Ref Image", type: "image" }
            ]}
            outputs={[{ id: "image", label: "Image", type: "image" }]}
            contentClassName="p-0 overflow-hidden isolate"
            onDelete={() => deleteElements({ nodes: [{ id }] })}
            onRun={onRun}
            isRunning={isRunning}
        >
            <div
                className="relative w-full bg-muted/30 group/image transition-all duration-300 ease-in-out"
                style={{ aspectRatio: (data.ratio as string || "1:1").replace(':', '/') }}
            >
                {isRunning ? (
                    <div className="h-full flex flex-col items-center justify-center p-6 text-center bg-gradient-to-br from-primary/5 to-muted/10">
                        <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center mb-3 text-primary">
                            <Loader2 className="w-6 h-6 animate-spin" />
                        </div>
                        <p className="text-xs font-medium text-muted-foreground">Generating image...</p>
                    </div>
                ) : output ? (
                    <>
                        <img
                            src={output}
                            alt="Generated"
                            className="w-full h-full object-cover transition-transform duration-700 group-hover/image:scale-105"
                        />
                        <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent opacity-0 group-hover/image:opacity-100 transition-opacity duration-300 pointer-events-none" />

                        {/* Download button */}
                        <button
                            onClick={handleDownload}
                            className="absolute top-3 right-3 w-8 h-8 bg-black/60 backdrop-blur-md border border-white/10 rounded-full flex items-center justify-center text-white/90 hover:bg-black/80 hover:text-white transition-all opacity-0 group-hover/image:opacity-100"
                        >
                            <Download className="w-4 h-4" />
                        </button>
                    </>
                ) : (
                    <div className="h-full flex flex-col items-center justify-center p-6 text-center bg-gradient-to-br from-muted/50 to-muted/10">
                        <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center mb-3 text-primary animate-pulse">
                            <Sparkles className="w-6 h-6" />
                        </div>
                        <p className="text-xs font-medium text-muted-foreground">Waiting for input...</p>
                    </div>
                )}

                {/* Controls Bar - Bottom Left (One Line) */}
                <div className="absolute bottom-3 left-3 right-3 flex items-center gap-1 opacity-0 group-hover/image:opacity-100 transition-all duration-300 translate-y-2 group-hover/image:translate-y-0 z-20">

                    {/* Count Pill */}
                    <div className="h-7 flex items-center bg-black/60 backdrop-blur-md border border-white/10 rounded-full px-1 text-white flex-shrink-0">
                        <button
                            className="h-full px-1.5 hover:text-primary transition-colors disabled:opacity-50"
                            onClick={(e) => {
                                e.stopPropagation();
                                const current = typeof data.count === 'number' ? data.count : 1;
                                updateNodeData(id, { count: Math.max(1, current - 1) });
                            }}
                        >
                            <Minus className="w-2.5 h-2.5" />
                        </button>
                        <span className="text-[10px] font-bold w-3 text-center">{typeof data.count === 'number' ? data.count : 1}</span>
                        <button
                            className="h-full px-1.5 hover:text-primary transition-colors disabled:opacity-50"
                            onClick={(e) => {
                                e.stopPropagation();
                                const current = typeof data.count === 'number' ? data.count : 1;
                                updateNodeData(id, { count: Math.min(4, current + 1) });
                            }}
                        >
                            <Plus className="w-2.5 h-2.5" />
                        </button>
                    </div>

                    {/* Model Pill */}
                    <div className="relative h-7 flex items-center gap-1.5 bg-black/60 backdrop-blur-md border border-white/10 rounded-full px-2 text-white/90 hover:bg-black/70 transition-colors min-w-0 flex-grow max-w-[110px]">
                        <span className="text-[10px] font-medium truncate">{typeof data.model === 'string' ? data.model : "Google Imagen"}</span>
                        <ChevronDown className="w-2.5 h-2.5 text-white/50 flex-shrink-0" />
                        <select
                            className="absolute inset-0 opacity-0 cursor-pointer"
                            value={typeof data.model === 'string' ? data.model : "Google Imagen"}
                            onChange={(e) => updateNodeData(id, { model: e.target.value })}
                        >
                            <option value="Google Imagen">Google Imagen</option>
                            <option value="Gemini Flash">Gemini Flash</option>
                        </select>
                    </div>

                    {/* Ratio Pill */}
                    <div className="relative h-7 flex items-center gap-1.5 bg-black/60 backdrop-blur-md border border-white/10 rounded-full px-2 text-white/90 hover:bg-black/70 transition-colors flex-shrink-0">
                        <Square className="w-2.5 h-2.5 text-white/70" />
                        <span className="text-[10px] font-medium">{typeof data.ratio === 'string' ? data.ratio : "1:1"}</span>
                        <ChevronDown className="w-2.5 h-2.5 text-white/50 flex-shrink-0" />
                        <select
                            className="absolute inset-0 opacity-0 cursor-pointer"
                            value={typeof data.ratio === 'string' ? data.ratio : "1:1"}
                            onChange={(e) => updateNodeData(id, { ratio: e.target.value })}
                        >
                            <option value="1:1">1:1</option>
                            <option value="16:9">16:9</option>
                            <option value="9:16">9:16</option>
                            <option value="4:3">4:3</option>
                            <option value="3:4">3:4</option>
                        </select>
                    </div>
                </div>


            </div>
        </NodeWrapper>
    );
});

ImageGenNode.displayName = "ImageGenNode";
