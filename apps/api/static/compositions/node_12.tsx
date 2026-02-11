import React from 'react';
import { AbsoluteFill, Sequence, useCurrentFrame, useVideoConfig, interpolate } from 'remotion';
import { Video } from '@remotion/media';

export const fps = 30;
export const width = 1920;
export const height = 1080;
export const durationInFrames = 28 * fps;

export default function MyComposition() {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const video1Url = "http://localhost:8000/static/videos/generated_1770826548.mp4";
  const video2Url = "http://localhost:8000/static/videos/generated_1770826553.mp4";
  const video3Url = "http://localhost:8000/static/videos/generated_1770826567.mp4";

  const video1Duration = 5 * fps;
  const video2Duration = 5 * fps;
  const video3Duration = 5 * fps;

  const video1PlaybackRate = 0.5;
  const video3PlaybackRate = 2;

  const video1EffectiveDuration = video1Duration / video1PlaybackRate;
  const video3EffectiveDuration = video3Duration / video3PlaybackRate;

  const totalVideoDuration = video1EffectiveDuration + video2Duration + video3EffectiveDuration;
  const logoRevealDuration = 2 * fps;
  const callToActionDuration = 4 * fps;

  const totalDuration = video1EffectiveDuration + video2Duration + video3EffectiveDuration + logoRevealDuration + callToActionDuration;

  return (
    <AbsoluteFill style={{ backgroundColor: 'black' }}>
      <Sequence from={0} durationInFrames={video1EffectiveDuration}>
        <AbsoluteFill>
          <Video
            src={video1Url}
            playbackRate={video1PlaybackRate}
            style={{ width: '100%', height: '100%', objectFit: 'cover' }}
          />
        </AbsoluteFill>
      </Sequence>

      <Sequence from={video1EffectiveDuration} durationInFrames={video2Duration}>
        <AbsoluteFill>
          <Video
            src={video2Url}
            style={{ width: '100%', height: '100%', objectFit: 'cover', transform: 'scaleX(-1)' }}
            playbackRate={1}
          />
        </AbsoluteFill>
      </Sequence>

      <Sequence from={video1EffectiveDuration + video2Duration} durationInFrames={video3EffectiveDuration}>
        <AbsoluteFill>
          <Video
            src={video3Url}
            playbackRate={video3PlaybackRate}
            style={{ width: '100%', height: '100%', objectFit: 'cover' }}
          />
        </AbsoluteFill>
      </Sequence>

      <Sequence from={video1EffectiveDuration + video2Duration + video3EffectiveDuration} durationInFrames={callToActionDuration}>
        <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
          <div style={{ color: 'white', fontSize: 60, fontWeight: 'bold', fontFamily: 'sans-serif', textAlign: 'center' }}>
            Kureita: Your Cursor for AI Videos.
            <br />
            Create effortlessly.
          </div>
        </AbsoluteFill>
      </Sequence>

      <Sequence from={video1EffectiveDuration + video2Duration + video3EffectiveDuration + callToActionDuration} durationInFrames={logoRevealDuration}>
        <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
          <div style={{ color: 'white', fontSize: 40, fontWeight: 'bold', fontFamily: 'sans-serif' }}>
            [Logo Reveal Placeholder]
          </div>
        </AbsoluteFill>
      </Sequence>
    </AbsoluteFill>
  );
}