"use client";

import { memo, useState, useEffect } from "react";
import { NodeProps, Node } from "@xyflow/react";
import { Image as ImageIcon, Sparkles, Loader2, RotateCcw, Check, Pencil, X, Wand2 } from "lucide-react";
import {
  BaseNode,
  BaseNodeHeader,
  BaseNodeContent,
  BaseNodeFooter,
  BaseNodeError
} from "./BaseNode";
import { Button, Textarea } from "@/components/ui";
import { useCanvasStore, SceneData } from "@/lib/canvas-store";
import { canvasApi } from "@/lib/api";

type ImageNodeData = {
  onProceed?: () => void;
};

interface EditablePrompt {
  id: number;
  visual_prompt: string;
}

export const ImageNode = memo(function ImageNode({ data }: NodeProps<Node<ImageNodeData>>) {
  const {
    projectId,
    scenes,
    setScenes,
    updateScene,
    nodeStatuses,
    setNodeStatus,
    setError,
    errors,
    storyData,
    storyOptions,
  } = useCanvasStore();

  const [generatingScene, setGeneratingScene] = useState<number | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [editedPrompts, setEditedPrompts] = useState<EditablePrompt[]>([]);
  const [isImproving, setIsImproving] = useState(false);

  const isLoading = nodeStatuses.images === "loading";
  const hasScenes = scenes.length > 0;
  const allImagesGenerated = scenes.every((s) => s.image_url);

  // Initialize edit mode with current prompts
  useEffect(() => {
    if (scenes.length > 0 && editedPrompts.length === 0) {
      setEditedPrompts(scenes.map(s => ({
        id: s.id,
        visual_prompt: s.visual_prompt || s.description || "",
      })));
    }
  }, [scenes, editedPrompts.length]);

  const handleStartEdit = () => {
    setEditedPrompts(scenes.map(s => ({
      id: s.id,
      visual_prompt: s.visual_prompt || s.description || "",
    })));
    setIsEditing(true);
  };

  const handleCancelEdit = () => {
    setIsEditing(false);
  };

  const handleSavePrompts = () => {
    // Update scenes with edited prompts
    const updatedScenes = scenes.map(scene => {
      const edited = editedPrompts.find(p => p.id === scene.id);
      if (edited) {
        return { ...scene, visual_prompt: edited.visual_prompt };
      }
      return scene;
    });
    setScenes(updatedScenes);
    setIsEditing(false);
  };

  const handleUpdatePrompt = (id: number, value: string) => {
    setEditedPrompts(prev => prev.map(p =>
      p.id === id ? { ...p, visual_prompt: value } : p
    ));
  };

  const handleImproveWithAI = async () => {
    if (!projectId) return;

    setIsImproving(true);

    try {
      const response = await canvasApi.improveImagePrompts(projectId, {
        prompts: editedPrompts.map(p => ({
          scene_id: p.id,
          visual_prompt: p.visual_prompt,
        })),
        visual_style: storyOptions.visualStyle,
      });

      const { prompts: improvedPrompts } = response.data;
      setEditedPrompts(improvedPrompts.map((p: { scene_id: number; visual_prompt: string }) => ({
        id: p.scene_id,
        visual_prompt: p.visual_prompt,
      })));
    } catch (err) {
      console.error("Failed to improve prompts:", err);
    } finally {
      setIsImproving(false);
    }
  };

  const handleGenerateAllImages = async () => {
    if (!projectId || !hasScenes) return;

    setNodeStatus("images", "loading");
    setError("images", null);

    try {
      const response = await canvasApi.generateImages(projectId, {
        visual_style: storyOptions.visualStyle,
      });

      const { scenes: updatedScenes } = response.data;
      updatedScenes.forEach((scene: SceneData) => {
        updateScene(scene.id, {
          image_url: scene.image_url,
          image_prompt: scene.image_prompt,
        });
      });

      setNodeStatus("images", "success");
      if (data?.onProceed) {
        data.onProceed();
      }
    } catch (err) {
      console.error("Failed to generate images:", err);
      setNodeStatus("images", "error");
      setError("images", err instanceof Error ? err.message : "Failed to generate images");
    }
  };

  const handleRegenerateSingleImage = async (sceneId: number) => {
    if (!projectId) return;

    setGeneratingScene(sceneId);
    try {
      const scene = scenes.find((s) => s.id === sceneId);
      const response = await canvasApi.regenerateImage(projectId, sceneId, {
        prompt: scene?.image_prompt || scene?.visual_prompt,
        visual_style: storyOptions.visualStyle,
      });

      updateScene(sceneId, {
        image_url: response.data.image_url,
        image_prompt: response.data.image_prompt,
      });
    } catch (err) {
      console.error("Failed to regenerate image:", err);
    } finally {
      setGeneratingScene(null);
    }
  };

  if (!storyData || scenes.length === 0) {
    return (
      <BaseNode status="idle">
        <BaseNodeHeader icon={<ImageIcon className="w-4 h-4" />}>
          Image Generation
        </BaseNodeHeader>
        <BaseNodeContent>
          <p className="text-sm text-foreground-muted">
            Waiting for story and script...
          </p>
        </BaseNodeContent>
      </BaseNode>
    );
  }

  return (
    <BaseNode status={nodeStatuses.images}>
      <BaseNodeHeader icon={<ImageIcon className="w-4 h-4" />} status={nodeStatuses.images}>
        Image Generation
      </BaseNodeHeader>

      <BaseNodeContent className="max-h-[450px] overflow-y-auto nowheel">
        {/* Edit Mode - Before Generation */}
        {isEditing && !allImagesGenerated && (
          <div className="space-y-4">
            {/* AI Improve Button */}
            <div className="flex items-center justify-between">
              <p className="text-xs text-foreground-muted">
                Edit prompts for better image generation
              </p>
              <Button
                variant="outline"
                size="sm"
                onClick={handleImproveWithAI}
                disabled={isImproving}
                className="nodrag"
                icon={isImproving ? <Loader2 className="w-3 h-3 animate-spin" /> : <Wand2 className="w-3 h-3" />}
              >
                {isImproving ? "Improving..." : "Improve with AI"}
              </Button>
            </div>

            {/* Editable Prompts */}
            <div className="space-y-3 max-h-[300px] overflow-y-auto nowheel">
              {editedPrompts.map((prompt, idx) => (
                <div key={prompt.id} className="p-3 rounded-lg border border-border space-y-2">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono text-foreground-subtle px-2 py-0.5 bg-background-secondary rounded">
                      Scene {idx + 1}
                    </span>
                    <span className="text-xs text-foreground-muted">
                      {scenes[idx]?.start_time}s - {scenes[idx]?.end_time}s
                    </span>
                  </div>

                  <Textarea
                    value={prompt.visual_prompt}
                    onChange={(e) => handleUpdatePrompt(prompt.id, e.target.value)}
                    rows={3}
                    className="text-xs nodrag nowheel"
                    placeholder="Describe the visual for this scene..."
                  />
                </div>
              ))}
            </div>
          </div>
        )}

        {/* View Mode - Show Scenes */}
        {!isEditing && (
          <>
            <p className="text-sm text-foreground-muted mb-4">
              {allImagesGenerated
                ? "All images generated. You can regenerate individual images."
                : "Review and edit prompts before generating images."
              }
            </p>

            <div className="space-y-3">
              {scenes.map((scene) => (
                <div key={scene.id} className="p-3 rounded-lg border border-border">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-mono text-foreground-subtle">
                      Scene {scene.id}
                    </span>
                    {scene.image_url && (
                      <button
                        onClick={() => handleRegenerateSingleImage(scene.id)}
                        disabled={generatingScene === scene.id}
                        className="p-1.5 rounded hover:bg-background-secondary text-foreground-subtle hover:text-foreground nodrag"
                      >
                        {generatingScene === scene.id ? (
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        ) : (
                          <RotateCcw className="w-3.5 h-3.5" />
                        )}
                      </button>
                    )}
                  </div>

                  <div className="aspect-video rounded-lg overflow-hidden bg-background-secondary mb-2">
                    {scene.image_url ? (
                      <img
                        src={scene.image_url}
                        alt={`Scene ${scene.id}`}
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center">
                        <ImageIcon className="w-6 h-6 text-foreground-subtle" />
                      </div>
                    )}
                  </div>

                  <p className="text-xs text-foreground-muted line-clamp-2">
                    {scene.visual_prompt || scene.description}
                  </p>
                </div>
              ))}
            </div>
          </>
        )}
      </BaseNodeContent>

      <BaseNodeError message={errors.images} />

      <BaseNodeFooter>
        {/* Edit Mode Actions */}
        {isEditing && !allImagesGenerated && (
          <div className="flex gap-2 w-full">
            <Button
              variant="ghost"
              onClick={handleCancelEdit}
              className="flex-1 nodrag"
              icon={<X className="w-4 h-4" />}
            >
              Cancel
            </Button>
            <Button
              onClick={handleSavePrompts}
              className="flex-1 nodrag"
              icon={<Check className="w-4 h-4" />}
            >
              Save Prompts
            </Button>
          </div>
        )}

        {/* Before Generation - View Mode */}
        {!isEditing && !allImagesGenerated && (
          <div className="space-y-2 w-full">
            <Button
              variant="outline"
              onClick={handleStartEdit}
              className="w-full nodrag"
              icon={<Pencil className="w-4 h-4" />}
            >
              Edit Prompts
            </Button>
            <Button
              onClick={handleGenerateAllImages}
              disabled={isLoading}
              className="w-full nodrag"
              icon={isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
            >
              {isLoading ? "Generating..." : `Generate All Images (${scenes.length})`}
            </Button>
          </div>
        )}

        {/* After Generation */}
        {allImagesGenerated && (
          <div className="flex items-center justify-center gap-2 p-2 rounded-lg bg-emerald-500/10 text-emerald-600 w-full">
            <Check className="w-4 h-4" />
            <span className="text-sm">All images generated</span>
          </div>
        )}
      </BaseNodeFooter>
    </BaseNode>
  );
});
