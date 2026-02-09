import { memo, useRef, useEffect } from "react";
import { NodeProps, useReactFlow } from "@xyflow/react";
import { Upload, Image as ImageIcon, Video, Music } from "lucide-react";
import { NodeWrapper } from "@/components/workflow/node-wrapper";
import { useWorkflowStore } from "@/lib/workflow-store";

export const MediaUploadNode = memo(({ id, selected, data }: NodeProps) => {
    const { deleteElements } = useReactFlow();
    const { runNode, clearNodeOutput, outputs, runningNodeId, setNodeOutput } = useWorkflowStore();
    const fileInputRef = useRef<HTMLInputElement>(null);

    const isRunning = runningNodeId === id;
    const output = (outputs[id] as string | undefined) || (data.output as string | undefined);

    // Determine media type from data or current output
    const mediaType = data.mediaType || (output ? (
        output.toString().includes('video') || output.toString().includes('.mp4') ? 'video' :
            output.toString().includes('audio') || output.toString().includes('.mp3') || output.toString().includes('.wav') ? 'audio' :
                'image'
    ) : null);

    // Get stored dimensions if available
    const aspectRatio = data.aspectRatio as number || 1;

    // Calculate aspect ratio for pre-filled media if missing
    useEffect(() => {
        if (output && (!data.aspectRatio || data.aspectRatio === 1)) {
            // Create a cleanup flag
            let isMounted = true;

            const updateRatio = (ar: number) => {
                if (!isMounted) return;

                // Update note data with aspect ratio
                const { setNodes, nodes } = useWorkflowStore.getState();
                setNodes(nodes.map(n => n.id === id ? { ...n, data: { ...n.data, aspectRatio: ar } } : n));
            };

            if (mediaType === 'video' || output.toString().match(/\.(mp4|mov|webm)$/i)) {
                const video = document.createElement('video');
                video.onloadedmetadata = () => {
                    if (video.videoWidth && video.videoHeight) {
                        updateRatio(video.videoWidth / video.videoHeight);
                    }
                };
                video.src = output as string;
            } else if (mediaType === 'image' || output.toString().match(/\.(jpg|jpeg|png|webp|gif)$/i)) {
                const img = new Image();
                img.onload = () => {
                    if (img.naturalWidth && img.naturalHeight) {
                        updateRatio(img.naturalWidth / img.naturalHeight);
                    }
                };
                img.src = output as string;
            }

            return () => {
                isMounted = false;
            };
        }
    }, [output, data.aspectRatio, id, mediaType]);

    const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = (e) => {
            const result = e.target?.result as string;
            if (!result) return;

            if (file.type.startsWith('image/')) {
                const img = new Image();
                img.onload = () => {
                    const ar = img.naturalWidth / img.naturalHeight;
                    setNodeOutput(id, result);
                    // Update note data with aspect ratio
                    const { setNodes, nodes } = useWorkflowStore.getState();
                    setNodes(nodes.map(n => n.id === id ? { ...n, data: { ...n.data, aspectRatio: ar } } : n));
                };
                img.src = result;
            } else if (file.type.startsWith('video/')) {
                const video = document.createElement('video');
                video.onloadedmetadata = () => {
                    const ar = video.videoWidth / video.videoHeight;
                    setNodeOutput(id, result);
                    // Update note data with aspect ratio
                    const { setNodes, nodes } = useWorkflowStore.getState();
                    setNodes(nodes.map(n => n.id === id ? { ...n, data: { ...n.data, aspectRatio: ar } } : n));
                };
                video.src = result;
            } else {
                setNodeOutput(id, result);
            }
        };
        reader.readAsDataURL(file);
    };

    const handleUploadClick = () => {
        if (!output) {
            fileInputRef.current?.click();
        }
    };

    const handleClear = () => {
        clearNodeOutput(id);
        if (fileInputRef.current) {
            fileInputRef.current.value = '';
        }
        // Reset aspect ratio
        const { setNodes, nodes } = useWorkflowStore.getState();
        setNodes(nodes.map(n => n.id === id ? { ...n, data: { ...n.data, aspectRatio: undefined } } : n));
    };

    // Calculate dimensions based on 6 dots (50px * 6 = 300px)
    const minSize = 300;
    // For audio, we'll use a square aspect ratio (1:1) if no output, or specialized ratio
    const effectiveAspectRatio = mediaType === 'audio' ? 1 : aspectRatio;
    const nodeWidth = Math.max(minSize, minSize * effectiveAspectRatio);
    const nodeHeight = Math.max(minSize, minSize / effectiveAspectRatio);

    // Output handle changes based on media type
    const nodeHandles = [{
        id: "output",
        label: mediaType === 'video' ? 'Video' : mediaType === 'audio' ? 'Audio' : mediaType === 'image' ? 'Image' : 'Media',
        type: (mediaType || 'any') as any
    }];

    return (
        <NodeWrapper
            title={`Asset #${useWorkflowStore((state) =>
                state.nodes
                    .filter(n => n.type === 'mediaUpload')
                    .findIndex(n => n.id === id) + 1
            )}`}
            icon={<Upload className="w-4 h-4" />}
            selected={selected}
            outputs={nodeHandles}
            contentClassName="p-0 h-full"
            onDelete={() => deleteElements({ nodes: [{ id }] })}
            onRun={() => runNode(id)}
            onClear={output ? handleClear : undefined}
            isRunning={isRunning}
            style={{ width: nodeWidth, height: nodeHeight }}
        >
            <div className="h-full flex flex-col">
                {/* Preview Area */}
                {output ? (
                    <div className="relative flex-1 w-full bg-black/5 flex items-center justify-center overflow-hidden">
                        {mediaType === 'video' ? (
                            <video
                                src={output as string}
                                controls
                                className="w-full h-full object-contain"
                            />
                        ) : mediaType === 'audio' ? (
                            <div className="w-full p-6 flex flex-col items-center gap-4">
                                <div className="w-16 h-16 rounded-full bg-blue-500/10 flex items-center justify-center">
                                    <Music className="w-8 h-8 text-blue-500" />
                                </div>
                                <audio
                                    src={output as string}
                                    controls
                                    className="w-full"
                                />
                            </div>
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
                            ) : mediaType === 'audio' ? (
                                <>
                                    <Music className="w-3 h-3 text-blue-400" />
                                    <span>Audio</span>
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
                    <div
                        className="flex-1 flex flex-col items-center justify-center p-4 bg-muted/20 hover:bg-muted/40 transition-colors cursor-pointer group/upload relative overflow-hidden"
                        onClick={handleUploadClick}
                    >
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

            {/* Hidden file input */}
            <input
                ref={fileInputRef}
                type="file"
                accept="image/*,video/*,audio/*"
                onChange={handleFileSelect}
                className="hidden"
            />
        </NodeWrapper>
    );
});

MediaUploadNode.displayName = "MediaUploadNode";
