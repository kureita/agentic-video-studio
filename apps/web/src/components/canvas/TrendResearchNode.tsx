"use client";

import { memo, useState } from "react";
import { NodeProps } from "@xyflow/react";
import { TrendingUp, Search, Loader2, ExternalLink, ChevronDown, Sparkles } from "lucide-react";
import {
    BaseNode,
    BaseNodeHeader,
    BaseNodeContent,
    BaseNodeFooter,
    BaseNodeError
} from "./BaseNode";
import { Button, Input } from "@/components/ui";
import { useCanvasStore } from "@/lib/canvas-store";
import { trendsApi, TrendResearchResult, SearchResult } from "@/lib/api";

interface TrendResearchNodeData {
    onProceed?: () => void;
    [key: string]: unknown;
}

const platformOptions = [
    { id: "general", label: "General" },
    { id: "tiktok", label: "TikTok" },
    { id: "instagram", label: "Instagram" },
    { id: "youtube", label: "YouTube" },
];

export const TrendResearchNode = memo(function TrendResearchNode({ data }: NodeProps) {
    const nodeData = data as TrendResearchNodeData;
    const {
        nodeStatuses,
        setNodeStatus,
        setError,
        errors,
        setTrendData,
        trendData,
    } = useCanvasStore();

    const [searchQuery, setSearchQuery] = useState("");
    const [platform, setPlatform] = useState("general");
    const [showPlatforms, setShowPlatforms] = useState(false);
    const [results, setResults] = useState<SearchResult[]>([]);
    const [summary, setSummary] = useState<string | null>(null);

    const isLoading = nodeStatuses.trend === "loading";
    const isSuccess = nodeStatuses.trend === "success";

    const handleSearch = async () => {
        if (!searchQuery.trim()) return;

        setNodeStatus("trend", "loading");
        setError("trend", null);

        try {
            const response = await trendsApi.searchViral(searchQuery, platform);
            const data = response.data;

            setResults(data.results);
            setSummary(data.summary || null);

            // Store in canvas state for use by InspirationNode
            setTrendData({
                query: searchQuery,
                platform,
                results: data.results,
                summary: data.summary,
            });

            setNodeStatus("trend", "success");

            if (nodeData?.onProceed) {
                nodeData.onProceed();
            }
        } catch (err) {
            console.error("Failed to search trends:", err);
            setNodeStatus("trend", "error");
            setError("trend", err instanceof Error ? err.message : "Failed to search trends");
        }
    };

    const selectedPlatform = platformOptions.find(p => p.id === platform);

    return (
        <BaseNode status={nodeStatuses.trend}>
            <BaseNodeHeader icon={<TrendingUp className="w-4 h-4" />} status={nodeStatuses.trend}>
                Trend Research
            </BaseNodeHeader>

            <BaseNodeContent>
                <p className="text-sm text-foreground-muted mb-4">
                    Search for viral trends and content inspiration.
                </p>

                <div className="space-y-3">
                    {/* Search Input */}
                    <Input
                        placeholder="e.g., nihilist penguin, day in my life..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        disabled={isLoading}
                        className="nodrag"
                        onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                    />

                    {/* Platform Selector */}
                    <div className="relative">
                        <button
                            onClick={() => setShowPlatforms(!showPlatforms)}
                            disabled={isLoading}
                            className="w-full flex items-center justify-between p-2 rounded-lg border border-border hover:border-foreground-subtle bg-background-secondary text-left text-sm transition-colors nodrag"
                        >
                            <span className="text-foreground">{selectedPlatform?.label}</span>
                            <ChevronDown className={`w-4 h-4 text-foreground-subtle transition-transform ${showPlatforms ? "rotate-180" : ""}`} />
                        </button>

                        {showPlatforms && (
                            <div className="absolute z-10 w-full mt-1 py-1 bg-background border border-border rounded-lg shadow-lg nowheel">
                                {platformOptions.map(opt => (
                                    <button
                                        key={opt.id}
                                        onClick={() => {
                                            setPlatform(opt.id);
                                            setShowPlatforms(false);
                                        }}
                                        className={`w-full px-3 py-2 text-left text-sm hover:bg-background-secondary nodrag ${platform === opt.id ? "bg-background-secondary font-medium" : ""
                                            }`}
                                    >
                                        {opt.label}
                                    </button>
                                ))}
                            </div>
                        )}
                    </div>
                </div>

                {/* Results */}
                {isSuccess && results.length > 0 && (
                    <div className="mt-4 space-y-3">
                        {summary && (
                            <div className="p-3 rounded-lg bg-accent/10 border border-accent/20">
                                <div className="flex items-start gap-2">
                                    <Sparkles className="w-4 h-4 text-accent mt-0.5 shrink-0" />
                                    <p className="text-sm text-foreground">{summary}</p>
                                </div>
                            </div>
                        )}

                        <div className="space-y-2 max-h-[200px] overflow-y-auto nowheel">
                            {results.slice(0, 4).map((result, idx) => (
                                <div key={idx} className="p-2 rounded-lg bg-background-secondary">
                                    <div className="flex items-start justify-between gap-2">
                                        <div className="flex-1 min-w-0">
                                            <p className="text-sm font-medium text-foreground truncate">{result.title}</p>
                                            <p className="text-xs text-foreground-muted line-clamp-2 mt-1">{result.content}</p>
                                        </div>
                                        {result.url && (
                                            <a
                                                href={result.url}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                className="p-1 hover:bg-background rounded shrink-0 nodrag"
                                            >
                                                <ExternalLink className="w-3 h-3 text-foreground-subtle" />
                                            </a>
                                        )}
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                )}
            </BaseNodeContent>

            <BaseNodeError message={errors.trend} />

            <BaseNodeFooter>
                <Button
                    onClick={handleSearch}
                    disabled={!searchQuery.trim() || isLoading}
                    className="w-full nodrag"
                    icon={isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
                >
                    {isLoading ? "Searching..." : isSuccess ? "Search Again" : "Search Trends"}
                </Button>
            </BaseNodeFooter>
        </BaseNode>
    );
});
