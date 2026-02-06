"use client";

import { memo, useState } from "react";
import { NodeProps } from "@xyflow/react";
import { Lightbulb, Sparkles, Loader2, Check, RefreshCw } from "lucide-react";
import {
    BaseNode,
    BaseNodeHeader,
    BaseNodeContent,
    BaseNodeFooter,
    BaseNodeError
} from "./BaseNode";
import { Button } from "@/components/ui";
import { useCanvasStore, InspirationBrief } from "@/lib/canvas-store";
import { trendsApi } from "@/lib/api";

interface InspirationNodeData {
    onProceed?: () => void;
    [key: string]: unknown;
}

export const InspirationNode = memo(function InspirationNode({ data }: NodeProps) {
    const nodeData = data as InspirationNodeData;
    const {
        brandData,
        trendData,
        nodeStatuses,
        setNodeStatus,
        setError,
        errors,
        setInspirationBrief,
        inspirationBrief,
    } = useCanvasStore();

    const isLoading = nodeStatuses.inspiration === "loading";
    const isSuccess = nodeStatuses.inspiration === "success";
    const canGenerate = brandData && trendData;

    const handleGenerateBrief = async () => {
        if (!brandData || !trendData) return;

        setNodeStatus("inspiration", "loading");
        setError("inspiration", null);

        try {
            const response = await trendsApi.generateBrief(
                brandData.name,
                brandData.description || "",
                trendData.query
            );

            const brief = response.data;

            // Convert API response to store format
            setInspirationBrief({
                brandName: brief.brand_name,
                trendSummary: brief.trend_summary,
                keyElements: brief.key_elements,
                suggestedAngles: brief.suggested_angles,
                viralHooks: brief.viral_hooks,
                contentIdeas: brief.content_ideas,
            });

            setNodeStatus("inspiration", "success");

            if (nodeData?.onProceed) {
                nodeData.onProceed();
            }
        } catch (err) {
            console.error("Failed to generate brief:", err);
            setNodeStatus("inspiration", "error");
            setError("inspiration", err instanceof Error ? err.message : "Failed to generate brief");
        }
    };

    if (!canGenerate) {
        return (
            <BaseNode status="idle">
                <BaseNodeHeader icon={<Lightbulb className="w-4 h-4" />}>
                    Inspiration Brief
                </BaseNodeHeader>
                <BaseNodeContent>
                    <p className="text-sm text-foreground-muted">
                        Waiting for brand and trend data...
                    </p>
                </BaseNodeContent>
            </BaseNode>
        );
    }

    return (
        <BaseNode status={nodeStatuses.inspiration}>
            <BaseNodeHeader icon={<Lightbulb className="w-4 h-4" />} status={nodeStatuses.inspiration}>
                Inspiration Brief
            </BaseNodeHeader>

            <BaseNodeContent>
                {!isSuccess ? (
                    <>
                        <p className="text-sm text-foreground-muted mb-4">
                            Combine brand context with trend research to generate creative ideas.
                        </p>

                        <div className="space-y-2 p-3 rounded-lg bg-background-secondary">
                            <div className="flex items-center gap-2">
                                <span className="text-xs text-foreground-muted">Brand:</span>
                                <span className="text-sm font-medium text-foreground">{brandData.name}</span>
                            </div>
                            <div className="flex items-center gap-2">
                                <span className="text-xs text-foreground-muted">Trend:</span>
                                <span className="text-sm font-medium text-foreground">{trendData.query}</span>
                            </div>
                        </div>
                    </>
                ) : inspirationBrief ? (
                    <div className="space-y-4">
                        {/* Summary */}
                        <div className="p-3 rounded-lg bg-accent/10 border border-accent/20">
                            <p className="text-sm text-foreground">{inspirationBrief.trendSummary}</p>
                        </div>

                        {/* Suggested Angles */}
                        <div>
                            <h4 className="text-xs font-medium text-foreground-muted mb-2">Suggested Angles</h4>
                            <div className="space-y-1">
                                {inspirationBrief.suggestedAngles.map((angle, idx) => (
                                    <div key={idx} className="flex items-start gap-2 text-sm">
                                        <span className="text-accent">•</span>
                                        <span className="text-foreground">{angle}</span>
                                    </div>
                                ))}
                            </div>
                        </div>

                        {/* Viral Hooks */}
                        <div>
                            <h4 className="text-xs font-medium text-foreground-muted mb-2">Viral Hooks</h4>
                            <div className="flex flex-wrap gap-1">
                                {inspirationBrief.viralHooks.map((hook, idx) => (
                                    <span
                                        key={idx}
                                        className="px-2 py-1 text-xs rounded-full bg-background-secondary text-foreground"
                                    >
                                        {hook}
                                    </span>
                                ))}
                            </div>
                        </div>

                        {/* Content Ideas */}
                        <div>
                            <h4 className="text-xs font-medium text-foreground-muted mb-2">Content Ideas</h4>
                            <div className="space-y-1 max-h-[120px] overflow-y-auto nowheel">
                                {inspirationBrief.contentIdeas.map((idea, idx) => (
                                    <div key={idx} className="p-2 text-sm rounded bg-background-secondary text-foreground">
                                        {idea}
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                ) : null}
            </BaseNodeContent>

            <BaseNodeError message={errors.inspiration} />

            <BaseNodeFooter>
                <Button
                    onClick={handleGenerateBrief}
                    disabled={isLoading}
                    className="w-full nodrag"
                    icon={isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : isSuccess ? <RefreshCw className="w-4 h-4" /> : <Sparkles className="w-4 h-4" />}
                >
                    {isLoading ? "Generating..." : isSuccess ? "Regenerate Brief" : "Generate Brief"}
                </Button>
            </BaseNodeFooter>
        </BaseNode>
    );
});
