"use client";

import { memo, useState } from "react";
import { NodeProps } from "@xyflow/react";
import { Download, Loader2, Check, Play, Share2, Film } from "lucide-react";
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

type RenderNodeData = Record<string, unknown>;

const resolutionOptions = [
  { id: "720p", label: "720p" },
  { id: "1080p", label: "1080p" },
  { id: "4k", label: "4K" },
];

export const RenderNode = memo(function RenderNode({}: NodeProps<RenderNodeData>) {
  const {
    projectId,
    compositionUrl,
    nodeStatuses,
    setNodeStatus,
    setError,
    errors,
    setFinalVideoUrl,
    finalVideoUrl,
  } = useCanvasStore();

  const [resolution, setResolution] = useState("1080p");
  const [showVideo, setShowVideo] = useState(false);

  const isLoading = nodeStatuses.render === "loading";
  const hasComposition = !!compositionUrl;

  const handleRender = async () => {
    if (!projectId || !hasComposition) return;

    setNodeStatus("render", "loading");
    setError("render", null);

    try {
      const response = await canvasApi.render(projectId, { resolution });
      setFinalVideoUrl(response.data.video_url);
      setNodeStatus("render", "success");
    } catch (err) {
      console.error("Failed to render video:", err);
      setNodeStatus("render", "error");
      setError("render", err instanceof Error ? err.message : "Failed to render video");
    }
  };

  const handleDownload = () => {
    if (finalVideoUrl) {
      const a = document.createElement("a");
      a.href = finalVideoUrl;
      a.download = "video.mp4";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    }
  };

  if (!hasComposition) {
    return (
      <BaseNode status="idle" hasOutput={false}>
        <BaseNodeHeader icon={<Download className="w-4 h-4" />}>
          Final Render
        </BaseNodeHeader>
        <BaseNodeContent>
          <p className="text-sm text-foreground-muted">
            Waiting for composition...
          </p>
        </BaseNodeContent>
      </BaseNode>
    );
  }

  return (
    <BaseNode status={nodeStatuses.render} hasOutput={false}>
      <BaseNodeHeader icon={<Download className="w-4 h-4" />} status={nodeStatuses.render}>
        Final Render
      </BaseNodeHeader>

      <BaseNodeContent>
        {!finalVideoUrl ? (
          <>
            <p className="text-sm text-foreground-muted mb-4">
              Export your video in high quality.
            </p>

            <div className="mb-4">
              <label className="block text-xs font-medium text-foreground mb-2">Resolution</label>
              <div className="flex gap-2">
                {resolutionOptions.map((opt) => (
                  <button
                    key={opt.id}
                    onClick={() => setResolution(opt.id)}
                    className={`flex-1 p-2 rounded-lg border text-center transition-colors nodrag ${
                      resolution === opt.id
                        ? "border-foreground bg-background-secondary"
                        : "border-border"
                    }`}
                  >
                    <p className="font-medium text-foreground text-sm">{opt.label}</p>
                  </button>
                ))}
              </div>
            </div>
          </>
        ) : (
          <>
            <div className="aspect-video rounded-lg overflow-hidden bg-black mb-4 relative">
              {showVideo ? (
                <video src={finalVideoUrl} className="w-full h-full object-contain" controls autoPlay />
              ) : (
                <button
                  onClick={() => setShowVideo(true)}
                  className="w-full h-full flex items-center justify-center group nodrag"
                >
                  <div className="w-14 h-14 rounded-full bg-white/90 flex items-center justify-center shadow-lg group-hover:scale-110 transition-transform">
                    <Play className="w-5 h-5 text-gray-900 ml-1" />
                  </div>
                </button>
              )}
            </div>

            <div className="flex items-center justify-center gap-2 p-2 rounded-lg bg-emerald-500/10 text-emerald-600 mb-4">
              <Check className="w-4 h-4" />
              <span className="text-sm">Video ready!</span>
            </div>
          </>
        )}
      </BaseNodeContent>

      <BaseNodeError message={errors.render} />

      <BaseNodeFooter>
        {!finalVideoUrl ? (
          <Button
            onClick={handleRender}
            disabled={isLoading}
            className="w-full nodrag"
            icon={isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Film className="w-4 h-4" />}
          >
            {isLoading ? "Rendering..." : "Render Final Video"}
          </Button>
        ) : (
          <div className="flex gap-2">
            <Button onClick={handleDownload} className="flex-1 nodrag" icon={<Download className="w-4 h-4" />}>
              Download
            </Button>
            <Button variant="outline" className="flex-1 nodrag" icon={<Share2 className="w-4 h-4" />}>
              Share
            </Button>
          </div>
        )}
      </BaseNodeFooter>
    </BaseNode>
  );
});
