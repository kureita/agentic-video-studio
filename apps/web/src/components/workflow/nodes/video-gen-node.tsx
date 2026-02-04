import { memo } from "react";
import { NodeProps, useReactFlow } from "@xyflow/react";
import { Video, Play, Clock, ChevronDown, Square, Loader2, Download } from "lucide-react";
import { NodeWrapper } from "@/components/workflow/node-wrapper";

export const VideoGenNode = memo(({ id, selected, data }: NodeProps) => {
    const { deleteElements, updateNodeData } = useReactFlow();

    const isRunning = data.isRunning as boolean;
    const onRun = data.onRun as (() => void) | undefined;
    const output = data.output as string | undefined;

    const handleDownload = () => {
        if (output) {
            const link = document.createElement('a');
            link.href = output;
            link.download = `generated-video-${Date.now()}.mp4`;
            link.target = '_blank';
            link.click();
        }
    };

    return (
        <NodeWrapper
            title="Video Generator"
            icon={<Video className="w-4 h-4" />}
            selected={selected}
            inputs={[
                { id: "text", label: "Text/Prompt", type: "text" },
                { id: "image", label: "Image", type: "image" }
            ]}
            outputs={[{ id: "video", label: "Video", type: "video" }]}
            contentClassName="p-0 overflow-hidden isolate"
            onDelete={() => deleteElements({ nodes: [{ id }] })}
            onRun={onRun}
            isRunning={isRunning}
        >
            <div
                className="relative w-full bg-muted/30 group/video transition-all duration-300 ease-in-out"
                style={{ aspectRatio: (data.ratio as string || "16:9").replace(':', '/') }}
            >
                {isRunning ? (
                    <div className="h-full flex flex-col items-center justify-center p-6 text-center bg-gradient-to-br from-rose-500/5 to-muted/10">
                        <div className="w-12 h-12 rounded-full bg-rose-500/10 flex items-center justify-center mb-3 text-rose-500">
                            <Loader2 className="w-6 h-6 animate-spin" />
                        </div>
                        <p className="text-xs font-medium text-muted-foreground">Generating video...</p>
                        <p className="text-[10px] text-muted-foreground/70 mt-1">This may take a few minutes</p>
                    </div>
                ) : output ? (
                    <>
                        <video
                            src={output}
                            className="w-full h-full object-cover"
                            controls
                            playsInline
                        />

                        {/* Download button */}
                        <button
                            onClick={handleDownload}
                            className="absolute top-3 right-3 w-8 h-8 bg-black/60 backdrop-blur-md border border-white/10 rounded-full flex items-center justify-center text-white/90 hover:bg-black/80 hover:text-white transition-all z-10"
                        >
                            <Download className="w-4 h-4" />
                        </button>
                    </>
                ) : (
                    <div className="h-full flex flex-col items-center justify-center p-6 text-center bg-gradient-to-br from-rose-500/5 to-muted/10">
                        <div className="w-12 h-12 rounded-full bg-rose-500/10 flex items-center justify-center mb-3 text-rose-500 animate-pulse">
                            <Play className="w-6 h-6 ml-1" />
                        </div>
                        <p className="text-xs font-medium text-muted-foreground">Waiting for input...</p>
                    </div>
                )}

                {/* Controls Bar - Bottom Left (One Line) */}
                <div className="absolute bottom-3 left-3 right-3 flex items-center gap-1 opacity-0 group-hover/video:opacity-100 transition-all duration-300 translate-y-2 group-hover/video:translate-y-0 z-20">
                    {/* Duration Pill */}
                    <div className="relative h-7 flex items-center gap-1.5 bg-black/60 backdrop-blur-md border border-white/10 rounded-full px-2 text-white/90 hover:bg-black/70 transition-colors">
                        <Clock className="w-2.5 h-2.5 text-white/70 flex-shrink-0" />
                        <span className="text-[10px] font-medium truncate">{typeof data.duration === 'string' ? data.duration : "5s"}</span>
                        <ChevronDown className="w-2.5 h-2.5 text-white/50 flex-shrink-0" />
                        <select
                            className="absolute inset-0 opacity-0 cursor-pointer"
                            value={typeof data.duration === 'string' ? data.duration : "5s"}
                            onChange={(e) => updateNodeData(id, { duration: e.target.value })}
                        >
                            <option value="5s">5s</option>
                            <option value="8s">8s</option>
                            <option value="10s">10s</option>
                        </select>
                    </div>

                    {/* Model Pill */}
                    <div className="relative h-7 flex items-center gap-1.5 bg-black/60 backdrop-blur-md border border-white/10 rounded-full px-2 text-white/90 hover:bg-black/70 transition-colors min-w-0 flex-grow max-w-[100px]">
                        <span className="text-[10px] font-medium truncate">{typeof data.model === 'string' ? data.model : "Google Veo"}</span>
                        <ChevronDown className="w-2.5 h-2.5 text-white/50 flex-shrink-0" />
                        <select
                            className="absolute inset-0 opacity-0 cursor-pointer"
                            value={typeof data.model === 'string' ? data.model : "Google Veo"}
                            onChange={(e) => updateNodeData(id, { model: e.target.value })}
                        >
                            <option value="Google Veo">Google Veo</option>
                            <option value="Veo Fast">Veo Fast</option>
                        </select>
                    </div>

                    {/* Ratio Pill */}
                    <div className="relative h-7 flex items-center gap-1.5 bg-black/60 backdrop-blur-md border border-white/10 rounded-full px-2 text-white/90 hover:bg-black/70 transition-colors flex-shrink-0">
                        <Square className="w-2.5 h-2.5 text-white/70 flex-shrink-0" />
                        <span className="text-[10px] font-medium">{typeof data.ratio === 'string' ? data.ratio : "16:9"}</span>
                        <ChevronDown className="w-2.5 h-2.5 text-white/50 flex-shrink-0" />
                        <select
                            className="absolute inset-0 opacity-0 cursor-pointer"
                            value={typeof data.ratio === 'string' ? data.ratio : "16:9"}
                            onChange={(e) => updateNodeData(id, { ratio: e.target.value })}
                        >
                            <option value="16:9">16:9</option>
                            <option value="9:16">9:16</option>
                            <option value="1:1">1:1</option>
                        </select>
                    </div>
                </div>


            </div>
        </NodeWrapper>
    );
});

VideoGenNode.displayName = "VideoGenNode";
