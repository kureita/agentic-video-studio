"use client";

import { memo, useState, useRef, useEffect } from "react";
import { NodeProps, Handle, Position } from "@xyflow/react";
import { Image as ImageIcon, Sparkles, Loader2, Upload, RefreshCw, Check, X, Maximize2 } from "lucide-react";
import {
    BaseNode,
    BaseNodeHeader,
    BaseNodeContent,
    BaseNodeFooter,
    BaseNodeError
} from "./BaseNode";
import { Button } from "@/components/ui";
import { useCanvasStore } from "@/lib/canvas-store";
import { canvasApi } from "@/lib/api";

interface BeatImageNodeData {
    beatId: string;
    onProceed?: (beatId: string) => void;
    [key: string]: unknown;
}

export const BeatImageNode = memo(function BeatImageNode({ data }: NodeProps) {
    const nodeData = data as BeatImageNodeData;
    const {
        projectId,
        storyBeats,
        updateStoryBeat,
        errors,
        setError,
    } = useCanvasStore();

    const beat = storyBeats.find(b => b.id === nodeData.beatId);
    const beatIndex = storyBeats.findIndex(b => b.id === nodeData.beatId);
    const prevBeat = beatIndex > 0 ? storyBeats[beatIndex - 1] : null;
    const prevFrame = prevBeat?.extractedFrameUrl;

    const fileInputRef = useRef<HTMLInputElement>(null);

    const [isGenerating, setIsGenerating] = useState(false);
    const [isUploading, setIsUploading] = useState(false);
    const [showFullImage, setShowFullImage] = useState(false);
    const [variations, setVariations] = useState<string[]>([]);
    const [selectedVariation, setSelectedVariation] = useState(0);

    // Auto-apply extracted frame if available and no image set
    useEffect(() => {
        if (beat && prevFrame && !beat.imageUrl && !isGenerating && !isUploading) {
            updateStoryBeat(beat.id, { imageUrl: prevFrame, generationStatus: "complete" });
        }
    }, [prevFrame, beat?.imageUrl, beat?.id, isGenerating, isUploading, updateStoryBeat]);

    if (!beat) {
        return (
            <BaseNode status="idle">
                <BaseNodeHeader icon={<ImageIcon className="w-4 h-4" />}>
                    Beat Image
                </BaseNodeHeader>
                <BaseNodeContent>
                    <p className="text-sm text-foreground-muted">Beat data not available.</p>
                </BaseNodeContent>
            </BaseNode>
        );
    }

    const handleGenerateImage = async () => {
        if (!projectId) return;

        setIsGenerating(true);
        setError(`beat-image-${beat.id}`, null);
        updateStoryBeat(beat.id, { generationStatus: "generating" });

        try {
            // Use the beat's visual prompt to generate an image
            const response = await canvasApi.regenerateImage(projectId, parseInt(beat.id), {
                prompt: beat.visualPrompt,
                visual_style: "cinematic",
            });

            const imageUrl = response.data.image_url;

            // Add to variations and select it
            setVariations(prev => [...prev, imageUrl]);
            setSelectedVariation(variations.length);

            updateStoryBeat(beat.id, {
                imageUrl,
                generationStatus: "complete"
            });

            if (nodeData.onProceed) {
                nodeData.onProceed(beat.id);
            }
        } catch (err) {
            console.error("Failed to generate image:", err);
            updateStoryBeat(beat.id, { generationStatus: "error" });
            setError(`beat-image-${beat.id}`, err instanceof Error ? err.message : "Failed to generate image");
        } finally {
            setIsGenerating(false);
        }
    };

    const handleUploadClick = () => {
        fileInputRef.current?.click();
    };

    const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;

        setIsUploading(true);
        setError(`beat-image-${beat.id}`, null);

        try {
            // Create a local URL for preview (in production, upload to server)
            const imageUrl = URL.createObjectURL(file);

            // Add to variations and select it
            setVariations(prev => [...prev, imageUrl]);
            setSelectedVariation(variations.length);

            updateStoryBeat(beat.id, {
                imageUrl,
                generationStatus: "complete"
            });
        } catch (err) {
            console.error("Failed to upload image:", err);
            setError(`beat-image-${beat.id}`, "Failed to upload image");
        } finally {
            setIsUploading(false);
        }
    };

    const handleSelectVariation = (index: number) => {
        setSelectedVariation(index);
        updateStoryBeat(beat.id, { imageUrl: variations[index] });
    };

    const status = isGenerating || isUploading ? "loading" : beat.imageUrl ? "success" : "idle";

    return (
        <BaseNode status={status}>
            {/* Input handle */}
            <Handle type="target" position={Position.Top} className="!bg-foreground-subtle !w-3 !h-3" />

            <input
                type="file"
                ref={fileInputRef}
                accept="image/*"
                className="hidden"
                onChange={handleFileChange}
            />

            <BaseNodeHeader icon={<ImageIcon className="w-4 h-4" />} status={status}>
                <div className="flex items-center gap-2">
                    <span className="px-1.5 py-0.5 text-xs rounded bg-background-secondary">
                        {beat.index + 1}
                    </span>
                    Beat Image
                </div>
            </BaseNodeHeader>

            <BaseNodeContent>
                {!beat.imageUrl ? (
                    <div className="space-y-3">
                        <p className="text-sm text-foreground-muted">
                            Generate or upload an image for this beat.
                        </p>

                        {prevFrame && (
                            <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
                                <div className="flex items-center gap-3">
                                    <div className="w-16 h-9 rounded overflow-hidden bg-black shrink-0">
                                        <img src={prevFrame} alt="Previous Frame" className="w-full h-full object-cover" />
                                    </div>
                                    <div className="flex-1">
                                        <p className="text-xs text-emerald-500 font-medium mb-1">Continuity Frame Available</p>
                                        <Button
                                            className="h-6 text-xs w-full"
                                            onClick={() => updateStoryBeat(beat.id, { imageUrl: prevFrame, generationStatus: "complete" })}
                                        >
                                            Use Extracted Frame
                                        </Button>
                                    </div>
                                </div>
                            </div>
                        )}

                        <div className="p-2 rounded bg-background-secondary">
                            <p className="text-xs text-foreground-muted mb-1">Visual Prompt</p>
                            <p className="text-xs text-foreground line-clamp-3">{beat.visualPrompt}</p>
                        </div>
                    </div>
                ) : (
                    <div className="space-y-3">
                        {/* Main Image */}
                        <div
                            className="aspect-video rounded-lg overflow-hidden bg-black relative cursor-pointer group"
                            onClick={() => setShowFullImage(true)}
                        >
                            <img
                                src={beat.imageUrl}
                                alt={beat.name}
                                className="w-full h-full object-cover"
                            />
                            <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity">
                                <Maximize2 className="w-6 h-6 text-white" />
                            </div>
                        </div>

                        {/* Variations */}
                        {variations.length > 1 && (
                            <div className="flex gap-1 overflow-x-auto nowheel">
                                {variations.map((url, idx) => (
                                    <button
                                        key={idx}
                                        onClick={() => handleSelectVariation(idx)}
                                        className={`w-12 h-12 rounded overflow-hidden shrink-0 border-2 nodrag ${selectedVariation === idx ? "border-accent" : "border-transparent"
                                            }`}
                                    >
                                        <img src={url} alt={`Variation ${idx + 1}`} className="w-full h-full object-cover" />
                                    </button>
                                ))}
                            </div>
                        )}
                    </div>
                )}
            </BaseNodeContent>

            <BaseNodeError message={errors[`beat-image-${beat.id}`]} />

            <BaseNodeFooter>
                {!beat.imageUrl ? (
                    <div className="flex gap-2">
                        <Button
                            onClick={handleGenerateImage}
                            disabled={isGenerating || isUploading}
                            className="flex-1 nodrag"
                            icon={isGenerating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                        >
                            {isGenerating ? "Generating..." : "Generate"}
                        </Button>
                        <Button
                            variant="outline"
                            onClick={handleUploadClick}
                            disabled={isGenerating || isUploading}
                            className="nodrag"
                            icon={isUploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
                        >
                            Upload
                        </Button>
                    </div>
                ) : (
                    <div className="flex gap-2">
                        <Button
                            variant="outline"
                            onClick={handleGenerateImage}
                            disabled={isGenerating}
                            className="flex-1 nodrag"
                            icon={isGenerating ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                        >
                            {isGenerating ? "Generating..." : "New Variation"}
                        </Button>
                        <Button
                            variant="outline"
                            onClick={handleUploadClick}
                            disabled={isUploading}
                            className="nodrag"
                            icon={<Upload className="w-4 h-4" />}
                        />
                    </div>
                )}
            </BaseNodeFooter>

            {/* Output handle */}
            <Handle type="source" position={Position.Bottom} className="!bg-foreground-subtle !w-3 !h-3" />

            {/* Full Image Modal */}
            {showFullImage && beat.imageUrl && (
                <div
                    className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-8"
                    onClick={() => setShowFullImage(false)}
                >
                    <button
                        className="absolute top-4 right-4 p-2 rounded-lg bg-white/10 hover:bg-white/20"
                        onClick={() => setShowFullImage(false)}
                    >
                        <X className="w-6 h-6 text-white" />
                    </button>
                    <img
                        src={beat.imageUrl}
                        alt={beat.name}
                        className="max-w-full max-h-full object-contain rounded-lg"
                    />
                </div>
            )}
        </BaseNode>
    );
});
