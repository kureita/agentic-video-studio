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
        nodeExecutionStates,
    } = useWorkflowStore();

    const [activeTool, setActiveTool] = useState("pointer");
    const [isInitialized, setIsInitialized] = useState(false);
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

    // Inject outputs and execution state into node data for display
    const nodesWithOutputs = nodes.map((node) => ({
        ...node,
        data: {
            ...node.data,
            output: outputs[node.id] || node.data.output,
            isRunning: runningNodeId === node.id,
            executionStatus: nodeExecutionStates[node.id]?.status || null,
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

    const onEdgeClick = useCallback((_event: MouseEvent | React.MouseEvent, edge: Edge) => {
        if (activeTool === "cut") {
            takeSnapshot(nodes, edges);
            setEdges(edges.filter((e) => e.id !== edge.id));
        }
    }, [activeTool, nodes, edges, setEdges, takeSnapshot]);

    // ============================================
    // Handlers for canvas clicks
    // ============================================

    const getFlowPosition = useCallback((clientX: number, clientY: number): XYPosition => {
        const position = reactFlowInstance.screenToFlowPosition({ x: clientX, y: clientY });
        return position;
    }, [reactFlowInstance]);

    const onPaneMouseDown = useCallback((event: MouseEvent | React.MouseEvent) => {
        if (activeTool === "comment") {
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
            {activeTool === "cut" && (
                <style dangerouslySetInnerHTML={{
                    __html: `
                        .react-flow__edge .react-flow__edge-interaction {
                            cursor: crosshair !important;
                        }
                        .react-flow__edge:hover .react-flow__edge-path {
                            stroke: #ef4444 !important;
                            stroke-width: 4px !important;
                        }
                    `
                }} />
            )}
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
                nodeTypes={nodeTypes}
                fitView
                className={cn(
                    "bg-background-secondary",
                    activeTool === "pointer" && "[&_.react-flow__pane]:!cursor-default [&_.react-flow__pane.selection]:!cursor-default [&_.react-flow__node]:!cursor-default",
                    activeTool === "cut" && "[&_.react-flow__pane]:!cursor-crosshair [&_.react-flow__pane.selection]:!cursor-crosshair [&_.react-flow__node]:!cursor-crosshair [&_.react-flow__edge:hover_.react-flow__edge-path]:!stroke-[#ef4444] [&_.react-flow__edge:hover_.react-flow__edge-path]:!stroke-[4px]",
                    activeTool === "hand" && "[&_.react-flow__pane]:!cursor-grab [&_.react-flow__pane.selection]:!cursor-grab [&_.react-flow__node]:!cursor-grab",
                    activeTool === "comment" && "[&_.react-flow__pane]:!cursor-cell [&_.react-flow__pane.selection]:!cursor-cell",
                )}
                minZoom={0.01}
                maxZoom={10}
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
                    showFitView
                    orientation="horizontal"
                    className="!flex !flex-row !absolute !bottom-4 !right-4 !left-auto !top-auto !transform-none !bg-card !border !border-border !rounded-full !shadow-lg !p-1"
                />
            </ReactFlow>
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
