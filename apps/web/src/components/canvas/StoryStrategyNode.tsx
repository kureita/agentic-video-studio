"use client";

import { memo } from "react";
import { NodeProps } from "@xyflow/react";
import { Target, Sparkles, Loader2, RefreshCw, Clock, Zap, TrendingUp } from "lucide-react";
import {
    BaseNode,
    BaseNodeHeader,
    BaseNodeContent,
    BaseNodeFooter,
    BaseNodeError
} from "./BaseNode";
import { Button } from "@/components/ui";
import { useCanvasStore, StoryStrategy } from "@/lib/canvas-store";
import { strategyApi } from "@/lib/api";

interface StoryStrategyNodeData {
    onProceed?: () => void;
    [key: string]: unknown;
}

export const StoryStrategyNode = memo(function StoryStrategyNode({ data }: NodeProps) {
    const nodeData = data as StoryStrategyNodeData;
    const {
        brandData,
        trendData,
        inspirationBrief,
        nodeStatuses,
        setNodeStatus,
        setError,
        errors,
        setStoryStrategy,
        storyStrategy,
        storyOptions,
    } = useCanvasStore();

    const isLoading = nodeStatuses.strategy === "loading";
    const isSuccess = nodeStatuses.strategy === "success";
    const canGenerate = brandData && trendData;

    const handleGenerateStrategy = async () => {
        if (!brandData || !trendData) return;

        setNodeStatus("strategy", "loading");
        setError("strategy", null);

        try {
            const response = await strategyApi.generate({
                brand_name: brandData.name,
                brand_description: brandData.description,
                trend_query: trendData.query,
                trend_summary: trendData.summary,
                inspiration_ideas: inspirationBrief?.contentIdeas || [],
                target_platform: trendData.platform,
                content_duration: storyOptions.duration,
                target_audience: storyOptions.targetAudience,
            });

            const data = response.data;

            // Convert API response to store format
            setStoryStrategy({
                objective: data.objective,
                keyMessage: data.key_message,
                emotionalArc: data.emotional_arc,
                hooks: data.hooks.map(h => ({
                    type: h.type,
                    content: h.content,
                    placement: h.placement,
                })),
                contentStructure: data.content_structure.map(b => ({
                    name: b.name,
                    description: b.description,
                    durationSeconds: b.duration_seconds,
                    purpose: b.purpose,
                })),
                callToAction: data.call_to_action,
                metrics: {
                    targetAudience: data.metrics.target_audience,
                    platform: data.metrics.platform,
                    contentDuration: data.metrics.content_duration,
                    tone: data.metrics.tone,
                    brandAlignmentScore: data.metrics.brand_alignment_score,
                    viralPotentialScore: data.metrics.viral_potential_score,
                },
                aiRecommendations: data.ai_recommendations,
            });

            setNodeStatus("strategy", "success");

            if (nodeData?.onProceed) {
                nodeData.onProceed();
            }
        } catch (err) {
            console.error("Failed to generate strategy:", err);
            setNodeStatus("strategy", "error");
            setError("strategy", err instanceof Error ? err.message : "Failed to generate strategy");
        }
    };

    if (!canGenerate) {
        return (
            <BaseNode status="idle">
                <BaseNodeHeader icon={<Target className="w-4 h-4" />}>
                    Story Strategy
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
        <BaseNode status={nodeStatuses.strategy}>
            <BaseNodeHeader icon={<Target className="w-4 h-4" />} status={nodeStatuses.strategy}>
                Story Strategy
            </BaseNodeHeader>

            <BaseNodeContent>
                {!isSuccess ? (
                    <>
                        <p className="text-sm text-foreground-muted mb-4">
                            Generate a content strategy with hooks, beats, and recommendations.
                        </p>

                        <div className="grid grid-cols-2 gap-2 p-3 rounded-lg bg-background-secondary">
                            <div className="flex items-center gap-2">
                                <Clock className="w-3 h-3 text-foreground-subtle" />
                                <span className="text-xs text-foreground">{storyOptions.duration}s</span>
                            </div>
                            <div className="flex items-center gap-2">
                                <TrendingUp className="w-3 h-3 text-foreground-subtle" />
                                <span className="text-xs text-foreground">{trendData.platform}</span>
                            </div>
                        </div>
                    </>
                ) : storyStrategy ? (
                    <div className="space-y-4 max-h-[350px] overflow-y-auto nowheel">
                        {/* Objective */}
                        <div className="p-3 rounded-lg bg-accent/10 border border-accent/20">
                            <h4 className="text-xs font-medium text-accent mb-1">Objective</h4>
                            <p className="text-sm text-foreground">{storyStrategy.objective}</p>
                        </div>

                        {/* Emotional Arc */}
                        <div>
                            <h4 className="text-xs font-medium text-foreground-muted mb-2">Emotional Arc</h4>
                            <p className="text-sm text-foreground">{storyStrategy.emotionalArc}</p>
                        </div>

                        {/* Hooks */}
                        <div>
                            <h4 className="text-xs font-medium text-foreground-muted mb-2">Hooks</h4>
                            <div className="space-y-2">
                                {storyStrategy.hooks.map((hook, idx) => (
                                    <div key={idx} className="flex items-start gap-2 text-sm">
                                        <span className="px-1.5 py-0.5 text-xs rounded bg-background-secondary text-foreground-muted">
                                            {hook.placement}
                                        </span>
                                        <span className="text-foreground">{hook.content}</span>
                                    </div>
                                ))}
                            </div>
                        </div>

                        {/* Content Structure */}
                        <div>
                            <h4 className="text-xs font-medium text-foreground-muted mb-2">Content Beats</h4>
                            <div className="space-y-1">
                                {storyStrategy.contentStructure.map((beat, idx) => (
                                    <div key={idx} className="flex items-center justify-between p-2 rounded bg-background-secondary">
                                        <div className="flex items-center gap-2">
                                            <span className="w-5 h-5 flex items-center justify-center text-xs font-medium rounded-full bg-background">
                                                {idx + 1}
                                            </span>
                                            <span className="text-sm text-foreground">{beat.name}</span>
                                        </div>
                                        <span className="text-xs text-foreground-muted">{beat.durationSeconds}s</span>
                                    </div>
                                ))}
                            </div>
                        </div>

                        {/* Metrics */}
                        <div className="grid grid-cols-2 gap-2">
                            <div className="p-2 rounded bg-background-secondary text-center">
                                <Zap className="w-4 h-4 mx-auto mb-1 text-amber-500" />
                                <p className="text-xs text-foreground-muted">Viral Potential</p>
                                <p className="text-sm font-medium text-foreground">
                                    {Math.round(storyStrategy.metrics.viralPotentialScore * 100)}%
                                </p>
                            </div>
                            <div className="p-2 rounded bg-background-secondary text-center">
                                <Target className="w-4 h-4 mx-auto mb-1 text-emerald-500" />
                                <p className="text-xs text-foreground-muted">Brand Fit</p>
                                <p className="text-sm font-medium text-foreground">
                                    {Math.round(storyStrategy.metrics.brandAlignmentScore * 100)}%
                                </p>
                            </div>
                        </div>

                        {/* AI Recommendations */}
                        <div>
                            <h4 className="text-xs font-medium text-foreground-muted mb-2">AI Recommendations</h4>
                            <div className="space-y-1">
                                {storyStrategy.aiRecommendations.slice(0, 4).map((rec, idx) => (
                                    <div key={idx} className="flex items-start gap-2 text-xs">
                                        <Sparkles className="w-3 h-3 text-accent shrink-0 mt-0.5" />
                                        <span className="text-foreground">{rec}</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                ) : null}
            </BaseNodeContent>

            <BaseNodeError message={errors.strategy} />

            <BaseNodeFooter>
                <Button
                    onClick={handleGenerateStrategy}
                    disabled={isLoading}
                    className="w-full nodrag"
                    icon={isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : isSuccess ? <RefreshCw className="w-4 h-4" /> : <Sparkles className="w-4 h-4" />}
                >
                    {isLoading ? "Generating..." : isSuccess ? "Regenerate Strategy" : "Generate Strategy"}
                </Button>
            </BaseNodeFooter>
        </BaseNode>
    );
});
