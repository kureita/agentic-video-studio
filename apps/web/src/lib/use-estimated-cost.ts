import { useMemo } from "react";
import { useModels } from "@/lib/use-models";
import { estimateVideoModelCost } from "@/lib/compute-cost";

/**
 * Compute the estimated cost for a node based on its model and config.
 *
 * Returns the `est_price_usd` from the matching model config, or
 * the model's first config price as a fallback.
 */
export function useEstimatedCost(
    modelId: string | undefined,
    nodeType: "image" | "video" | "audio",
    configHints?: {
        ratio?: string;
        resolution?: string;
        duration?: number;
    }
): number | null {
    const { models } = useModels();
    const ratio = configHints?.ratio;
    const resolution = configHints?.resolution;
    const durationHint = configHints?.duration;

    return useMemo(() => {
        let resolvedModelId = modelId;
        if (!resolvedModelId) {
            if (nodeType === "image") resolvedModelId = "flux-dev";
            else if (nodeType === "video") resolvedModelId = "kling-video-3-standard";
            else if (nodeType === "audio") resolvedModelId = "elevenlabs";
        }

        if (!resolvedModelId) return null;

        const model = models.find(
            (m) => m.id === resolvedModelId && m.type === nodeType
        );
        if (!model || !model.configs || model.configs.length === 0) return null;

        // Audio-driven video models (avatar, lipsync) bill per second of input
        // audio. There is no honest pre-run estimate without the audio length —
        // the UI should display "—" rather than a misleading default.
        if (model.requires_input_duration) return null;

        const parseDuration = () =>
            typeof durationHint === "number"
                ? durationHint
                : parseFloat(String(durationHint || "0").replace(/s$/i, ""));

        // Try to match a specific config
        if (ratio || resolution || durationHint) {
            for (const cfg of model.configs) {
                // For video: match by resolution + duration
                if (nodeType === "video" && cfg.duration && cfg.resolution) {
                    const parsedDuration = parseDuration();
                    if (
                        cfg.resolution === resolution &&
                        cfg.duration === parsedDuration
                    ) {
                        return cfg.est_price_usd ?? null;
                    }
                }
                // For image: match by aspect ratio
                if (nodeType === "image" && cfg.id === ratio) {
                    return cfg.est_price_usd ?? null;
                }
            }
        }

        if (nodeType === "video" && resolution) {
            const parsedDuration = parseDuration();
            if (parsedDuration > 0) {
                const videoCost = estimateVideoModelCost(model, resolution, parsedDuration);
                if (videoCost > 0) return videoCost;
            }
        }

        // Fallback: use the default config or first config
        const defaultCfg = model.configs.find(
            (c) => c.id === model.default_config_id
        );
        if (nodeType === "audio" && defaultCfg?.est_price_usd_per_min) {
            const duration = parseDuration();
            if (!duration || duration <= 0) return null;
            return defaultCfg.est_price_usd_per_min * (duration / 60);
        }
        return (defaultCfg?.est_price_usd ?? model.configs[0]?.est_price_usd) ?? null;
    }, [models, modelId, nodeType, ratio, resolution, durationHint]);
}
