"use client";

import { memo, useState } from "react";
import { NodeProps, Node } from "@xyflow/react";
import { BookOpen, Sparkles, Loader2, Pencil, Check, X, Wand2 } from "lucide-react";
import {
  BaseNode,
  BaseNodeHeader,
  BaseNodeContent,
  BaseNodeFooter,
  BaseNodeError
} from "./BaseNode";
import { Button, Textarea } from "@/components/ui";
import {
  useCanvasStore,
  visualStyleOptions,
  durationOptions,
  storyTemplates,
  SceneData,
} from "@/lib/canvas-store";
import { canvasApi } from "@/lib/api";
import { toast } from "sonner";

type StoryNodeData = {
  onProceed?: () => void;
};

export const StoryNode = memo(function StoryNode({ data }: NodeProps<Node<StoryNodeData>>) {
  const {
    projectId,
    brandData,
    storyOptions,
    setStoryOptions,
    storyData,
    setStoryData,
    setScenes,
    scenes,
    nodeStatuses,
    setNodeStatus,
    setError,
    errors,
  } = useCanvasStore();

  const [isEditing, setIsEditing] = useState(false);
  const [editedSynopsis, setEditedSynopsis] = useState("");
  const [editedScenes, setEditedScenes] = useState<{ id: number; description: string; visual_prompt: string }[]>([]);
  const [showTemplates, setShowTemplates] = useState(true);
  const [isImproving, setIsImproving] = useState(false);

  const isLoading = nodeStatuses.story === "loading";

  const handleSelectTemplate = (templateId: string) => {
    const template = storyTemplates.find((t) => t.id === templateId);
    if (template) {
      setStoryOptions(template.options);
    }
    setShowTemplates(false);
  };

  const handleGenerateStory = async () => {
    if (!projectId || !brandData) return;

    setNodeStatus("story", "loading");
    setError("story", null);

    try {
      const response = await canvasApi.generateStory(projectId, {
        theme: storyOptions.theme,
        visual_style: storyOptions.visualStyle,
        direction: storyOptions.direction,
        duration: storyOptions.duration,
        target_audience: storyOptions.targetAudience,
        additional_notes: storyOptions.additionalNotes,
      });

      const { story, scenes: newScenes } = response.data;
      setStoryData(story);
      setScenes(newScenes);
      setNodeStatus("story", "success");
      toast.success("Story & script generated");

      if (data?.onProceed) {
        data.onProceed();
      }
    } catch (err) {
      console.error("Failed to generate story:", err);
      setNodeStatus("story", "error");
      setError("story", err instanceof Error ? err.message : "Failed to generate story");
      toast.error("Failed to generate story");
    }
  };

  const handleStartEdit = () => {
    if (storyData) {
      setEditedSynopsis(storyData.synopsis);
      setEditedScenes(scenes.map(s => ({
        id: s.id,
        description: s.description,
        visual_prompt: s.visual_prompt,
      })));
      setIsEditing(true);
    }
  };

  const handleCancelEdit = () => {
    setIsEditing(false);
    setEditedSynopsis("");
    setEditedScenes([]);
  };

  const handleImproveWithAI = async () => {
    if (!projectId) return;

    setIsImproving(true);

    try {
      // Build script text from edited scenes
      const scriptText = editedScenes.map(s =>
        `Scene ${s.id}: ${s.description}\nVisual: ${s.visual_prompt}`
      ).join("\n\n");

      const response = await canvasApi.improveStory(projectId, {
        synopsis: editedSynopsis,
        script_text: scriptText,
      });

      const { story, scenes: improvedScenes } = response.data;

      // Update the edit fields with improved content
      setEditedSynopsis(story.synopsis || editedSynopsis);
      setEditedScenes(improvedScenes.map((s: SceneData) => ({
        id: s.id,
        description: s.description,
        visual_prompt: s.visual_prompt,
      })));

    } catch (err) {
      console.error("Failed to improve with AI:", err);
      toast.error("Failed to improve story with AI");
    } finally {
      setIsImproving(false);
    }
  };

  const handleSaveEdit = () => {
    if (!storyData) return;

    // Update story data
    setStoryData({
      ...storyData,
      synopsis: editedSynopsis,
    });

    // Update scenes
    const updatedScenes = scenes.map(scene => {
      const edited = editedScenes.find(e => e.id === scene.id);
      if (edited) {
        return {
          ...scene,
          description: edited.description,
          visual_prompt: edited.visual_prompt,
        };
      }
      return scene;
    });
    setScenes(updatedScenes);

    setIsEditing(false);
  };

  const handleUpdateSceneField = (id: number, field: "description" | "visual_prompt", value: string) => {
    setEditedScenes(prev => prev.map(s =>
      s.id === id ? { ...s, [field]: value } : s
    ));
  };

  if (!brandData) {
    return (
      <BaseNode status="idle">
        <BaseNodeHeader icon={<BookOpen className="w-4 h-4" />}>
          Story & Script
        </BaseNodeHeader>
        <BaseNodeContent>
          <p className="text-sm text-foreground-muted">
            Waiting for brand analysis...
          </p>
        </BaseNodeContent>
      </BaseNode>
    );
  }

  return (
    <BaseNode status={nodeStatuses.story}>
      <BaseNodeHeader icon={<BookOpen className="w-4 h-4" />} status={nodeStatuses.story}>
        Story & Script
      </BaseNodeHeader>

      <BaseNodeContent className="max-h-[500px] overflow-y-auto nowheel">
        {/* Brand Summary */}
        <div className="p-3 rounded-lg bg-background-secondary mb-4">
          <p className="text-xs text-foreground-muted mb-1">Brand</p>
          <p className="font-medium text-foreground">{brandData.name}</p>
          {brandData.tagline && (
            <p className="text-sm text-foreground-muted">{brandData.tagline}</p>
          )}
        </div>

        {/* Templates or Options - Before story generation */}
        {!storyData && !isEditing && (
          <>
            {showTemplates ? (
              <div className="space-y-3">
                <p className="text-sm font-medium text-foreground">Quick Start Templates</p>
                <div className="grid grid-cols-2 gap-2">
                  {storyTemplates.slice(0, 4).map((template) => (
                    <button
                      key={template.id}
                      onClick={() => handleSelectTemplate(template.id)}
                      className="p-3 rounded-lg border border-border hover:border-foreground-subtle text-left transition-colors nodrag"
                    >
                      <p className="font-medium text-sm text-foreground">{template.name}</p>
                      <p className="text-xs text-foreground-muted">{template.description}</p>
                    </button>
                  ))}
                </div>
                <button
                  onClick={() => setShowTemplates(false)}
                  className="text-xs text-foreground-muted hover:text-foreground nodrag"
                >
                  Or customize settings →
                </button>
              </div>
            ) : (
              <div className="space-y-4">
                {/* Visual Style */}
                <div>
                  <label className="block text-sm font-medium text-foreground mb-2">Visual Style</label>
                  <div className="grid grid-cols-3 gap-2">
                    {visualStyleOptions.slice(0, 6).map((opt) => (
                      <button
                        key={opt.id}
                        onClick={() => setStoryOptions({ visualStyle: opt.id })}
                        className={`p-2 rounded-lg border text-left transition-colors nodrag ${storyOptions.visualStyle === opt.id
                          ? "border-foreground bg-background-secondary"
                          : "border-border hover:border-foreground-subtle"
                          }`}
                      >
                        <p className="text-xs font-medium text-foreground">{opt.label}</p>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Duration */}
                <div>
                  <label className="block text-sm font-medium text-foreground mb-2">Duration</label>
                  <div className="flex gap-2">
                    {durationOptions.map((opt) => (
                      <button
                        key={opt.value}
                        onClick={() => setStoryOptions({ duration: opt.value })}
                        className={`flex-1 p-2 rounded-lg border text-center transition-colors nodrag ${storyOptions.duration === opt.value
                          ? "border-foreground bg-background-secondary"
                          : "border-border hover:border-foreground-subtle"
                          }`}
                      >
                        <p className="font-medium text-foreground">{opt.label}</p>
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </>
        )}

        {/* Story Result - View Mode */}
        {storyData && !isEditing && (
          <div className="space-y-4">
            <div className="p-3 rounded-lg bg-background-secondary">
              <h4 className="font-medium text-foreground mb-1">{storyData.title}</h4>
              <p className="text-sm text-foreground-muted">{storyData.synopsis}</p>
            </div>

            <div>
              <p className="text-sm font-medium text-foreground mb-2">
                Script ({scenes.length} scenes)
              </p>
              <div className="space-y-2 max-h-[200px] overflow-y-auto nowheel">
                {scenes.map((scene) => (
                  <div key={scene.id} className="p-2 rounded-lg border border-border text-xs">
                    <span className="font-mono text-foreground-subtle">
                      {scene.start_time}s - {scene.end_time}s
                    </span>
                    <p className="text-foreground mt-1">{scene.description}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Edit Mode */}
        {isEditing && (
          <div className="space-y-4">
            {/* AI Improve Button */}
            <div className="flex justify-end">
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

            {/* Synopsis Edit */}
            <div>
              <label className="block text-xs font-medium text-foreground mb-1">Synopsis</label>
              <Textarea
                value={editedSynopsis}
                onChange={(e) => setEditedSynopsis(e.target.value)}
                rows={3}
                className="text-sm nodrag nowheel"
                placeholder="Describe your story..."
              />
            </div>

            {/* Scenes Edit */}
            <div>
              <label className="block text-xs font-medium text-foreground mb-2">Scenes</label>
              <div className="space-y-3 max-h-[250px] overflow-y-auto nowheel">
                {editedScenes.map((scene, idx) => (
                  <div key={scene.id} className="p-3 rounded-lg border border-border space-y-2">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-mono text-foreground-subtle px-2 py-0.5 bg-background-secondary rounded">
                        Scene {idx + 1}
                      </span>
                    </div>

                    <div>
                      <label className="block text-xs text-foreground-muted mb-1">Description</label>
                      <Textarea
                        value={scene.description}
                        onChange={(e) => handleUpdateSceneField(scene.id, "description", e.target.value)}
                        rows={2}
                        className="text-xs nodrag nowheel"
                      />
                    </div>

                    <div>
                      <label className="block text-xs text-foreground-muted mb-1">Visual Prompt</label>
                      <Textarea
                        value={scene.visual_prompt}
                        onChange={(e) => handleUpdateSceneField(scene.id, "visual_prompt", e.target.value)}
                        rows={2}
                        className="text-xs nodrag nowheel"
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </BaseNodeContent>

      <BaseNodeError message={errors.story} />

      <BaseNodeFooter>
        {/* Before story generation */}
        {!storyData && !isEditing && (
          <Button
            onClick={handleGenerateStory}
            disabled={isLoading || showTemplates}
            className="w-full nodrag"
            icon={isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
          >
            {isLoading ? "Generating..." : "Generate Story & Script"}
          </Button>
        )}

        {/* After story generation - View mode */}
        {storyData && !isEditing && (
          <Button
            variant="outline"
            onClick={handleStartEdit}
            className="w-full nodrag"
            icon={<Pencil className="w-4 h-4" />}
          >
            Edit Story & Script
          </Button>
        )}

        {/* Edit mode */}
        {isEditing && (
          <div className="flex gap-2">
            <Button
              variant="ghost"
              onClick={handleCancelEdit}
              className="flex-1 nodrag"
              icon={<X className="w-4 h-4" />}
            >
              Cancel
            </Button>
            <Button
              onClick={handleSaveEdit}
              className="flex-1 nodrag"
              icon={<Check className="w-4 h-4" />}
            >
              Save Changes
            </Button>
          </div>
        )}
      </BaseNodeFooter>
    </BaseNode>
  );
});
