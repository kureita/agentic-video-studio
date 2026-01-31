import express from "express";
import { bundle } from "@remotion/bundler";
import { renderMedia, selectComposition } from "@remotion/renderer";
import path from "path";
import fs from "fs";
import { RenderRequestSchema, type VideoCompositionProps } from "./types";

const app = express();
app.use(express.json({ limit: "50mb" }));

const PORT = process.env.PORT || 3001;
// Output to API's static folder so videos are served correctly
// Use process.cwd() since we run from apps/remotion
const OUTPUT_DIR = process.env.OUTPUT_DIR || path.resolve(process.cwd(), "../api/static/videos");

// Ensure output directory exists
if (!fs.existsSync(OUTPUT_DIR)) {
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
}
console.log(`[Remotion] Output directory resolved to: ${path.resolve(OUTPUT_DIR)}`);

// Health check
app.get("/health", (req, res) => {
  res.json({ status: "healthy", service: "remotion-renderer" });
});

// Render video endpoint
app.post("/render", async (req, res) => {
  const startTime = Date.now();
  
  try {
    // Validate request
    const parsed = RenderRequestSchema.safeParse(req.body);
    if (!parsed.success) {
      return res.status(400).json({ 
        error: "Invalid request", 
        details: parsed.error.issues 
      });
    }
    
    const { project_id, scenes, brand, story, output_filename } = parsed.data;
    
    console.log(`[Remotion] Starting render for project: ${project_id}`);
    console.log(`[Remotion] Scenes: ${scenes.length}, Duration: ${scenes[scenes.length - 1]?.end_time || 0}s`);
    
    // Calculate video metadata
    const fps = 30;
    const lastScene = scenes[scenes.length - 1];
    const durationInFrames = lastScene ? Math.round(lastScene.end_time * fps) : fps * 10;
    
    // Build input props
    const inputProps: VideoCompositionProps = {
      scenes,
      brand,
      story,
      fps,
      width: 1920,
      height: 1080,
    };
    
    // Bundle the Remotion project
    console.log("[Remotion] Bundling...");
    const bundleLocation = await bundle({
      entryPoint: path.join(__dirname, "index.ts"),
      onProgress: (progress) => {
        if (progress % 25 === 0) {
          console.log(`[Remotion] Bundle progress: ${progress}%`);
        }
      },
    });
    
    // Select composition
    const composition = await selectComposition({
      serveUrl: bundleLocation,
      id: "VideoAd",
      inputProps,
    });
    
    // Output file
    const filename = output_filename || `${project_id}_${Date.now()}.mp4`;
    const outputPath = path.join(OUTPUT_DIR, filename);
    
    // Render the video
    console.log("[Remotion] Rendering...");
    await renderMedia({
      composition: {
        ...composition,
        durationInFrames,
        fps,
        width: 1920,
        height: 1080,
      },
      serveUrl: bundleLocation,
      codec: "h264",
      outputLocation: outputPath,
      inputProps,
      onProgress: ({ progress }) => {
        if (Math.round(progress * 100) % 10 === 0) {
          console.log(`[Remotion] Render progress: ${Math.round(progress * 100)}%`);
        }
      },
    });
    
    const duration = ((Date.now() - startTime) / 1000).toFixed(1);
    console.log(`[Remotion] Render complete in ${duration}s: ${outputPath}`);
    
    // Return the output path
    res.json({
      success: true,
      output_path: outputPath,
      filename,
      duration_seconds: parseFloat(duration),
    });
    
  } catch (error) {
    console.error("[Remotion] Render error:", error);
    res.status(500).json({ 
      error: "Render failed", 
      message: error instanceof Error ? error.message : "Unknown error" 
    });
  }
});

// Get render status (for future async rendering)
app.get("/status/:jobId", (req, res) => {
  // TODO: Implement job queue for async rendering
  res.json({ status: "not_implemented" });
});

app.listen(PORT, () => {
  console.log(`[Remotion] Render server running on port ${PORT}`);
  console.log(`[Remotion] Output directory: ${OUTPUT_DIR}`);
});

