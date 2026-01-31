import { z } from "zod";

// Scene data from the API
export const SceneSchema = z.object({
  id: z.number(),
  start_time: z.number(),
  end_time: z.number(),
  description: z.string(),
  visual_prompt: z.string(),
  voiceover_text: z.string().optional().nullable(),
  on_screen_text: z.string().optional().nullable(),
  asset_url: z.string().optional().nullable(),
});

export type Scene = z.infer<typeof SceneSchema>;

// Brand profile for styling
export const BrandProfileSchema = z.object({
  name: z.string(),
  tagline: z.string().optional().nullable(),
  primary_colors: z.array(z.string()).default([]),
  logo_url: z.string().optional().nullable(),
  tone: z.string().default("professional"),
});

export type BrandProfile = z.infer<typeof BrandProfileSchema>;

// Story info for CTA
export const StorySchema = z.object({
  title: z.string(),
  call_to_action: z.string(),
});

export type Story = z.infer<typeof StorySchema>;

// Input props for the video composition
export const VideoCompositionPropsSchema = z.object({
  scenes: z.array(SceneSchema),
  brand: BrandProfileSchema,
  story: StorySchema,
  fps: z.number().default(30),
  width: z.number().default(1920),
  height: z.number().default(1080),
});

export type VideoCompositionProps = z.infer<typeof VideoCompositionPropsSchema>;

// Render request from API
export const RenderRequestSchema = z.object({
  project_id: z.string(),
  scenes: z.array(SceneSchema),
  brand: BrandProfileSchema,
  story: StorySchema,
  output_filename: z.string().optional(),
});

export type RenderRequest = z.infer<typeof RenderRequestSchema>;

