"use client";

/**
 * useClientRender
 *
 * React hook that:
 * 1. Compiles AI-generated Remotion TSX code into a React component
 * 2. Renders it to MP4 using renderMediaOnWeb()
 * 3. Returns a blob URL for <video> display
 */

import { useCallback, useRef, useState } from "react";
import { renderMediaOnWeb } from "@remotion/web-renderer";
import type { RenderMediaOnWebProgressCallback } from "@remotion/web-renderer";
import { compileComposition } from "./compile-composition";

export interface ClientRenderState {
    isRendering: boolean;
    /** 0–100 */
    progress: number;
    error: string | null;
    /** Blob URL of the rendered MP4 */
    blobUrl: string | null;
    /** Phase of the render: compiling code, rendering frames, done */
    phase: "idle" | "compiling" | "rendering" | "done" | "error";
}

export interface UseClientRender {
    state: ClientRenderState;
    /** Compile + render from TSX code string. Returns blob URL on success. */
    renderFromCode: (tsxCode: string) => Promise<string | null>;
    /** Cancel an in-progress render */
    cancel: () => void;
    /** Trigger browser download of the rendered video */
    download: (filename?: string) => void;
    /** Clear the rendered blob */
    clear: () => void;
}

const INITIAL_STATE: ClientRenderState = {
    isRendering: false,
    progress: 0,
    error: null,
    blobUrl: null,
    phase: "idle",
};

export function useClientRender(): UseClientRender {
    const [state, setState] = useState<ClientRenderState>(INITIAL_STATE);
    const abortRef = useRef<AbortController | null>(null);

    const renderFromCode = useCallback(
        async (tsxCode: string): Promise<string | null> => {
            // Clean up previous
            if (state.blobUrl) {
                URL.revokeObjectURL(state.blobUrl);
            }

            const abortController = new AbortController();
            abortRef.current = abortController;

            setState({
                isRendering: true,
                progress: 0,
                error: null,
                blobUrl: null,
                phase: "compiling",
            });

            // ──── 1. Compile the TSX code ────
            let meta;
            try {
                meta = compileComposition(tsxCode);
            } catch (err) {
                const msg = err instanceof Error ? err.message : "Compilation failed";
                setState({
                    isRendering: false,
                    progress: 0,
                    error: msg,
                    blobUrl: null,
                    phase: "error",
                });
                console.error("[useClientRender] Compile error:", err);
                return null;
            }

            // ──── 2. Render with renderMediaOnWeb ────
            setState((prev) => ({ ...prev, phase: "rendering", progress: 5 }));

            const onProgress: RenderMediaOnWebProgressCallback = ({
                renderedFrames,
            }) => {
                const pct = Math.min(
                    100,
                    Math.round((renderedFrames / meta.durationInFrames) * 100)
                );
                setState((prev) => ({ ...prev, progress: pct }));
            };

            try {
                const { getBlob } = await renderMediaOnWeb({
                    composition: {
                        component: meta.component,
                        durationInFrames: meta.durationInFrames,
                        fps: meta.fps,
                        width: meta.width,
                        height: meta.height,
                        id: "dynamic-composition",
                    },
                    container: "mp4",
                    videoCodec: "h264",
                    onProgress,
                    signal: abortController.signal,
                    licenseKey: "free-license",
                });

                const blob = await getBlob();
                const url = URL.createObjectURL(blob);

                setState({
                    isRendering: false,
                    progress: 100,
                    error: null,
                    blobUrl: url,
                    phase: "done",
                });

                return url;
            } catch (err) {
                if (abortController.signal.aborted) {
                    setState({ ...INITIAL_STATE });
                    return null;
                }

                const message = err instanceof Error ? err.message : "Render failed";
                setState({
                    isRendering: false,
                    progress: 0,
                    error: message,
                    blobUrl: null,
                    phase: "error",
                });
                console.error("[useClientRender] Render error:", err);
                return null;
            } finally {
                abortRef.current = null;
            }
        },
        [state.blobUrl]
    );

    const cancel = useCallback(() => {
        abortRef.current?.abort();
    }, []);

    const download = useCallback(
        (filename?: string) => {
            if (!state.blobUrl) return;
            const a = document.createElement("a");
            a.href = state.blobUrl;
            a.download = filename ?? `edited-video-${Date.now()}.mp4`;
            a.click();
        },
        [state.blobUrl]
    );

    const clear = useCallback(() => {
        if (state.blobUrl) {
            URL.revokeObjectURL(state.blobUrl);
        }
        setState({ ...INITIAL_STATE });
    }, [state.blobUrl]);

    return { state, renderFromCode, cancel, download, clear };
}
