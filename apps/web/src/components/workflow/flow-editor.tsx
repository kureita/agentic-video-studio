"use client";

import { useCallback, useEffect, MouseEvent, useRef, useState } from "react";
import {
    ReactFlow,
    Controls,
    Background,
    applyNodeChanges,
    applyEdgeChanges,
    addEdge,
    NodeChange,
    EdgeChange,
    Connection,
    Edge,
    Node,
    BackgroundVariant,
    useReactFlow,
    ReactFlowProvider,
    XYPosition,
} from "@xyflow/react";
import { cn } from "@/lib/utils";
import "@xyflow/react/dist/style.css";

// Custom Nodes
import { TextNode } from "./nodes/text-node";
import { UploadNode } from "./nodes/upload-node";
import { ImageGenNode } from "./nodes/image-gen-node";
import { AudioGenNode } from "./nodes/audio-gen-node";
import { VideoGenNode } from "./nodes/video-gen-node";
import { VisionNode } from "./nodes/vision-node";
import { EditorAgentNode } from "./nodes/editor-agent-node";
import { MediaUploadNode } from "./nodes/media-upload-node";
import { CommentNode } from "./nodes/comment-node";

// Store
import { useWorkflowStore } from "@/lib/workflow-store";

const nodeTypes = {
    text: TextNode,
    upload: UploadNode,
    imageGen: ImageGenNode,
    audioGen: AudioGenNode,
    videoGen: VideoGenNode,
    vision: VisionNode,
    assistant: VisionNode, // Keep backward compatibility
    editorAgent: EditorAgentNode,
    mediaUpload: MediaUploadNode,
    comment: CommentNode,
};

import { WorkflowToolbar } from "./toolbar";
import { useUndoRedo } from "@/hooks/use-undo-redo";

interface FlowEditorProps {
    workflowId?: string;
}

// ============================================
// Geometry helpers for cut/snip tool
// ============================================

function segmentsIntersect(
    p1: XYPosition, p2: XYPosition,
    p3: XYPosition, p4: XYPosition,
): boolean {
    const d1x = p2.x - p1.x;
    const d1y = p2.y - p1.y;
    const d2x = p4.x - p3.x;
    const d2y = p4.y - p3.y;

    const cross = d1x * d2y - d1y * d2x;
    if (Math.abs(cross) < 1e-10) return false;

    const t = ((p3.x - p1.x) * d2y - (p3.y - p1.y) * d2x) / cross;
    const u = ((p3.x - p1.x) * d1y - (p3.y - p1.y) * d1x) / cross;

    return t >= 0 && t <= 1 && u >= 0 && u <= 1;
}

function rectIntersectsSegment(
    rect: { x: number; y: number; width: number; height: number },
    p1: XYPosition,
    p2: XYPosition,
): boolean {
    const { x, y, width, height } = rect;
    const tl = { x, y };
    const tr = { x: x + width, y };
    const br = { x: x + width, y: y + height };
    const bl = { x, y: y + height };

    // Check if either endpoint is inside the rect
    if (
        p1.x >= x && p1.x <= x + width && p1.y >= y && p1.y <= y + height
    ) return true;
    if (
        p2.x >= x && p2.x <= x + width && p2.y >= y && p2.y <= y + height
    ) return true;

    // Check intersection with each edge of the rect
    return (
        segmentsIntersect(p1, p2, tl, tr) ||
        segmentsIntersect(p1, p2, tr, br) ||
        segmentsIntersect(p1, p2, br, bl) ||
        segmentsIntersect(p1, p2, bl, tl)
    );
}

// ============================================
// Inner FlowEditor (needs ReactFlowProvider as parent)
// ============================================

function FlowEditorInner({ workflowId }: FlowEditorProps) {
    const {
        nodes,
        edges,
        outputs,
        runningNodeId,
        setNodes,
        setEdges,
        loadWorkflow,
        runNode,
    } = useWorkflowStore();

    const [activeTool, setActiveTool] = useState("pointer");
    const [isInitialized, setIsInitialized] = useState(false);

    // Snip tool state
    const [isCutting, setIsCutting] = useState(false);
    const [cutLine, setCutLine] = useState<{ start: XYPosition; end: XYPosition } | null>(null);
    const flowWrapperRef = useRef<HTMLDivElement>(null);

    const { takeSnapshot, undo, redo, canUndo, canRedo } = useUndoRedo();

    const reactFlowInstance = useReactFlow();

    // Load workflow on mount if ID is provided
    useEffect(() => {
        let mounted = true;

        const loadWorkflowData = async () => {
            if (workflowId && workflowId !== "new" && !isInitialized) {
                try {
                    await loadWorkflow(workflowId);
                    // Small delay to ensure state has propagated
                    await new Promise(resolve => setTimeout(resolve, 50));
                    if (mounted) {
                        setIsInitialized(true);
                    }
                } catch (error) {
                    console.error("[FlowEditor] Failed to load workflow:", error);
                    if (mounted) {
                        setIsInitialized(true);
                    }
                }
            } else if (workflowId === "new") {
                setIsInitialized(true);
            }
        };

        loadWorkflowData();

        return () => {
            mounted = false;
        };
    }, [workflowId, loadWorkflow, isInitialized]);

    // Inject outputs into node data for display
    const nodesWithOutputs = nodes.map((node) => ({
        ...node,
        data: {
            ...node.data,
            output: outputs[node.id] || node.data.output,
            isRunning: runningNodeId === node.id,
            onRun: () => runNode(node.id),
        },
    }));

    const onNodesChange = useCallback(
        (changes: NodeChange[]) => {
            // Take snapshot BEFORE delete actions (so undo can restore)
            const hasRemove = changes.some(c => c.type === "remove");
            if (hasRemove) {
                takeSnapshot(nodes, edges);
            }

            const newNodes = applyNodeChanges(changes, nodes);
            setNodes(newNodes);
        },
        [nodes, edges, setNodes, takeSnapshot]
    );

    const onEdgesChange = useCallback(
        (changes: EdgeChange[]) => {
            const hasRemove = changes.some(c => c.type === "remove");
            if (hasRemove) {
                takeSnapshot(nodes, edges);
            }

            const newEdges = applyEdgeChanges(changes, edges);
            setEdges(newEdges);
        },
        [nodes, edges, setEdges, takeSnapshot]
    );

    // Snapshot before node drag starts
    const onNodeDragStart = useCallback(() => {
        takeSnapshot(nodes, edges);
    }, [nodes, edges, takeSnapshot]);

    const isValidConnection = useCallback((connection: Connection | Edge) => {
        const sourceType = connection.sourceHandle?.split('|')[0];
        const targetType = connection.targetHandle?.split('|')[0];
        const targetHandleId = connection.targetHandle?.split('|')[1];

        if (!sourceType || !targetType || sourceType === 'any' || targetType === 'any') {
            // Continue to connection limit check
        } else if (sourceType !== targetType) {
            return false;
        }

        const singleConnectionHandles = ['ref_video', 'reference_video', 'start_image', 'end_image'];

        if (targetHandleId && singleConnectionHandles.includes(targetHandleId)) {
            const connectionId = 'id' in connection ? connection.id : null;
            const existingConnection = edges.find(
                (edge) =>
                    edge.target === connection.target &&
                    edge.targetHandle?.split('|')[1] === targetHandleId &&
                    edge.id !== connectionId
            );

            if (existingConnection) {
                console.log(`[FlowEditor] Connection rejected: ${targetHandleId} already has a connection`);
                return false;
            }
        }

        return true;
    }, [edges]);

    const onConnect = useCallback(
        (params: Connection) => {
            takeSnapshot(nodes, edges);
            const newEdges = addEdge(params, edges);
            setEdges(newEdges);
        },
        [nodes, edges, setEdges, takeSnapshot]
    );

    const onEdgeClick = useCallback((_event: MouseEvent, edge: Edge) => {
        if (activeTool === "cut") {
            takeSnapshot(nodes, edges);
            setEdges(edges.filter((e) => e.id !== edge.id));
        }
    }, [activeTool, nodes, edges, setEdges, takeSnapshot]);

    // ============================================
    // Snip/Cut tool - drag to cut
    // ============================================

    const getFlowPosition = useCallback((clientX: number, clientY: number): XYPosition => {
        const position = reactFlowInstance.screenToFlowPosition({ x: clientX, y: clientY });
        return position;
    }, [reactFlowInstance]);

    const onPaneMouseDown = useCallback((event: MouseEvent) => {
        if (activeTool === "cut") {
            const pos = getFlowPosition(event.clientX, event.clientY);
            setIsCutting(true);
            setCutLine({ start: pos, end: pos });
        } else if (activeTool === "comment") {
            // Place a comment node at click position
            const pos = getFlowPosition(event.clientX, event.clientY);
            takeSnapshot(nodes, edges);
            const id = `comment_${Math.random().toString(36).substring(7)}`;
            const newNode: Node = {
                id,
                type: "comment",
                position: pos,
                data: { text: "", color: "#fbbf24" },
                style: { width: 200, height: 100 },
            };
            setNodes([...nodes, newNode]);
            // Switch back to pointer after placing
            setActiveTool("pointer");
        }
    }, [activeTool, getFlowPosition, nodes, edges, setNodes, takeSnapshot]);

    const onPaneMouseMove = useCallback((event: MouseEvent) => {
        if (isCutting && cutLine) {
            const pos = getFlowPosition(event.clientX, event.clientY);
            setCutLine(prev => prev ? { ...prev, end: pos } : null);
        }
    }, [isCutting, cutLine, getFlowPosition]);

    const onPaneMouseUp = useCallback(() => {
        if (isCutting && cutLine) {
            const { start, end } = cutLine;

            // Only process if the drag was meaningful (> 5px in flow coords)
            const dragDist = Math.sqrt((end.x - start.x) ** 2 + (end.y - start.y) ** 2);
            if (dragDist > 5) {
                takeSnapshot(nodes, edges);

                // Find edges that intersect with the cut line
                const edgesToRemove = new Set<string>();
                for (const edge of edges) {
                    const sourceNode = nodes.find(n => n.id === edge.source);
                    const targetNode = nodes.find(n => n.id === edge.target);
                    if (!sourceNode || !targetNode) continue;

                    // Approximate edge as straight line from source center-right to target center-left
                    const sourceWidth = (sourceNode.measured?.width ?? sourceNode.width ?? 200);
                    const sourceHeight = (sourceNode.measured?.height ?? sourceNode.height ?? 100);
                    const targetHeight = (targetNode.measured?.height ?? targetNode.height ?? 100);

                    const edgeP1: XYPosition = {
                        x: sourceNode.position.x + sourceWidth,
                        y: sourceNode.position.y + sourceHeight / 2,
                    };
                    const edgeP2: XYPosition = {
                        x: targetNode.position.x,
                        y: targetNode.position.y + targetHeight / 2,
                    };

                    // Check if the cut line intersects this edge (using multiple segments for bezier approximation)
                    const midX = (edgeP1.x + edgeP2.x) / 2;
                    const cp1: XYPosition = { x: midX, y: edgeP1.y };
                    const cp2: XYPosition = { x: midX, y: edgeP2.y };

                    // Check straight segments of bezier approximation
                    const points = [edgeP1, cp1, cp2, edgeP2];
                    for (let i = 0; i < points.length - 1; i++) {
                        if (segmentsIntersect(start, end, points[i], points[i + 1])) {
                            edgesToRemove.add(edge.id);
                            break;
                        }
                    }
                    // Also check direct line
                    if (segmentsIntersect(start, end, edgeP1, edgeP2)) {
                        edgesToRemove.add(edge.id);
                    }
                }

                // Find nodes that the cut line crosses through
                const nodesToRemove = new Set<string>();
                for (const node of nodes) {
                    // Skip comment nodes from cut (they're decorative)
                    if (node.type === "comment") {
                        // Still allow cutting comments
                    }

                    const nodeWidth = node.measured?.width ?? node.width ?? 200;
                    const nodeHeight = node.measured?.height ?? node.height ?? 100;

                    const rect = {
                        x: node.position.x,
                        y: node.position.y,
                        width: typeof nodeWidth === 'number' ? nodeWidth : 200,
                        height: typeof nodeHeight === 'number' ? nodeHeight : 100,
                    };

                    if (rectIntersectsSegment(rect, start, end)) {
                        nodesToRemove.add(node.id);
                    }
                }

                // Also remove edges connected to deleted nodes
                for (const edge of edges) {
                    if (nodesToRemove.has(edge.source) || nodesToRemove.has(edge.target)) {
                        edgesToRemove.add(edge.id);
                    }
                }

                // Apply deletions
                if (edgesToRemove.size > 0 || nodesToRemove.size > 0) {
                    const newEdges = edges.filter(e => !edgesToRemove.has(e.id));
                    const newNodes = nodes.filter(n => !nodesToRemove.has(n.id));
                    setEdges(newEdges);
                    setNodes(newNodes);
                }
            }

            setIsCutting(false);
            setCutLine(null);
        }
    }, [isCutting, cutLine, nodes, edges, setNodes, setEdges, takeSnapshot]);

    // ============================================
    // Add node handler
    // ============================================

    const handleAddNode = useCallback((type: string) => {
        takeSnapshot(nodes, edges);
        const id = Math.random().toString(36).substring(7);
        const position = {
            x: Math.random() * 400 + 100,
            y: Math.random() * 400 + 100
        };

        const newNode: Node = {
            id,
            type,
            position,
            data: { label: `${type} node` }
        };

        setNodes([...nodes, newNode]);
    }, [nodes, edges, setNodes, takeSnapshot]);

    // ============================================
    // Undo / Redo handlers
    // ============================================

    const handleUndo = useCallback(() => {
        const result = undo(nodes, edges);
        if (result) {
            setNodes(result.nodes);
            setEdges(result.edges);
        }
    }, [undo, nodes, edges, setNodes, setEdges]);

    const handleRedo = useCallback(() => {
        const result = redo(nodes, edges);
        if (result) {
            setNodes(result.nodes);
            setEdges(result.edges);
        }
    }, [redo, nodes, edges, setNodes, setEdges]);

    // Keyboard shortcuts for undo/redo
    useEffect(() => {
        const handler = (e: KeyboardEvent) => {
            if ((e.metaKey || e.ctrlKey) && e.key === "z") {
                e.preventDefault();
                if (e.shiftKey) {
                    handleRedo();
                } else {
                    handleUndo();
                }
            }
            if ((e.metaKey || e.ctrlKey) && e.key === "y") {
                e.preventDefault();
                handleRedo();
            }
        };
        window.addEventListener("keydown", handler);
        return () => window.removeEventListener("keydown", handler);
    }, [handleUndo, handleRedo]);

    // Don't render ReactFlow until initialized to prevent race conditions
    if (!isInitialized) {
        return (
            <div className="w-full h-full flex items-center justify-center">
                <div className="text-muted-foreground">Loading workflow...</div>
            </div>
        );
    }

    return (
        <div className="w-full h-full relative" ref={flowWrapperRef}>
            <WorkflowToolbar
                onAddNode={handleAddNode}
                activeTool={activeTool}
                onToolChange={setActiveTool}
                onUndo={handleUndo}
                onRedo={handleRedo}
                canUndo={canUndo}
                canRedo={canRedo}
            />

            <ReactFlow
                nodes={nodesWithOutputs}
                edges={edges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onConnect={onConnect}
                isValidConnection={isValidConnection}
                onEdgeClick={onEdgeClick}
                onNodeDragStart={onNodeDragStart}
                onMoveStart={() => {
                    // Close cut line if panning
                    if (isCutting) {
                        setIsCutting(false);
                        setCutLine(null);
                    }
                }}
                onPaneMouseMove={onPaneMouseMove}
                nodeTypes={nodeTypes}
                fitView
                className={cn(
                    "bg-background-secondary",
                    activeTool === "pointer" && "[&_.react-flow__pane]:!cursor-default [&_.react-flow__pane.selection]:!cursor-default [&_.react-flow__node]:!cursor-default",
                    activeTool === "cut" && "[&_.react-flow__pane]:!cursor-crosshair [&_.react-flow__pane.selection]:!cursor-crosshair [&_.react-flow__node]:!cursor-crosshair",
                    activeTool === "hand" && "[&_.react-flow__pane]:!cursor-grab [&_.react-flow__pane.selection]:!cursor-grab [&_.react-flow__node]:!cursor-grab",
                    activeTool === "comment" && "[&_.react-flow__pane]:!cursor-cell [&_.react-flow__pane.selection]:!cursor-cell",
                )}
                minZoom={0.5}
                maxZoom={1.5}
                panOnDrag={activeTool === "hand"}
                selectionOnDrag={activeTool === "pointer"}
                selectionMode={"partial" as never}
                panOnScroll={true}
                nodesDraggable={activeTool !== "cut" && activeTool !== "comment"}
                nodesConnectable={activeTool !== "cut" && activeTool !== "comment"}
                elementsSelectable={activeTool !== "cut" && activeTool !== "comment"}
                onPaneClick={(event) => {
                    onPaneMouseDown(event as unknown as MouseEvent);
                }}
                defaultEdgeOptions={{
                    animated: true,
                    style: {
                        stroke: 'hsl(var(--primary))',
                        strokeWidth: 2,
                        cursor: activeTool === 'cut' ? 'crosshair' : (activeTool === 'pointer' ? 'default' : 'pointer'),
                    },
                }}
            >
                <Background variant={BackgroundVariant.Dots} gap={50} size={2} color="rgba(255, 255, 255, 0.2)" />
                <Controls
                    orientation="horizontal"
                    className="!flex !flex-row !absolute !bottom-4 !right-4 !left-auto !top-auto !transform-none !bg-card !border !border-border !rounded-full !shadow-lg !p-1"
                />

                {/* Cut line SVG overlay */}
                {isCutting && cutLine && (
                    <svg
                        className="absolute inset-0 w-full h-full pointer-events-none"
                        style={{ zIndex: 9999 }}
                    >
                        <line
                            x1={cutLine.start.x}
                            y1={cutLine.start.y}
                            x2={cutLine.end.x}
                            y2={cutLine.end.y}
                            stroke="#ef4444"
                            strokeWidth="2"
                            strokeDasharray="6 3"
                            strokeLinecap="round"
                        />
                    </svg>
                )}
            </ReactFlow>

            {/* Screen-space cut line overlay (rendered outside ReactFlow viewport) */}
            {isCutting && cutLine && (
                <svg
                    className="absolute inset-0 w-full h-full pointer-events-none"
                    style={{ zIndex: 9999 }}
                >
                    {(() => {
                        const startScreen = reactFlowInstance.flowToScreenPosition(cutLine.start);
                        const endScreen = reactFlowInstance.flowToScreenPosition(cutLine.end);
                        const wrapperRect = flowWrapperRef.current?.getBoundingClientRect();
                        const offsetX = wrapperRect?.left ?? 0;
                        const offsetY = wrapperRect?.top ?? 0;
                        return (
                            <line
                                x1={startScreen.x - offsetX}
                                y1={startScreen.y - offsetY}
                                x2={endScreen.x - offsetX}
                                y2={endScreen.y - offsetY}
                                stroke="#ef4444"
                                strokeWidth="2"
                                strokeDasharray="8 4"
                                strokeLinecap="round"
                                opacity="0.8"
                            />
                        );
                    })()}
                </svg>
            )}

            {/* Global mouse handlers for cut tool (need to capture outside ReactFlow pane) */}
            {activeTool === "cut" && (
                <div
                    className="absolute inset-0 z-[5]"
                    style={{ cursor: "crosshair" }}
                    onMouseDown={(e) => {
                        const pos = getFlowPosition(e.clientX, e.clientY);
                        setIsCutting(true);
                        setCutLine({ start: pos, end: pos });
                    }}
                    onMouseMove={(e) => {
                        if (isCutting) {
                            const pos = getFlowPosition(e.clientX, e.clientY);
                            setCutLine(prev => prev ? { ...prev, end: pos } : null);
                        }
                    }}
                    onMouseUp={onPaneMouseUp}
                    onMouseLeave={() => {
                        if (isCutting) {
                            onPaneMouseUp();
                        }
                    }}
                />
            )}
        </div>
    );
}

// ============================================
// Wrapper with ReactFlowProvider
// ============================================

export default function FlowEditor({ workflowId }: FlowEditorProps) {
    return (
        <ReactFlowProvider>
            <FlowEditorInner workflowId={workflowId} />
        </ReactFlowProvider>
    );
}
