import { memo, useRef, useEffect, useState } from "react";
import { NodeProps, useReactFlow } from "@xyflow/react";
import { Upload, Image as ImageIcon, Video, Music, Loader2 } from "lucide-react";
import { NodeWrapper } from "@/components/workflow/node-wrapper";
import { S3Image } from "@/components/ui/s3-image";
import { usePresignedUrl } from "@/lib/use-presigned-url";
import { useWorkflowStore } from "@/lib/workflow-store";
import { assetsApi } from "@/lib/api";
import axios from "axios";
import { toast } from "sonner";
import { workflowApi } from "@/lib/workflow-api";
import { extractFrameFromVideo } from "@/lib/video-utils";
import { ALLOWED_MEDIA_TYPES } from "@/lib/utils";

export const MediaUploadNode = memo(({ id, selected, data }: NodeProps) => {
    const { deleteElements } = useReactFlow();
    const { runNode, clearNodeOutput, outputs, runningNodeId, setNodeOutput, setRawOutput } = useWorkflowStore();
    const fileInputRef = useRef<HTMLInputElement>(null);
    const [isUploading, setIsUploading] = useState(false);
    const [uploadProgress, setUploadProgress] = useState<number>(0);
    const [isDragOver, setIsDragOver] = useState<boolean>(false);
    const [extractingHandle, setExtractingHandle] = useState<string | null>(null);
    const [extractionError, setExtractionError] = useState<string | null>(null);

    const isRunning = runningNodeId === id;
    const rawOutput = (outputs[id] as string | undefined) || (data.output as string | undefined);

    // Get presigned URL for S3 assets
    const { url: presignedOutput } = usePresignedUrl(rawOutput);
    const output = presignedOutput || rawOutput;

    // Derive workflowId from the URL query param
    const workflowId = typeof window !== 'undefined' ? new URLSearchParams(window.location.search).get('id') || '' : '';

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

    const handleExtractFrames = async (handleId: string, videoUrl: string) => {
        if (!workflowId || extractingHandle || !videoUrl) return;
        setExtractingHandle(handleId);
        setExtractionError(null);
        try {
            const timeRatio = handleId === 'end_frame' ? 1 : 0;
            const base64Image = await extractFrameFromVideo(videoUrl, timeRatio);

            const startFramePayload = handleId === 'start_frame' ? base64Image : undefined;
            const endFramePayload = handleId === 'end_frame' ? base64Image : undefined;

            await workflowApi.extractFrames(workflowId, id, startFramePayload, endFramePayload);
            setRawOutput(`${id}__${handleId}`, base64Image);
        } catch (err: unknown) {
            console.error('[ExtractFrames] Error:', err);
            const msg = err instanceof Error ? err.message : 'Could not extract frame';
            setExtractionError(msg);
            toast.error(msg);
        } finally {
            setExtractingHandle(null);
        }
    };

    const processFile = async (file: File) => {
        if (!ALLOWED_MEDIA_TYPES.includes(file.type)) {
            toast.error("Format not supported. Please use accepted image, video, or audio formats.");
            return;
        }

        setIsUploading(true);
        setUploadProgress(0);
        const { setNodes, nodes } = useWorkflowStore.getState();

        try {
            let uploadedUrl: string;
            const uploadedType = file.type.split('/')[0];

            // 1. Try to get a presigned URL first (better for large files in prod)
            try {
                const presignedRes = await assetsApi.getPresignedUrl(file.name, file.type);
                if (presignedRes.data.success && presignedRes.data.upload_url && !presignedRes.data.is_local) {
                    const { upload_url, file_url } = presignedRes.data;

                    // Direct upload to S3 using PUT
                    await axios.put(upload_url, file, {
                        headers: { "Content-Type": file.type },
                        onUploadProgress: (progressEvent: { loaded: number; total?: number }) => {
                            const percentCompleted = progressEvent.total ? Math.round((progressEvent.loaded * 100) / progressEvent.total) : 0;
                            setUploadProgress(percentCompleted);
                        }
                    });

                    uploadedUrl = file_url!;
                } else {
                    // Fallback to standard multipart upload
                    const response = await assetsApi.upload(file, (progressEvent: { loaded: number; total?: number }) => {
                        const percentCompleted = progressEvent.total ? Math.round((progressEvent.loaded * 100) / progressEvent.total) : 0;
                        setUploadProgress(percentCompleted);
                    });
                    uploadedUrl = response.data.url;
                }
            } catch (err) {
                console.warn("Presigned upload failed, falling back to standard upload:", err);
                const response = await assetsApi.upload(file, (progressEvent: { loaded: number; total?: number }) => {
                    const percentCompleted = progressEvent.total ? Math.round((progressEvent.loaded * 100) / progressEvent.total) : 0;
                    setUploadProgress(percentCompleted);
                });
                uploadedUrl = response.data.url;
            }

            // Update mediaType and ratio locally before output
            setNodes(nodes.map(n => n.id === id ? {
                ...n,
                data: { ...n.data, mediaType: uploadedType, output: uploadedUrl }
            } : n));

            setNodeOutput(id, uploadedUrl);

            // Clear any running state for this node forcefully after a short delay
            const { nodeExecutionStates } = useWorkflowStore.getState();
            useWorkflowStore.setState({
                runningNodeId: null,
                nodeExecutionStates: {
                    ...nodeExecutionStates,
                    [id]: { status: "completed" }
                }
            });

            // Auto-evaluate the node
            runNode(id);

            // For videos, start auto-extraction
            if (uploadedType === 'video') {
                // Create a blob URL for safe local extraction without CORS
                const safeBlobUrl = URL.createObjectURL(file);

                setTimeout(async () => {
                    try {
                        const startFrame = await extractFrameFromVideo(safeBlobUrl, 0);
                        setRawOutput(`${id}__start_frame`, startFrame);
                        const endFrame = await extractFrameFromVideo(safeBlobUrl, 1);
                        setRawOutput(`${id}__end_frame`, endFrame);

                        if (workflowId) {
                            await workflowApi.extractFrames(workflowId, id, startFrame, endFrame);
                        }
                    } catch (err) {
                        console.error('[VideoNode auto-extraction] Error:', err);
                    } finally {
                        URL.revokeObjectURL(safeBlobUrl);
                    }
                }, 1000);
            }
        } catch (error: unknown) {
            console.error("Upload error:", error);
            const axiosError = error as { response?: { status?: number } };
            // If it's a 413, even with presigned URL attempt, it might be an S3 limit or something else
            // but usually 413 comes from API Gateway/Lambda
            if (axiosError.response?.status === 413) {
                toast.error("File is too large.");
            } else {
                toast.error("An error occurred during upload.");
            }
        } finally {
            setIsUploading(false);
            setUploadProgress(0);
            if (fileInputRef.current) fileInputRef.current.value = '';
        }
    };

    const handleFileSelect = async (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0];
        if (!file) return;
        await processFile(file);
    };

    const handleDragEnter = (e: React.DragEvent<HTMLDivElement>) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragOver(true);
    };

    const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
        e.preventDefault();
        e.stopPropagation();
        if (!isDragOver) setIsDragOver(true);
    };

    const handleDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
        e.preventDefault();
        e.stopPropagation();
        if (!e.currentTarget.contains(e.relatedTarget as Node)) {
            setIsDragOver(false);
        }
    };

    const handleDrop = async (e: React.DragEvent<HTMLDivElement>) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragOver(false);
        const file = e.dataTransfer.files?.[0];
        if (file) {
            await processFile(file);
        }
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
        type: (mediaType || 'any') as "video" | "audio" | "image" | "any" | "text"
    }];

    // Add start and end frames for video uploads
    if (mediaType === 'video') {
        nodeHandles.push({
            id: "start_frame",
            label: "Start (Frame 0)",
            type: "image",
            // Custom props handled inside NodeWrapper
            framePreview: outputs[`${id}__start_frame`] as string | undefined,
            hasVideoOutput: true,
            onExtractFrames: () => output && handleExtractFrames('start_frame', output as string),
            isExtractingFrames: extractingHandle === 'start_frame',
            extractionError: extractionError || undefined,
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
        } as any);
        nodeHandles.push({
            id: "end_frame",
            label: "End (Last Frame)",
            type: "image",
            // Custom props handled inside NodeWrapper
            framePreview: outputs[`${id}__end_frame`] as string | undefined,
            hasVideoOutput: true,
            onExtractFrames: () => output && handleExtractFrames('end_frame', output as string),
            isExtractingFrames: extractingHandle === 'end_frame',
            extractionError: extractionError || undefined,
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
        } as any);
    }

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
            onClear={output ? handleClear : undefined}
            isRunning={isRunning}
            executionStatus={null}
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
                                className="w-full h-full object-contain nodrag nopan nowheel"
                            />
                        ) : mediaType === 'audio' ? (
                            <div className="w-full p-6 flex flex-col items-center gap-4">
                                <div className="w-16 h-16 rounded-full bg-blue-500/10 flex items-center justify-center">
                                    <Music className="w-8 h-8 text-blue-500" />
                                </div>
                                <audio
                                    src={output as string}
                                    controls
                                    className="w-full nodrag nopan nowheel"
                                />
                            </div>
                        ) : (
                            <S3Image
                                src={rawOutput}
                                alt="Uploaded media"
                                fill
                                className="object-contain"
                                unoptimized
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
                        className={`flex-1 flex flex-col items-center justify-center p-4 transition-colors cursor-pointer group/upload relative overflow-hidden ${isDragOver ? "bg-primary/5 border-primary" : "bg-muted/20 hover:bg-muted/40"}`}
                        onClick={handleUploadClick}
                        onDragEnter={handleDragEnter}
                        onDragOver={handleDragOver}
                        onDragLeave={handleDragLeave}
                        onDrop={handleDrop}
                    >
                        <div className={`absolute inset-0 border-2 border-dashed transition-colors m-2 rounded-lg ${isDragOver ? "border-primary/50" : "border-muted-foreground/20 group-hover/upload:border-primary/50"}`} />

                        <div className="relative z-10 flex flex-col items-center animate-in fade-in zoom-in duration-500">
                            {isUploading ? (
                                <>
                                    <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-blue-500/20 to-blue-500/5 flex items-center justify-center mb-3 shadow-inner">
                                        <Loader2 className="w-5 h-5 text-blue-500 animate-spin" />
                                    </div>
                                    <p className="text-xs font-medium text-foreground mb-1">
                                        Uploading... {uploadProgress > 0 && `${uploadProgress}%`}
                                    </p>
                                    <div className="w-24 h-1.5 bg-muted rounded-full mt-1 overflow-hidden">
                                        <div
                                            className="h-full bg-blue-500 transition-all duration-300 ease-out rounded-full"
                                            style={{ width: `${uploadProgress}%` }}
                                        />
                                    </div>
                                </>
                            ) : (
                                <>
                                    <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-blue-500/20 to-blue-500/5 flex items-center justify-center mb-3 shadow-inner group-hover/upload:scale-110 transition-transform duration-300">
                                        <Upload className="w-5 h-5 text-blue-500" />
                                    </div>
                                    <p className="text-xs font-medium text-foreground mb-1">Upload Image, Video or Audio</p>
                                </>
                            )}
                            {!isUploading && (
                                <p className="text-[10px] text-muted-foreground text-center max-w-[160px]">
                                    Drag & drop or click to browse
                                </p>
                            )}
                            <div className="flex items-center gap-2 mt-3">
                                <div className="flex items-center gap-1 px-2 py-1 rounded bg-muted/50 text-[9px] text-muted-foreground">
                                    <ImageIcon className="w-2.5 h-2.5" />
                                    <span>JPG, PNG</span>
                                </div>
                                <div className="flex items-center gap-1 px-2 py-1 rounded bg-muted/50 text-[9px] text-muted-foreground">
                                    <Video className="w-2.5 h-2.5" />
                                    <span>MP4, MOV</span>
                                </div>
                                <div className="flex items-center gap-1 px-2 py-1 rounded bg-muted/50 text-[9px] text-muted-foreground">
                                    <Music className="w-2.5 h-2.5" />
                                    <span>MP3, WAV</span>
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
                accept={ALLOWED_MEDIA_TYPES.join(',')}
                onChange={handleFileSelect}
                className="hidden"
            />
        </NodeWrapper>
    );
});

MediaUploadNode.displayName = "MediaUploadNode";
