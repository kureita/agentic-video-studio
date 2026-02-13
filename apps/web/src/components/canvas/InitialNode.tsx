"use client";

import { memo, useState } from "react";
import { NodeProps, Node } from "@xyflow/react";
import { Globe, ArrowRight, Loader2 } from "lucide-react";
import {
  BaseNode,
  BaseNodeHeader,
  BaseNodeContent,
  BaseNodeFooter,
  BaseNodeError
} from "./BaseNode";
import { Button, Input } from "@/components/ui";
import { useCanvasStore } from "@/lib/canvas-store";
import { canvasApi } from "@/lib/api";
import { toast } from "sonner";

type InitialNodeData = {
  onProceed?: () => void;
};

export const InitialNode = memo(function InitialNode({ data }: NodeProps<Node<InitialNodeData>>) {
  const {
    websiteUrl,
    setWebsiteUrl,
    setProjectId,
    setBrandData,
    nodeStatuses,
    setNodeStatus,
    setError,
    errors,
  } = useCanvasStore();

  const [localUrl, setLocalUrl] = useState(websiteUrl || "");
  const isValid = localUrl.startsWith("http");
  const isLoading = nodeStatuses.brand === "loading";
  const isSuccess = nodeStatuses.brand === "success";

  const handleAnalyze = async () => {
    if (!isValid) return;

    setWebsiteUrl(localUrl);
    setNodeStatus("brand", "loading");
    setError("brand", null);

    try {
      const response = await canvasApi.create({ website_url: localUrl });
      const { project_id, brand_profile } = response.data;

      setProjectId(project_id);
      setBrandData(brand_profile);
      setNodeStatus("brand", "success");
      toast.success("Brand analysis complete");

      // Proceed to next node
      if (data?.onProceed) {
        data.onProceed();
      }
    } catch (err) {
      console.error("Failed to analyze website:", err);
      setNodeStatus("brand", "error");
      setError("brand", err instanceof Error ? err.message : "Failed to analyze website");
      toast.error("Failed to analyze website");
    }
  };

  return (
    <BaseNode hasInput={false} status={nodeStatuses.brand}>
      <BaseNodeHeader icon={<Globe className="w-4 h-4" />} status={nodeStatuses.brand}>
        Start
      </BaseNodeHeader>

      <BaseNodeContent>
        <p className="text-sm text-foreground-muted mb-4">
          Enter your website URL to begin. We&apos;ll analyze your brand and create a video.
        </p>

        <Input
          placeholder="https://yourbrand.com"
          value={localUrl}
          onChange={(e) => setLocalUrl(e.target.value)}
          disabled={isLoading || isSuccess}
          className="nodrag"
        />
      </BaseNodeContent>

      <BaseNodeError message={errors.brand} />

      <BaseNodeFooter>
        <Button
          onClick={handleAnalyze}
          disabled={!isValid || isLoading || isSuccess}
          className="w-full nodrag"
          icon={
            isLoading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <ArrowRight className="w-4 h-4" />
            )
          }
          iconPosition="right"
        >
          {isLoading ? "Analyzing..." : isSuccess ? "Analyzed ✓" : "Analyze Website"}
        </Button>
      </BaseNodeFooter>
    </BaseNode>
  );
});
