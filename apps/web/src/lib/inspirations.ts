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
1. Hook (0-3s): Video 1. Add bold text overlay: 'Me fighting my hormonal acne for the 100th time this month.'
2. Solution (3-8s): Video 2. Add subtle lower-third text: 'Finally trying the BHA+ Zinc serum everyone is talking about.'
3. Transformation (8-15s): Video 3. Add dynamic text overlay: 'Wait. 7 days later. My skin has never felt this calm.'
Layer the Audio. Use a snappy 0.1s cut between scenes, no long fades. Ensure raw, UGC (User Generated Content) feel. NO emojis in any text.`,
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

    // ────────────────────────────────────────────
    // 5. Cinematic Product Promo (Nike Pegasus-inspired)
    //
    //    Full production pipeline: Style Frame Images → Scene Videos → Audio Layers → Editor Compositor
    //
    //    Philosophy: A complete, cinematic approach to product promos with multiple style frames
    //    anchoring visual consistency, scene-by-scene video generation with reference images,
    //    layered audio design (ambient, score, fanfare, SFX), and a detailed Remotion compositor
    //    with frame-accurate timeline, text overlays, effects, and audio mixing.
    // ────────────────────────────────────────────
    {
        id: "cinematic-product-promo",
        name: "Cinematic Product Promo",
        description: "Full production pipeline for cinematic product videos. Style frames anchor visual consistency across 6 scenes with layered audio design and frame-accurate editing.",
        insight: "Style Frames → Scene Videos → Audio Layers → Compositor · 15s · 9:16",
        duration: 15,
        ratio: "9:16",
        nodes: [
            // ═══════════════════════════════════
            // TEXT PROMPTS — Image Descriptions
            // ═══════════════════════════════════
            {
                id: "t_hero",
                type: "text",
                position: { x: 0, y: 0 },
                data: {
                    text: "Product photography, Nike Pegasus running shoe, matte gray and volt neon green colorway, three-quarter angle, sitting upright on raw concrete surface. Harsh directional sunlight from upper left, sharp cast shadow. Shallow depth of field, background falls to smooth bokeh. Clean minimal composition, no props, no people. Commercial editorial style, high detail, photorealistic. Vertical 9:16 frame.",
                },
            },
            {
                id: "t_street",
                type: "text",
                position: { x: 0, y: 400 },
                data: {
                    text: "Empty city sidewalk, early morning golden hour. Wet concrete pavement with subtle reflections. Blurred pedestrians and storefronts in the background at f/1.8 depth of field. Desaturated cinematic color grading, lifted blacks, warm highlight tones. Wide establishing composition, low angle close to ground level. Urban street photography. No text, no logos. Vertical 9:16 frame.",
                },
            },
            {
                id: "t_finish",
                type: "text",
                position: { x: 0, y: 800 },
                data: {
                    text: "Marathon finish line, red and white tape stretched across an empty city road. Morning light, golden hour flare from behind. Confetti frozen mid-air. Crowd silhouettes in soft focus background, out of focus bokeh lights. Low angle hero shot looking slightly upward. Cinematic sports photography, triumphant atmosphere. Desaturated color palette with warm highlights. No people in foreground. Vertical 9:16 frame.",
                },
            },
            {
                id: "t_endcard",
                type: "text",
                position: { x: 0, y: 1200 },
                data: {
                    text: "Minimal graphic design layout on solid black background. Clean white sans-serif typography centered in frame. Upper text area at 40% height, logo area at 70% height. Pure black and white only, no color, no gradients. Editorial typography poster style. High contrast. Vertical 9:16 frame.",
                },
            },

            // ═══════════════════════════════════
            // IMAGE GENERATION — Style Frames
            // ═══════════════════════════════════
            {
                id: "img_hero",
                type: "imageGen",
                position: { x: 500, y: 0 },
                data: {
                    prompt: "@Text #1",
                    ratio: "9:16",
                },
            },
            {
                id: "img_street",
                type: "imageGen",
                position: { x: 500, y: 400 },
                data: {
                    prompt: "@Text #2",
                    ratio: "9:16",
                },
            },
            {
                id: "img_finish",
                type: "imageGen",
                position: { x: 500, y: 800 },
                data: {
                    prompt: "@Text #3",
                    ratio: "9:16",
                },
            },
            {
                id: "img_endcard",
                type: "imageGen",
                position: { x: 500, y: 1200 },
                data: {
                    prompt: "@Text #4",
                    ratio: "9:16",
                },
            },

            // ═══════════════════════════════════
            // VIDEO GENERATION — Scene Clips
            // ═══════════════════════════════════
            {
                id: "vid_hook",
                type: "videoGen",
                position: { x: 1000, y: 0 },
                data: {
                    ratio: "9:16",
                    duration: "3s",
                    prompt: "Using the provided shoe reference image and street environment reference image: A single Nike running shoe sitting upright, alone on a concrete city sidewalk. Match the exact shoe colorway and design from the hero reference. Early morning golden hour light matching the street environment reference. Slow cinematic push-in camera move toward the shoe. Shallow depth of field, urban environment softly blurred behind. The shoe is completely still. No people visible, no movement except camera. Quiet, contemplative mood. Commercial film quality, desaturated color grading, lifted blacks. 9:16 vertical, 3 seconds.",
                },
            },
            {
                id: "vid_tap",
                type: "videoGen",
                position: { x: 1000, y: 400 },
                data: {
                    ratio: "9:16",
                    duration: "4s",
                    prompt: "Using the provided shoe reference image — match the exact shoe design, colorway, and texture: Close-up of the same Nike running shoe on concrete. The shoe begins tapping its toe impatiently, as if a foot is inside but there is no foot, the shoe moves on its own. The shoelace slowly rises upward and sways like a living tentacle, searching the air. Slightly unnatural physics, the movement is organic but wrong. Low angle shot, shallow depth of field. Cinematic lighting, morning sun. 9:16 vertical, 4 seconds.",
                },
            },
            {
                id: "vid_run",
                type: "videoGen",
                position: { x: 1000, y: 800 },
                data: {
                    ratio: "9:16",
                    duration: "5s",
                    prompt: "Using the provided shoe reference image and street environment reference image — maintain visual consistency with both references: The same Nike running shoe from the reference lifts itself off the ground and begins running down the city sidewalk from the environment reference, entirely on its own, no foot inside. The shoe wobbles, stumbles, and has terrible running form, bouncing unevenly and flopping side to side. Comedic and absurd motion. Side-angle tracking shot following the shoe at shoe-level. Slight motion blur. Golden hour morning light, shallow depth of field. 9:16 vertical, 5 seconds.",
                },
            },
            {
                id: "vid_sprint",
                type: "videoGen",
                position: { x: 1000, y: 1200 },
                data: {
                    ratio: "9:16",
                    duration: "6s",
                    prompt: "Using the provided shoe reference image and street environment reference image — the shoe must match the reference exactly: The same Nike running shoe from the reference sprinting at high speed down the busy city sidewalk from the environment reference, weaving between the legs of pedestrians. The pedestrians look down confused and startled. Dynamic low-angle tracking shot, camera close to the ground. Heavy motion blur on background, shoe stays sharp. Action movie energy, fast and kinetic. Warm golden light, cinematic film grain. 9:16 vertical, 6 seconds.",
                },
            },
            {
                id: "vid_finish",
                type: "videoGen",
                position: { x: 1000, y: 1600 },
                data: {
                    ratio: "9:16",
                    duration: "5s",
                    prompt: "Using the provided shoe reference image and finish line environment reference image — match the shoe design from reference and the finish line setting from the environment reference: The same Nike running shoe breaking through the marathon finish line tape, crossing the line triumphantly by itself, no runner. Slow motion. Confetti explodes from above. A gold medal drops from the sky and lands on top of the shoe. Low angle hero shot looking up, dramatic backlighting with golden lens flare. Crowd silhouettes cheering in soft focus. Epic cinematic sports photography. 9:16 vertical, 5 seconds.",
                },
            },
            {
                id: "vid_endcard",
                type: "videoGen",
                position: { x: 1000, y: 2000 },
                data: {
                    ratio: "9:16",
                    duration: "3s",
                    prompt: "Using the provided end card reference image as the visual base: Slow, subtle particle dust floating in a beam of light against the pure black background from the reference. Maintain the minimal graphic layout. Almost invisible movement. Tiny white and gold specks drifting downward very slowly. Cinematic, elegant, quiet. 9:16 vertical, 3 seconds.",
                },
            },

            // ═══════════════════════════════════
            // AUDIO GENERATION
            // ═══════════════════════════════════
            {
                id: "aud_ambient",
                type: "audioGen",
                position: { x: 1000, y: 2500 },
                data: {
                    audioType: "sfx",
                    duration: 15,
                    prompt: "Quiet early morning city ambience. Distant traffic hum, no horns. Soft bird calls, occasional. Gentle urban atmosphere, realistic field recording style. Subtle and understated. Stereo, warm tone, no wind noise. 15 seconds, seamless loop-friendly.",
                },
            },
            {
                id: "aud_score",
                type: "audioGen",
                position: { x: 1000, y: 2900 },
                data: {
                    audioType: "music",
                    duration: 15,
                    prompt: "Orchestral comedic underscore. Starts with quiet plucked pizzicato strings creating mischief and curiosity. Playful woodwind accents join at 3 seconds. Energy builds progressively, adding snare rolls and brass stabs. By 8 seconds full chaotic energy, fast-paced and kinetic, like an action comedy chase. Whimsical but cinematic. Ends abruptly at 12 seconds on a hard stop. Orchestral only. 12 seconds.",
                },
            },
            {
                id: "aud_fanfare",
                type: "audioGen",
                position: { x: 1000, y: 3300 },
                data: {
                    audioType: "music",
                    duration: 10,
                    prompt: "Short epic orchestral victory fanfare. Bright brass section playing a triumphant 4-note ascending melody. Timpani hit on the downbeat. Cymbal crash. Heroic but slightly over-the-top. Punchy, loud, then fading to silence. Orchestral only. 4 seconds.",
                },
            },
            {
                id: "aud_swoosh",
                type: "audioGen",
                position: { x: 1000, y: 3700 },
                data: {
                    audioType: "sfx",
                    duration: 10,
                    prompt: "Clean sharp whoosh cutting through air, left to right pan, followed by a deep subtle bass drop impact. Modern sound design, punchy and tight. Cinematic trailer style. 1.5 seconds total.",
                },
            },

            // ═══════════════════════════════════
            // FINAL COMPOSITOR
            // ═══════════════════════════════════
            {
                id: "final",
                type: "editorAgent",
                position: { x: 1600, y: 1200 },
                data: {
                    instruction: `EDITOR AGENT — CINEMATIC PRODUCT PROMO COMPOSITION

PROJECT CONFIG: 1080×1920 (9:16), 15 seconds, 30fps, 450 frames total.

TIMELINE:

SCENE 1 — HOOK (0:00–0:01, frames 0–30)
Source: VID-01 (shoe on sidewalk). Trim to best 1s, tightest framing.
Audio: Ambient at -12dB, fade in from silence over 10 frames.
Text: "POV: You said you'd go running today" — Inter Bold 44px, white, center X, Y at 16%, drop shadow. Fade in frames 0–8, hold, fade out 25–30.
Transition: Hard cut.

SCENE 2 — IMPATIENT TAP (0:01–0:03, frames 30–90)
Source: VID-02. Best 2s with clear lace movement.
Audio: Ambient at -12dB. Score begins frame 30, fade in 15 frames to -8dB.
Effect: Subtle slow zoom scale 1.00→1.03 over 60 frames.
Transition: Hard cut.

SCENE 3 — SHOE RUNS (0:03–0:06, frames 90–180)
Source: VID-03. Best 3s with visible wobble.
Audio: Score builds -8dB to -6dB. Ambient at -14dB.
Transition: Whip pan blur — 4-frame directional motion blur, left to right.

SCENE 4 — SPRINT THROUGH CROWD (0:06–0:10, frames 180–300)
Source: VID-04. Best 4s with pedestrian reactions.
Audio: Score at peak -4dB. Ambient fades out by frame 200.
Speed ramp: Frames 180–220 at 80% speed, then accelerate to 120%.
Flash frames: 1-frame white at 40% opacity at frames 230, 260, 285.
Effect: Slight handheld shake — 2px random X/Y offset.
Transition: Impact zoom scale 1.0→1.12 over 2 frames.

SCENE 5 — FINISH LINE (0:10–0:13, frames 300–390)
Source: VID-05. Segment with tape-break and confetti.
Audio: Score hard-stop frame 300. Fanfare at -2dB.
Effect: Anamorphic lens flare sweep left to right, warm tone.
Transition: Fade to black over 15 frames (375–390).

SCENE 6 — END CARD (0:13–0:15, frames 390–450)
Source: VID-06 as background at 60% opacity over black.
Audio: Fanfare fading out. Swoosh SFX triggers frame 420 at -3dB.
Text 1: "Your shoes have more discipline than you." — Inter Medium 34px, white, center, Y 40%. Fade in 390–405.
Text 2: "Nike Pegasus" — Inter Light 22px, #999999, center, Y 53%. Fade in 405–418.
Logo: Swoosh SVG, white, 56px wide, center, Y 68%. Scale in 418–428 with slight overshoot bounce.

POST-PROCESSING: 15% desaturation, lifted blacks, warm highlights, 1.05 contrast. Film grain 2.5% opacity. Subtle vignette 12%.
SAFE ZONES: Top 10%, bottom 15%, sides 5%.
EXPORT: H.264 Main, 8Mbps CBR, AAC-LC 192kbps stereo, 30fps constant.`,
                },
            },
        ],
        edges: [
            // Text → Images
            { id: "e_th_ih", source: "t_hero", target: "img_hero", sourceHandle: "text|text", targetHandle: "text|prompt" },
            { id: "e_ts_is", source: "t_street", target: "img_street", sourceHandle: "text|text", targetHandle: "text|prompt" },
            { id: "e_tf_if", source: "t_finish", target: "img_finish", sourceHandle: "text|text", targetHandle: "text|prompt" },
            { id: "e_te_ie", source: "t_endcard", target: "img_endcard", sourceHandle: "text|text", targetHandle: "text|prompt" },

            // Hero image → multiple video scenes (visual consistency anchor)
            { id: "e_ih_v1", source: "img_hero", target: "vid_hook", sourceHandle: "image|image", targetHandle: "image|start_image" },
            { id: "e_ih_v2", source: "img_hero", target: "vid_tap", sourceHandle: "image|image", targetHandle: "image|start_image" },
            { id: "e_ih_v3", source: "img_hero", target: "vid_run", sourceHandle: "image|image", targetHandle: "image|start_image" },
            { id: "e_ih_v4", source: "img_hero", target: "vid_sprint", sourceHandle: "image|image", targetHandle: "image|start_image" },

            // Street environment → street-based videos
            { id: "e_is_v1", source: "img_street", target: "vid_hook", sourceHandle: "image|image", targetHandle: "image|end_image" },
            { id: "e_is_v3", source: "img_street", target: "vid_run", sourceHandle: "image|image", targetHandle: "image|end_image" },
            { id: "e_is_v4", source: "img_street", target: "vid_sprint", sourceHandle: "image|image", targetHandle: "image|end_image" },

            // Finish line environment → finish video
            { id: "e_if_v5", source: "img_finish", target: "vid_finish", sourceHandle: "image|image", targetHandle: "image|start_image" },

            // End card layout → end card video
            { id: "e_ie_v6", source: "img_endcard", target: "vid_endcard", sourceHandle: "image|image", targetHandle: "image|start_image" },

            // All videos → editor
            { id: "e_v1_f", source: "vid_hook", target: "final", sourceHandle: "video|video", targetHandle: "video|ref_videos" },
            { id: "e_v2_f", source: "vid_tap", target: "final", sourceHandle: "video|video", targetHandle: "video|ref_videos" },
            { id: "e_v3_f", source: "vid_run", target: "final", sourceHandle: "video|video", targetHandle: "video|ref_videos" },
            { id: "e_v4_f", source: "vid_sprint", target: "final", sourceHandle: "video|video", targetHandle: "video|ref_videos" },
            { id: "e_v5_f", source: "vid_finish", target: "final", sourceHandle: "video|video", targetHandle: "video|ref_videos" },
            { id: "e_v6_f", source: "vid_endcard", target: "final", sourceHandle: "video|video", targetHandle: "video|ref_videos" },

            // All audio → editor
            { id: "e_a1_f", source: "aud_ambient", target: "final", sourceHandle: "audio|audio", targetHandle: "audio|audio" },
            { id: "e_a2_f", source: "aud_score", target: "final", sourceHandle: "audio|audio", targetHandle: "audio|audio" },
            { id: "e_a3_f", source: "aud_fanfare", target: "final", sourceHandle: "audio|audio", targetHandle: "audio|audio" },
            { id: "e_a4_f", source: "aud_swoosh", target: "final", sourceHandle: "audio|audio", targetHandle: "audio|audio" },
        ],
    },
];
