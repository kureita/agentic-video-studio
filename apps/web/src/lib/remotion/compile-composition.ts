"use client";

/**
 * compile-composition.ts
 *
 * Transpiles AI-generated Remotion TSX code in the browser using sucrase,
 * then evaluates it to produce a React component that can be passed to
 * renderMediaOnWeb().
 */

import { transform } from "sucrase";
import React from "react";
import * as Remotion from "remotion";
import * as RemotionMedia from "@remotion/media";

export interface CompositionMeta {
    component: React.FC;
    fps: number;
    width: number;
    height: number;
    durationInFrames: number;
}

/**
 * Compile a Remotion TSX source code string into a usable React component
 * with composition metadata (fps, width, height, durationInFrames).
 *
 * The generated code should export:
 *  - `default` (or named `MyComposition`): the React component
 *  - `fps`, `width`, `height`, `durationInFrames`: composition metadata
 *
 * Imports from 'react', 'remotion', and '@remotion/media' are provided
 * automatically — the generated code should use standard import syntax.
 */
export function compileComposition(tsxCode: string): CompositionMeta {
    // ──── 0. Validate input ────
    const trimmed = tsxCode.trim();

    // Detect if this is JSON (old config format) instead of TSX
    if (trimmed.startsWith("{") || trimmed.startsWith("[")) {
        throw new Error(
            "[compileComposition] Received JSON instead of TSX code. " +
            "Please re-run the editor agent node to generate composition code."
        );
    }

    // ──── 1. Transpile TSX → CommonJS ────
    // We use Sucrase with the "imports" transform so that:
    // - `import { x } from 'y'` -> `const { x } = require('y')`
    // - `export const z = ...` -> `exports.z = ...`
    let jsCode: string;
    try {
        const result = transform(trimmed, {
            transforms: ["typescript", "jsx", "imports"],
            jsxRuntime: "classic",
            production: true,
        });
        jsCode = result.code;
    } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        console.error("[compileComposition] Failed to transpile code:\n", trimmed.slice(0, 500));
        throw new Error(`[compileComposition] TSX transpilation failed:\n${msg}`);
    }

    // ──── 2. Evaluate in a sandboxed scope ────
    const moduleExports: Record<string, unknown> = {};

    const scopedRequire = (mod: string) => {
        if (mod === "react") return React;
        if (mod === "remotion") return Remotion;
        if (mod === "@remotion/media") return RemotionMedia;

        // Handle common variations/subpaths if needed
        if (mod === "remotion/media") return RemotionMedia;

        console.warn(`[compileComposition] Unknown module requested: ${mod}`);
        return {};
    };

    try {
        // Create the function. We only need `exports` and `require`.
        // React is implicitly needed by the transpiled JSX (React.createElement).
        const fn = new Function(
            "exports",
            "require",
            "React",
            jsCode
        );

        fn(
            moduleExports,
            scopedRequire,
            React
        );
    } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        console.error("[compileComposition] Code evaluation error. JS code:\n", jsCode.slice(0, 500));
        throw new Error(`[compileComposition] Code evaluation failed:\n${msg}`);
    }

    // ──── 4. Extract component + metadata ────
    const component = (moduleExports.default ??
        moduleExports.MyComposition ??
        moduleExports.Composition) as React.FC | undefined;

    if (!component || typeof component !== "function") {
        const availableExports = Object.keys(moduleExports).join(", ");
        throw new Error(
            `[compileComposition] No default export or MyComposition found. ` +
            `Available exports: [${availableExports}]`
        );
    }

    const fps = (moduleExports.fps as number) ?? 30;
    const width = (moduleExports.width as number) ?? 1920;
    const height = (moduleExports.height as number) ?? 1080;
    const durationInFrames = (moduleExports.durationInFrames as number) ?? 300;

    return { component, fps, width, height, durationInFrames };
}
