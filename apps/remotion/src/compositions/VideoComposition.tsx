import { AbsoluteFill, Sequence, useCurrentFrame, useVideoConfig, OffthreadVideo, interpolate, spring } from "remotion";
import type { VideoCompositionProps, Scene } from "../types";

// Text overlay component with animation
const TextOverlay: React.FC<{
  text: string;
  position: "top" | "center" | "bottom";
  style?: "title" | "subtitle" | "caption";
  delay?: number;
}> = ({ text, position, style = "subtitle", delay = 0 }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  
  // Fade in animation
  const opacity = interpolate(
    frame - delay,
    [0, fps * 0.5],
    [0, 1],
    { extrapolateRight: "clamp" }
  );
  
  // Slide up animation
  const translateY = interpolate(
    frame - delay,
    [0, fps * 0.5],
    [20, 0],
    { extrapolateRight: "clamp" }
  );

  const positionStyles: Record<string, React.CSSProperties> = {
    top: { top: 60, left: 0, right: 0 },
    center: { top: "50%", left: 0, right: 0, transform: `translateY(-50%) translateY(${translateY}px)` },
    bottom: { bottom: 100, left: 0, right: 0 },
  };

  const textStyles: Record<string, React.CSSProperties> = {
    title: { fontSize: 72, fontWeight: 700, letterSpacing: -1 },
    subtitle: { fontSize: 42, fontWeight: 500 },
    caption: { fontSize: 28, fontWeight: 400 },
  };

  return (
    <div
      style={{
        position: "absolute",
        ...positionStyles[position],
        display: "flex",
        justifyContent: "center",
        padding: "0 80px",
        opacity,
        transform: position !== "center" ? `translateY(${translateY}px)` : undefined,
      }}
    >
      <div
        style={{
          color: "white",
          textAlign: "center",
          textShadow: "0 2px 20px rgba(0,0,0,0.8), 0 4px 40px rgba(0,0,0,0.5)",
          maxWidth: "80%",
          ...textStyles[style],
        }}
      >
        {text}
      </div>
    </div>
  );
};

// Brand logo/watermark component
const BrandWatermark: React.FC<{
  brandName: string;
  logoUrl?: string | null;
}> = ({ brandName, logoUrl }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  
  const opacity = interpolate(
    frame,
    [0, fps * 0.5],
    [0, 0.8],
    { extrapolateRight: "clamp" }
  );

  return (
    <div
      style={{
        position: "absolute",
        top: 40,
        right: 40,
        opacity,
        display: "flex",
        alignItems: "center",
        gap: 12,
      }}
    >
      {logoUrl && (
        <img
          src={logoUrl}
          alt={brandName}
          style={{ height: 40, objectFit: "contain" }}
        />
      )}
      <span
        style={{
          color: "white",
          fontSize: 24,
          fontWeight: 600,
          textShadow: "0 2px 10px rgba(0,0,0,0.5)",
        }}
      >
        {brandName}
      </span>
    </div>
  );
};

// Single scene component
const SceneClip: React.FC<{
  scene: Scene;
  isFirst: boolean;
  isLast: boolean;
  brandName: string;
  callToAction: string;
}> = ({ scene, isFirst, isLast, brandName, callToAction }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  
  // Fade transition at start and end
  const fadeInDuration = fps * 0.3;
  const fadeOutDuration = fps * 0.3;
  
  const opacity = interpolate(
    frame,
    [0, fadeInDuration, durationInFrames - fadeOutDuration, durationInFrames],
    [isFirst ? 1 : 0, 1, 1, isLast ? 1 : 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  return (
    <AbsoluteFill style={{ opacity }}>
      {/* Background video */}
      {scene.asset_url && (
        <OffthreadVideo
          src={scene.asset_url}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "cover",
          }}
        />
      )}
      
      {/* Gradient overlay for text readability */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: "linear-gradient(to bottom, rgba(0,0,0,0.3) 0%, transparent 30%, transparent 70%, rgba(0,0,0,0.5) 100%)",
        }}
      />
      
      {/* On-screen text */}
      {scene.on_screen_text && (
        <TextOverlay
          text={scene.on_screen_text}
          position="bottom"
          style="subtitle"
          delay={fps * 0.5}
        />
      )}
      
      {/* CTA on last scene */}
      {isLast && callToAction && (
        <TextOverlay
          text={callToAction}
          position="center"
          style="title"
          delay={fps * 2}
        />
      )}
    </AbsoluteFill>
  );
};

// Main video composition
export const VideoComposition: React.FC<VideoCompositionProps> = ({
  scenes,
  brand,
  story,
  fps = 30,
}) => {
  // Calculate scene durations in frames
  const sceneDurations = scenes.map((scene) => {
    const duration = scene.end_time - scene.start_time;
    return Math.round(duration * fps);
  });

  // Build sequences
  let currentFrame = 0;

  return (
    <AbsoluteFill style={{ backgroundColor: "black" }}>
      {scenes.map((scene, index) => {
        const from = currentFrame;
        const duration = sceneDurations[index];
        currentFrame += duration;

        return (
          <Sequence key={scene.id} from={from} durationInFrames={duration}>
            <SceneClip
              scene={scene}
              isFirst={index === 0}
              isLast={index === scenes.length - 1}
              brandName={brand.name}
              callToAction={story.call_to_action}
            />
          </Sequence>
        );
      })}
      
      {/* Brand watermark (always visible) */}
      <BrandWatermark brandName={brand.name} logoUrl={brand.logo_url} />
    </AbsoluteFill>
  );
};

