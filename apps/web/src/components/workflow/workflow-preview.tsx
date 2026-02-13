"use client";

import { useMemo } from "react";
import { WorkflowListItemNode, WorkflowListItemEdge } from "@/lib/workflow-api";

// Map node types to colors (matching node-wrapper color props used across nodes)
const NODE_COLORS: Record<string, string> = {
    text: "#3b82f6",        // blue-500
    imageGen: "#a855f7",    // purple-500
    videoGen: "#f43f5e",    // rose-500
    audioGen: "#f97316",    // orange-500
    vision: "#10b981",      // emerald-500
    assistant: "#10b981",   // emerald-500
    editorAgent: "#a855f7", // purple-500
    mediaUpload: "#6366f1", // indigo-500
    upload: "#6366f1",      // indigo-500
    comment: "#fbbf24",     // amber-400
};

const NODE_WIDTH = 100;
const NODE_HEIGHT = 32;
const PADDING = 24;

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
                };
            })
            .filter(Boolean) as Array<{ id: string; x1: number; y1: number; x2: number; y2: number }>;

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
                {/* Dot grid pattern */}
                <pattern id="dotGrid" x="0" y="0" width="50" height="50" patternUnits="userSpaceOnUse">
                    <circle cx="25" cy="25" r="1.5" fill="rgba(255,255,255,0.06)" />
                </pattern>
                {/* Glow filter for edges */}
                <filter id="edgeGlow" x="-20%" y="-20%" width="140%" height="140%">
                    <feGaussianBlur stdDeviation="2" result="blur" />
                    <feMerge>
                        <feMergeNode in="blur" />
                        <feMergeNode in="SourceGraphic" />
                    </feMerge>
                </filter>
            </defs>

            {/* Background grid */}
            <rect width="100%" height="100%" fill="url(#dotGrid)" />

            {/* Edges (bezier curves) */}
            {scaledEdges.map(e => {
                const dx = Math.abs(e.x2 - e.x1) * 0.5;
                const path = `M ${e.x1} ${e.y1} C ${e.x1 + dx} ${e.y1}, ${e.x2 - dx} ${e.y2}, ${e.x2} ${e.y2}`;
                return (
                    <g key={e.id}>
                        <path
                            d={path}
                            fill="none"
                            stroke="rgba(139,92,246,0.3)"
                            strokeWidth="3"
                            filter="url(#edgeGlow)"
                        />
                        <path
                            d={path}
                            fill="none"
                            stroke="rgba(139,92,246,0.6)"
                            strokeWidth="1.5"
                            strokeDasharray="6 4"
                        >
                            <animate
                                attributeName="stroke-dashoffset"
                                from="0"
                                to="-20"
                                dur="2s"
                                repeatCount="indefinite"
                            />
                        </path>
                    </g>
                );
            })}

            {/* Nodes */}
            {scaledNodes.map(node => {
                const x = node.position?.x ?? 0;
                const y = node.position?.y ?? 0;
                const color = NODE_COLORS[node.type] || "#64748b";

                return (
                    <g key={node.id}>
                        {/* Node shadow */}
                        <rect
                            x={x + 2}
                            y={y + 3}
                            width={NODE_WIDTH}
                            height={NODE_HEIGHT}
                            rx={8}
                            fill="rgba(0,0,0,0.3)"
                        />
                        {/* Node body */}
                        <rect
                            x={x}
                            y={y}
                            width={NODE_WIDTH}
                            height={NODE_HEIGHT}
                            rx={6}
                            fill="rgba(30,30,40,0.85)"
                            stroke={color}
                            strokeWidth="1"
                            strokeOpacity="0.5"
                        />
                        {/* Color accent bar */}
                        <rect
                            x={x}
                            y={y}
                            width={NODE_WIDTH}
                            height={7}
                            rx={6}
                            fill={color}
                            opacity={0.7}
                        />
                        {/* Bottom clip to make accent bar flat at bottom */}
                        <rect
                            x={x}
                            y={y + 4}
                            width={NODE_WIDTH}
                            height={3}
                            fill={color}
                            opacity={0.7}
                        />
                        {/* Type label */}
                        <text
                            x={x + NODE_WIDTH / 2}
                            y={y + NODE_HEIGHT / 2 + 5}
                            textAnchor="middle"
                            fill="rgba(255,255,255,0.6)"
                            fontSize="8"
                            fontFamily="Inter, system-ui, sans-serif"
                            fontWeight="500"
                        >
                            {node.type === "imageGen" ? "Image" :
                                node.type === "videoGen" ? "Video" :
                                    node.type === "audioGen" ? "Audio" :
                                        node.type === "editorAgent" ? "Editor" :
                                            node.type === "mediaUpload" ? "Media" :
                                                node.type === "text" ? "Text" :
                                                    node.type === "vision" ? "Vision" :
                                                        node.type}
                        </text>
                        {/* Connection dots */}
                        <circle cx={x} cy={y + NODE_HEIGHT / 2} r={2.5} fill={color} opacity={0.6} />
                        <circle cx={x + NODE_WIDTH} cy={y + NODE_HEIGHT / 2} r={2.5} fill={color} opacity={0.6} />
                    </g>
                );
            })}
        </svg>
    );
}
