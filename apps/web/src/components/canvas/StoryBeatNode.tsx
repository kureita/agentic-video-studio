"use client";

import { memo, useState } from "react";
import { NodeProps, Handle, Position } from "@xyflow/react";
import { Film, Pencil, Check, X, Image, Video, Clock, Sparkles } from "lucide-react";
import {
    BaseNode,
    BaseNodeHeader,
    BaseNodeContent,
    BaseNodeFooter,
    BaseNodeError
} from "./BaseNode";
import { Button, Textarea, Input } from "@/components/ui";
import { useCanvasStore, StoryBeat } from "@/lib/canvas-store";

interface StoryBeatNodeData {
    beatId: string;
    onGenerateImage?: (beatId: string) => void;
    onGenerateVideo?: (beatId: string) => void;
    [key: string]: unknown;
}

export const StoryBeatNode = memo(function StoryBeatNode({ data }: NodeProps) {
    const nodeData = data as StoryBeatNodeData;
    const { storyBeats, updateStoryBeat, errors } = useCanvasStore();

    const beat = storyBeats.find(b => b.id === nodeData.beatId);

    const [isEditing, setIsEditing] = useState(false);
    const [editedScript, setEditedScript] = useState("");
    const [editedVisualPrompt, setEditedVisualPrompt] = useState("");

    if (!beat) {
        return (
            <BaseNode status="idle">
                <BaseNodeHeader icon={<Film className="w-4 h-4" />}>
                    Beat Not Found
                </BaseNodeHeader>
                <BaseNodeContent>
                    <p className="text-sm text-foreground-muted">Beat data not available.</p>
                </BaseNodeContent>
            </BaseNode>
        );
    }

    const handleStartEdit = () => {
        setEditedScript(beat.script);
        setEditedVisualPrompt(beat.visualPrompt);
        setIsEditing(true);
    };

    const handleSaveEdit = () => {
        updateStoryBeat(beat.id, {
            script: editedScript,
            visualPrompt: editedVisualPrompt,
        });
        setIsEditing(false);
    };

    const handleCancelEdit = () => {
        setIsEditing(false);
    };

    const statusToNodeStatus = (status: StoryBeat["generationStatus"]) => {
        if (status === "generating") return "loading";
        if (status === "complete") return "success";
        if (status === "error") return "error";
        return "idle";
    };

    return (
        <BaseNode status={statusToNodeStatus(beat.generationStatus)}>
            {/* Input handle for connection from previous beat/strategy */}
            <Handle type="target" position={Position.Top} className="!bg-foreground-subtle !w-3 !h-3" />

            <BaseNodeHeader
                icon={<Film className="w-4 h-4" />}
                status={statusToNodeStatus(beat.generationStatus)}
            >
                <div className="flex items-center gap-2">
                    <span className="px-1.5 py-0.5 text-xs rounded bg-background-secondary">
                        {beat.index + 1}
                    </span>
                    {beat.name}
                </div>
            </BaseNodeHeader>

            <BaseNodeContent>
                {!isEditing ? (
                    <div className="space-y-3">
                        {/* Duration & Purpose */}
                        <div className="flex items-center justify-between text-xs">
                            <div className="flex items-center gap-1 text-foreground-muted">
                                <Clock className="w-3 h-3" />
                                <span>{beat.durationSeconds}s</span>
                            </div>
                            <span className="text-foreground-subtle">{beat.purpose}</span>
                        </div>

                        {/* Description */}
                        <p className="text-sm text-foreground">{beat.description}</p>

                        {/* Script */}
                        <div className="p-2 rounded bg-background-secondary">
                            <p className="text-xs font-medium text-foreground-muted mb-1">Script</p>
                            <p className="text-sm text-foreground">{beat.script}</p>
                        </div>

                        {/* Visual Prompt */}
                        <div className="p-2 rounded border border-border">
                            <p className="text-xs font-medium text-foreground-muted mb-1">Visual Prompt</p>
                            <p className="text-xs text-foreground-subtle">{beat.visualPrompt}</p>
                        </div>

                        {/* Generated Media */}
                        {beat.imageUrl && (
                            <div className="aspect-video rounded-lg overflow-hidden bg-black">
                                <img src={beat.imageUrl} alt={beat.name} className="w-full h-full object-cover" />
                            </div>
                        )}

                        {beat.videoUrl && (
                            <div className="aspect-video rounded-lg overflow-hidden bg-black">
                                <video src={beat.videoUrl} className="w-full h-full object-cover" controls />
                            </div>
                        )}

                        {/* Hook if present */}
                        {beat.hook && (
                            <div className="flex items-start gap-2 p-2 rounded bg-accent/10">
                                <Sparkles className="w-3 h-3 text-accent mt-0.5 shrink-0" />
                                <p className="text-xs text-accent">{beat.hook}</p>
                            </div>
                        )}
                    </div>
                ) : (
                    <div className="space-y-3">
                        <div>
                            <label className="block text-xs font-medium text-foreground-muted mb-1">Script</label>
                            <Textarea
                                value={editedScript}
                                onChange={(e) => setEditedScript(e.target.value)}
                                className="nodrag text-sm"
                                rows={3}
                            />
                        </div>
                        <div>
                            <label className="block text-xs font-medium text-foreground-muted mb-1">Visual Prompt</label>
                            <Textarea
                                value={editedVisualPrompt}
                                onChange={(e) => setEditedVisualPrompt(e.target.value)}
                                className="nodrag text-sm"
                                rows={2}
                            />
                        </div>
                    </div>
                )}
            </BaseNodeContent>

            <BaseNodeError message={errors[`beat-${beat.id}`]} />

            <BaseNodeFooter>
                {!isEditing ? (
                    <div className="flex gap-2">
                        <Button
                            variant="outline"
                            onClick={handleStartEdit}
                            className="flex-1 nodrag"
                            icon={<Pencil className="w-3 h-3" />}
                        >
                            Edit
                        </Button>
                        {!beat.imageUrl && nodeData.onGenerateImage && (
                            <Button
                                variant="outline"
                                onClick={() => nodeData.onGenerateImage?.(beat.id)}
                                className="nodrag"
                                icon={<Image className="w-3 h-3" />}
                            />
                        )}
                        {beat.imageUrl && !beat.videoUrl && nodeData.onGenerateVideo && (
                            <Button
                                variant="outline"
                                onClick={() => nodeData.onGenerateVideo?.(beat.id)}
                                className="nodrag"
                                icon={<Video className="w-3 h-3" />}
                            />
                        )}
                    </div>
                ) : (
                    <div className="flex gap-2">
                        <Button
                            variant="outline"
                            onClick={handleCancelEdit}
                            className="flex-1 nodrag"
                            icon={<X className="w-3 h-3" />}
                        >
                            Cancel
                        </Button>
                        <Button
                            onClick={handleSaveEdit}
                            className="flex-1 nodrag"
                            icon={<Check className="w-3 h-3" />}
                        >
                            Save
                        </Button>
                    </div>
                )}
            </BaseNodeFooter>

            {/* Output handle for connection to next beat/image */}
            <Handle type="source" position={Position.Bottom} className="!bg-foreground-subtle !w-3 !h-3" />
        </BaseNode>
    );
});
