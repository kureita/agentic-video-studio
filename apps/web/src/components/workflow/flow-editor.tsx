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
import { VideoGenNode } from "./nodes/video-gen-node";
import { AssistantNode } from "./nodes/assistant-node";
import { UpscalerNode } from "./nodes/upscaler-node";

// Store
import { useWorkflowStore } from "@/lib/workflow-store";

const nodeTypes = {
    text: TextNode,
    upload: UploadNode,
    imageGen: ImageGenNode,
    videoGen: VideoGenNode,
    assistant: AssistantNode,
    upscaler: UpscalerNode,
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
        if (workflowId && workflowId !== "new" && !isInitialized) {
            loadWorkflow(workflowId).then(() => setIsInitialized(true));
        } else {
            setIsInitialized(true);
        }
    }, [workflowId, loadWorkflow, isInitialized]);

    // Take snapshot for undo/redo when nodes/edges change
    useEffect(() => {
        if (isInitialized) {
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

        // If types are not specified or one is 'any', allow the connection
        if (!sourceType || !targetType || sourceType === 'any' || targetType === 'any') {
            return true;
        }

        // Only allow same types to connect
        return sourceType === targetType;
    }, []);

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
