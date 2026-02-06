"use client";

import { memo, useState } from "react";
import { NodeProps, Handle, Position } from "@xyflow/react";
import { Image as ImageIcon, Loader2, ArrowRight, Scissors } from "lucide-react";
import {
    BaseNode,
    BaseNodeHeader,
    BaseNodeContent,
    BaseNodeFooter,
} from "./BaseNode";
import { Button } from "@/components/ui";
import { useCanvasStore } from "@/lib/canvas-store";
import { canvasApi } from "@/lib/api";

interface FrameExtractorNodeData {
    beatId: string;
    videoUrl?: string; // Optional direct override
    onProceed?: () => void;
    [key: string]: unknown;
}

export const FrameExtractorNode = memo(function FrameExtractorNode({ data, id }: NodeProps) {
    const nodeData = data as FrameExtractorNodeData;
    const {
        storyBeats,
        updateStoryBeat,
        projectId,
        setError
    } = useCanvasStore();

    const [isExtracting, setIsExtracting] = useState(false);

    // Find the beat this extractor belongs to
    const beat = storyBeats.find(b => b.id === nodeData.beatId);
    const videoUrl = nodeData.videoUrl || beat?.videoUrl;
    const frameUrl = beat?.extractedFrameUrl;

    const handleExtract = async () => {
        if (!videoUrl || !projectId) return;

        setIsExtracting(true);
        try {
            const response = await canvasApi.extractFrame(projectId, videoUrl);

            // Update store
            if (beat) {
                updateStoryBeat(beat.id, { extractedFrameUrl: response.data.frame_url });
            }

            if (nodeData.onProceed) {
                nodeData.onProceed();
            }
        } catch (err) {
            console.error("Failed to extract frame:", err);
            setError("visual", "Failed to extract frame");
        } finally {
            setIsExtracting(false);
        }
    };

    if (!videoUrl) {
        return (
            <BaseNode status="idle">
                <Handle type="target" position={Position.Left} />
                <BaseNodeHeader icon={<Scissors className="w-4 h-4" />}>
                    Frame Extractor
                </BaseNodeHeader>
                <BaseNodeContent>
                    <p className="text-sm text-foreground-muted">Waiting for video...</p>
                </BaseNodeContent>
                <Handle type="source" position={Position.Right} />
            </BaseNode>
        );
    }

    return (
        <BaseNode status={frameUrl ? "success" : "idle"}>
            <Handle type="target" position={Position.Left} />

            <BaseNodeHeader
                icon={<Scissors className="w-4 h-4" />}
                status={frameUrl ? "success" : "idle"}
            >
                Last Frame Extractor
            </BaseNodeHeader>

            <BaseNodeContent>
                <div className="space-y-3">
                    {frameUrl ? (
                        <div className="relative aspect-video rounded-md overflow-hidden bg-black/20 border border-border">
                            {/* eslint-disable-next-line @next/next/no-img-element */}
                            <img
                                src={frameUrl}
                                alt="Extracted Frame"
                                className="w-full h-full object-cover"
                            />
                            <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent flex items-end p-2">
                                <span className="text-xs text-white font-medium">Ready for next beat</span>
                            </div>
                        </div>
                    ) : (
                        <div className="flex flex-col items-center justify-center py-4 text-center">
                            <p className="text-sm text-foreground-muted mb-2">
                                Extract the last frame to maintain continuity.
                            </p>
                        </div>
                    )}
                </div>
            </BaseNodeContent>

            <BaseNodeFooter>
                <Button
                    onClick={handleExtract}
                    disabled={isExtracting}
                    className="w-full nodrag"
                    variant={frameUrl ? "outline" : "primary"}
                    icon={isExtracting ? <Loader2 className="w-4 h-4 animate-spin" /> : <ImageIcon className="w-4 h-4" />}
                >
                    {isExtracting ? "Extracting..." : frameUrl ? "Re-extract Frame" : "Extract Last Frame"}
                </Button>
            </BaseNodeFooter>

            <Handle type="source" position={Position.Right} />
        </BaseNode>
    );
});
