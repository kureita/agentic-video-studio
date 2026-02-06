"use client";

import { memo, useState } from "react";
import { NodeProps, Handle, Position } from "@xyflow/react";
import { Video, Sparkles, Loader2, Play, RefreshCw, Image as ImageIcon, Check } from "lucide-react";
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

interface BeatVideoNodeData {
    beatId: string;
    previousBeatId?: string; // For frame continuation
    onProceed?: (beatId: string) => void;
    [key: string]: unknown;
}

export const BeatVideoNode = memo(function BeatVideoNode({ data }: NodeProps) {
    const nodeData = data as BeatVideoNodeData;
    const {
        projectId,
        storyBeats,
        updateStoryBeat,
        updateScene,
        errors,
        setError,
    } = useCanvasStore();

    const beat = storyBeats.find(b => b.id === nodeData.beatId);
    const previousBeat = nodeData.previousBeatId
        ? storyBeats.find(b => b.id === nodeData.previousBeatId)
        : null;

    const [isGenerating, setIsGenerating] = useState(false);
    const [showVideo, setShowVideo] = useState(false);
    const [lastFrameUrl, setLastFrameUrl] = useState<string | null>(null);

    if (!beat) {
        return (
            <BaseNode status="idle">
                <BaseNodeHeader icon={<Video className="w-4 h-4" />}>
                    Beat Video
                </BaseNodeHeader>
                <BaseNodeContent>
                    <p className="text-sm text-foreground-muted">Beat data not available.</p>
                </BaseNodeContent>
            </BaseNode>
        );
    }

    const handleGenerateVideo = async () => {
        if (!projectId || !beat.imageUrl) return;

        setIsGenerating(true);
        setError(`beat-video-${beat.id}`, null);
        updateStoryBeat(beat.id, { generationStatus: "generating" });

        try {
            // Generate video from the beat's image
            const response = await canvasApi.regenerateVideo(projectId, parseInt(beat.id), {
                prompt: beat.videoPrompt || undefined,
                imageUrl: beat.imageUrl // Use explicit image URL from the beat state
            });

            const videoUrl = response.data.video_url;

            updateStoryBeat(beat.id, {
                videoUrl,
                generationStatus: "complete"
            });

            // Sync with scenes store so CompositionNode can see it
            const sceneId = parseInt(beat.id);
            if (!isNaN(sceneId)) {
                updateScene(sceneId, { video_url: videoUrl });
            }

            // Extract last frame for next beat's continuity
            // In production, this would call a frame extraction API
            setLastFrameUrl(`${videoUrl}?lastFrame=true`);

            if (nodeData.onProceed) {
                nodeData.onProceed(beat.id);
            }
        } catch (err) {
            console.error("Failed to generate video:", err);
            updateStoryBeat(beat.id, { generationStatus: "error" });
            setError(`beat-video-${beat.id}`, err instanceof Error ? err.message : "Failed to generate video");
        } finally {
            setIsGenerating(false);
        }
    };

    const status = isGenerating ? "loading" : beat.videoUrl ? "success" : beat.imageUrl ? "idle" : "idle";
    const canGenerate = !!beat.imageUrl;

    return (
        <BaseNode status={status}>
            {/* Input handle */}
            <Handle type="target" position={Position.Top} className="!bg-foreground-subtle !w-3 !h-3" />

            <BaseNodeHeader icon={<Video className="w-4 h-4" />} status={status}>
                <div className="flex items-center gap-2">
                    <span className="px-1.5 py-0.5 text-xs rounded bg-background-secondary">
                        {beat.index + 1}
                    </span>
                    Beat Video
                </div>
            </BaseNodeHeader>

            <BaseNodeContent>
                {!canGenerate ? (
                    <div className="p-3 rounded-lg bg-background-secondary text-center">
                        <ImageIcon className="w-6 h-6 mx-auto mb-2 text-foreground-muted" />
                        <p className="text-sm text-foreground-muted">
                            Generate an image first to create video.
                        </p>
                    </div>
                ) : !beat.videoUrl ? (
                    <div className="space-y-3">
                        <p className="text-sm text-foreground-muted">
                            Generate video from the beat image.
                        </p>

                        {/* Prompt Editor */}
                        <div className="space-y-1">
                            <label className="text-xs font-medium text-foreground-muted">Video Prompt</label>
                            <textarea
                                value={beat.videoPrompt || beat.visualPrompt || ""}
                                onChange={(e) => updateStoryBeat(beat.id, { videoPrompt: e.target.value })}
                                className="w-full text-xs p-2 rounded bg-background border border-border resize-none focus:outline-none focus:ring-1 focus:ring-primary"
                                rows={3}
                                placeholder="Describe the motion for the video..."
                            />
                        </div>

                        {/* Source Image Preview */}
                        <div className="aspect-video rounded-lg overflow-hidden bg-black">
                            <img
                                src={beat.imageUrl}
                                alt={beat.name}
                                className="w-full h-full object-cover opacity-70"
                            />
                        </div>

                        <div className="text-xs text-foreground-muted">
                            Duration: ~{beat.durationSeconds}s
                        </div>
                    </div>
                ) : (
                    <div className="space-y-3">
                        {/* Video Player */}
                        <div className="aspect-video rounded-lg overflow-hidden bg-black relative">
                            {showVideo ? (
                                <video
                                    src={beat.videoUrl}
                                    className="w-full h-full object-cover"
                                    controls
                                    autoPlay
                                />
                            ) : (
                                <button
                                    onClick={() => setShowVideo(true)}
                                    className="w-full h-full flex items-center justify-center group nodrag"
                                >
                                    <img
                                        src={beat.imageUrl}
                                        alt={beat.name}
                                        className="absolute inset-0 w-full h-full object-cover"
                                    />
                                    <div className="relative z-10 w-12 h-12 rounded-full bg-white/90 flex items-center justify-center shadow-lg group-hover:scale-110 transition-transform">
                                        <Play className="w-5 h-5 text-gray-900 ml-0.5" />
                                    </div>
                                </button>
                            )}
                        </div>

                        {/* Success Indicator */}
                        <div className="flex items-center justify-center gap-2 p-2 rounded-lg bg-emerald-500/10 text-emerald-600">
                            <Check className="w-4 h-4" />
                            <span className="text-sm">Video generated</span>
                        </div>
                        {/* Prompt Display */}
                        <div className="bg-background-secondary p-2 rounded text-xs text-foreground-muted">
                            <div className="font-semibold mb-1">Prompt Used:</div>
                            {beat.videoPrompt || beat.visualPrompt}
                        </div>
                    </div>
                )}
            </BaseNodeContent>

            <BaseNodeError message={errors[`beat-video-${beat.id}`]} />

            <BaseNodeFooter>
                {canGenerate && (
                    <Button
                        onClick={handleGenerateVideo}
                        disabled={isGenerating}
                        className="w-full nodrag"
                        icon={isGenerating ? <Loader2 className="w-4 h-4 animate-spin" /> : beat.videoUrl ? <RefreshCw className="w-4 h-4" /> : <Sparkles className="w-4 h-4" />}
                    >
                        {isGenerating ? "Generating..." : beat.videoUrl ? "Regenerate" : "Generate Video"}
                    </Button>
                )}
            </BaseNodeFooter>

            {/* Output handle */}
            <Handle type="source" position={Position.Bottom} className="!bg-foreground-subtle !w-3 !h-3" />
        </BaseNode>
    );
});
