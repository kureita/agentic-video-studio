"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Header } from "@/components/layout";
import { Button, Card, Badge, Input } from "@/components/ui";
import { 
  Plus, 
  Search,
  Film,
  Clock,
  ExternalLink,
  MoreHorizontal,
  Grid3X3,
  List,
  Loader2,
  Trash2
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

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid");
  const [searchQuery, setSearchQuery] = useState("");

  useEffect(() => {
    fetchProjects();
  }, []);

  const fetchProjects = async () => {
    try {
      const response = await projectsApi.list();
      setProjects(response.data);
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
      setProjects(projects.filter(p => p.id !== projectId));
    } catch (err) {
      console.error("Failed to delete project:", err);
    }
  };

  const filteredProjects = projects.filter(
    (p) =>
      (p.brand_name?.toLowerCase().includes(searchQuery.toLowerCase()) ?? false) ||
      p.website_url.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  const getStatus = (status: string) => {
    return statusConfig[status as keyof typeof statusConfig] || statusConfig.draft;
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

  return (
    <div className="min-h-screen bg-background">
      <Header />
      
      <main className="container-wide py-12">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="font-display text-display-sm text-foreground mb-2">
              Projects
            </h1>
            <p className="text-foreground-muted">
              {projects.length} total project{projects.length !== 1 ? "s" : ""}
            </p>
          </div>
          <Link href="/projects/new">
            <Button icon={<Plus className="w-4 h-4" />}>
              New Project
            </Button>
          </Link>
        </div>

        {/* Filters */}
        <div className="flex items-center gap-4 mb-8">
          <div className="flex-1 max-w-md">
            <Input
              placeholder="Search projects..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              icon={<Search className="w-4 h-4" />}
            />
          </div>
          <div className="flex items-center gap-1 p-1 bg-background-secondary rounded-lg">
            <button
              onClick={() => setViewMode("grid")}
              className={`p-2 rounded-md transition-colors ${
                viewMode === "grid" 
                  ? "bg-surface text-foreground shadow-subtle" 
                  : "text-foreground-muted hover:text-foreground"
              }`}
            >
              <Grid3X3 className="w-4 h-4" />
            </button>
            <button
              onClick={() => setViewMode("list")}
              className={`p-2 rounded-md transition-colors ${
                viewMode === "list" 
                  ? "bg-surface text-foreground shadow-subtle" 
                  : "text-foreground-muted hover:text-foreground"
              }`}
            >
              <List className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Projects Grid/List */}
        {viewMode === "grid" ? (
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredProjects.map((project) => (
              <Link key={project.id} href={`/projects/${project.id}`}>
                <Card variant="interactive" className="p-0 overflow-hidden h-full">
                  {/* Thumbnail */}
                  <div className="aspect-video bg-gradient-to-br from-background-secondary to-background-tertiary flex items-center justify-center relative">
                    {project.thumbnail_url ? (
                      <img 
                        src={project.thumbnail_url} 
                        alt={project.brand_name || "Project"} 
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      <Film className="w-10 h-10 text-foreground-subtle" />
                    )}
                  </div>
                  
                  {/* Content */}
                  <div className="p-5">
                    <div className="flex items-start justify-between mb-3">
                      <h3 className="font-medium text-foreground line-clamp-1">
                        {project.brand_name || "Untitled Project"}
                      </h3>
                      <button 
                        className="p-1.5 -mr-1.5 rounded-lg hover:bg-red-500/10 text-foreground-subtle hover:text-red-500 transition-colors"
                        onClick={(e) => handleDelete(e, project.id)}
                        title="Delete project"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                    
                    <div className="flex items-center gap-3 text-sm text-foreground-muted mb-4">
                      <span className="flex items-center gap-1.5 truncate">
                        <ExternalLink className="w-3.5 h-3.5 flex-shrink-0" />
                        {new URL(project.website_url).hostname}
                      </span>
                    </div>

                    <div className="flex items-center justify-between">
                      <Badge variant={getStatus(project.status).variant}>
                        {getStatus(project.status).label}
                      </Badge>
                      <span className="flex items-center gap-1.5 text-sm text-foreground-subtle">
                        <Clock className="w-3.5 h-3.5" />
                        {formatDuration(project.video_duration)}
                      </span>
                    </div>
                  </div>
                </Card>
              </Link>
            ))}
          </div>
        ) : (
          <div className="grid gap-3">
            {filteredProjects.map((project) => (
              <Link key={project.id} href={`/projects/${project.id}`}>
                <Card variant="interactive" className="p-4">
                  <div className="flex items-center gap-4">
                    <div className="w-16 h-16 rounded-lg bg-gradient-to-br from-background-secondary to-background-tertiary flex items-center justify-center flex-shrink-0 overflow-hidden">
                      {project.thumbnail_url ? (
                        <img 
                          src={project.thumbnail_url} 
                          alt={project.brand_name || "Project"} 
                          className="w-full h-full object-cover"
                        />
                      ) : (
                        <Film className="w-6 h-6 text-foreground-subtle" />
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <h3 className="font-medium text-foreground mb-1 truncate">
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
                </Card>
              </Link>
            ))}
          </div>
        )}

        {/* Empty State */}
        {filteredProjects.length === 0 && !loading && (
          <Card className="text-center py-16">
            {searchQuery ? (
              <>
                <Search className="w-12 h-12 text-foreground-subtle mx-auto mb-4" />
                <h3 className="text-lg font-medium text-foreground mb-2">
                  No projects found
                </h3>
                <p className="text-foreground-muted">
                  Try adjusting your search query
                </p>
              </>
            ) : (
              <>
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
              </>
            )}
          </Card>
        )}
      </main>
    </div>
  );
}
