"use client";

import { useMemo } from "react";
import { WorkflowListItemNode, WorkflowListItemEdge } from "@/lib/workflow-api";

// Map node types to refined, muted professional colors
const NODE_COLORS: Record<string, { fill: string; stroke: string; accent: string }> = {
    text: { fill: "#1e293b", stroke: "#475569", accent: "#94a3b8" },  // slate
    imageGen: { fill: "#1e2337", stroke: "#4f6199", accent: "#818cf8" },  // indigo
    videoGen: { fill: "#271e2a", stroke: "#7c5388", accent: "#c084fc" },  // purple
    audioGen: { fill: "#27211e", stroke: "#8a6d45", accent: "#fbbf24" },  // amber
    editorAgent: { fill: "#1e2725", stroke: "#47756b", accent: "#5eead4" },  // teal
    mediaUpload: { fill: "#1e2530", stroke: "#4b7399", accent: "#7dd3fc" },  // sky
    upload: { fill: "#1e2530", stroke: "#4b7399", accent: "#7dd3fc" },  // sky
    comment: { fill: "#26251e", stroke: "#7c7544", accent: "#facc15" },  // yellow
};

const DEFAULT_COLOR = { fill: "#1e1e24", stroke: "#525266", accent: "#a1a1b5" };

const NODE_WIDTH = 110;
const NODE_HEIGHT = 36;
const PADDING = 30;

// Short labels for display
const TYPE_LABELS: Record<string, string> = {
    imageGen: "Image",
    videoGen: "Video",
    audioGen: "Audio",
    editorAgent: "Editor",
    mediaUpload: "Media",
    text: "Text",
    upload: "Upload",
    comment: "Note",
};

interface WorkflowPreviewProps {
    nodes: WorkflowListItemNode[];
    edges: WorkflowListItemEdge[];
}

export function WorkflowPreview({ nodes, edges }: WorkflowPreviewProps) {
    const { viewBox, scaledNodes, scaledEdges } = useMemo(() => {
        if (nodes.length === 0) {
            return { viewBox: "0 0 300 200", scaledNodes: [], scaledEdges: [] };
        }

        // Calculate bounding box
        let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
        for (const node of nodes) {
            const x = node.position?.x ?? 0;
            const y = node.position?.y ?? 0;
            minX = Math.min(minX, x);
            minY = Math.min(minY, y);
            maxX = Math.max(maxX, x + NODE_WIDTH);
            maxY = Math.max(maxY, y + NODE_HEIGHT);
        }

        const contentW = maxX - minX + PADDING * 2;
        const contentH = maxY - minY + PADDING * 2;

        const vb = `${minX - PADDING} ${minY - PADDING} ${contentW} ${contentH}`;

        // Build node lookup for edge rendering
        const nodeMap = new Map(nodes.map(n => [n.id, n]));

        const sEdges = edges
            .map(e => {
                const src = nodeMap.get(e.source);
                const tgt = nodeMap.get(e.target);
                if (!src || !tgt) return null;
                return {
                    id: e.id,
                    x1: (src.position?.x ?? 0) + NODE_WIDTH,
                    y1: (src.position?.y ?? 0) + NODE_HEIGHT / 2,
                    x2: tgt.position?.x ?? 0,
                    y2: (tgt.position?.y ?? 0) + NODE_HEIGHT / 2,
                    srcType: src.type,
                    tgtType: tgt.type,
                };
            })
            .filter(Boolean) as Array<{ id: string; x1: number; y1: number; x2: number; y2: number; srcType: string; tgtType: string }>;

        return {
            viewBox: vb,
            scaledNodes: nodes,
            scaledEdges: sEdges,
        };
    }, [nodes, edges]);

    if (nodes.length === 0) {
        return (
            <div className="absolute inset-0 flex items-center justify-center">
                <p className="text-[10px] text-muted-foreground/40 font-medium tracking-wide">Empty</p>
            </div>
        );
    }

    return (
        <svg
            viewBox={viewBox}
            className="absolute inset-0 w-full h-full"
            preserveAspectRatio="xMidYMid meet"
        >
            <defs>
                {/* Subtle line grid pattern */}
                <pattern id="previewGrid" x="0" y="0" width="40" height="40" patternUnits="userSpaceOnUse">
                    <path d="M 40 0 L 0 0 0 40" fill="none" stroke="rgba(255,255,255,0.03)" strokeWidth="0.5" />
                </pattern>

                {/* Subtle drop shadow for nodes */}
                <filter id="nodeShadow" x="-10%" y="-10%" width="130%" height="140%">
                    <feDropShadow dx="0" dy="1" stdDeviation="2" floodColor="rgba(0,0,0,0.25)" />
                </filter>

                {/* Per-type gradients */}
                {Object.entries(NODE_COLORS).map(([type, colors]) => (
                    <linearGradient key={type} id={`grad-${type}`} x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor={colors.fill} stopOpacity="1" />
                        <stop offset="100%" stopColor={colors.fill} stopOpacity="0.85" />
                    </linearGradient>
                ))}
            </defs>

            {/* Background grid */}
            <rect width="100%" height="100%" fill="url(#previewGrid)" />

            {/* Edges — clean, subtle bezier curves */}
            {scaledEdges.map(e => {
                const dx = Math.abs(e.x2 - e.x1) * 0.4;
                const path = `M ${e.x1} ${e.y1} C ${e.x1 + dx} ${e.y1}, ${e.x2 - dx} ${e.y2}, ${e.x2} ${e.y2}`;
                const srcColors = NODE_COLORS[e.srcType] || DEFAULT_COLOR;

                return (
                    <path
                        key={e.id}
                        d={path}
                        fill="none"
                        stroke={srcColors.accent}
                        strokeWidth="1.2"
                        strokeOpacity="0.25"
                    />
                );
            })}

            {/* Nodes */}
            {scaledNodes.map(node => {
                const x = node.position?.x ?? 0;
                const y = node.position?.y ?? 0;
                const colors = NODE_COLORS[node.type] || DEFAULT_COLOR;
                const label = TYPE_LABELS[node.type] || node.type;

                return (
                    <g key={node.id}>
                        {/* Node body */}
                        <rect
                            x={x}
                            y={y}
                            width={NODE_WIDTH}
                            height={NODE_HEIGHT}
                            rx={6}
                            fill={`url(#grad-${node.type})`}
                            stroke={colors.stroke}
                            strokeWidth="0.8"
                            strokeOpacity="0.6"
                            filter="url(#nodeShadow)"
                        />
                        {/* Left accent bar */}
                        <rect
                            x={x}
                            y={y}
                            width={3}
                            height={NODE_HEIGHT}
                            rx={1.5}
                            fill={colors.accent}
                            opacity={0.7}
                        />
                        {/* Type label */}
                        <text
                            x={x + 14}
                            y={y + NODE_HEIGHT / 2 + 3.5}
                            textAnchor="start"
                            fill="rgba(255,255,255,0.55)"
                            fontSize="8.5"
                            fontFamily="Inter, system-ui, sans-serif"
                            fontWeight="500"
                            letterSpacing="0.3"
                        >
                            {label}
                        </text>
                        {/* Right connection dot */}
                        <circle
                            cx={x + NODE_WIDTH}
                            cy={y + NODE_HEIGHT / 2}
                            r={2}
                            fill={colors.accent}
                            opacity={0.45}
                        />
                        {/* Left connection dot */}
                        <circle
                            cx={x}
                            cy={y + NODE_HEIGHT / 2}
                            r={2}
                            fill={colors.accent}
                            opacity={0.45}
                        />
                    </g>
                );
            })}
        </svg>
    );
}
