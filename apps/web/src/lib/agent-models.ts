import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";

export interface AgentModel {
    display_name: string;
    openrouter_model: string;
    input_modalities: string[];
    is_multimodal: boolean;
}

const FALLBACK_AGENT_MODELS: AgentModel[] = [
    {
        display_name: "Gemini 3.1 Pro Preview (High)",
        openrouter_model: "google/gemini-3.1-pro-preview",
        input_modalities: ["text", "image"],
        is_multimodal: true,
    },
    {
        display_name: "Gemini 3.1 Flash Lite Preview (Low)",
        openrouter_model: "google/gemini-3.1-flash-lite-preview",
        input_modalities: ["text", "image"],
        is_multimodal: true,
    },
    {
        display_name: "Claude 4.6 Opus (High)",
        openrouter_model: "anthropic/claude-opus-4.6",
        input_modalities: ["text", "image"],
        is_multimodal: true,
    },
    {
        display_name: "Claude 4.6 Sonnet (Medium)",
        openrouter_model: "anthropic/claude-sonnet-4.6",
        input_modalities: ["text", "image"],
        is_multimodal: true,
    },
    {
        display_name: "Claude 4.5 Haiku (Low)",
        openrouter_model: "anthropic/claude-haiku-4.5",
        input_modalities: ["text", "image"],
        is_multimodal: true,
    },
    {
        display_name: "GPT-5.4 Pro (High)",
        openrouter_model: "openai/gpt-5.4-pro",
        input_modalities: ["text", "image"],
        is_multimodal: true,
    },
    {
        display_name: "GPT-5 Mini (Medium)",
        openrouter_model: "openai/gpt-5-mini",
        input_modalities: ["text", "image", "audio"],
        is_multimodal: true,
    },
    {
        display_name: "GPT-5 Nano (Low)",
        openrouter_model: "openai/gpt-5-nano",
        input_modalities: ["text", "image"],
        is_multimodal: true,
    },
];

export function useAgentModels() {
    const [models, setModels] = useState<AgentModel[]>(FALLBACK_AGENT_MODELS);

    useEffect(() => {
        let mounted = true;

        const loadModels = async () => {
            try {
                const response = await api.get<{ models: AgentModel[] }>("/api/agent/models");
                if (mounted && Array.isArray(response.data?.models) && response.data.models.length > 0) {
                    setModels(response.data.models);
                }
            } catch (err) {
                console.warn("[useAgentModels] Falling back to static model list", err);
            }
        };

        void loadModels();
        return () => {
            mounted = false;
        };
    }, []);

    const multimodalModels = useMemo(
        () => models.filter((model) => model.is_multimodal),
        [models]
    );

    return {
        models,
        multimodalModels,
    };
}
