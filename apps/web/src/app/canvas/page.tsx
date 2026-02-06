"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import dynamic from "next/dynamic";
import { ArrowLeft, RotateCcw, Loader2, FolderOpen, Save, Check } from "lucide-react";
import { Button } from "@/components/ui";
import { useCanvasStore } from "@/lib/canvas-store";
import { ChatOverlay } from "@/components/canvas"; // Import the Sidebar component
import { canvasApi, projectsApi, Project } from "@/lib/api";

// Dynamically import React Flow to avoid SSR issues
const CanvasFlow = dynamic(() => import("./CanvasFlow"), {
  ssr: false,
  loading: () => (
    <div className="flex-1 flex items-center justify-center bg-background">
      <div className="flex items-center gap-3 text-foreground-muted">
        <Loader2 className="w-5 h-5 animate-spin" />
        <span>Loading canvas...</span>
      </div>
    </div>
  ),
});

export default function CanvasPage() {
  const searchParams = useSearchParams();
  const projectIdParam = searchParams.get("project");

  const {
    reset,
    nodeStatuses,
    projectId,
    loadFromProject,
    setCanvasNodes,
    setCanvasEdges,
    applyGraphPlan // Destructure this to pass to Chat
  } = useCanvasStore();

  const [isLoading, setIsLoading] = useState(false);
  const [showProjectPicker, setShowProjectPicker] = useState(false);
  const [projects, setProjects] = useState<Project[]>([]);
  const [isSaved, setIsSaved] = useState(false);

  // Load project from URL parameter
  useEffect(() => {
    if (projectIdParam && projectIdParam !== projectId) {
      loadProject(projectIdParam);
    }
  }, [projectIdParam]);

  const loadProject = async (id: string) => {
    setIsLoading(true);
    try {
      const response = await canvasApi.load(id);
      const data = response.data;

      // Determine node statuses based on what data exists
      const statuses: Partial<typeof nodeStatuses> = {
        brand: data.brand_profile ? "success" : "idle",
        story: data.story ? "success" : "idle",
        images: data.scenes?.some(s => s.image_url) ? "success" : "idle",
        videos: data.scenes?.some(s => s.video_url) ? "success" : "idle",
        composition: data.status === "completed" ? "success" : "idle",
        render: data.status === "completed" ? "success" : "idle",
      };

      loadFromProject({
        projectId: data.project_id,
        brandData: data.brand_profile,
        storyData: data.story,
        scenes: data.scenes,
        storyOptions: data.story_options,
        canvasNodes: data.canvas_state?.nodes || [],
        canvasEdges: data.canvas_state?.edges || [],
        nodeStatuses: statuses,
      });

    } catch (err) {
      console.error("Failed to load project:", err);
    } finally {
      setIsLoading(false);
    }
  };

  const fetchProjects = async () => {
    try {
      const response = await projectsApi.list();
      // Filter to only canvas projects or recent ones
      setProjects(response.data.slice(0, 10));
    } catch (err) {
      console.error("Failed to fetch projects:", err);
    }
  };

  const handleOpenProject = () => {
    fetchProjects();
    setShowProjectPicker(true);
  };

  const handleSelectProject = (project: Project) => {
    setShowProjectPicker(false);
    // Update URL and load project
    window.history.pushState({}, "", `/canvas?project=${project.id}`);
    loadProject(project.id);
  };

  const handleReset = () => {
    // Clear localStorage first
    if (typeof window !== "undefined") {
      localStorage.removeItem("kureita-canvas-store");
    }
    reset();
    window.history.pushState({}, "", "/canvas");
    window.location.reload();
  };

  const handleManualSave = async () => {
    if (!projectId) return;

    const state = useCanvasStore.getState();
    try {
      await canvasApi.saveState(projectId, state.canvasNodes, state.canvasEdges);
      setIsSaved(true);
      setTimeout(() => setIsSaved(false), 2000);
    } catch (err) {
      console.error("Failed to save:", err);
    }
  };

  if (isLoading) {
    return (
      <div className="h-screen flex flex-col bg-background">
        {/* Removed Header */}
        <div className="flex-1 flex items-center justify-center">
          <div className="flex items-center gap-3 text-foreground-muted">
            <Loader2 className="w-5 h-5 animate-spin" />
            <span>Loading project...</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col bg-background overflow-hidden font-sans">

      {/* Canvas Header - Compact IDE Style */}
      <div className="border-b border-border bg-background/95 backdrop-blur-sm px-4 py-2 flex items-center justify-between shrink-0 h-14 z-20">
        <div className="flex items-center gap-4">
          <Link
            href="/dashboard"
            className="flex items-center gap-2 text-foreground-muted hover:text-foreground transition-colors group"
          >
            <div className="w-6 h-6 flex items-center justify-center rounded-md group-hover:bg-background-secondary transition-colors">
              <ArrowLeft className="w-4 h-4" />
            </div>
            <span className="text-sm font-medium">Back</span>
          </Link>
          <div className="w-px h-5 bg-border" />
          <h1 className="font-semibold text-sm text-foreground">Video Pipeline Canvas</h1>
          {projectId && (
            <span className="text-[10px] text-foreground-muted bg-background-secondary px-1.5 py-0.5 rounded font-mono border border-border/50">
              {projectId.slice(0, 8)}...
            </span>
          )}
        </div>

        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            onClick={handleOpenProject}
            icon={<FolderOpen className="w-3.5 h-3.5" />}
            className="h-8 text-xs"
          >
            Open
          </Button>
          {projectId && (
            <Button
              variant="ghost"
              size="sm"
              onClick={handleManualSave}
              icon={isSaved ? <Check className="w-3.5 h-3.5 text-emerald-500" /> : <Save className="w-3.5 h-3.5" />}
              className="h-8 text-xs"
            >
              {isSaved ? "Saved" : "Save"}
            </Button>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={handleReset}
            icon={<RotateCcw className="w-3.5 h-3.5" />}
            className="h-8 text-xs"
          >
            New
          </Button>
        </div>
      </div>

      {/* Main Workspace Area (Split Pane) */}
      <div className="flex-1 flex overflow-hidden relative">

        {/* Left Pane: Canvas & Status */}
        <div className="flex-1 flex flex-col relative min-w-0">

          {/* React Flow Canvas */}
          <div className="flex-1 relative bg-background-secondary/5">
            <CanvasFlow />
          </div>

          {/* Status Bar - Compact */}
          <div className="border-t border-border bg-background/95 backdrop-blur-sm px-4 py-1.5 shrink-0 z-10 flex items-center justify-between">
            <div className="flex items-center gap-6">
              {Object.entries(nodeStatuses).map(([key, status]) => (
                <div key={key} className="flex items-center gap-1.5 opacity-80 hover:opacity-100 transition-opacity">
                  <div
                    className={`w-1.5 h-1.5 rounded-full ${status === "success"
                        ? "bg-emerald-500"
                        : status === "loading"
                          ? "bg-amber-500 animate-pulse"
                          : status === "error"
                            ? "bg-red-500"
                            : "bg-foreground-subtle"
                      }`}
                  />
                  <span className="text-[10px] uppercase tracking-wide font-medium text-foreground-muted">{key}</span>
                </div>
              ))}
            </div>
            <div className="text-[10px] text-foreground-muted">
              Wait for AI completion before editing manually.
            </div>
          </div>
        </div>

        {/* Right Pane: AI Assistant Sidebar */}
        <div className="w-[360px] border-l border-border bg-background h-full shrink-0 z-30 flex flex-col shadow-[-1px_0_0_0_rgba(0,0,0,0.05)]">
          <ChatOverlay
            onPlanReceived={(plan) => {
              console.log("Plan from Sidebar:", plan);
              applyGraphPlan(plan);
            }}
          />
        </div>

      </div>

      {/* Project Picker Modal */}
      {showProjectPicker && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
          <div className="bg-background border border-border rounded-xl shadow-2xl w-full max-w-md p-6">
            <h2 className="text-lg font-semibold text-foreground mb-4">Open Project</h2>

            {projects.length === 0 ? (
              <p className="text-foreground-muted text-sm">No projects found.</p>
            ) : (
              <div className="space-y-2 max-h-[300px] overflow-y-auto pr-2">
                {projects.map((project) => (
                  <button
                    key={project.id}
                    onClick={() => handleSelectProject(project)}
                    className="w-full p-3 rounded-lg border border-border hover:bg-background-secondary text-left transition-colors flex justify-between items-center group"
                  >
                    <div>
                      <p className="font-medium text-foreground text-sm group-hover:text-indigo-500 transition-colors">
                        {project.brand_name || "Untitled"}
                      </p>
                      <p className="text-xs text-foreground-muted">
                        {new URL(project.website_url).hostname}
                      </p>
                    </div>
                    <span className="text-[10px] bg-background-secondary px-2 py-0.5 rounded text-foreground-muted uppercase">
                      {project.status}
                    </span>
                  </button>
                ))}
              </div>
            )}

            <div className="flex justify-end mt-4">
              <Button variant="ghost" onClick={() => setShowProjectPicker(false)}>
                Cancel
              </Button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
