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
import { AssistantNode } from "./nodes/assistant-node";
import { EditorAgentNode } from "./nodes/editor-agent-node";
import { MediaUploadNode } from "./nodes/media-upload-node";
import { CommentNode } from "./nodes/comment-node";

// Store
import { useWorkflowStore } from "@/lib/workflow-store";
import { usePublicView } from "@/lib/public-view-context";
import { inferMediaKind } from "@/lib/media-utils";

const nodeTypes = {
    text: TextNode,
    upload: UploadNode,
    imageGen: ImageGenNode,
    audioGen: AudioGenNode,
    videoGen: VideoGenNode,
    assistant: AssistantNode,
    vision: AssistantNode,
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
        isPublicView,
    } = useWorkflowStore();
    const { isPublicView: isPublicCtx, requireLogin } = usePublicView();

    const [activeTool, setActiveTool] = useState("hand");
    const [isInitialized, setIsInitialized] = useState(false);
    const flowWrapperRef = useRef<HTMLDivElement>(null);

    const { takeSnapshot, undo, redo, canUndo, canRedo } = useUndoRedo();

    const reactFlowInstance = useReactFlow();

    const storeId = useWorkflowStore((s) => s.id);

    // Load workflow on mount if ID is provided
    useEffect(() => {
        let mounted = true;

        const loadWorkflowData = async () => {
            if (workflowId && workflowId !== "new" && !isInitialized) {
                // If the store already has this workflow loaded (page did it), skip re-fetching
                if (isPublicView || storeId === workflowId) {
                    setIsInitialized(true);
                    return;
                }
                try {
                    await loadWorkflow(workflowId);
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
    }, [workflowId, loadWorkflow, isInitialized, isPublicView, storeId]);

    const isReadOnly = isPublicView || isPublicCtx;

    // Inject outputs and execution state into node data for display
    const nodesWithOutputs = nodes.map((node) => ({
        ...node,
        data: {
            ...node.data,
            output: outputs[node.id] || node.data.output,
            isRunning: runningNodeId === node.id,
            executionStatus: nodeExecutionStates[node.id]?.status || null,
            onRun: isReadOnly
                ? () => requireLogin("Sign in to run nodes and generate media.")
                : () => runNode(node.id),
            isPublicView: isReadOnly,
        },
    }));

    const onNodesChange = useCallback(
        (changes: NodeChange[]) => {
            if (isReadOnly) {
                // In public view, only allow selection changes (for viewing node details)
                const selectionOnly = changes.filter(c => c.type === "select");
                if (selectionOnly.length > 0) {
                    const newNodes = applyNodeChanges(selectionOnly, nodes);
                    setNodes(newNodes);
                }
                return;
            }

            const hasRemove = changes.some(c => c.type === "remove");
            if (hasRemove) {
                takeSnapshot(nodes, edges);
            }

            const newNodes = applyNodeChanges(changes, nodes);
            setNodes(newNodes);
        },
        [nodes, edges, setNodes, takeSnapshot, isReadOnly]
    );

    const onEdgesChange = useCallback(
        (changes: EdgeChange[]) => {
            if (isReadOnly) return;

            const hasRemove = changes.some(c => c.type === "remove");
            if (hasRemove) {
                takeSnapshot(nodes, edges);
            }

            const newEdges = applyEdgeChanges(changes, edges);
            setEdges(newEdges);
        },
        [nodes, edges, setEdges, takeSnapshot, isReadOnly]
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

        const singleConnectionHandles = ['ref_video', 'reference_video', 'reference_image', 'start_image', 'end_image'];

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

        // Elements mode compatibility guard:
        // - elements_video cannot coexist with elements_image/elements_audio
        // - elements_image/elements_audio can coexist with each other
        // - if elements_video exists, block new elements_image/elements_audio links
        if (targetHandleId && connection.target) {
            const targetNode = nodes.find((node) => node.id === connection.target);
            if (targetNode?.type === "videoGen") {
                const existingTargetHandles = edges
                    .filter((edge) => edge.target === connection.target)
                    .map((edge) => edge.targetHandle?.split('|')[1] || "");

                const hasElementsVideo = existingTargetHandles.includes("elements_video");
                const hasElementsImageOrAudio = existingTargetHandles.includes("elements_image")
                    || existingTargetHandles.includes("elements_audio");

                if (targetHandleId === "elements_video" && hasElementsImageOrAudio) {
                    console.log("[FlowEditor] Connection rejected: elements_video cannot be combined with elements_image/elements_audio");
                    return false;
                }

                if ((targetHandleId === "elements_image" || targetHandleId === "elements_audio") && hasElementsVideo) {
                    console.log("[FlowEditor] Connection rejected: elements_image/elements_audio cannot be combined with elements_video");
                    return false;
                }
            }
        }

        return true;
    }, [edges, nodes]);

    const onConnect = useCallback(
        (params: Connection) => {
            if (isReadOnly) return;
            takeSnapshot(nodes, edges);
            const newEdges = addEdge(params, edges);
            setEdges(newEdges);
        },
        [nodes, edges, setEdges, takeSnapshot, isReadOnly]
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
            // Switch back to hand after placing
            setActiveTool("hand");
        }
    }, [activeTool, getFlowPosition, nodes, edges, setNodes, takeSnapshot]);

    // ============================================
    // Add node handler
    // ============================================

    const handleAddNode = useCallback((type: string) => {
        takeSnapshot(nodes, edges);
        const id = Math.random().toString(36).substring(7);

        let position = {
            x: Math.random() * 400 + 100,
            y: Math.random() * 400 + 100
        };

        if (flowWrapperRef.current) {
            const rect = flowWrapperRef.current.getBoundingClientRect();
            const x = rect.left + rect.width / 2;
            const y = rect.top + rect.height / 2;

            const offsetX = (Math.random() - 0.5) * 50;
            const offsetY = (Math.random() - 0.5) * 50;

            position = reactFlowInstance.screenToFlowPosition({
                x: x + offsetX,
                y: y + offsetY
            });
        }

        const newNode: Node = {
            id,
            type,
            position,
            data: { label: `${type} node` }
        };

        setNodes([...nodes, newNode]);
    }, [nodes, edges, setNodes, takeSnapshot, reactFlowInstance]);

    // ============================================
    // Drop asset from "Your Stuff" → create node
    // ============================================

    const onDragOver = useCallback((event: React.DragEvent) => {
        event.preventDefault();
        event.dataTransfer.dropEffect = "copy";
        // console.log("onDragOver fired");
    }, []);

    const { setNodeOutput } = useWorkflowStore();

    const onDropAsset = useCallback((event: React.DragEvent) => {
        event.preventDefault();
        if (isReadOnly) return;

        const jsonStr = event.dataTransfer.getData("application/kureita-asset");
        if (!jsonStr) return;

        let payload: {
            type?: string;
            url?: string;
            presigned_url?: string;
            asset_category?: string;
            media_type?: string;
            mime_type?: string;
            node_type?: string;
            node_data?: Record<string, unknown>;
        };

        try {
            payload = JSON.parse(jsonStr);
        } catch {
            return;
        }

        if (payload.type !== "asset" || !payload.url) return;

        // Determine which node type to create
        const nodeType = payload.node_type || (() => {
            const cat = payload.asset_category || "";
            if (cat === "generated_image") return "imageGen";
            if (cat === "generated_video") return "videoGen";
            if (cat === "generated_audio") return "audioGen";
            if (cat === "rendered_video") return "editorAgent";
            return "mediaUpload";
        })();

        // Build node data from saved settings
        const savedData = payload.node_data || {};
        const nodeData: Record<string, unknown> = { ...savedData, output: payload.url };
        if (nodeType === "mediaUpload" && !nodeData.mediaType) {
            const inferredKind = inferMediaKind({
                mimeType: payload.mime_type,
                assetCategory: payload.media_type || payload.asset_category,
                url: payload.url || payload.presigned_url,
            });
            if (inferredKind !== "unknown") {
                nodeData.mediaType = inferredKind;
            }
        }

        // Generate unique ID & position at drop point
        const id = `${nodeType}_${Math.random().toString(36).substring(2, 9)}`;
        const position = reactFlowInstance.screenToFlowPosition({
            x: event.clientX,
            y: event.clientY,
        });

        takeSnapshot(nodes, edges);

        const newNode: Node = {
            id,
            type: nodeType,
            position,
            data: nodeData,
        };

        setNodes([...nodes, newNode]);

        // Pre-fill the output so the node immediately shows the asset preview
        setNodeOutput(id, payload.url);

        console.log(`[FlowEditor] Created ${nodeType} node from dropped asset`, {
            id,
            nodeData: Object.keys(savedData),
        });
    }, [nodes, edges, setNodes, takeSnapshot, reactFlowInstance, isReadOnly, setNodeOutput]);

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

    // Allow external callers (agent sidebar) to request a fit-view after applying workflow updates.
    useEffect(() => {
        const handler = (event: Event) => {
            const customEvent = event as CustomEvent<{ workflowId?: string }>;
            const targetWorkflowId = customEvent.detail?.workflowId;
            if (targetWorkflowId && workflowId && targetWorkflowId !== workflowId) return;

            window.setTimeout(() => {
                const currentNodes = reactFlowInstance.getNodes();
                if (!currentNodes.length) return;
                reactFlowInstance.fitView({
                    padding: 0.2,
                    duration: 380,
                    includeHiddenNodes: true,
                });
            }, 60);
        };

        window.addEventListener("kureita:fit-workflow-view", handler as EventListener);
        return () => window.removeEventListener("kureita:fit-workflow-view", handler as EventListener);
    }, [reactFlowInstance, workflowId]);

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
            {activeTool === "cut" && !isReadOnly && (
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
            {!isReadOnly && (
                <WorkflowToolbar
                    onAddNode={handleAddNode}
                    activeTool={activeTool}
                    onToolChange={setActiveTool}
                    onUndo={handleUndo}
                    onRedo={handleRedo}
                    canUndo={canUndo}
                    canRedo={canRedo}
                />
            )}

            <ReactFlow
                nodes={nodesWithOutputs}
                edges={edges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onConnect={onConnect}
                isValidConnection={isValidConnection}
                onEdgeClick={onEdgeClick}
                onNodeDragStart={onNodeDragStart}
                onDragOver={onDragOver}
                onDrop={onDropAsset}
                nodeTypes={nodeTypes}
                defaultViewport={(()=>{
                    if (workflowId && workflowId !== "new" && typeof window !== 'undefined') {
                        try {
                            const saved = localStorage.getItem(`kureita_viewport_${workflowId}`);
                            if (saved) return JSON.parse(saved);
                        } catch (e) {
                            console.error("Failed to load viewport", e);
                        }
                    }
                    return { x: 0, y: 0, zoom: 1 };
                })()}
                onMoveEnd={(event, viewport) => {
                    if (workflowId && workflowId !== "new" && typeof window !== 'undefined') {
                        localStorage.setItem(`kureita_viewport_${workflowId}`, JSON.stringify(viewport));
                    }
                }}
                className={cn(
                    "bg-background-secondary",
                    activeTool === "cut" && "[&_.react-flow__pane]:!cursor-crosshair [&_.react-flow__pane.selection]:!cursor-crosshair [&_.react-flow__node]:!cursor-crosshair [&_.react-flow__edge:hover_.react-flow__edge-path]:!stroke-[#ef4444] [&_.react-flow__edge:hover_.react-flow__edge-path]:!stroke-[4px]",
                    activeTool === "hand" && "[&_.react-flow__pane]:!cursor-grab [&_.react-flow__pane.selection]:!cursor-grab [&_.react-flow__node]:!cursor-grab",
                    activeTool === "comment" && "[&_.react-flow__pane]:!cursor-cell [&_.react-flow__pane.selection]:!cursor-cell",
                )}
                minZoom={0.01}
                maxZoom={10}
                panOnDrag={isReadOnly || activeTool === "hand"}
                selectionOnDrag={false}
                selectionMode={"partial" as never}
                panOnScroll={true}
                nodesDraggable={!isReadOnly && activeTool !== "cut" && activeTool !== "comment"}
                nodesConnectable={!isReadOnly && activeTool !== "cut" && activeTool !== "comment"}
                elementsSelectable={activeTool !== "cut" && activeTool !== "comment"}
                onPaneClick={(event) => {
                    onPaneMouseDown(event as unknown as MouseEvent);
                }}
                defaultEdgeOptions={{
                    animated: true,
                    style: {
                        stroke: 'var(--primary)',
                        strokeWidth: 2,
                        cursor: activeTool === 'cut' ? 'crosshair' : 'pointer',
                    },
                }}
            >
                <Background variant={BackgroundVariant.Dots} gap={50} size={2} color="rgba(255, 255, 255, 0.2)" />
                <Controls
                    showFitView
                    orientation="horizontal"
                    className="!flex !flex-row !absolute !bottom-[72px] md:!bottom-4 !left-2 md:!left-auto md:!right-4 !top-auto !transform-none !bg-card !border !border-border !rounded-full !shadow-lg !p-0.5 md:!p-1"
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
