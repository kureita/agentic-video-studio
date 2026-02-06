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

import { useCanvasStore, CanvasNodeData, CanvasEdgeData, StoryBeat } from "@/lib/canvas-store";
import { canvasApi } from "@/lib/api";
import {
  InitialNode,
  BrandSelectorNode,
  TrendResearchNode,
  InspirationNode,
  StoryStrategyNode,
  StoryNode,
  StoryBeatNode,
  BeatImageNode,
  BeatVideoNode,
  ImageNode,
  VideoNode,
  CompositionNode,
  RenderNode,
  FrameExtractorNode,
  GenericInputNode,
  AtomicLLMNode,
  AtomicVideoNode
} from "@/components/canvas";

// Define custom node types - MUST be outside component
const nodeTypes = {
  initial: InitialNode,
  brand: BrandSelectorNode,
  trend: TrendResearchNode,
  inspiration: InspirationNode,
  strategy: StoryStrategyNode,
  story: StoryNode,
  beat: StoryBeatNode,
  beatImage: BeatImageNode,
  beatVideo: BeatVideoNode,
  image: ImageNode,
  video: VideoNode,
  composition: CompositionNode,
  render: RenderNode,
  frameExtractor: FrameExtractorNode,
  // Atomic / Generic Nodes (Phase 3)
  atomic_input: GenericInputNode,
  atomic_llm: AtomicLLMNode,
  atomic_video: AtomicVideoNode,
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
  trendData: unknown,
  inspirationBrief: unknown,
  storyStrategy: unknown,
  storyData: unknown,
  storyBeats: StoryBeat[],
  scenes: { image_url?: string; video_url?: string }[],
  savedNodes: CanvasNodeData[]
): Node[] => {
  const nodes: Node[] = [];
  const NODE_WIDTH = 380;
  const NODE_GAP = 100;
  let xOffset = 0;

  // Helper to get saved position or calculate new one
  const getPosition = (id: string, defaultY = 0) => {
    const saved = savedNodes.find(n => n.id === id)?.position;
    if (saved) return saved;
    const pos = { x: xOffset, y: defaultY };
    xOffset += NODE_WIDTH + NODE_GAP;
    return pos;
  };

  // Initial node
  nodes.push({
    id: "initial",
    type: "initial",
    position: getPosition("initial"),
    data: {},
  });

  // Brand node (if URL entered)
  if (brandData) {
    nodes.push({
      id: "brand",
      type: "brand",
      position: getPosition("brand"),
      data: {},
    });
  }

  // Trend research node (after brand)
  if (brandData) {
    nodes.push({
      id: "trend",
      type: "trend",
      position: getPosition("trend"),
      data: {},
    });
  }

  // Inspiration node (after trend)
  if (trendData) {
    nodes.push({
      id: "inspiration",
      type: "inspiration",
      position: getPosition("inspiration"),
      data: {},
    });
  }

  // Strategy node (after inspiration)
  if (inspirationBrief || trendData) {
    nodes.push({
      id: "strategy",
      type: "strategy",
      position: getPosition("strategy"),
      data: {},
    });
  }

  // Story node (after strategy/brand)
  if (brandData) {
    nodes.push({
      id: "story",
      type: "story",
      position: getPosition("story"),
      data: {},
    });
  }

  // Add beat nodes if story beats exist
  if (storyBeats.length > 0) {
    const beatStartX = xOffset;
    const beatHeight = 350;
    const beatGap = 20;

    storyBeats.forEach((beat, idx) => {
      const beatX = beatStartX;
      const beatY = idx * (beatHeight + beatGap);

      // Beat node
      nodes.push({
        id: `beat-${beat.id}`,
        type: "beat",
        position: savedNodes.find(n => n.id === `beat-${beat.id}`)?.position || { x: beatX, y: beatY },
        data: { beatId: beat.id },
      });

      // Beat image node (right of beat)
      nodes.push({
        id: `beatImage-${beat.id}`,
        type: "beatImage",
        position: savedNodes.find(n => n.id === `beatImage-${beat.id}`)?.position || { x: beatX + NODE_WIDTH + NODE_GAP, y: beatY },
        data: { beatId: beat.id },
      });

      // Beat video node (right of image)
      nodes.push({
        id: `beatVideo-${beat.id}`,
        type: "beatVideo",
        position: savedNodes.find(n => n.id === `beatVideo-${beat.id}`)?.position || { x: beatX + 2 * (NODE_WIDTH + NODE_GAP), y: beatY },
        data: { beatId: beat.id, previousBeatId: idx > 0 ? storyBeats[idx - 1].id : undefined },
      });

      // Frame Extractor (between beats)
      // Only add if not the last beat, as it connects to the next beat
      if (idx < storyBeats.length - 1) {
        nodes.push({
          id: `beatExtractor-${beat.id}`,
          type: "frameExtractor",
          position: savedNodes.find(n => n.id === `beatExtractor-${beat.id}`)?.position || { x: beatX + 3 * (NODE_WIDTH + NODE_GAP), y: beatY },
          data: { beatId: beat.id },
        });
      }
    });

    xOffset = beatStartX + 3 * (NODE_WIDTH + NODE_GAP);
  } else if (storyData) {
    // Fallback to old image/video nodes if no beats
    nodes.push({
      id: "image",
      type: "image",
      position: getPosition("image"),
      data: {},
    });

    if (scenes.some(s => s.image_url)) {
      nodes.push({
        id: "video",
        type: "video",
        position: getPosition("video"),
        data: {},
      });
    }
  }

  // Composition node (after all beats/videos)
  // Check if videos exist in either scenes or beats
  const hasVideos = scenes.some(s => s.video_url) || storyBeats.some(b => b.videoUrl);

  if (hasVideos) {
    nodes.push({
      id: "composition",
      type: "composition",
      position: getPosition("composition"),
      data: {},
    });
  }

  return nodes;
};

// Build edges based on nodes
const buildEdgesFromNodes = (nodes: Node[], storyBeats: StoryBeat[] = []): Edge[] => {
  const edges: Edge[] = [];
  const nodeIds = nodes.map(n => n.id);

  // Main flow order (new nodes)
  const mainFlow = ["initial", "brand", "trend", "inspiration", "strategy", "story"];

  // Create main flow edges
  for (let i = 0; i < mainFlow.length - 1; i++) {
    const source = mainFlow[i];
    const target = mainFlow[i + 1];
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

  // Create beat flow edges (story -> beat1 -> beat2 -> ... -> composition)
  if (storyBeats.length > 0) {
    // Story to first beat
    if (nodeIds.includes("story") && nodeIds.includes(`beat-${storyBeats[0].id}`)) {
      edges.push({
        id: `story-beat-${storyBeats[0].id}`,
        source: "story",
        target: `beat-${storyBeats[0].id}`,
        animated: false,
        style: { stroke: "#8A8984", strokeWidth: 2 },
      });
    }

    // Beat chain: beat -> beatImage -> beatVideo
    storyBeats.forEach((beat, idx) => {
      const beatId = `beat-${beat.id}`;
      const imageId = `beatImage-${beat.id}`;
      const videoId = `beatVideo-${beat.id}`;

      // Beat -> Image
      if (nodeIds.includes(beatId) && nodeIds.includes(imageId)) {
        edges.push({
          id: `${beatId}-${imageId}`,
          source: beatId,
          target: imageId,
          animated: false,
          style: { stroke: "#6366f1", strokeWidth: 2 },
        });
      }

      // Image -> Video
      if (nodeIds.includes(imageId) && nodeIds.includes(videoId)) {
        edges.push({
          id: `${imageId}-${videoId}`,
          source: imageId,
          target: videoId,
          animated: false,
          style: { stroke: "#6366f1", strokeWidth: 2 },
        });
      }

      // Video -> Next beat (vertical connection)
      if (idx < storyBeats.length - 1) {
        const nextBeatId = `beat-${storyBeats[idx + 1].id}`;
        const nextImageId = `beatImage-${storyBeats[idx + 1].id}`;
        const extractorId = `beatExtractor-${beat.id}`;

        // Video -> Extractor
        if (nodeIds.includes(videoId) && nodeIds.includes(extractorId)) {
          edges.push({
            id: `${videoId}-${extractorId}`,
            source: videoId,
            target: extractorId,
            animated: false,
            style: { stroke: "#6366f1", strokeWidth: 2 },
          });
        }

        // Extractor -> Next Image (Sequential Video Flow)
        if (nodeIds.includes(extractorId) && nodeIds.includes(nextImageId)) {
          edges.push({
            id: `${extractorId}-${nextImageId}`,
            source: extractorId,
            target: nextImageId,
            animated: true,
            style: { stroke: "#10b981", strokeWidth: 2 },
          });
        }

        // Also link Beat Node -> Image Node (handled in loop for current beat)
        // But we want to visualizing that Extractor feeds into next Image
      }
    });

    // Last beat video -> composition
    const lastBeatVideoId = `beatVideo-${storyBeats[storyBeats.length - 1].id}`;
    if (nodeIds.includes(lastBeatVideoId) && nodeIds.includes("composition")) {
      edges.push({
        id: `${lastBeatVideoId}-composition`,
        source: lastBeatVideoId,
        target: "composition",
        animated: false,
        style: { stroke: "#8A8984", strokeWidth: 2 },
      });
    }
  } else {
    // Fallback to old flow
    const oldFlow = ["story", "image", "video", "composition", "render"];
    for (let i = 0; i < oldFlow.length - 1; i++) {
      const source = oldFlow[i];
      const target = oldFlow[i + 1];
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
  const {
    projectId,
    setProjectId,
    brandData,
    trendData,
    inspirationBrief,
    storyStrategy,
    storyData,
    storyBeats,
    scenes,
    canvasNodes: savedNodes,
    canvasEdges: savedEdges,
    setCanvasNodes,
    setCanvasEdges,
  } = useCanvasStore();

  const { fitView } = useReactFlow();

  // Load state from store or build wizard nodes if empty
  const initialData = useMemo(() => {
    // If we have a dynamic plan from the Director, use it!
    if (savedNodes.length > 0) {
      // Safety check: If we have an invalid project ID in store, clear it so we don't error out on save
      if (projectId && projectId.startsWith("brand-")) {
        console.warn("Found invalid legacy project ID in store. Clearing it.");
        setProjectId(null);
      }
      return { nodes: savedNodes, edges: savedEdges };
    }

    // Fallback: Build the wizard flow (Legacy Logic)
    // ... (Existing logic below remains, but as fallback or I can refactor it out later)
    // For now, I'll keep the existing wizard build logic below but wrap it.

    // REVERT NOTE: I cannot wrap the huge existing logic easily in replace_file_content.
    // Instead, I will use a useEffect to OVERRIDE nodes if savedNodes changes.
    return { nodes: [], edges: [] };
  }, [savedNodes, savedEdges]); // Just a dependency reference, won't use this directly to replace the big block.

  // Build backup wizard nodes (Legacy Support)
  const wizardNodes = useMemo(() => {
    return buildNodesFromState(brandData, trendData, inspirationBrief, storyStrategy, storyData, storyBeats, scenes, savedNodes);
  }, [brandData, trendData, inspirationBrief, storyStrategy, storyData, storyBeats, scenes, savedNodes]);

  const wizardEdges = useMemo(() => {
    return buildEdgesFromNodes(wizardNodes, storyBeats);
  }, [wizardNodes, storyBeats]);

  // Initialize ReactFlow with either Saved Dynamic Graph OR Legacy Wizard Graph
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>(savedNodes.length > 0 ? savedNodes : wizardNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>(savedNodes.length > 0 ? savedEdges : wizardEdges);

  const [isReady, setIsReady] = useState(false);

  // Sync Store -> ReactFlow (One-way binding for Director updates)
  useEffect(() => {
    if (savedNodes.length > 0) {
      console.log("Syncing Canvas from Store:", savedNodes);
      setNodes(savedNodes.map(n => ({
        ...n,
        type: n.type || 'default'
      })));
      setEdges(savedEdges);
      // Removed fitView here to prevent resetting zoom on every update
    }
  }, [savedNodes, savedEdges, setNodes, setEdges]);

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
    const newNodes = buildNodesFromState(brandData, trendData, inspirationBrief, storyStrategy, storyData, storyBeats, scenes, savedNodes);
    const newEdges = buildEdgesFromNodes(newNodes, storyBeats);

    // Only update if nodes changed
    if (JSON.stringify(newNodes.map(n => n.id)) !== JSON.stringify(nodes.map(n => n.id))) {
      setNodes(newNodes);
      setEdges(newEdges);
      setTimeout(() => fitView({ padding: 0.3, maxZoom: 1 }), 50);
    }
  }, [brandData, trendData, inspirationBrief, storyStrategy, storyData, storyBeats, scenes]);

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

        // Save to MongoDB if we have a valid project
        const currentProjectId = useCanvasStore.getState().projectId;
        if (currentProjectId && !currentProjectId.startsWith("brand-")) {
          canvasApi.saveState(currentProjectId, nodeData, edgeData).catch((err) => {
            console.error("Failed to save canvas state:", err);
          });
        } else if (currentProjectId?.startsWith("brand-")) {
          console.warn("Skipping save: Invalid temporary project ID:", currentProjectId);
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
    <>
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


    </>
  );
}

// Wrapper to provide ReactFlow context
import { ReactFlowProvider } from "@xyflow/react";

export default function CanvasFlow() {
  return (
    <div className="h-full w-full">
      <ReactFlowProvider>
        <CanvasFlowInner />
      </ReactFlowProvider>
    </div>
  );
}
