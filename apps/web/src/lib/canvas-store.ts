import { create } from "zustand";
import { persist } from "zustand/middleware";

// Types for the canvas pipeline
export interface BrandData {
  name: string;
  tagline?: string;
  description?: string;
  primary_colors: string[];
  logo_url?: string;
  tone: string;
  products: string[];
  unique_selling_points: string[];
}

export interface StoryData {
  title: string;
  synopsis: string;
  key_messages: string[];
  target_emotion: string;
  call_to_action: string;
}

export interface SceneData {
  id: number;
  start_time: number;
  end_time: number;
  description: string;
  visual_prompt: string;
  image_prompt?: string;
  voiceover_text?: string;
  on_screen_text?: string;
  image_url?: string;
  video_url?: string;
}

export interface StoryBeat {
  id: string;
  index: number;
  name: string;
  description: string;
  script: string;
  visualPrompt: string;
  durationSeconds: number;
  purpose: string;
  hook?: string;
  emotionalNote?: string;
  // Visual generation state
  imageUrl?: string;
  videoUrl?: string;
  videoPrompt?: string;
  extractedFrameUrl?: string;
  generationStatus: "idle" | "generating" | "complete" | "error";
}

export interface StoryOptions {
  theme: string;
  visualStyle: string;
  direction: string;
  duration: number;
  targetAudience?: string;
  additionalNotes?: string;
}

export interface TrendSearchResult {
  title: string;
  url: string;
  content: string;
  score: number;
}

export interface TrendData {
  query: string;
  platform: string;
  results: TrendSearchResult[];
  summary?: string;
}

export interface InspirationBrief {
  brandName: string;
  trendSummary: string;
  keyElements: string[];
  suggestedAngles: string[];
  viralHooks: string[];
  contentIdeas: string[];
}

export interface StoryHook {
  type: string;
  content: string;
  placement: string;
}

export interface ContentBeat {
  name: string;
  description: string;
  durationSeconds: number;
  purpose: string;
}

export interface StrategyMetrics {
  targetAudience: string;
  platform: string;
  contentDuration: number;
  tone: string;
  brandAlignmentScore: number;
  viralPotentialScore: number;
}

export interface StoryStrategy {
  objective: string;
  keyMessage: string;
  emotionalArc: string;
  hooks: StoryHook[];
  contentStructure: ContentBeat[];
  callToAction: string;
  metrics: StrategyMetrics;
  aiRecommendations: string[];
}

export type NodeStatus = "idle" | "loading" | "success" | "error";

export interface CanvasNodeData {
  id: string;
  type: string;
  position: { x: number; y: number };
  data: Record<string, unknown>;
}

export interface CanvasEdgeData {
  id: string;
  source: string;
  target: string;
  animated?: boolean;
  style?: Record<string, unknown>;
}


// Graph Plan Types (from backend)
export interface GraphNode {
  id: string;
  type: string;
  data: Record<string, unknown>;
  position?: { x: number; y: number };
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  label?: string;
}

export interface GraphPlan {
  nodes: GraphNode[];
  edges: GraphEdge[];
  narrative: string;
}

export interface CanvasPipelineState {
  // Project info
  projectId: string | null;
  websiteUrl: string;

  // Pipeline data
  brandData: BrandData | null;
  trendData: TrendData | null;
  inspirationBrief: InspirationBrief | null;
  storyStrategy: StoryStrategy | null;
  storyOptions: StoryOptions;
  storyData: StoryData | null;
  storyBeats: StoryBeat[];
  scenes: SceneData[];

  // Node statuses
  nodeStatuses: {
    brand: NodeStatus;
    trend: NodeStatus;
    inspiration: NodeStatus;
    strategy: NodeStatus;
    story: NodeStatus;
    images: NodeStatus;
    videos: NodeStatus;
    composition: NodeStatus;
    render: NodeStatus;
  };

  // Errors
  errors: Record<string, string | null>;

  // Composition settings
  compositionUrl: string | null;
  finalVideoUrl: string | null;

  // Canvas flow state (for persistence)
  canvasNodes: CanvasNodeData[];
  canvasEdges: CanvasEdgeData[];

  // Actions
  setWebsiteUrl: (url: string) => void;
  setProjectId: (id: string | null) => void;
  setBrandData: (data: BrandData) => void;
  setTrendData: (data: TrendData) => void;
  setInspirationBrief: (data: InspirationBrief) => void;
  setStoryStrategy: (data: StoryStrategy) => void;
  setStoryOptions: (options: Partial<StoryOptions>) => void;
  setStoryData: (data: StoryData) => void;
  setStoryBeats: (beats: StoryBeat[]) => void;
  updateStoryBeat: (beatId: string, data: Partial<StoryBeat>) => void;
  setScenes: (scenes: SceneData[]) => void;
  updateScene: (id: number, data: Partial<SceneData>) => void;
  setNodeStatus: (node: keyof CanvasPipelineState["nodeStatuses"], status: NodeStatus) => void;
  setError: (node: string, error: string | null) => void;
  setCompositionUrl: (url: string) => void;
  setFinalVideoUrl: (url: string) => void;
  setCanvasNodes: (nodes: CanvasNodeData[]) => void;
  setCanvasEdges: (edges: CanvasEdgeData[]) => void;
  applyGraphPlan: (plan: GraphPlan) => void; // New action
  loadFromProject: (data: {
    projectId: string;
    brandData?: BrandData | null;
    storyData?: StoryData | null;
    scenes?: SceneData[];
    storyOptions?: Partial<StoryOptions>;
    canvasNodes?: CanvasNodeData[];
    canvasEdges?: CanvasEdgeData[];
    nodeStatuses?: Partial<CanvasPipelineState["nodeStatuses"]>;
  }) => void;
  reset: () => void;
}


const defaultStoryOptions: StoryOptions = {
  theme: "modern",
  visualStyle: "realistic",
  direction: "inspirational",
  duration: 30,
  targetAudience: "",
  additionalNotes: "",
};

const defaultNodeStatuses = {
  brand: "idle" as NodeStatus,
  trend: "idle" as NodeStatus,
  inspiration: "idle" as NodeStatus,
  strategy: "idle" as NodeStatus,
  story: "idle" as NodeStatus,
  images: "idle" as NodeStatus,
  videos: "idle" as NodeStatus,
  composition: "idle" as NodeStatus,
  render: "idle" as NodeStatus,
};

export const useCanvasStore = create<CanvasPipelineState>()(
  persist(
    (set) => ({
      projectId: null,
      websiteUrl: "",
      brandData: null,
      trendData: null,
      inspirationBrief: null,
      storyStrategy: null,
      storyOptions: defaultStoryOptions,
      storyData: null,
      storyBeats: [],
      scenes: [],
      nodeStatuses: { ...defaultNodeStatuses },
      errors: {},
      compositionUrl: null,
      finalVideoUrl: null,
      canvasNodes: [],
      canvasEdges: [],

      // Actions
      setWebsiteUrl: (url) => set({ websiteUrl: url }),
      setProjectId: (id) => set({ projectId: id }),
      setBrandData: (data) => set({ brandData: data }),
      setTrendData: (data) => set({ trendData: data }),
      setInspirationBrief: (data) => set({ inspirationBrief: data }),
      setStoryStrategy: (data) => set({ storyStrategy: data }),
      setStoryOptions: (options) => set((state) => ({
        storyOptions: { ...state.storyOptions, ...options }
      })),
      setStoryData: (data) => set({ storyData: data }),
      setStoryBeats: (beats) => set({ storyBeats: beats }),
      updateStoryBeat: (beatId, data) => set((state) => ({
        storyBeats: state.storyBeats.map((b) => b.id === beatId ? { ...b, ...data } : b)
      })),
      setScenes: (scenes) => set({ scenes }),
      updateScene: (id, data) => set((state) => ({
        scenes: state.scenes.map((s) => s.id === id ? { ...s, ...data } : s)
      })),
      setNodeStatus: (node, status) => set((state) => ({
        nodeStatuses: { ...state.nodeStatuses, [node]: status }
      })),
      setError: (node, error) => set((state) => ({
        errors: { ...state.errors, [node]: error }
      })),
      setCompositionUrl: (url) => set({ compositionUrl: url }),
      setFinalVideoUrl: (url) => set({ finalVideoUrl: url }),
      setCanvasNodes: (nodes) => set({ canvasNodes: nodes }),
      setCanvasEdges: (edges) => set({ canvasEdges: edges }),
      applyGraphPlan: (plan) => set((state) => {
        // Map backend nodes to frontend CanvasNodes
        const newNodes = plan.nodes.map((node, index) => ({
          id: node.id,
          type: node.type, // TODO: Map backend types to frontend types in Phase 3
          position: node.position || { x: 250, y: index * 150 + 100 }, // Simple auto-layout vertical
          data: node.data
        }));

        const newEdges = plan.edges.map(edge => ({
          id: edge.id,
          source: edge.source,
          target: edge.target,
          animated: true
        }));

        return {
          canvasNodes: newNodes,
          canvasEdges: newEdges
        };
      }),
      loadFromProject: (data) => set((state) => ({
        projectId: data.projectId,
        brandData: data.brandData || null,
        storyData: data.storyData || null,
        scenes: data.scenes || [],
        storyOptions: data.storyOptions ? { ...state.storyOptions, ...data.storyOptions } : state.storyOptions,
        canvasNodes: data.canvasNodes || [],
        canvasEdges: data.canvasEdges || [],
        nodeStatuses: data.nodeStatuses ? { ...state.nodeStatuses, ...data.nodeStatuses } : state.nodeStatuses,
      })),
      reset: () => set({
        projectId: null,
        websiteUrl: "",
        brandData: null,
        storyOptions: defaultStoryOptions,
        storyData: null,
        scenes: [],
        nodeStatuses: { ...defaultNodeStatuses },
        errors: {},
        compositionUrl: null,
        finalVideoUrl: null,
        canvasNodes: [],
        canvasEdges: [],
      }),
    }),
    {
      name: "kureita-canvas-store",
      partialize: (state) => ({
        projectId: state.projectId,
        websiteUrl: state.websiteUrl,
        brandData: state.brandData,
        storyOptions: state.storyOptions,
        storyData: state.storyData,
        scenes: state.scenes,
        nodeStatuses: state.nodeStatuses,
        compositionUrl: state.compositionUrl,
        finalVideoUrl: state.finalVideoUrl,
        canvasNodes: state.canvasNodes,
        canvasEdges: state.canvasEdges,
      }),
    }
  )
);

// Preset templates
export const storyTemplates = [
  {
    id: "product-launch",
    name: "Product Launch",
    description: "Introduce a new product with impact",
    options: { theme: "modern", direction: "exciting", visualStyle: "realistic" }
  },
  {
    id: "brand-story",
    name: "Brand Story",
    description: "Tell your brand's origin and mission",
    options: { theme: "warm", direction: "inspirational", visualStyle: "cinematic" }
  },
  {
    id: "testimonial",
    name: "Customer Testimonial",
    description: "Showcase customer success stories",
    options: { theme: "authentic", direction: "trustworthy", visualStyle: "documentary" }
  },
  {
    id: "explainer",
    name: "Explainer Video",
    description: "Break down complex concepts simply",
    options: { theme: "clean", direction: "educational", visualStyle: "animated" }
  },
  {
    id: "promo",
    name: "Promotional Campaign",
    description: "Drive action with urgency",
    options: { theme: "bold", direction: "energetic", visualStyle: "dynamic" }
  },
];

// Visual style options
export const visualStyleOptions = [
  { id: "realistic", label: "Realistic", description: "Photorealistic imagery" },
  { id: "cinematic", label: "Cinematic", description: "Movie-like quality" },
  { id: "animated", label: "Animated", description: "Motion graphics style" },
  { id: "cartoon", label: "Cartoon", description: "Illustrated look" },
  { id: "minimalist", label: "Minimalist", description: "Clean and simple" },
  { id: "dramatic", label: "Dramatic", description: "High contrast, bold" },
];

// Theme options
export const themeOptions = [
  { id: "modern", label: "Modern" },
  { id: "warm", label: "Warm" },
  { id: "cool", label: "Cool" },
  { id: "bold", label: "Bold" },
  { id: "elegant", label: "Elegant" },
  { id: "playful", label: "Playful" },
];

// Direction options
export const directionOptions = [
  { id: "inspirational", label: "Inspirational" },
  { id: "educational", label: "Educational" },
  { id: "entertaining", label: "Entertaining" },
  { id: "trustworthy", label: "Trustworthy" },
  { id: "exciting", label: "Exciting" },
  { id: "calm", label: "Calm" },
];

// Duration options
export const durationOptions = [
  { value: 15, label: "15s", description: "Social media" },
  { value: 30, label: "30s", description: "Standard promo" },
  { value: 60, label: "60s", description: "Detailed story" },
  { value: 90, label: "90s", description: "Full narrative" },
];

