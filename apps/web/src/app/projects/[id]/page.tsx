"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Header } from "@/components/layout";
import { Button, Card, Badge } from "@/components/ui";
import { 
  ArrowLeft,
  Play,
  Download,
  Share2,
  RefreshCw,
  Film,
  Clock,
  ExternalLink,
  Sparkles,
  CheckCircle2,
  Circle,
  Loader2,
  AlertCircle
} from "lucide-react";
import { projectsApi, ProjectWithStages, GenerationStage } from "@/lib/api";

const stageIcons: Record<string, React.ReactNode> = {
  completed: <CheckCircle2 className="w-5 h-5 text-emerald-500" />,
  in_progress: <Loader2 className="w-5 h-5 text-accent animate-spin" />,
  pending: <Circle className="w-5 h-5 text-foreground-subtle" />,
  failed: <AlertCircle className="w-5 h-5 text-red-500" />,
};

const defaultStages: GenerationStage[] = [
  { id: "analyze", label: "Analyzing Website", status: "pending" },
  { id: "story", label: "Crafting Story", status: "pending" },
  { id: "script", label: "Writing Script", status: "pending" },
  { id: "assets", label: "Generating Assets", status: "pending" },
  { id: "compose", label: "Composing Video", status: "pending" },
  { id: "audio", label: "Adding Audio", status: "pending" },
  { id: "finalize", label: "Final Render", status: "pending" },
];

export default function ProjectDetailPage() {
  const params = useParams();
  const projectId = params.id as string;
  
  const [project, setProject] = useState<ProjectWithStages | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showVideo, setShowVideo] = useState(false);

  const fetchProject = useCallback(async () => {
    try {
      const response = await projectsApi.get(projectId);
      setProject(response.data);
      setError(null);
      return response.data;
    } catch (err) {
      console.error("Failed to fetch project:", err);
      setError("Failed to load project");
      return null;
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  // Initial fetch
  useEffect(() => {
    fetchProject();
  }, [fetchProject]);

  // Polling for in-progress projects
  useEffect(() => {
    if (!project) return;
    
    const isInProgress = ["analyzing", "planning", "generating", "composing", "processing"].includes(project.status);
    if (!isInProgress) return;

    const interval = setInterval(() => {
      fetchProject();
    }, 3000); // Poll every 3 seconds for better UX
    
    return () => clearInterval(interval);
  }, [project?.status, fetchProject]);

  const handleStartGeneration = async () => {
    try {
      await projectsApi.start(projectId);
      fetchProject();
    } catch (err) {
      console.error("Failed to start generation:", err);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-background">
        <Header />
        <main className="container-wide py-12">
          <div className="flex items-center justify-center h-64">
            <Loader2 className="w-8 h-8 animate-spin text-foreground-muted" />
          </div>
        </main>
      </div>
    );
  }

  if (error || !project) {
    return (
      <div className="min-h-screen bg-background">
        <Header />
        <main className="container-wide py-12">
          <Link 
            href="/projects" 
            className="inline-flex items-center gap-2 text-foreground-muted hover:text-foreground transition-colors mb-8"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Projects
          </Link>
          <Card className="p-8 text-center">
            <AlertCircle className="w-12 h-12 text-red-500 mx-auto mb-4" />
            <h2 className="text-xl font-semibold text-foreground mb-2">
              {error || "Project not found"}
            </h2>
            <p className="text-foreground-muted mb-6">
              The project you&apos;re looking for doesn&apos;t exist or couldn&apos;t be loaded.
            </p>
            <Button onClick={() => fetchProject()}>
              Try Again
            </Button>
          </Card>
        </main>
      </div>
    );
  }

  const stages = project.stages?.length ? project.stages : defaultStages;
  const isGenerating = ["analyzing", "planning", "generating", "composing", "processing"].includes(project.status);
  const isCompleted = project.status === "completed";
  const isDraft = project.status === "draft";

  // Format duration
  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  return (
    <div className="min-h-screen bg-background">
      <Header />
      
      <main className="container-wide py-12">
        {/* Back Button */}
        <Link 
          href="/projects" 
          className="inline-flex items-center gap-2 text-foreground-muted hover:text-foreground transition-colors mb-8"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Projects
        </Link>

        <div className="grid lg:grid-cols-3 gap-8">
          {/* Main Content */}
          <div className="lg:col-span-2 space-y-8">
            {/* Video Player */}
            <Card variant="elevated" className="p-0 overflow-hidden">
              <div className="aspect-video bg-gradient-to-br from-background-secondary to-background-tertiary flex items-center justify-center relative">
                {isDraft ? (
                  <div className="text-center">
                    <div className="w-20 h-20 rounded-full bg-foreground/10 flex items-center justify-center mx-auto mb-4">
                      <Film className="w-10 h-10 text-foreground" />
                    </div>
                    <p className="text-foreground-muted mb-4">Ready to generate your video</p>
                    <Button onClick={handleStartGeneration}>
                      <Sparkles className="w-4 h-4 mr-2" />
                      Start Generation
                    </Button>
                  </div>
                ) : isGenerating ? (
                  <div className="text-center">
                    <div className="w-20 h-20 rounded-full bg-foreground/10 flex items-center justify-center mx-auto mb-4">
                      <Sparkles className="w-10 h-10 text-foreground animate-pulse" />
                    </div>
                    <p className="text-foreground-muted mb-2">Generating your video...</p>
                    <div className="flex items-center gap-2 justify-center">
                      <div className="w-32 h-2 rounded-full bg-background-tertiary overflow-hidden">
                        <div 
                          className="h-full bg-accent transition-all duration-500"
                          style={{ width: `${project.progress}%` }}
                        />
                      </div>
                      <span className="text-sm text-foreground-subtle">{project.progress}%</span>
                    </div>
                  </div>
                ) : isCompleted && project.video_url ? (
                  showVideo ? (
                    <video
                      src={project.video_url}
                      poster={project.thumbnail_url}
                      className="w-full h-full object-contain bg-black"
                      controls
                      autoPlay
                    />
                  ) : (
                    <button 
                      onClick={() => setShowVideo(true)}
                      className="absolute inset-0 flex items-center justify-center group"
                    >
                      <div className="w-20 h-20 rounded-full bg-white/90 flex items-center justify-center shadow-lg group-hover:scale-110 transition-transform">
                        <Play className="w-8 h-8 text-gray-900 ml-1" />
                      </div>
                    </button>
                  )
                ) : (
                  <div className="w-20 h-20 rounded-full bg-foreground/10 flex items-center justify-center">
                    <Film className="w-8 h-8 text-foreground-muted" />
                  </div>
                )}
              </div>

              {/* Video Info */}
              <div className="p-6">
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <h1 className="text-2xl font-semibold text-foreground mb-2">
                      {project.brand_name || "Untitled Project"}
                    </h1>
                    <div className="flex items-center gap-4 text-sm text-foreground-muted">
                      <span className="flex items-center gap-1.5">
                        <ExternalLink className="w-4 h-4" />
                        {new URL(project.website_url).hostname}
                      </span>
                      <span className="flex items-center gap-1.5">
                        <Clock className="w-4 h-4" />
                        {formatDuration(project.video_duration)}
                      </span>
                      <Badge variant="accent" className="capitalize">
                        {project.style}
                      </Badge>
                    </div>
                  </div>
                  <Badge 
                    variant={isCompleted ? "success" : isGenerating ? "warning" : "default"}
                    className="capitalize"
                  >
                    {isGenerating ? "Generating..." : project.status}
                  </Badge>
                </div>

                <div className="flex gap-3">
                  <Button 
                    icon={<Download className="w-4 h-4" />}
                    disabled={!isCompleted || !project.video_url}
                  >
                    Download
                  </Button>
                  <Button 
                    variant="outline"
                    icon={<Share2 className="w-4 h-4" />}
                    disabled={!isCompleted}
                  >
                    Share
                  </Button>
                  <Button 
                    variant="ghost"
                    icon={<RefreshCw className="w-4 h-4" />}
                    onClick={handleStartGeneration}
                    disabled={isGenerating}
                  >
                    Regenerate
                  </Button>
                </div>
              </div>
            </Card>

            {/* Story & Script */}
            {project.story && (
              <Card>
                <h2 className="text-lg font-semibold text-foreground mb-4">
                  Story: {project.story.title}
                </h2>
                <p className="text-foreground-muted mb-6 leading-relaxed">
                  {project.story.synopsis}
                </p>
                
                {project.story.key_messages?.length > 0 && (
                  <div className="flex flex-wrap gap-2 mb-6">
                    {project.story.key_messages.map((msg: string) => (
                      <Badge key={msg} variant="default">
                        {msg}
                      </Badge>
                    ))}
                  </div>
                )}

                {project.scenes && project.scenes.length > 0 && (
                  <>
                    <h3 className="text-sm font-medium text-foreground mb-3">
                      Scene Breakdown
                    </h3>
                    <div className="space-y-2">
                      {project.scenes.map((scene) => (
                        <div 
                          key={scene.id}
                          className="flex items-center gap-4 p-3 rounded-lg bg-background-secondary"
                        >
                          <span className="text-sm font-mono text-foreground-subtle w-20">
                            {formatDuration(scene.start_time)}-{formatDuration(scene.end_time)}
                          </span>
                          <span className="text-sm text-foreground">
                            {scene.description}
                          </span>
                        </div>
                      ))}
                    </div>
                  </>
                )}
              </Card>
            )}

            {/* Brand Profile */}
            {project.brand_profile && (
              <Card>
                <h2 className="text-lg font-semibold text-foreground mb-4">
                  Brand Analysis
                </h2>
                <div className="space-y-4">
                  <div>
                    <h3 className="text-sm font-medium text-foreground-muted mb-1">Brand</h3>
                    <p className="text-foreground">{project.brand_profile.name}</p>
                    {project.brand_profile.tagline && (
                      <p className="text-sm text-foreground-muted italic">&ldquo;{project.brand_profile.tagline}&rdquo;</p>
                    )}
                  </div>
                  
                  {project.brand_profile.description && (
                    <div>
                      <h3 className="text-sm font-medium text-foreground-muted mb-1">Description</h3>
                      <p className="text-foreground text-sm">{project.brand_profile.description}</p>
                    </div>
                  )}

                  {project.brand_profile.unique_selling_points?.length > 0 && (
                    <div>
                      <h3 className="text-sm font-medium text-foreground-muted mb-2">Key Points</h3>
                      <div className="flex flex-wrap gap-2">
                        {project.brand_profile.unique_selling_points.map((point: string, i: number) => (
                          <Badge key={i} variant="default">{point}</Badge>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </Card>
            )}
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            {/* Progress */}
            <Card>
              <h2 className="text-lg font-semibold text-foreground mb-4">
                Generation Progress
              </h2>
              <div className="space-y-4">
                {stages.map((stage) => (
                  <div key={stage.id} className="flex items-center gap-3">
                    {stageIcons[stage.status] || stageIcons.pending}
                    <span 
                      className={`text-sm ${
                        stage.status === "completed" 
                          ? "text-foreground" 
                          : stage.status === "in_progress"
                          ? "text-foreground font-medium"
                          : "text-foreground-subtle"
                      }`}
                    >
                      {stage.label}
                    </span>
                  </div>
                ))}
              </div>
            </Card>

            {/* Project Details */}
            <Card>
              <h2 className="text-lg font-semibold text-foreground mb-4">
                Project Details
              </h2>
              <div className="space-y-3 text-sm">
                <div className="flex justify-between">
                  <span className="text-foreground-muted">Created</span>
                  <span className="text-foreground">
                    {new Date(project.created_at).toLocaleDateString()}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-foreground-muted">Duration</span>
                  <span className="text-foreground">{project.video_duration}s</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-foreground-muted">Style</span>
                  <span className="text-foreground capitalize">{project.style}</span>
                </div>
                {project.target_audience && (
                  <div className="flex justify-between">
                    <span className="text-foreground-muted">Audience</span>
                    <span className="text-foreground text-right max-w-[60%]">
                      {project.target_audience}
                    </span>
                  </div>
                )}
              </div>
            </Card>

            {/* Quick Actions */}
            <Card>
              <h2 className="text-lg font-semibold text-foreground mb-4">
                Quick Actions
              </h2>
              <div className="space-y-2">
                <Button variant="outline" className="w-full justify-start" disabled={!isCompleted}>
                  <Film className="w-4 h-4 mr-2" />
                  Edit Storyboard
                </Button>
                <Button variant="outline" className="w-full justify-start" disabled={isGenerating}>
                  <RefreshCw className="w-4 h-4 mr-2" />
                  Regenerate Scene
                </Button>
                <Button variant="outline" className="w-full justify-start" disabled={isGenerating}>
                  <Sparkles className="w-4 h-4 mr-2" />
                  Change Style
                </Button>
              </div>
            </Card>
          </div>
        </div>
      </main>
    </div>
  );
}
