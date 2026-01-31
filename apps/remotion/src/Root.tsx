import { Composition } from "remotion";
import { VideoComposition } from "./compositions/VideoComposition";
import type { VideoCompositionProps } from "./types";

// Default props for Remotion Studio preview
const defaultProps: VideoCompositionProps = {
  scenes: [
    {
      id: 1,
      start_time: 0,
      end_time: 8,
      description: "Opening scene",
      visual_prompt: "A beautiful landscape",
      voiceover_text: "Welcome to our brand",
      on_screen_text: "Welcome",
      asset_url: null,
    },
    {
      id: 2,
      start_time: 8,
      end_time: 16,
      description: "Product showcase",
      visual_prompt: "Product in action",
      voiceover_text: "Discover the difference",
      on_screen_text: "Innovation",
      asset_url: null,
    },
    {
      id: 3,
      start_time: 16,
      end_time: 24,
      description: "Call to action",
      visual_prompt: "Happy customers",
      voiceover_text: "Join us today",
      on_screen_text: null,
      asset_url: null,
    },
  ],
  brand: {
    name: "Demo Brand",
    tagline: "Innovation meets simplicity",
    primary_colors: ["#6366f1", "#8b5cf6"],
    logo_url: null,
    tone: "professional",
  },
  story: {
    title: "Our Story",
    call_to_action: "Get Started Today",
  },
  fps: 30,
  width: 1920,
  height: 1080,
};

// Calculate total duration from scenes
const calculateDuration = (scenes: VideoCompositionProps["scenes"], fps: number): number => {
  if (!scenes.length) return fps * 10; // Default 10 seconds
  const lastScene = scenes[scenes.length - 1];
  return Math.round(lastScene.end_time * fps);
};

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="VideoAd"
        component={VideoComposition}
        durationInFrames={calculateDuration(defaultProps.scenes, defaultProps.fps)}
        fps={defaultProps.fps}
        width={defaultProps.width}
        height={defaultProps.height}
        defaultProps={defaultProps}
        calculateMetadata={({ props }) => {
          return {
            durationInFrames: calculateDuration(props.scenes, props.fps),
            fps: props.fps,
            width: props.width,
            height: props.height,
          };
        }}
      />
    </>
  );
};

