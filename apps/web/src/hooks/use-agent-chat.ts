"use client";

import { useState, useCallback, useRef } from "react";
import axios from "axios";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface ChatMessage {
    role: "user" | "assistant" | "system";
    content: string;
    questions?: string[];
    timestamp?: Date;
}

export interface AgentAction {
    type: "addNode" | "removeNode" | "updateNode" | "addEdge" | "removeEdge";
    node?: any;
    nodeId?: string;
    data?: any;
    edge?: any;
    edgeId?: string;
}

export interface AgentResponse {
    intent: string;
    thinking: string;
    message: string;
    questions?: string[];
    actions: AgentAction[];
}

export interface WorkflowState {
    nodes: any[];
    edges: any[];
}

export type ModelProvider = "openai" | "claude" | "gemini";

interface UseAgentChatOptions {
    onAction?: (action: AgentAction) => void;
    onComplete?: (response: AgentResponse) => void;
    onError?: (error: string) => void;
}

export function useAgentChat(options: UseAgentChatOptions = {}) {
    const [messages, setMessages] = useState<ChatMessage[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [status, setStatus] = useState<string | null>(null);
    const [thinking, setThinking] = useState<string | null>(null);
    const [pendingActions, setPendingActions] = useState<AgentAction[]>([]);
    const [model, setModel] = useState<ModelProvider>("openai");

    const abortControllerRef = useRef<AbortController | null>(null);

    const sendMessage = useCallback(async (
        content: string,
        workflow?: WorkflowState,
    ) => {
        if (!content.trim() || isLoading) return;

        // Add user message
        const userMessage: ChatMessage = {
            role: "user",
            content,
            timestamp: new Date(),
        };
        setMessages((prev) => [...prev, userMessage]);
        setIsLoading(true);
        setStatus("Connecting...");
        setThinking(null);
        setPendingActions([]);

        // Prepare request
        const allMessages = [...messages, userMessage].map((m) => ({
            role: m.role,
            content: m.content,
        }));

        try {
            // Use non-streaming endpoint for now (SSE requires more setup)
            const response = await axios.post<AgentResponse>(
                `${API_BASE}/api/agent/chat`,
                {
                    messages: allMessages,
                    workflow: workflow || { nodes: [], edges: [] },
                    model,
                },
            );

            const data = response.data;

            // Set thinking
            if (data.thinking) {
                setThinking(data.thinking);
            }

            // Process actions
            if (data.actions && data.actions.length > 0) {
                setPendingActions(data.actions);
                // Call onAction for each action
                data.actions.forEach((action) => {
                    options.onAction?.(action);
                });
            }

            // Add assistant message
            const assistantMessage: ChatMessage = {
                role: "assistant",
                content: data.message,
                questions: data.questions,
                timestamp: new Date(),
            };
            setMessages((prev) => [...prev, assistantMessage]);

            // Complete callback
            options.onComplete?.(data);

            setStatus(null);
        } catch (error: any) {
            console.error("Agent chat error:", error);
            const errorMessage = error.response?.data?.detail || error.message || "Unknown error";
            options.onError?.(errorMessage);

            // Add error as assistant message
            const errorAssistantMessage: ChatMessage = {
                role: "assistant",
                content: `❌ Error: ${errorMessage}`,
                timestamp: new Date(),
            };
            setMessages((prev) => [...prev, errorAssistantMessage]);
            setStatus(null);
        } finally {
            setIsLoading(false);
        }
    }, [messages, model, isLoading, options]);

    const clearMessages = useCallback(() => {
        setMessages([]);
        setPendingActions([]);
        setThinking(null);
        setStatus(null);
    }, []);

    const cancelRequest = useCallback(() => {
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
            abortControllerRef.current = null;
        }
        setIsLoading(false);
        setStatus(null);
    }, []);

    return {
        messages,
        isLoading,
        status,
        thinking,
        pendingActions,
        model,
        setModel,
        sendMessage,
        clearMessages,
        cancelRequest,
    };
}
