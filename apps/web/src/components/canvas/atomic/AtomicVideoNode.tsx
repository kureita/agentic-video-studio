"use client";

import { memo, useState } from "react";
import { NodeProps, Handle, Position } from "@xyflow/react";
import { Video, Film, PlayCircle } from "lucide-react";
import {
    BaseNode,
    BaseNodeHeader,
    BaseNodeContent,
} from "../BaseNode";

interface AtomicVideoData {
    aspectRatio?: "16:9" | "9:16" | "1:1";
    duration?: number;
    videoUrl?: string;
    [key: string]: unknown;
}

export const AtomicVideoNode = memo(function AtomicVideoNode({ data }: NodeProps) {
    const nodeData = data as AtomicVideoData;
    const aspectRatio = nodeData.aspectRatio || "16:9";

    // Calculate simulated dimensions for preview
    const isPortrait = aspectRatio === "9:16";
    const heightClass = isPortrait ? "h-64" : "h-32";
    const widthClass = isPortrait ? "w-36" : "w-full";

    return (
        <BaseNode status={nodeData.videoUrl ? "success" : "idle"} className="w-[300px]">
            <Handle type="target" position={Position.Left} className="!bg-foreground-subtle !w-3 !h-3" />

            <BaseNodeHeader icon={<Video className="w-4 h-4" />}>
                Video Generator ({aspectRatio})
            </BaseNodeHeader>

            <BaseNodeContent>
                <div className="flex justify-center bg-black/10 p-4 rounded-lg border border-border">
                    <div className={`bg-black rounded border border-white/10 flex items-center justify-center relative ${widthClass} ${heightClass}`}>
                        <div className="text-center">
                            <Film className="w-8 h-8 text-foreground-subtle mx-auto mb-2 opacity-50" />
                            <span className="text-xs text-foreground-muted">
                                {nodeData.duration || 15}s Output
                            </span>
                        </div>

                        {/* Play overlay simulation */}
                        <div className="absolute inset-0 flex items-center justify-center opacity-0 hover:opacity-100 bg-black/40 transition-opacity cursor-pointer">
                            <PlayCircle className="w-10 h-10 text-white" />
                        </div>
                    </div>
                </div>
            </BaseNodeContent>

            <Handle type="source" position={Position.Right} className="!bg-foreground-subtle !w-3 !h-3" />
        </BaseNode>
    );
});
