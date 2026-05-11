import axios from "axios";
import { toast } from "sonner";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

// ============================================
// Auth0 Token Integration
// ============================================

// The AuthProvider sets this after mounting
let authTokenGetter: (() => Promise<string>) | null = null;

export function setAuthTokenGetter(getter: () => Promise<string>) {
  authTokenGetter = getter;
}

// Request interceptor — attach Auth0 access token
api.interceptors.request.use(
  async (config) => {
    if (authTokenGetter) {
      try {
        const token = await authTokenGetter();
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
      } catch (err) {
        // Token fetch failed — request will go through without auth
        console.warn("Failed to get auth token:", err);
      }
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      if (typeof window !== "undefined") {
        // Don't trigger logout/toast on public view pages
        const isPublicPage = window.location.pathname.startsWith("/w");
        if (!isPublicPage) {
          toast.error("Session expired. Please log in again.");
          window.dispatchEvent(new CustomEvent("auth:unauthorized"));
        }
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
  regenerateVideo: (projectId: string, sceneId: number) =>
    api.post<{ video_url: string }>(`/api/canvas/${projectId}/videos/${sceneId}`),

  // Compose video with Remotion
  compose: (projectId: string, options: { transition: string; show_brand_watermark: boolean; show_cta: boolean }) =>
    api.post<CanvasComposeResponse>(`/api/canvas/${projectId}/compose`, options),

  // Final render
  render: (projectId: string, options: { resolution: string }) =>
    api.post<CanvasRenderResponse>(`/api/canvas/${projectId}/render`, options),
};

// ============================================
// Billing API
// ============================================

export interface ModelConfig {
  id: string;
  label: string;
  width?: number;
  height?: number;
  quality?: string;
  resolution?: string;
  duration?: number;
  audio?: boolean;
  pricing_note?: string;
  est_price_usd?: number;
  est_provider_price_usd?: number;
  est_price_usd_per_min?: number;
  est_provider_price_usd_per_min?: number;
  est_price_usd_per_second?: number;
  est_provider_price_usd_per_second?: number;
  est_price_source?: string;
  fal_endpoint_id?: string;
  fal_unit?: string;
  fal_unit_price_usd?: number;
  fal_price_source?: string;
}

export interface Model {
  id: string;
  name: string;
  provider: string;
  type: "image" | "video" | "audio" | "llm";
  tier: string;
  category?: string;        // Sub-type for audio: "voice_design" | "voice_clone" | "music" | "sfx"
  coming_soon?: boolean;    // True if model is announced but not yet available
  capabilities: string[];
  input_modes?: string[];
  duration_min?: number;
  duration_max?: number;
  duration_step?: number;
  reference_images_min?: number;
  reference_images_max?: number;
  elements_min?: number;
  elements_max?: number;
  frame_images_min?: number;
  frame_images_max?: number;
  native_audio_default?: boolean;
  requires_input_duration?: boolean;
  configs: ModelConfig[];
  default_config_id: string;
}

export const billingApi = {
  getModels: () => api.get<{ models: Model[] }>("/api/billing/models"),
  getBalance: () => api.get<{ balance: number }>("/api/billing/balance"),
};

// ============================================
// Assets API
// ============================================

export interface PresignedUploadResponse {
  success: boolean;
  upload_url?: string;
  upload_method?: "PUT" | "POST";
  upload_fields?: Record<string, string>;
  file_url?: string;
  key?: string;
  is_local?: boolean;
  max_file_size?: number;
  tenant_used_bytes?: number;
  tenant_quota_bytes?: number;
}

export const assetsApi = {
  getPresignedUrl: (filename: string, contentType: string, fileSize: number) =>
    api.get<PresignedUploadResponse>("/api/assets/upload/presigned", {
      params: { filename, content_type: contentType, file_size: fileSize },
    }),

  confirmPresignedUpload: (data: {
    fileUrl: string;
    workflowId?: string;
    workflowName?: string;
    nodeId?: string;
    nodeType?: string;
    nodeData?: Record<string, unknown>;
  }) =>
    api.post<{
      success: boolean;
      url: string;
      type: string;
      media_kind: string;
      asset_size_bytes: number;
      tenant_used_bytes: number;
      tenant_quota_bytes: number;
    }>("/api/assets/upload/presigned/confirm", {
      file_url: data.fileUrl,
      workflow_id: data.workflowId,
      workflow_name: data.workflowName,
      node_id: data.nodeId,
      node_type: data.nodeType,
      node_data: data.nodeData,
    }),

  upload: (
    file: File,
    onUploadProgress?: (progressEvent: { loaded: number; total?: number }) => void,
    options?: { workflowId?: string; workflowName?: string }
  ) => {
    const formData = new FormData();
    formData.append("file", file);
    if (options?.workflowId) {
      formData.append("workflow_id", options.workflowId);
    }
    if (options?.workflowName) {
      formData.append("workflow_name", options.workflowName);
    }
    return api.post("/api/assets/upload", formData, {
      headers: { "Content-Type": "multipart/form-data" },
      onUploadProgress,
    });
  },
};

// ============================================
// Health Check
// ============================================

export const healthApi = {
  check: () => api.get("/health"),
};
