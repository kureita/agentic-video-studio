"use client";

import { useCallback, useMemo, useEffect, useRef, useState } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  addEdge,
  Connection,
  BackgroundVariant,
  Node,
  Edge,
  useReactFlow,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { useCanvasStore, CanvasNodeData, CanvasEdgeData } from "@/lib/canvas-store";
import { canvasApi } from "@/lib/api";
import {
  InitialNode,
  StoryNode,
  ImageNode,
  VideoNode,
  CompositionNode,
  RenderNode,
} from "@/components/canvas";

// Define custom node types - MUST be outside component
const nodeTypes = {
  initial: InitialNode,
  story: StoryNode,
  image: ImageNode,
  video: VideoNode,
  composition: CompositionNode,
  render: RenderNode,
};

// Default initial node
const createDefaultNodes = (): Node[] => [
  {
    id: "initial",
    type: "initial",
    position: { x: 0, y: 0 },
    data: {},
  },
];

// Build nodes based on what data exists in the store
const buildNodesFromState = (
  brandData: unknown,
  storyData: unknown,
  scenes: { image_url?: string; video_url?: string }[],
  savedNodes: CanvasNodeData[]
): Node[] => {
  const nodes: Node[] = [];
  
  // Always start with initial node
  const initialPos = savedNodes.find(n => n.id === "initial")?.position || { x: 0, y: 0 };
  nodes.push({
    id: "initial",
    type: "initial",
    position: initialPos,
    data: {},
  });

  // Add story node if brand exists
  if (brandData) {
    const storyPos = savedNodes.find(n => n.id === "story")?.position || { x: 450, y: 0 };
    nodes.push({
      id: "story",
      type: "story",
      position: storyPos,
      data: {},
    });
  }

  // Add image node if story exists
  if (storyData) {
    const imagePos = savedNodes.find(n => n.id === "image")?.position || { x: 900, y: 0 };
    nodes.push({
      id: "image",
      type: "image",
      position: imagePos,
      data: {},
    });
  }

  // Add video node if images exist
  if (scenes.some(s => s.image_url)) {
    const videoPos = savedNodes.find(n => n.id === "video")?.position || { x: 1350, y: 0 };
    nodes.push({
      id: "video",
      type: "video",
      position: videoPos,
      data: {},
    });
  }

  // Add composition node if videos exist
  if (scenes.some(s => s.video_url)) {
    const compPos = savedNodes.find(n => n.id === "composition")?.position || { x: 1800, y: 0 };
    nodes.push({
      id: "composition",
      type: "composition",
      position: compPos,
      data: {},
    });
  }

  return nodes;
};

// Build edges based on nodes
const buildEdgesFromNodes = (nodes: Node[]): Edge[] => {
  const edges: Edge[] = [];
  const nodeIds = nodes.map(n => n.id);
  const order = ["initial", "story", "image", "video", "composition", "render"];
  
  for (let i = 0; i < order.length - 1; i++) {
    const source = order[i];
    const target = order[i + 1];
    if (nodeIds.includes(source) && nodeIds.includes(target)) {
      edges.push({
        id: `${source}-${target}`,
        source,
        target,
        animated: false,
        style: { stroke: "#8A8984", strokeWidth: 2 },
      });
    }
  }
  
  return edges;
};

// Debounce helper
function debounce<T extends (...args: Parameters<T>) => void>(
  func: T,
  wait: number
): (...args: Parameters<T>) => void {
  let timeout: NodeJS.Timeout | null = null;
  return (...args: Parameters<T>) => {
    if (timeout) clearTimeout(timeout);
    timeout = setTimeout(() => func(...args), wait);
  };
}

function CanvasFlowInner() {
  const { fitView } = useReactFlow();
  const {
    projectId,
    canvasNodes,
    canvasEdges,
    setCanvasNodes,
    setCanvasEdges,
    brandData,
    storyData,
    scenes,
  } = useCanvasStore();

  // Build initial nodes based on store state
  const initialNodes = useMemo(() => {
    return buildNodesFromState(brandData, storyData, scenes, canvasNodes);
  }, []);

  const initialEdges = useMemo(() => {
    return buildEdgesFromNodes(initialNodes);
  }, [initialNodes]);

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const [isReady, setIsReady] = useState(false);

  // Fit view after initial render
  useEffect(() => {
    const timer = setTimeout(() => {
      fitView({ padding: 0.3, maxZoom: 1 });
      setIsReady(true);
    }, 100);
    return () => clearTimeout(timer);
  }, [fitView]);

  // Rebuild nodes when store data changes (e.g., after loading a project)
  useEffect(() => {
    const newNodes = buildNodesFromState(brandData, storyData, scenes, canvasNodes);
    const newEdges = buildEdgesFromNodes(newNodes);
    
    // Only update if nodes changed
    if (JSON.stringify(newNodes.map(n => n.id)) !== JSON.stringify(nodes.map(n => n.id))) {
      setNodes(newNodes);
      setEdges(newEdges);
      setTimeout(() => fitView({ padding: 0.3, maxZoom: 1 }), 50);
    }
  }, [brandData, storyData, scenes]);

  // Auto-save to store and MongoDB (debounced)
  const saveToStore = useMemo(
    () =>
      debounce((nodesToSave: Node[], edgesToSave: Edge[]) => {
        const nodeData: CanvasNodeData[] = nodesToSave.map((n) => ({
          id: n.id,
          type: n.type || "initial",
          position: n.position,
          data: {},
        }));
        const edgeData: CanvasEdgeData[] = edgesToSave.map((e) => ({
          id: e.id,
          source: e.source,
          target: e.target,
          animated: e.animated,
        }));

        setCanvasNodes(nodeData);
        setCanvasEdges(edgeData);

        // Save to MongoDB if we have a project
        const currentProjectId = useCanvasStore.getState().projectId;
        if (currentProjectId) {
          canvasApi.saveState(currentProjectId, nodeData, edgeData).catch((err) => {
            console.error("Failed to save canvas state:", err);
          });
        }
      }, 1500),
    [setCanvasNodes, setCanvasEdges]
  );

  // Save whenever nodes or edges change (after ready)
  useEffect(() => {
    if (isReady && nodes.length > 0) {
      saveToStore(nodes, edges);
    }
  }, [nodes, edges, saveToStore, isReady]);

  // Add new node to the canvas - horizontal flow (left to right)
  const addNode = useCallback(
    (type: string, id: string, afterId: string) => {
      setNodes((nds) => {
        if (nds.some((n) => n.id === id)) return nds;

        const afterNode = nds.find((n) => n.id === afterId);
        if (!afterNode) return nds;

        const newNode: Node = {
          id,
          type,
          position: { x: afterNode.position.x + 450, y: afterNode.position.y },
          data: {},
        };

        return [...nds, newNode];
      });

      setEdges((eds) => {
        const edgeId = `${afterId}-${id}`;
        if (eds.some((e) => e.id === edgeId)) return eds;

        const newEdge: Edge = {
          id: edgeId,
          source: afterId,
          target: id,
          animated: false,
          style: { stroke: "#8A8984", strokeWidth: 2 },
        };

        return [...eds, newEdge];
      });

      // Fit view after adding node
      setTimeout(() => fitView({ padding: 0.3, maxZoom: 1 }), 50);
    },
    [setNodes, setEdges, fitView]
  );

  // Handle edge connections
  const onConnect = useCallback(
    (connection: Connection) => {
      setEdges((eds) => addEdge(connection, eds));
    },
    [setEdges]
  );

  // Create proceed handlers for each node type
  const nodeDataHandlers = useMemo(
    () => ({
      initial: { onProceed: () => addNode("story", "story", "initial") },
      story: { onProceed: () => addNode("image", "image", "story") },
      image: { onProceed: () => addNode("video", "video", "image") },
      video: { onProceed: () => addNode("composition", "composition", "video") },
      composition: { onProceed: () => addNode("render", "render", "composition") },
      render: {},
    }),
    [addNode]
  );

  // Inject handlers into nodes
  const nodesWithHandlers = useMemo(() => {
    return nodes.map((node) => ({
      ...node,
      data: {
        ...node.data,
        ...(nodeDataHandlers[node.id as keyof typeof nodeDataHandlers] || {}),
      },
    }));
  }, [nodes, nodeDataHandlers]);

  return (
    <ReactFlow
      nodes={nodesWithHandlers}
      edges={edges}
      onNodesChange={onNodesChange}
      onEdgesChange={onEdgesChange}
      onConnect={onConnect}
      nodeTypes={nodeTypes}
      fitView
      fitViewOptions={{ padding: 0.3, maxZoom: 1 }}
      minZoom={0.1}
      maxZoom={2}
      proOptions={{ hideAttribution: true }}
      nodesDraggable
      nodesConnectable={false}
      className="bg-background"
    >
      <Background
        variant={BackgroundVariant.Dots}
        gap={24}
        size={1}
        color="#8A8984"
        className="opacity-30"
      />
      <Controls
        showInteractive={false}
        className="!bg-background !border !border-border !rounded-xl !shadow-lg"
      />
      <MiniMap
        nodeStrokeWidth={3}
        zoomable
        pannable
        className="!bg-background-secondary !border !border-border !rounded-xl"
        maskColor="rgba(0, 0, 0, 0.1)"
      />
    </ReactFlow>
  );
}

// Wrapper to provide ReactFlow context
import { ReactFlowProvider } from "@xyflow/react";

export default function CanvasFlow() {
  return (
    <div className="flex-1 w-full">
      <ReactFlowProvider>
        <CanvasFlowInner />
      </ReactFlowProvider>
    </div>
  );
}
