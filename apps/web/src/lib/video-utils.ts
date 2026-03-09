/**
 * Video utility functions for client-side video rendering
 */

export interface VideoClip {
  url: string;
  startTime: number;
  duration: number;
  transition?: "fade" | "slide" | "cut" | "zoom";
}

export interface VideoCompositionConfig {
  clips: VideoClip[];
  audio?: string;
  width?: number;
  height?: number;
  fps?: number;
}

/**
 * Parse editing instruction and generate video composition config
 */
export function parseEditingInstruction(
  instruction: string,
  videoUrls: string[],
  audioUrl?: string
): VideoCompositionConfig {
  const lowerInstruction = instruction.toLowerCase();

  // Default configuration
  const config: VideoCompositionConfig = {
    clips: [],
    audio: audioUrl,
    width: 1920,
    height: 1080,
    fps: 30,
  };

  // Determine transition type from instruction
  let transition: VideoClip["transition"] = "fade";
  if (lowerInstruction.includes("cut") || lowerInstruction.includes("quick")) {
    transition = "cut";
  } else if (lowerInstruction.includes("slide")) {
    transition = "slide";
  } else if (lowerInstruction.includes("zoom")) {
    transition = "zoom";
  }

  // Determine clip duration from instruction
  let clipDuration = 4; // Default 4 seconds
  const durationMatch = lowerInstruction.match(/(\d+)\s*(?:second|sec|s)/);
  if (durationMatch) {
    clipDuration = parseInt(durationMatch[1], 10);
  }

  // Create clips
  let currentTime = 0;
  videoUrls.forEach((url) => {
    config.clips.push({
      url,
      startTime: currentTime,
      duration: clipDuration,
      transition,
    });
    currentTime += clipDuration;
  });

  return config;
}

/**
 * Calculate total duration of video composition
 */
export function calculateTotalDuration(clips: VideoClip[]): number {
  if (clips.length === 0) return 0;

  const lastClip = clips[clips.length - 1];
  return lastClip.startTime + lastClip.duration;
}

/**
 * Convert duration in seconds to frames
 */
export function secondsToFrames(seconds: number, fps: number = 30): number {
  return Math.round(seconds * fps);
}

/**
 * Convert frames to seconds
 */
export function framesToSeconds(frames: number, fps: number = 30): number {
  return frames / fps;
}

/**
 * Validate video URL
 */
export function isValidVideoUrl(url: string): boolean {
  if (!url) return false;

  // Check if it's a valid URL or path
  try {
    new URL(url);
    return true;
  } catch {
    // Could be a relative path
    return url.startsWith('/') || url.startsWith('./');
  }
}

/**
 * Get video metadata (duration, dimensions) from URL
 * Returns a promise that resolves with video metadata
 */
export function getVideoMetadata(url: string): Promise<{
  duration: number;
  width: number;
  height: number;
}> {
  return new Promise((resolve, reject) => {
    const video = document.createElement('video');
    video.preload = 'metadata';

    video.onloadedmetadata = () => {
      resolve({
        duration: video.duration,
        width: video.videoWidth,
        height: video.videoHeight,
      });
      video.remove();
    };

    video.onerror = () => {
      reject(new Error(`Failed to load video metadata from ${url}`));
      video.remove();
    };

    video.src = url;
  });
}

/**
 * Adjust clip durations to match actual video durations
 */
export async function adjustClipDurations(clips: VideoClip[]): Promise<VideoClip[]> {
  const adjustedClips: VideoClip[] = [];
  let currentTime = 0;

  for (const clip of clips) {
    try {
      const metadata = await getVideoMetadata(clip.url);
      adjustedClips.push({
        ...clip,
        startTime: currentTime,
        duration: Math.min(clip.duration, metadata.duration),
      });
      currentTime += adjustedClips[adjustedClips.length - 1].duration;
    } catch {
      console.warn(`Failed to get metadata for ${clip.url}, using default duration`);
      adjustedClips.push({
        ...clip,
        startTime: currentTime,
      });
      currentTime += clip.duration;
    }
  }

  return adjustedClips;
}

/**
 * Export video composition to server for high-quality rendering
 */
export async function exportVideoComposition(
  config: VideoCompositionConfig,
  outputFilename?: string
): Promise<{ success: boolean; videoUrl?: string; error?: string }> {
  try {
    const response = await fetch('/api/render-video', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        clips: config.clips,
        audio: config.audio,
        width: config.width,
        height: config.height,
        fps: config.fps,
        outputFilename,
      }),
    });

    if (!response.ok) {
      throw new Error(`Server responded with ${response.status}`);
    }

    const result = await response.json();
    return {
      success: true,
      videoUrl: result.videoUrl,
    };
  } catch (error) {
    console.error('Export failed:', error);
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error',
    };
  }
}

/**
 * Download video from URL
 */
export function downloadVideo(url: string, filename?: string): void {
  const link = document.createElement('a');
  link.href = url;
  link.download = filename || `video-${Date.now()}.mp4`;
  link.target = '_blank';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

/**
 * Extract a specific frame from a video URL as a base64 Data URL.
 * 
 * @param videoUrl The URL of the video to extract from
 * @param timeRatio The relative position in the video (0 for start, 1 for end, etc.)
 * @returns A promise resolving to a base64 encoded JPEG image
 */
export const extractFrameFromVideo = (videoUrl: string, timeRatio: number): Promise<string> => {
  return new Promise((resolve, reject) => {
    const video = document.createElement('video');
    video.crossOrigin = "anonymous";
    video.src = videoUrl;

    // Timeout safeguard
    const timeoutId = setTimeout(() => reject(new Error("Video load timeout")), 15000);

    video.onloadeddata = () => {
      const targetTime = timeRatio === 1 ? Math.max(0, video.duration - 0.1) : 0;
      video.currentTime = targetTime;
    };

    video.onseeked = () => {
      clearTimeout(timeoutId);
      try {
        const canvas = document.createElement('canvas');
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        const ctx = canvas.getContext('2d');
        if (!ctx) throw new Error("Failed to get canvas context");
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        resolve(canvas.toDataURL('image/jpeg', 0.9));
      } catch (err) {
        reject(err);
      }
    };

    video.onerror = () => {
      clearTimeout(timeoutId);
      reject(new Error("Video loading error (possible CORS issue)"));
    };

    video.load();
  });
};
