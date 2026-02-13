"use client";

import { memo, useState } from "react";
import { NodeProps, Node } from "@xyflow/react";
import { Layers, Sparkles, Loader2, Check, Settings2 } from "lucide-react";
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
import { toast } from "sonner";

type CompositionNodeData = {
  onProceed?: () => void;
};

const transitionOptions = [
  { id: "fade", label: "Fade" },
  { id: "cut", label: "Cut" },
  { id: "dissolve", label: "Dissolve" },
];

export const CompositionNode = memo(function CompositionNode({ data }: NodeProps<Node<CompositionNodeData>>) {
  const {
    projectId,
    scenes,
    nodeStatuses,
    setNodeStatus,
    setError,
    errors,
    setCompositionUrl,
    compositionUrl,
  } = useCanvasStore();

  const [showSettings, setShowSettings] = useState(false);
  const [transition, setTransition] = useState("fade");
  const [showBrandWatermark, setShowBrandWatermark] = useState(true);
  const [showCTA, setShowCTA] = useState(true);

  const isLoading = nodeStatuses.composition === "loading";
  const hasVideos = scenes.some((s) => s.video_url);
  const isSuccess = nodeStatuses.composition === "success";

  const handleCompose = async () => {
    if (!projectId || !hasVideos) return;

    setNodeStatus("composition", "loading");
    setError("composition", null);

    try {
      const response = await canvasApi.compose(projectId, {
        transition,
        show_brand_watermark: showBrandWatermark,
        show_cta: showCTA,
      });

      setCompositionUrl(response.data.preview_url);
      setNodeStatus("composition", "success");
      toast.success("Video composed successfully");
      if (data?.onProceed) {
        data.onProceed();
      }
    } catch (err) {
      console.error("Failed to compose video:", err);
      setNodeStatus("composition", "error");
      setError("composition", err instanceof Error ? err.message : "Failed to compose video");
      toast.error("Failed to compose video");
    }
  };

  if (!hasVideos) {
    return (
      <BaseNode status="idle">
        <BaseNodeHeader icon={<Layers className="w-4 h-4" />}>
          Composition
        </BaseNodeHeader>
        <BaseNodeContent>
          <p className="text-sm text-foreground-muted">
            Waiting for video clips...
          </p>
        </BaseNodeContent>
      </BaseNode>
    );
  }

  return (
    <BaseNode status={nodeStatuses.composition}>
      <BaseNodeHeader icon={<Layers className="w-4 h-4" />} status={nodeStatuses.composition}>
        Composition
      </BaseNodeHeader>

      <BaseNodeContent>
        <div className="p-3 rounded-lg bg-background-secondary mb-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-foreground">
                {scenes.filter(s => s.video_url).length} clips ready
              </p>
              <p className="text-xs text-foreground-muted">
                ~{scenes.length * 8}s total
              </p>
            </div>
            <button
              onClick={() => setShowSettings(!showSettings)}
              className={`p-2 rounded-lg transition-colors nodrag ${showSettings ? "bg-background" : "hover:bg-background"
                }`}
            >
              <Settings2 className="w-4 h-4 text-foreground-subtle" />
            </button>
          </div>
        </div>

        {showSettings && (
          <div className="space-y-4 p-3 rounded-lg border border-border mb-4">
            <div>
              <label className="block text-xs font-medium text-foreground mb-2">Transitions</label>
              <div className="flex gap-2">
                {transitionOptions.map((opt) => (
                  <button
                    key={opt.id}
                    onClick={() => setTransition(opt.id)}
                    className={`flex-1 p-2 rounded-lg border text-xs transition-colors nodrag ${transition === opt.id
                      ? "border-foreground bg-background-secondary"
                      : "border-border"
                      }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="space-y-2">
              <label className="flex items-center gap-2 text-xs nodrag cursor-pointer">
                <input
                  type="checkbox"
                  checked={showBrandWatermark}
                  onChange={(e) => setShowBrandWatermark(e.target.checked)}
                  className="w-3 h-3"
                />
                <span>Brand watermark</span>
              </label>
              <label className="flex items-center gap-2 text-xs nodrag cursor-pointer">
                <input
                  type="checkbox"
                  checked={showCTA}
                  onChange={(e) => setShowCTA(e.target.checked)}
                  className="w-3 h-3"
                />
                <span>Call to action</span>
              </label>
            </div>
          </div>
        )}

        {compositionUrl && (
          <div className="aspect-video rounded-lg overflow-hidden bg-black mb-4">
            <video src={compositionUrl} className="w-full h-full object-contain" controls />
          </div>
        )}
      </BaseNodeContent>

      <BaseNodeError message={errors.composition} />

      <BaseNodeFooter>
        <Button
          onClick={handleCompose}
          disabled={isLoading}
          className="w-full nodrag"
          icon={isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : isSuccess ? <Check className="w-4 h-4" /> : <Sparkles className="w-4 h-4" />}
        >
          {isLoading ? "Composing..." : isSuccess ? "Re-compose" : "Compose Video"}
        </Button>
      </BaseNodeFooter>
    </BaseNode>
  );
});
