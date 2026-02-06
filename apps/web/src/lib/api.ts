import axios from "axios";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

// Request interceptor for auth tokens
api.interceptors.request.use(
  (config) => {
    // Add auth token if available
    const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    // Handle common errors
    if (error.response?.status === 401) {
      // Handle unauthorized
      if (typeof window !== "undefined") {
        localStorage.removeItem("token");
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

// ============================================
// Project API
// ============================================

export interface CreateProjectData {
  website_url: string;
  brand_name?: string;
  description?: string;
  target_audience?: string;
  video_duration?: number;
  style?: string;
}

export interface Project {
  id: string;
  website_url: string;
  brand_name?: string;
  description?: string;
  target_audience?: string;
  video_duration: number;
  style: string;
  status: string;
  progress: number;
  brand_profile?: BrandProfile;
  story?: Story;
  scenes?: Scene[];
  video_url?: string;
  thumbnail_url?: string;
  created_at: string;
  updated_at: string;
}

export interface BrandProfile {
  name: string;
  tagline?: string;
  description?: string;
  primary_colors: string[];
  logo_url?: string;
  tone: string;
  products: string[];
  unique_selling_points: string[];
}

export interface Story {
  title: string;
  synopsis: string;
  key_messages: string[];
  target_emotion: string;
  call_to_action: string;
}

export interface Scene {
  id: number;
  start_time: number;
  end_time: number;
  description: string;
  visual_prompt: string;
  voiceover_text?: string;
  on_screen_text?: string;
  asset_url?: string;
}

export interface GenerationStage {
  id: string;
  label: string;
  status: "pending" | "in_progress" | "completed" | "failed";
  started_at?: string;
  completed_at?: string;
  error?: string;
}

export interface ProjectWithStages extends Project {
  stages: GenerationStage[];
}

export const projectsApi = {
  list: (status?: string) =>
    api.get<Project[]>("/api/projects", { params: { status } }),

  get: (id: string) =>
    api.get<ProjectWithStages>(`/api/projects/${id}`),

  create: (data: CreateProjectData) =>
    api.post<Project>("/api/projects", data),

  update: (id: string, data: Partial<CreateProjectData>) =>
    api.patch<Project>(`/api/projects/${id}`, data),

  delete: (id: string) =>
    api.delete(`/api/projects/${id}`),

  start: (id: string) =>
    api.post(`/api/projects/${id}/start`),
};

// ============================================
// Scrape API
// ============================================

export interface ScrapeResponse {
  url: string;
  title?: string;
  meta_description?: string;
  content_preview: string;
  images_count: number;
  brand_profile?: BrandProfile;
}

export const scrapeApi = {
  scrape: (url: string, brand_name?: string) =>
    api.post<ScrapeResponse>("/api/scrape", { url, brand_name }),

  analyze: (url: string, brand_name?: string) =>
    api.post("/api/scrape/analyze", { url, brand_name }),
};

// ============================================
// Generate API
// ============================================

export const generateApi = {
  story: (projectId: string) =>
    api.post("/api/generate/story", { project_id: projectId }),

  video: (prompt: string, duration?: number, useFastModel?: boolean) =>
    api.post("/api/generate/video", {
      prompt,
      duration: duration || 8,
      use_fast_model: useFastModel || false,
    }),

  audio: (text: string, voiceId?: string) =>
    api.post("/api/generate/audio", { text, voice_id: voiceId }),

  voices: () =>
    api.get("/api/generate/voices"),

  assets: (projectId: string) =>
    api.post(`/api/generate/${projectId}/assets`),
};

// ============================================
// Canvas Pipeline API
// ============================================

export interface CanvasCreateData {
  website_url: string;
}

export interface StoryOptionsData {
  theme: string;
  visual_style: string;
  direction: string;
  duration: number;
  target_audience?: string;
  additional_notes?: string;
}

export interface CanvasBrandResponse {
  project_id: string;
  brand_profile: BrandProfile;
}

export interface CanvasStoryResponse {
  story: Story;
  scenes: Scene[];
}

export interface CanvasImageResponse {
  scenes: Scene[];
}

export interface CanvasVideoResponse {
  scenes: Scene[];
}

export interface CanvasComposeResponse {
  preview_url: string;
}

export interface CanvasRenderResponse {
  video_url: string;
}

export interface CanvasNode {
  id: string;
  type: string;
  position: { x: number; y: number };
  data: Record<string, unknown>;
}

export interface CanvasEdge {
  id: string;
  source: string;
  target: string;
  animated?: boolean;
  style?: Record<string, unknown>;
}

export interface CanvasStateResponse {
  nodes: CanvasNode[];
  edges: CanvasEdge[];
}

export interface ProjectLoadResponse {
  project_id: string;
  brand_profile?: BrandProfile;
  story?: Story;
  scenes: Scene[];
  story_options?: {
    theme: string;
    visual_style: string;
    direction: string;
    duration: number;
    target_audience?: string;
    additional_notes?: string;
  };
  canvas_state?: {
    nodes: CanvasNode[];
    edges: CanvasEdge[];
  };
  status: string;
  progress: number;
}

export const canvasApi = {
  // Load existing canvas project
  load: (projectId: string) =>
    api.get<ProjectLoadResponse>(`/api/canvas/${projectId}`),

  // Save canvas state (nodes and edges)
  saveState: (projectId: string, nodes: CanvasNode[], edges: CanvasEdge[]) =>
    api.put<CanvasStateResponse>(`/api/canvas/${projectId}/state`, { nodes, edges }),

  // Create canvas project and analyze brand
  create: (data: CanvasCreateData) =>
    api.post<CanvasBrandResponse>("/api/canvas", data),

  // Generate story and script
  generateStory: (projectId: string, options: StoryOptionsData) =>
    api.post<CanvasStoryResponse>(`/api/canvas/${projectId}/story`, options),

  // Improve/edit story with LLM
  improveStory: (projectId: string, data: { synopsis: string; script_text: string }) =>
    api.post<CanvasStoryResponse>(`/api/canvas/${projectId}/story/improve`, data),

  // Improve image prompts with AI
  improveImagePrompts: (projectId: string, data: { prompts: { scene_id: number; visual_prompt: string }[]; visual_style: string }) =>
    api.post<{ prompts: { scene_id: number; visual_prompt: string }[] }>(`/api/canvas/${projectId}/images/improve`, data),

  // Generate images for all scenes
  generateImages: (projectId: string, options: { visual_style: string }) =>
    api.post<CanvasImageResponse>(`/api/canvas/${projectId}/images`, options),

  // Regenerate single image
  regenerateImage: (projectId: string, sceneId: number, data: { prompt?: string; visual_style: string }) =>
    api.post<{ image_url: string; image_prompt: string }>(`/api/canvas/${projectId}/images/${sceneId}`, data),

  // Generate videos for all scenes
  generateVideos: (projectId: string) =>
    api.post<CanvasVideoResponse>(`/api/canvas/${projectId}/videos`),

  // Regenerate single video
  // Regenerate single video
  regenerateVideo: (projectId: string, sceneId: number, options?: { prompt?: string; imageUrl?: string }) =>
    api.post<{ video_url: string }>(`/api/canvas/${projectId}/videos/${sceneId}`, {
      prompt: options?.prompt,
      image_url: options?.imageUrl
    }),

  // Compose video with Remotion
  compose: (projectId: string, options: { transition: string; show_brand_watermark: boolean; show_cta: boolean }) =>
    api.post<CanvasComposeResponse>(`/api/canvas/${projectId}/compose`, options),

  // Final render
  render: (projectId: string, options: { resolution: string }) =>
    api.post<CanvasRenderResponse>(`/api/canvas/${projectId}/render`, options),

  // Extract last frame from video
  extractFrame: (projectId: string, videoUrl: string) =>
    api.post<{ frame_url: string }>(`/api/canvas/${projectId}/video/extract-frame`, {
      video_url: videoUrl,
      num_frames: 1,
    }),
};

// ============================================
// Brands API
// ============================================

export interface Brand {
  id: string;
  name: string;
  website_url?: string;
  tagline?: string;
  description?: string;
  primary_colors: string[];
  logo_url?: string;
  tone: string;
  products: string[];
  unique_selling_points: string[];
  target_audience?: string;
  created_at: string;
  updated_at: string;
}

export interface BrandCreateData {
  name: string;
  website_url?: string;
  tagline?: string;
  description?: string;
  primary_colors?: string[];
  logo_url?: string;
  tone?: string;
  products?: string[];
  unique_selling_points?: string[];
  target_audience?: string;
}

export interface BrandUpdateData {
  name?: string;
  website_url?: string;
  tagline?: string;
  description?: string;
  primary_colors?: string[];
  logo_url?: string;
  tone?: string;
  products?: string[];
  unique_selling_points?: string[];
  target_audience?: string;
}

export interface BrandListResponse {
  brands: Brand[];
  total: number;
}

export const brandsApi = {
  // List all brands
  list: (skip?: number, limit?: number) =>
    api.get<BrandListResponse>("/api/brands", { params: { skip, limit } }),

  // Get single brand
  get: (brandId: string) =>
    api.get<Brand>(`/api/brands/${brandId}`),

  // Create brand
  create: (data: BrandCreateData) =>
    api.post<Brand>("/api/brands", data),

  // Update brand
  update: (brandId: string, data: BrandUpdateData) =>
    api.put<Brand>(`/api/brands/${brandId}`, data),

  // Delete brand
  delete: (brandId: string) =>
    api.delete(`/api/brands/${brandId}`),

  // Analyze website and create brand
  analyzeWebsite: (websiteUrl: string) =>
    api.post<Brand>("/api/brands/analyze-website", { website_url: websiteUrl }),
};

// ============================================
// Trends API
// ============================================

export interface SearchResult {
  title: string;
  url: string;
  content: string;
  score: number;
}

export interface TrendResearchResult {
  query: string;
  results: SearchResult[];
  summary?: string;
}

export interface InspirationBrief {
  brand_name: string;
  trend_summary: string;
  key_elements: string[];
  suggested_angles: string[];
  viral_hooks: string[];
  content_ideas: string[];
}

export const trendsApi = {
  // Search trends
  search: (query: string, maxResults?: number) =>
    api.post<TrendResearchResult>("/api/trends/search", { query, max_results: maxResults || 5 }),

  // Search viral trends
  searchViral: (topic: string, platform?: string) =>
    api.post<TrendResearchResult>("/api/trends/viral", { topic, platform: platform || "general" }),

  // Search content inspiration
  searchInspiration: (brandName: string, industry: string, contentType?: string) =>
    api.post<TrendResearchResult>("/api/trends/inspiration", {
      brand_name: brandName,
      industry,
      content_type: contentType || "video",
    }),

  // Generate inspiration brief
  generateBrief: (brandName: string, brandDescription: string, trendQuery: string) =>
    api.post<InspirationBrief>("/api/trends/brief", null, {
      params: { brand_name: brandName, brand_description: brandDescription, trend_query: trendQuery },
    }),
};

// ============================================
// Strategy API
// ============================================

export interface StoryHook {
  type: string;
  content: string;
  placement: string;
}

export interface ContentBeat {
  name: string;
  description: string;
  duration_seconds: number;
  purpose: string;
}

export interface StrategyMetrics {
  target_audience: string;
  platform: string;
  content_duration: number;
  tone: string;
  brand_alignment_score: number;
  viral_potential_score: number;
}

export interface StoryStrategy {
  objective: string;
  key_message: string;
  emotional_arc: string;
  hooks: StoryHook[];
  content_structure: ContentBeat[];
  call_to_action: string;
  metrics: StrategyMetrics;
  ai_recommendations: string[];
}

export interface StrategyRequest {
  brand_name: string;
  brand_description?: string;
  trend_query: string;
  trend_summary?: string;
  inspiration_ideas?: string[];
  target_platform?: string;
  content_duration?: number;
  target_audience?: string;
}

export const strategyApi = {
  // Generate story strategy
  generate: (request: StrategyRequest) =>
    api.post<StoryStrategy>("/api/strategy/generate", request),
};

// ============================================
// Beats API
// ============================================

export interface Beat {
  id: string;
  index: number;
  name: string;
  description: string;
  script: string;
  visual_prompt: string;
  duration_seconds: number;
  purpose: string;
  hook?: string;
  emotional_note?: string;
  image_url?: string;
  video_url?: string;
  generation_status: "idle" | "generating" | "complete" | "error";
}

export interface BeatCreate {
  index: number;
  name: string;
  description: string;
  script?: string;
  visual_prompt?: string;
  duration_seconds?: number;
  purpose?: string;
  hook?: string;
  emotional_note?: string;
}

export interface BeatUpdate {
  name?: string;
  description?: string;
  script?: string;
  visual_prompt?: string;
  duration_seconds?: number;
  purpose?: string;
  hook?: string;
  emotional_note?: string;
  index?: number;
}

export interface BeatList {
  beats: Beat[];
  total: number;
}

export interface GenerateBeatsRequest {
  project_id: string;
  strategy_objective: string;
  content_structure: { name: string; description: string; duration_seconds: number; purpose: string }[];
  target_duration?: number;
}

export interface GenerateBeatsResponse {
  beats: Beat[];
  message: string;
}

export const beatsApi = {
  // Get all beats for a project
  getAll: (projectId: string) =>
    api.get<BeatList>(`/api/beats/${projectId}`),

  // Get a single beat
  get: (projectId: string, beatId: string) =>
    api.get<Beat>(`/api/beats/${projectId}/${beatId}`),

  // Create a new beat
  create: (projectId: string, beat: BeatCreate) =>
    api.post<Beat>(`/api/beats/${projectId}`, beat),

  // Update a beat
  update: (projectId: string, beatId: string, updates: BeatUpdate) =>
    api.patch<Beat>(`/api/beats/${projectId}/${beatId}`, updates),

  // Delete a beat
  delete: (projectId: string, beatId: string) =>
    api.delete(`/api/beats/${projectId}/${beatId}`),

  // Generate beats from strategy
  generate: (projectId: string, request: GenerateBeatsRequest) =>
    api.post<GenerateBeatsResponse>(`/api/beats/${projectId}/generate`, request),

  // Reorder beats
  reorder: (projectId: string, beatOrder: string[]) =>
    api.post<BeatList>(`/api/beats/${projectId}/reorder`, beatOrder),
};

// ============================================
// Health Check
// ============================================

export const healthApi = {
  check: () => api.get("/health"),
};
