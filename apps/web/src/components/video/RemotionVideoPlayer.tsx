"use client";

import { Player } from "@remotion/player";
import { AbsoluteFill, Sequence, OffthreadVideo, Audio, interpolate, useCurrentFrame } from "remotion";
import { useMemo } from "react";

interface VideoClip {
  url: string;
  startTime: number;
  duration: number;
  transition?: "fade" | "slide" | "cut";
}

interface RemotionVideoPlayerProps {
  clips: VideoClip[];
  audio?: string;
  width?: number;
  height?: number;
  fps?: number;
  className?: string;
  controls?: boolean;
  autoPlay?: boolean;
  loop?: boolean;
}

// Video composition component
const VideoComposition: React.FC<{
  clips: VideoClip[];
  audio?: string;
  fps: number;
}> = ({ clips, audio, fps }) => {
  const frame = useCurrentFrame();

  return (
    <AbsoluteFill style={{ backgroundColor: "black" }}>
      {clips.map((clip, index) => {
        const fromFrame = Math.round(clip.startTime * fps);
        const durationInFrames = Math.round(clip.duration * fps);
        const transition = clip.transition || "fade";

        // Calculate opacity for transitions
        const transitionFrames = fps * 0.5; // 0.5 second transition
        const localFrame = frame - fromFrame;
        
        let opacity = 1;
        if (transition === "fade") {
          // Fade in at start
          if (localFrame < transitionFrames) {
            opacity = interpolate(localFrame, [0, transitionFrames], [0, 1]);
          }
          // Fade out at end
          if (localFrame > durationInFrames - transitionFrames) {
            opacity = interpolate(
              localFrame,
              [durationInFrames - transitionFrames, durationInFrames],
              [1, 0]
            );
          }
        }

        return (
          <Sequence
            key={`clip-${index}`}
            from={fromFrame}
            durationInFrames={durationInFrames}
          >
            <AbsoluteFill style={{ opacity }}>
              <OffthreadVideo
                src={clip.url}
                style={{
                  width: "100%",
                  height: "100%",
                  objectFit: "cover",
                }}
              />
            </AbsoluteFill>
          </Sequence>
        );
      })}

      {/* Audio track */}
      {audio && <Audio src={audio} />}
    </AbsoluteFill>
  );
};

export const RemotionVideoPlayer: React.FC<RemotionVideoPlayerProps> = ({
  clips,
  audio,
  width = 1920,
  height = 1080,
  fps = 30,
  className = "",
  controls = true,
  autoPlay = false,
  loop = false,
}) => {
  // Calculate total duration
  const durationInFrames = useMemo(() => {
    if (clips.length === 0) return fps * 5; // Default 5 seconds
    
    const lastClip = clips[clips.length - 1];
    return Math.round((lastClip.startTime + lastClip.duration) * fps);
  }, [clips, fps]);

  // If no clips, show placeholder
  if (clips.length === 0) {
    return (
      <div
        className={`flex items-center justify-center bg-black text-white/50 ${className}`}
        style={{ aspectRatio: `${width}/${height}` }}
      >
        <p className="text-sm">No video clips to display</p>
      </div>
    );
  }

  return (
    <div className={className}>
      <Player
        component={VideoComposition}
        durationInFrames={durationInFrames}
        compositionWidth={width}
        compositionHeight={height}
        fps={fps}
        inputProps={{
          clips,
          audio,
          fps,
        }}
        controls={controls}
        autoPlay={autoPlay}
        loop={loop}
        style={{
          width: "100%",
          height: "100%",
        }}
      />
    </div>
  );
};
