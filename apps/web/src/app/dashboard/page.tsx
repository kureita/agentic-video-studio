"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Header } from "@/components/layout";
import { Button, Card, Badge } from "@/components/ui";
import { 
  Plus, 
  ArrowRight, 
  Clock, 
  Film,
  ExternalLink,
  Sparkles,
  Loader2,
  Trash2,
  Workflow
} from "lucide-react";
import { projectsApi, Project } from "@/lib/api";

const statusConfig = {
  draft: { label: "Draft", variant: "default" as const },
  analyzing: { label: "Analyzing", variant: "warning" as const },
  generating: { label: "Generating", variant: "warning" as const },
  processing: { label: "Processing", variant: "warning" as const },
  completed: { label: "Completed", variant: "success" as const },
  failed: { label: "Failed", variant: "error" as const },
};

export default function DashboardPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState({ total: 0, completed: 0, totalDuration: 0 });

  useEffect(() => {
    fetchProjects();
  }, []);

  const fetchProjects = async () => {
    try {
      const response = await projectsApi.list();
      const allProjects = response.data;
      setProjects(allProjects.slice(0, 5)); // Show only recent 5
      
      // Calculate stats
      const completed = allProjects.filter(p => p.status === "completed").length;
      const totalDuration = allProjects.reduce((acc, p) => acc + (p.video_duration || 0), 0);
      setStats({ total: allProjects.length, completed, totalDuration });
    } catch (err) {
      console.error("Failed to fetch projects:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (e: React.MouseEvent, projectId: string) => {
    e.preventDefault();
    e.stopPropagation();
    
    if (!confirm("Are you sure you want to delete this project?")) return;
    
    try {
      await projectsApi.delete(projectId);
      fetchProjects(); // Refresh the list
    } catch (err) {
      console.error("Failed to delete project:", err);
    }
  };

  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  const getStatus = (status: string) => {
    return statusConfig[status as keyof typeof statusConfig] || statusConfig.draft;
  };

  return (
    <div className="min-h-screen bg-background">
      <Header />
      
      <main className="container-wide py-12">
        {/* Welcome Section */}
        <div className="mb-12">
          <h1 className="font-display text-display-sm text-foreground mb-2">
            Welcome back
          </h1>
          <p className="text-foreground-muted text-lg">
            Create and manage your AI-generated promotional videos
          </p>
        </div>

        {/* Quick Actions */}
        <div className="grid md:grid-cols-3 gap-6 mb-16">
          <Link href="/projects/new">
            <Card variant="interactive" className="h-full group">
              <div className="flex items-start justify-between">
                <div>
                  <div className="w-12 h-12 rounded-xl bg-accent-muted flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                    <Plus className="w-6 h-6 text-accent" />
                  </div>
                  <h3 className="text-xl font-semibold text-foreground mb-2">
                    Quick Create
                  </h3>
                  <p className="text-foreground-muted">
                    Auto-generate video from a website URL
                  </p>
                </div>
                <ArrowRight className="w-5 h-5 text-foreground-subtle group-hover:text-foreground group-hover:translate-x-1 transition-all" />
              </div>
            </Card>
          </Link>

          <Link href="/canvas">
            <Card variant="interactive" className="h-full group">
              <div className="flex items-start justify-between">
                <div>
                  <div className="w-12 h-12 rounded-xl bg-emerald-500/10 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                    <Workflow className="w-6 h-6 text-emerald-500" />
                  </div>
                  <h3 className="text-xl font-semibold text-foreground mb-2">
                    Canvas Studio
                  </h3>
                  <p className="text-foreground-muted">
                    Full control with visual pipeline editor
                  </p>
                </div>
                <ArrowRight className="w-5 h-5 text-foreground-subtle group-hover:text-foreground group-hover:translate-x-1 transition-all" />
              </div>
            </Card>
          </Link>

          <Card className="h-full">
            <div className="flex items-start justify-between">
              <div className="w-full">
                <div className="w-12 h-12 rounded-xl bg-background-secondary flex items-center justify-center mb-4">
                  <Sparkles className="w-6 h-6 text-foreground" />
                </div>
                <h3 className="text-xl font-semibold text-foreground mb-2">
                  Quick Stats
                </h3>
                {loading ? (
                  <div className="flex items-center justify-center h-16">
                    <Loader2 className="w-5 h-5 animate-spin text-foreground-muted" />
                  </div>
                ) : (
                  <div className="grid grid-cols-3 gap-6 mt-4">
                    <div>
                      <p className="text-2xl font-semibold text-foreground">{stats.total}</p>
                      <p className="text-sm text-foreground-muted">Videos Created</p>
                    </div>
                    <div>
                      <p className="text-2xl font-semibold text-foreground">{stats.completed}</p>
                      <p className="text-sm text-foreground-muted">Completed</p>
                    </div>
                    <div>
                      <p className="text-2xl font-semibold text-foreground">{formatDuration(stats.totalDuration)}</p>
                      <p className="text-sm text-foreground-muted">Total Duration</p>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </Card>
        </div>

        {/* Recent Projects */}
        <div>
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-semibold text-foreground">
              Recent Projects
            </h2>
            <Link href="/projects">
              <Button variant="ghost" size="sm" icon={<ArrowRight className="w-4 h-4" />} iconPosition="right">
                View All
              </Button>
            </Link>
          </div>

          {loading ? (
            <div className="flex items-center justify-center h-32">
              <Loader2 className="w-6 h-6 animate-spin text-foreground-muted" />
            </div>
          ) : projects.length > 0 ? (
            <div className="grid gap-4">
              {projects.map((project) => (
                <Link key={project.id} href={`/projects/${project.id}`}>
                  <Card variant="interactive" className="p-0 overflow-hidden">
                    <div className="flex items-center">
                      {/* Thumbnail */}
                      <div className="w-48 h-28 bg-gradient-to-br from-background-secondary to-background-tertiary flex items-center justify-center border-r border-border flex-shrink-0 overflow-hidden">
                        {project.thumbnail_url ? (
                          <img 
                            src={project.thumbnail_url} 
                            alt={project.brand_name || "Project"} 
                            className="w-full h-full object-cover"
                          />
                        ) : (
                          <Film className="w-8 h-8 text-foreground-subtle" />
                        )}
                      </div>

                      {/* Content */}
                      <div className="flex-1 p-5">
                        <div className="flex items-start justify-between">
                          <div>
                            <h3 className="font-medium text-foreground mb-1">
                              {project.brand_name || "Untitled Project"}
                            </h3>
                            <div className="flex items-center gap-3 text-sm text-foreground-muted">
                              <span className="flex items-center gap-1.5">
                                <ExternalLink className="w-3.5 h-3.5" />
                                {new URL(project.website_url).hostname}
                              </span>
                              <span className="flex items-center gap-1.5">
                                <Clock className="w-3.5 h-3.5" />
                                {formatDuration(project.video_duration)}
                              </span>
                            </div>
                          </div>
                          <div className="flex items-center gap-3">
                            <Badge variant={getStatus(project.status).variant}>
                              {getStatus(project.status).label}
                            </Badge>
                            <button 
                              className="p-2 rounded-lg hover:bg-red-500/10 text-foreground-subtle hover:text-red-500 transition-colors"
                              onClick={(e) => handleDelete(e, project.id)}
                              title="Delete project"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </div>
                        </div>
                      </div>
                    </div>
                  </Card>
                </Link>
              ))}
            </div>
          ) : (
            <Card className="text-center py-12">
              <Film className="w-12 h-12 text-foreground-subtle mx-auto mb-4" />
              <h3 className="text-lg font-medium text-foreground mb-2">
                No projects yet
              </h3>
              <p className="text-foreground-muted mb-6">
                Create your first AI-generated promo video
              </p>
              <Link href="/projects/new">
                <Button icon={<Plus className="w-4 h-4" />}>
                  New Project
                </Button>
              </Link>
            </Card>
          )}
        </div>
      </main>
    </div>
  );
}
