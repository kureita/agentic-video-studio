"use client";

import { memo, useState, useRef, useEffect, useCallback } from "react";
import { NodeProps } from "@xyflow/react";
import { Film, Sparkles, Loader2, RotateCcw, Check, Play, Pause, Volume2, VolumeX, Maximize } from "lucide-react";
import {
  BaseNode,
  BaseNodeHeader,
  BaseNodeContent,
  BaseNodeFooter,
  BaseNodeError
} from "./BaseNode";
import { Button } from "@/components/ui";
import { useCanvasStore, SceneData } from "@/lib/canvas-store";
import { canvasApi } from "@/lib/api";

interface VideoNodeData {
  onProceed?: () => void;
  [key: string]: unknown;
}

export const VideoNode = memo(function VideoNode({ data }: NodeProps) {
  const nodeData = data as VideoNodeData;
  const {
    projectId,
    scenes,
    updateScene,
    nodeStatuses,
    setNodeStatus,
    setError,
    errors,
  } = useCanvasStore();

  const [generatingScene, setGeneratingScene] = useState<number | null>(null);
  const [activeVideoId, setActiveVideoId] = useState<number | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isMuted, setIsMuted] = useState(false);

  const videoRefs = useRef<Map<number, HTMLVideoElement>>(new Map());

  const isLoading = nodeStatuses.videos === "loading";
  const hasImages = scenes.some((s) => s.image_url);
  const allVideosGenerated = scenes.every((s) => s.video_url);

  // Stop all other videos when one starts playing
  const stopAllVideos = useCallback(() => {
    videoRefs.current.forEach((video) => {
      video.pause();
      video.currentTime = 0;
    });
  }, []);

  // Handle play/pause for a specific video
  const handlePlayPause = useCallback((sceneId: number) => {
    const video = videoRefs.current.get(sceneId);
    if (!video) return;

    if (activeVideoId === sceneId && isPlaying) {
      // Pause current video
      video.pause();
      setIsPlaying(false);
    } else {
      // Stop all other videos first
      stopAllVideos();

      // Play this video
      setActiveVideoId(sceneId);
      video.muted = isMuted;
      video.play();
      setIsPlaying(true);
    }
  }, [activeVideoId, isPlaying, isMuted, stopAllVideos]);

  // Handle mute/unmute
  const handleMuteToggle = useCallback(() => {
    const newMuted = !isMuted;
    setIsMuted(newMuted);

    // Update the active video's mute state
    if (activeVideoId) {
      const video = videoRefs.current.get(activeVideoId);
      if (video) {
        video.muted = newMuted;
      }
    }
  }, [activeVideoId, isMuted]);

  // Handle video end
  const handleVideoEnd = useCallback((sceneId: number) => {
    if (activeVideoId === sceneId) {
      setIsPlaying(false);
    }
  }, [activeVideoId]);

  // Handle fullscreen
  const handleFullscreen = useCallback((sceneId: number) => {
    const video = videoRefs.current.get(sceneId);
    if (!video) return;

    if (video.requestFullscreen) {
      video.requestFullscreen();
    } else if ((video as any).webkitRequestFullscreen) {
      (video as any).webkitRequestFullscreen();
    } else if ((video as any).msRequestFullscreen) {
      (video as any).msRequestFullscreen();
    }

    // Auto-play in fullscreen if not already playing
    if (!isPlaying || activeVideoId !== sceneId) {
      stopAllVideos();
      setActiveVideoId(sceneId);
      video.muted = isMuted;
      video.play();
      setIsPlaying(true);
    }
  }, [activeVideoId, isPlaying, isMuted, stopAllVideos]);

  // Set video ref
  const setVideoRef = useCallback((sceneId: number, el: HTMLVideoElement | null) => {
    if (el) {
      videoRefs.current.set(sceneId, el);
    } else {
      videoRefs.current.delete(sceneId);
    }
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopAllVideos();
    };
  }, [stopAllVideos]);

  const handleGenerateAllVideos = async () => {
    if (!projectId || !hasImages) return;

    setNodeStatus("videos", "loading");
    setError("videos", null);

    try {
      const response = await canvasApi.generateVideos(projectId);
      const { scenes: updatedScenes } = response.data;

      updatedScenes.forEach((scene: SceneData) => {
        updateScene(scene.id, { video_url: scene.video_url });
      });

      setNodeStatus("videos", "success");
      if (nodeData?.onProceed) {
        nodeData.onProceed();
      }
    } catch (err) {
      console.error("Failed to generate videos:", err);
      setNodeStatus("videos", "error");
      setError("videos", err instanceof Error ? err.message : "Failed to generate videos");
    }
  };

  const handleRegenerateSingleVideo = async (sceneId: number) => {
    if (!projectId) return;

    // Stop playing if regenerating active video
    if (activeVideoId === sceneId) {
      stopAllVideos();
      setActiveVideoId(null);
      setIsPlaying(false);
    }

    setGeneratingScene(sceneId);
    try {
      const response = await canvasApi.regenerateVideo(projectId, sceneId);
      updateScene(sceneId, { video_url: response.data.video_url });
    } catch (err) {
      console.error("Failed to regenerate video:", err);
    } finally {
      setGeneratingScene(null);
    }
  };

  if (!hasImages) {
    return (
      <BaseNode status="idle">
        <BaseNodeHeader icon={<Film className="w-4 h-4" />}>
          Video Generation
        </BaseNodeHeader>
        <BaseNodeContent>
          <p className="text-sm text-foreground-muted">
            Waiting for images to be generated...
          </p>
        </BaseNodeContent>
      </BaseNode>
    );
  }

  return (
    <BaseNode status={nodeStatuses.videos}>
      <BaseNodeHeader icon={<Film className="w-4 h-4" />} status={nodeStatuses.videos}>
        Video Generation
      </BaseNodeHeader>

      <BaseNodeContent className="max-h-[400px] overflow-y-auto nowheel">
        <p className="text-sm text-foreground-muted mb-4">
          Animate images into video clips using Veo.
        </p>

        <div className="space-y-3">
          {scenes.map((scene) => {
            const isActive = activeVideoId === scene.id;
            const isThisPlaying = isActive && isPlaying;

            return (
              <div key={scene.id} className="p-3 rounded-lg border border-border">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-mono text-foreground-subtle">
                    Scene {scene.id}
                  </span>
                  {scene.video_url && (
                    <button
                      onClick={() => handleRegenerateSingleVideo(scene.id)}
                      disabled={generatingScene === scene.id}
                      className="p-1.5 rounded hover:bg-background-secondary text-foreground-subtle hover:text-foreground nodrag"
                      title="Regenerate video"
                    >
                      {generatingScene === scene.id ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <RotateCcw className="w-3.5 h-3.5" />
                      )}
                    </button>
                  )}
                </div>

                <div className="aspect-video rounded-lg overflow-hidden bg-background-secondary relative">
                  {scene.video_url ? (
                    <>
                      {/* Video element - always present for proper ref management */}
                      <video
                        ref={(el) => setVideoRef(scene.id, el)}
                        src={scene.video_url}
                        className="w-full h-full object-cover"
                        onEnded={() => handleVideoEnd(scene.id)}
                        playsInline
                        preload="metadata"
                      />

                      {/* Poster overlay when not playing */}
                      {!isThisPlaying && scene.image_url && (
                        <div className="absolute inset-0">
                          <img
                            src={scene.image_url}
                            alt=""
                            className="w-full h-full object-cover"
                          />
                        </div>
                      )}

                      {/* Controls overlay */}
                      <div className={`absolute inset-0 flex items-center justify-center transition-opacity ${isThisPlaying ? "opacity-0 hover:opacity-100" : "opacity-100"
                        }`}>
                        <div className="absolute inset-0 bg-black/30" />

                        {/* Play/Pause button */}
                        <button
                          onClick={() => handlePlayPause(scene.id)}
                          className="relative z-10 w-12 h-12 rounded-full bg-white/90 flex items-center justify-center hover:bg-white transition-colors nodrag"
                        >
                          {isThisPlaying ? (
                            <Pause className="w-5 h-5 text-gray-900" />
                          ) : (
                            <Play className="w-5 h-5 text-gray-900 ml-0.5" />
                          )}
                        </button>

                        {/* Bottom controls */}
                        <div className="absolute bottom-2 left-2 right-2 flex items-center justify-between">
                          <span className="px-2 py-1 rounded bg-black/70 text-xs text-white">
                            {isThisPlaying ? "Playing" : "Video Ready"}
                          </span>

                          {/* Right side controls */}
                          {scene.video_url && (
                            <div className="flex items-center gap-1">
                              {/* Mute/Unmute */}
                              <button
                                onClick={handleMuteToggle}
                                className="p-1.5 rounded bg-black/70 hover:bg-black/90 transition-colors nodrag"
                                title={isMuted ? "Unmute" : "Mute"}
                              >
                                {isMuted ? (
                                  <VolumeX className="w-4 h-4 text-white" />
                                ) : (
                                  <Volume2 className="w-4 h-4 text-white" />
                                )}
                              </button>

                              {/* Fullscreen */}
                              <button
                                onClick={() => handleFullscreen(scene.id)}
                                className="p-1.5 rounded bg-black/70 hover:bg-black/90 transition-colors nodrag"
                                title="Fullscreen"
                              >
                                <Maximize className="w-4 h-4 text-white" />
                              </button>
                            </div>
                          )}
                        </div>
                      </div>
                    </>
                  ) : scene.image_url ? (
                    <div className="relative w-full h-full">
                      <img src={scene.image_url} alt="" className="w-full h-full object-cover opacity-50" />
                      <div className="absolute inset-0 flex items-center justify-center">
                        <Film className="w-6 h-6 text-foreground-subtle" />
                      </div>
                    </div>
                  ) : (
                    <div className="w-full h-full flex items-center justify-center">
                      <Film className="w-6 h-6 text-foreground-subtle" />
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </BaseNodeContent>

      <BaseNodeError message={errors.videos} />

      <BaseNodeFooter>
        {!allVideosGenerated ? (
          <Button
            onClick={handleGenerateAllVideos}
            disabled={isLoading}
            className="w-full nodrag"
            icon={isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
          >
            {isLoading ? "Generating..." : `Generate All Videos (${scenes.length})`}
          </Button>
        ) : (
          <div className="flex items-center justify-center gap-2 p-2 rounded-lg bg-emerald-500/10 text-emerald-600">
            <Check className="w-4 h-4" />
            <span className="text-sm">All videos generated</span>
          </div>
        )}
      </BaseNodeFooter>
    </BaseNode>
  );
});
