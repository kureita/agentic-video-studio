import { WorkflowNode, WorkflowEdge } from "./workflow-api";

export interface WorkflowInspiration {
    id: string;
    name: string;
    description: string;
    /** Research-backed insight shown as a tooltip/badge */
    insight?: string;
    /** Recommended video duration in seconds */
    duration?: number;
    /** Aspect ratio for the video */
    ratio?: string;
    nodes: WorkflowNode[];
    edges: WorkflowEdge[];
}

/** @deprecated Use WorkflowInspiration instead */
export type WorkflowTemplate = WorkflowInspiration;

export const workflowInspirations: WorkflowInspiration[] = [
    // ────────────────────────────────────────────
    // 1. Viral Authentic Reel (Replacing Product Glow-Up)
    //
    //    Pipeline: Character & Product Prompts → Base Images → Scene Images (with Refs) → Videos → Compositor
    //
    //    Philosophy: We focus on viral authenticity: "beautiful absurdity" or relatable imperfect visuals.
    //    Consistency is maintained by generating the character and product first, then referencing them in scene images.
    //    Editor simply stitches and adds motion graphics without creative interference.
    // ────────────────────────────────────────────
    {
        id: "product-glow-up",
        name: "Viral Authentic Reel",
        description: "Viral format built for authenticity. Generates consistent character and product first, then animates into a relatable, stop-scroll flow.",
        insight: "Base Images → Scene Images → Videos → Compositor · 15s · 9:16",
        duration: 15,
        ratio: "9:16",
        nodes: [
            // ═══════════════════════════════════
            {
                id: "t1",
                type: "text",
                position: { x: 0, y: 100 },
                data: {
                    text: "Base Character: Close-up smartphone selfie shot of a relatable 22-year-old woman in a slightly messy bathroom. She has visible, inflamed cystic acne on her lower cheeks and chin, featuring red, textured blemishes. Lighting is harsh, natural bathroom lighting, emphasizing the uneven skin texture and redness. Unfiltered, candid, raw aesthetic, capturing genuine frustration. Dressed in a loose grey t-shirt."
                },
            },
            {
                id: "t_product",
                type: "text",
                position: { x: 0, y: 300 },
                data: {
                    text: "Base Product: A small, clinical-looking translucent green glass dropper bottle containing an anti-acne serum. The label is minimalist white with bold black typography reading 'BHA+ Zinc Clarity'. The bottle is resting on a wet bathroom sink edge next to a white ceramic soap dish. Soft, diffused lighting highlighting the medical-grade, effective aesthetic of the bottle."
                },
            },
            {
                id: "c_img",
                type: "imageGen",
                position: { x: 400, y: 100 },
                data: {
                    prompt: "@Text #1",
                    ratio: "9:16",
                },
            },
            {
                id: "p_img",
                type: "imageGen",
                position: { x: 400, y: 300 },
                data: {
                    prompt: "@Text #2",
                    ratio: "9:16",
                },
            },

            // ═══════════════════════════════════
            // SCENE TEXT PROMPTS
            // ═══════════════════════════════════
            {
                id: "t2",
                type: "text",
                position: { x: 0, y: 500 },
                data: {
                    text: "Hook (0-3s): Extreme close-up shot, smartphone style. The character is aggressively poking at a particularly red, painful pimple on her jawline while looking into the bathroom mirror. Her expression is pure annoyance and exasperation. The vibe is a visceral 'we've all been there' moment of skin-picking desperation."
                },
            },
            {
                id: "t3",
                type: "text",
                position: { x: 0, y: 900 },
                data: {
                    text: "Pain / Solution (3-8s): Eye-level angle. The character is carefully applying a single drop of the green 'BHA+ Zinc Clarity' serum directly onto the inflamed pimple using the glass dropper. Her expression shifts from frustrated to focused and hopeful. The serum gleams slightly on the skin. Natural, unfiltered lighting."
                },
            },
            {
                id: "t4",
                type: "text",
                position: { x: 0, y: 1300 },
                data: {
                    text: "Transformation (8-15s): Same character, same bathroom, but shot 7 days later. Her skin is visibly calmer, the redness drastically reduced, and the large pimple is flattened and fading into a minor hyperpigmentation mark. She is touching her cheek gently, looking directly at the camera with a genuine, relieved, and subtly confident smile. The lighting feels slightly warmer and softer, representing the 'after' state."
                },
            },

            // ═══════════════════════════════════
            // IMAGE GENERATION LAYER (Referencing Character & Product)
            // ═══════════════════════════════════
            {
                id: "i1",
                type: "imageGen",
                position: { x: 800, y: 500 },
                data: {
                    prompt: "@Text #3",
                    ratio: "9:16",
                },
            },
            {
                id: "i2",
                type: "imageGen",
                position: { x: 800, y: 900 },
                data: {
                    prompt: "@Text #4",
                    ratio: "9:16",
                },
            },
            {
                id: "i3",
                type: "imageGen",
                position: { x: 800, y: 1300 },
                data: {
                    prompt: "@Text #5",
                    ratio: "9:16",
                },
            },

            // ═══════════════════════════════════
            // VIDEO GENERATION LAYER
            // ═══════════════════════════════════
            {
                id: "v1",
                type: "videoGen",
                position: { x: 1200, y: 500 },
                data: {
                    ratio: "9:16",
                    duration: "4s",
                    prompt: "Visceral, frantic handheld smartphone movement pushing into an extreme close-up of a red, inflamed pimple on a jawline. The character's finger prods the bump twice in frustration. Raw, unpolished motion.",
                },
            },
            {
                id: "v2",
                type: "videoGen",
                position: { x: 1200, y: 900 },
                data: {
                    ratio: "9:16",
                    duration: "4s",
                    prompt: "Slow, deliberate handheld motion. A glass dropper dispenses a single drop of clear green serum onto a red pimple. The drop rolls slightly down the cheek. The character's face relaxes. Intimate, focused.",
                },
            },
            {
                id: "v3",
                type: "videoGen",
                position: { x: 1200, y: 1300 },
                data: {
                    ratio: "9:16",
                    duration: "6s",
                    prompt: "Smooth, gentle camera pan across a calmer, clearer cheek. The character turns to the lens, breaking out into a relieved, authentic smile. Her hand brushes away a loose strand of hair. Warm, satisfying.",
                },
            },

            // ═══════════════════════════════════
            // AUDIO
            // ═══════════════════════════════════
            {
                id: "a1",
                type: "audioGen",
                position: { x: 1200, y: 1800 },
                data: {
                    voice: "Bella",
                },
            },

            // ═══════════════════════════════════
            // FINAL COMPOSITOR
            // ═══════════════════════════════════
            {
                id: "final",
                type: "editorAgent",
                position: { x: 1800, y: 900 },
                data: {
                    instruction: `FINAL COMPOSITOR — Stitch the 3 video segments sequentially.
1. Hook (0-3s): Video 1. Add bold text overlay: 'Me fighting my hormonal acne for the 100th time this month 😭'.
2. Solution (3-8s): Video 2. Add subtle lower-third text: 'Finally trying the BHA+ Zinc serum everyone is talking about.'
3. Transformation (8-15s): Video 3. Add dynamic text overlay: 'Wait... 7 days later?! My skin has never felt this calm.'
Layer the Audio. Use a snappy 0.1s cut between scenes, no long fades. Ensure raw, UGC (User Generated Content) feel.`,
                },
            },
        ],
        edges: [
            // Base Character & Product Flow
            { id: "e_t1_c", source: "t1", target: "c_img", sourceHandle: "text|text", targetHandle: "text|prompt" },
            { id: "e_tp_p", source: "t_product", target: "p_img", sourceHandle: "text|text", targetHandle: "text|prompt" },

            // Character Reference to Scenes
            { id: "e_c_i1", source: "c_img", target: "i1", sourceHandle: "image|image", targetHandle: "image|image" },
            { id: "e_c_i2", source: "c_img", target: "i2", sourceHandle: "image|image", targetHandle: "image|image" },
            { id: "e_c_i3", source: "c_img", target: "i3", sourceHandle: "image|image", targetHandle: "image|image" },

            // Product Reference to Scenes
            { id: "e_p_i1", source: "p_img", target: "i1", sourceHandle: "image|image", targetHandle: "image|image" },
            { id: "e_p_i2", source: "p_img", target: "i2", sourceHandle: "image|image", targetHandle: "image|image" },
            { id: "e_p_i3", source: "p_img", target: "i3", sourceHandle: "image|image", targetHandle: "image|image" },

            // Text to Images
            { id: "e_t2_i1", source: "t2", target: "i1", sourceHandle: "text|text", targetHandle: "text|prompt" },
            { id: "e_t3_i2", source: "t3", target: "i2", sourceHandle: "text|text", targetHandle: "text|prompt" },
            { id: "e_t4_i3", source: "t4", target: "i3", sourceHandle: "text|text", targetHandle: "text|prompt" },

            // Images to Videos
            { id: "e_i1_v1", source: "i1", target: "v1", sourceHandle: "image|image", targetHandle: "image|start_image" },
            { id: "e_i2_v2", source: "i2", target: "v2", sourceHandle: "image|image", targetHandle: "image|start_image" },
            { id: "e_i3_v3", source: "i3", target: "v3", sourceHandle: "image|image", targetHandle: "image|start_image" },

            // Videos and Audio to Compositor
            { id: "e_v1_final", source: "v1", target: "final", sourceHandle: "video|video", targetHandle: "video|ref_videos" },
            { id: "e_v2_final", source: "v2", target: "final", sourceHandle: "video|video", targetHandle: "video|ref_videos" },
            { id: "e_v3_final", source: "v3", target: "final", sourceHandle: "video|video", targetHandle: "video|ref_videos" },
            { id: "e_a1_final", source: "a1", target: "final", sourceHandle: "audio|audio", targetHandle: "audio|audio" },
        ],
    },

    // ────────────────────────────────────────────
    // 2. Product Showcase (updated descriptions)
    // ────────────────────────────────────────────
    {
        id: "product-showcase",
        name: "Product Showcase",
        description: "AI-generated video from a text description. Great for quick product demos.",
        insight: "40% higher completion with bold text overlays",
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
                data: { ratio: "16:9", duration: "8s", prompt: "Create a cinematic product showcase video. Smooth camera movement, professional lighting, aspirational quality. Based on: @Text #1" },
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
    // 3. Brand Story (updated)
    // ────────────────────────────────────────────
    {
        id: "brand-story",
        name: "Brand Story",
        description: "Cinematic brand narrative. Ideal for about-us content.",
        insight: "35% higher retention when faces appear in first 3s",
        nodes: [
            {
                id: "t1",
                type: "text",
                position: { x: 0, y: 80 },
                data: { text: "Brand Story Script: Describe the visual style, tone, and key messages. Cinematic brand narrative, emotional storytelling." },
            },
            {
                id: "v1",
                type: "videoGen",
                position: { x: 350, y: 0 },
                data: { ratio: "16:9", duration: "8s", prompt: "@Text #1" },
            },
            {
                id: "a1",
                type: "audioGen",
                position: { x: 350, y: 200 },
                data: { voice: "Adam" },
            },
            {
                id: "e1",
                type: "editorAgent",
                position: { x: 700, y: 80 },
                data: { instruction: "Combine video and audio smoothly. Do not run any creative loops." },
            },
        ],
        edges: [
            { id: "e_t1_v1", source: "t1", target: "v1", sourceHandle: "text|text", targetHandle: "text|text" },
            { id: "e_t1_a1", source: "t1", target: "a1", sourceHandle: "text|text", targetHandle: "text|text" },
            { id: "e_v1_e1", source: "v1", target: "e1", sourceHandle: "video|video", targetHandle: "video|ref_videos" },
            { id: "e_a1_e1", source: "a1", target: "e1", sourceHandle: "audio|audio", targetHandle: "audio|audio" },
        ],
    },

    // ────────────────────────────────────────────
    // 4. Short-form Reel (updated descriptions)
    // ────────────────────────────────────────────
    {
        id: "short-form-reel",
        name: "Short-form Reel",
        description: "Vertical video for TikTok, Reels, and Shorts. Upload media or start from scratch.",
        insight: "77% of consumers trust UGC-style content more",
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
                data: { ratio: "9:16", duration: "5s", prompt: "Short-form vertical video. Energetic motion, vibrant colors, scroll-stopping movement. Based on: @Text #1" },
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
];

/** @deprecated Use workflowInspirations instead */
export const workflowTemplates = workflowInspirations;