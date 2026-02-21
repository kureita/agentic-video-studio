import { WorkflowNode, WorkflowEdge } from "./workflow-api";

export interface WorkflowTemplate {
    id: string;
    name: string;
    description: string;
    nodes: WorkflowNode[];
    edges: WorkflowEdge[];
}

export const workflowTemplates: WorkflowTemplate[] = [
    // ────────────────────────────────────────────
    // 1. Product Showcase
    // ────────────────────────────────────────────
    {
        id: "product-showcase",
        name: "Product Showcase",
        description: "Promotional video from product description",
        nodes: [
            {
                id: "t1",
                type: "text",
                position: { x: 0, y: 150 },
                data: { text: "Describe your product here — features, benefits, and what makes it unique..." },
            },
            {
                id: "i1",
                type: "imageGen",
                position: { x: 350, y: 0 },
                data: { prompt: "@Text #1", ratio: "16:9" },
            },
            {
                id: "a1",
                type: "audioGen",
                position: { x: 350, y: 300 },
                data: { voice: "Rachel" },
            },
            {
                id: "v1",
                type: "videoGen",
                position: { x: 700, y: 0 },
                data: { ratio: "16:9", duration: "8s" },
            },
            {
                id: "e1",
                type: "editorAgent",
                position: { x: 1050, y: 150 },
                data: {},
            },
        ],
        edges: [
            { id: "e_t1_i1", source: "t1", target: "i1", sourceHandle: "text|text", targetHandle: "text|prompt" },
            { id: "e_t1_a1", source: "t1", target: "a1", sourceHandle: "text|text", targetHandle: "text|text" },
            { id: "e_i1_v1", source: "i1", target: "v1", sourceHandle: "image|image", targetHandle: "image|start_image" },
            { id: "e_t1_v1", source: "t1", target: "v1", sourceHandle: "text|text", targetHandle: "text|text" },
            { id: "e_v1_e1", source: "v1", target: "e1", sourceHandle: "video|video", targetHandle: "video|ref_videos" },
            { id: "e_a1_e1", source: "a1", target: "e1", sourceHandle: "audio|audio", targetHandle: "audio|audio" },
            { id: "e_t1_e1", source: "t1", target: "e1", sourceHandle: "text|text", targetHandle: "text|text" },
        ],
    },

    // ────────────────────────────────────────────
    // 2. Brand Story
    // ────────────────────────────────────────────
    {
        id: "brand-story",
        name: "Brand Story",
        description: "Cinematic narrative from brand analysis",
        nodes: [
            {
                id: "t1",
                type: "text",
                position: { x: 0, y: 80 },
                data: { text: "Enter your brand website URL or describe your brand identity..." },
            },
            {
                id: "vi1",
                type: "vision",
                position: { x: 350, y: 80 },
                data: { instruction: "Analyze this brand and craft a compelling video narrative. Describe the visual style, tone, and key messages." },
            },
            {
                id: "v1",
                type: "videoGen",
                position: { x: 700, y: 0 },
                data: { ratio: "16:9" },
            },
            {
                id: "a1",
                type: "audioGen",
                position: { x: 700, y: 200 },
                data: { voice: "Adam" },
            },
            {
                id: "e1",
                type: "editorAgent",
                position: { x: 1050, y: 80 },
                data: {},
            },
        ],
        edges: [
            { id: "e_t1_vi1", source: "t1", target: "vi1", sourceHandle: "text|text", targetHandle: "text|text" },
            { id: "e_vi1_v1", source: "vi1", target: "v1", sourceHandle: "text|output", targetHandle: "text|text" },
            { id: "e_vi1_a1", source: "vi1", target: "a1", sourceHandle: "text|output", targetHandle: "text|text" },
            { id: "e_v1_e1", source: "v1", target: "e1", sourceHandle: "video|video", targetHandle: "video|ref_videos" },
            { id: "e_a1_e1", source: "a1", target: "e1", sourceHandle: "audio|audio", targetHandle: "audio|audio" },
        ],
    },

    // ────────────────────────────────────────────
    // 3. Short-form Reel
    // ────────────────────────────────────────────
    {
        id: "short-form-reel",
        name: "Short-form Reel",
        description: "Vertical video for social platforms",
        nodes: [
            {
                id: "m1",
                type: "mediaUpload",
                position: { x: 0, y: 0 },
                data: {},
            },
            {
                id: "t1",
                type: "text",
                position: { x: 0, y: 220 },
                data: { text: "Write your reel concept — hook, message, and call to action..." },
            },
            {
                id: "v1",
                type: "videoGen",
                position: { x: 400, y: 0 },
                data: { ratio: "9:16", duration: "5s" },
            },
            {
                id: "a1",
                type: "audioGen",
                position: { x: 400, y: 220 },
                data: { voice: "Bella" },
            },
            {
                id: "e1",
                type: "editorAgent",
                position: { x: 800, y: 110 },
                data: {},
            },
        ],
        edges: [
            { id: "e_m1_v1", source: "m1", target: "v1", sourceHandle: "any|output", targetHandle: "image|start_image" },
            { id: "e_t1_v1", source: "t1", target: "v1", sourceHandle: "text|text", targetHandle: "text|text" },
            { id: "e_t1_a1", source: "t1", target: "a1", sourceHandle: "text|text", targetHandle: "text|text" },
            { id: "e_v1_e1", source: "v1", target: "e1", sourceHandle: "video|video", targetHandle: "video|ref_videos" },
            { id: "e_a1_e1", source: "a1", target: "e1", sourceHandle: "audio|audio", targetHandle: "audio|audio" },
            { id: "e_t1_e1", source: "t1", target: "e1", sourceHandle: "text|text", targetHandle: "text|text" },
        ],
    },
]