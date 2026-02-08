"use client";

import { useCallback, useEffect, MouseEvent } from "react";
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
};

import { useState } from "react";
import { WorkflowToolbar } from "./toolbar";
import { useUndoRedo } from "@/hooks/use-undo-redo";

interface FlowEditorProps {
    workflowId?: string;
}

export default function FlowEditor({ workflowId }: FlowEditorProps) {
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

    const { takeSnapshot, undo, redo, canUndo, canRedo } = useUndoRedo(nodes, edges);

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
                        setIsInitialized(true); // Still mark as initialized to prevent infinite loop
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

    // Take snapshot for undo/redo when nodes/edges change
    useEffect(() => {
        if (isInitialized && (nodes.length > 0 || edges.length > 0)) {
            takeSnapshot(nodes, edges);
        }
    }, [nodes, edges, takeSnapshot, isInitialized]);

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
            const newNodes = applyNodeChanges(changes, nodes);
            setNodes(newNodes);
        },
        [nodes, setNodes]
    );

    const onEdgesChange = useCallback(
        (changes: EdgeChange[]) => {
            const newEdges = applyEdgeChanges(changes, edges);
            setEdges(newEdges);
        },
        [edges, setEdges]
    );

    const isValidConnection = useCallback((connection: Connection | Edge) => {
        const sourceType = connection.sourceHandle?.split('|')[0];
        const targetType = connection.targetHandle?.split('|')[0];
        const targetHandleId = connection.targetHandle?.split('|')[1]; // e.g., "start_image", "end_image"

        // Check type compatibility first
        if (!sourceType || !targetType || sourceType === 'any' || targetType === 'any') {
            // Continue to connection limit check
        } else if (sourceType !== targetType) {
            // Only allow same types to connect
            return false;
        }

        // Check connection limits for specific handles
        // These handles should only accept ONE connection
        const singleConnectionHandles = ['ref_video', 'reference_video', 'start_image', 'end_image'];

        if (targetHandleId && singleConnectionHandles.includes(targetHandleId)) {
            // Check if there's already a connection to this target handle
            const connectionId = 'id' in connection ? connection.id : null;
            const existingConnection = edges.find(
                (edge) =>
                    edge.target === connection.target &&
                    edge.targetHandle?.split('|')[1] === targetHandleId &&
                    edge.id !== connectionId // Don't count the current edge if it's being updated
            );

            if (existingConnection) {
                console.log(`[FlowEditor] Connection rejected: ${targetHandleId} already has a connection`);
                return false;
            }
        }

        // reference_images can have multiple connections (no restriction)
        return true;
    }, [edges]);

    const onConnect = useCallback(
        (params: Connection) => {
            const newEdges = addEdge(params, edges);
            setEdges(newEdges);
        },
        [edges, setEdges]
    );

    const onEdgeClick = useCallback((event: MouseEvent, edge: Edge) => {
        if (activeTool === "cut") {
            setEdges(edges.filter((e) => e.id !== edge.id));
        }
    }, [activeTool, edges, setEdges]);

    const handleAddNode = useCallback((type: string) => {
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
    }, [nodes, setNodes]);

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


    // Don't render ReactFlow until initialized to prevent race conditions
    if (!isInitialized) {
        return (
            <div className="w-full h-full flex items-center justify-center">
                <div className="text-muted-foreground">Loading workflow...</div>
            </div>
        );
    }

    return (
        <div className="w-full h-full relative">
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
                nodeTypes={nodeTypes}
                fitView
                className={cn(
                    "bg-background-secondary",
                    activeTool === "pointer" && "[&_.react-flow__pane]:!cursor-default [&_.react-flow__pane.selection]:!cursor-default [&_.react-flow__node]:!cursor-default",
                    activeTool === "cut" && "[&_.react-flow__pane]:!cursor-crosshair [&_.react-flow__pane.selection]:!cursor-crosshair [&_.react-flow__node]:!cursor-crosshair",
                    activeTool === "hand" && "[&_.react-flow__pane]:!cursor-grab [&_.react-flow__pane.selection]:!cursor-grab [&_.react-flow__node]:!cursor-grab"
                )}
                minZoom={0.5}
                maxZoom={1.5}
                panOnDrag={activeTool === "hand"}
                selectionOnDrag={activeTool === "pointer" || activeTool === "cut"}
                selectionMode={"partial" as never}
                panOnScroll={true}
                defaultEdgeOptions={{
                    animated: true,
                    style: { stroke: 'hsl(var(--primary))', strokeWidth: 2, cursor: activeTool === 'cut' ? 'crosshair' : (activeTool === 'pointer' ? 'default' : 'pointer') },
                }}
            >
                <Background variant={BackgroundVariant.Dots} gap={50} size={2} color="rgba(255, 255, 255, 0.2)" />
                <Controls
                    orientation="horizontal"
                    className="!flex !flex-row !absolute !bottom-4 !right-4 !left-auto !top-auto !transform-none !bg-card !border !border-border !rounded-full !shadow-lg !p-1"
                />
            </ReactFlow>
        </div>
    );
}
