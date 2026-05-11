import React, { memo } from "react";
import { NodeProps, useReactFlow } from "@xyflow/react";
import { Music, Loader2, Download, ChevronDown, Volume2, Wand2, AudioWaveform, Clock } from "lucide-react";
import { NodeWrapper } from "@/components/workflow/node-wrapper";
import { HighlightedTextarea } from "@/components/workflow/nodes/highlighted-textarea";
import { usePresignedUrl } from "@/lib/use-presigned-url";
import { useWorkflowStore } from "@/lib/workflow-store";
import { useModels } from "@/lib/use-models";
import { useEstimatedCost } from "@/lib/use-estimated-cost";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";
import { getNodeReferenceLabel, getNodeReferenceLabelById } from "@/lib/node-references";

type AudioType = "voice_design" | "voice_clone" | "music" | "sfx";

// Map audioType → registry category
const AUDIO_TYPE_TO_CATEGORY: Record<AudioType, string> = {
    voice_design: "voice_design",
    voice_clone: "voice_clone",
    music: "music",
    sfx: "sfx",
};

const AUDIO_TYPE_OPTIONS: { value: AudioType; label: string; icon: React.ReactNode; description: string }[] = [
    { value: "voice_design", label: "Voice Design", icon: <Wand2 className="w-3 h-3" />, description: "Create a voice from a description" },
    { value: "voice_clone", label: "Instant Clone", icon: <AudioWaveform className="w-3 h-3" />, description: "Clone from an audio sample" },
    { value: "music", label: "Music", icon: <Music className="w-3 h-3" />, description: "Generate music from a description" },
    { value: "sfx", label: "Sound FX", icon: <Volume2 className="w-3 h-3" />, description: "Generate sound effects" },
];

const PLACEHOLDER_MAP: Record<AudioType, string> = {
    voice_design: "Describe the voice — age, tone, accent, pacing, texture, personality...",
    voice_clone: "Preview text for the cloned voice...",
    music: "Describe the music — genre, mood, instruments, tempo, structure...",
    sfx: "Describe the sound effect — whoosh, impact, ambience, foley...",
};

const isAudioType = (value: string): value is AudioType =>
    value === "voice_design" || value === "voice_clone" || value === "music" || value === "sfx";

export const AudioGenNode = memo(({ id, selected, data }: NodeProps) => {
    const { deleteElements, updateNodeData } = useReactFlow();
    const { runNode, clearNodeOutput, outputs, runningNodeId, setNodes } = useWorkflowStore();
    const { models } = useModels();

    // Filter audio models by current audioType's category. Legacy voiceover
    // nodes now fall back to Voice Design.
    const rawAudioType = typeof data.audioType === "string" ? data.audioType : "";
    const audioType: AudioType = isAudioType(rawAudioType) ? rawAudioType : "voice_design";
    const category = AUDIO_TYPE_TO_CATEGORY[audioType];
    const audioModels = React.useMemo(
        () => models.filter(m => m.type === "audio" && m.category === category && !m.coming_soon),
        [models, category]
    );
    const comingSoonModels = React.useMemo(
        () => models.filter(m => m.type === "audio" && m.category === category && m.coming_soon),
        [models, category]
    );
    const currentModelId = typeof data.model === 'string'
        ? data.model
        : (audioModels.length > 0 ? audioModels[0].id : "");
    const currentModelEntry = audioModels.find(m => m.id === currentModelId) || audioModels.find(m => m.name === currentModelId);
    const currentModelDisplayName = currentModelEntry?.name || currentModelId;

    // Keep selected model aligned with current audio type/category.
    React.useEffect(() => {
        if (audioModels.length > 0 && !currentModelEntry) {
            const fallbackModelId = audioModels[0].id;
            const state = useWorkflowStore.getState();
            const targetNode = state.nodes.find((node) => node.id === id);
            const storedModel = targetNode?.data?.model;
            if (storedModel !== fallbackModelId) {
                setNodes(
                    state.nodes.map((node) =>
                        node.id === id
                            ? { ...node, data: { ...node.data, model: fallbackModelId } }
                            : node
                    )
                );
            }
            updateNodeData(id, { model: fallbackModelId });
        }
    }, [audioModels, currentModelEntry, id, updateNodeData, setNodes]);

    const isRunning = runningNodeId === id;
    const rawOutput = (outputs[id] as string | undefined) || (data.output as string | undefined);

    // Get presigned URL for S3 audio assets
    const { url: presignedOutput } = usePresignedUrl(rawOutput);
    const output = presignedOutput || rawOutput;
    
    // Voice ID from voice design / voice clone output
    const voiceId = (outputs[`${id}__voice_id`] as string | undefined) || undefined;


    const handleDownload = () => {
        if (output) {
            const link = document.createElement('a');
            link.href = output;
            link.download = `generated-${audioType}-${Date.now()}.mp3`;
            link.target = '_blank';
            link.click();
        }
    };

    const textareaRef = React.useRef<HTMLTextAreaElement>(null);
    const [showSuggestions, setShowSuggestions] = React.useState(false);
    const [filterText, setFilterText] = React.useState("");

    const [showTypeMenu, setShowTypeMenu] = React.useState(false);
    const [showModelMenu, setShowModelMenu] = React.useState(false);

    const typeMenuRef = React.useRef<HTMLDivElement>(null);
    const modelMenuRef = React.useRef<HTMLDivElement>(null);

    React.useEffect(() => {
        const handleClickOutside = (e: MouseEvent) => {
            if (typeMenuRef.current && !typeMenuRef.current.contains(e.target as Node)) {
                setShowTypeMenu(false);
            }
            if (modelMenuRef.current && !modelMenuRef.current.contains(e.target as Node)) {
                setShowModelMenu(false);
            }
        };
        if (showTypeMenu || showModelMenu) {
            document.addEventListener('mousedown', handleClickOutside);
            return () => document.removeEventListener('mousedown', handleClickOutside);
        }
    }, [showTypeMenu, showModelMenu]);

    // Get only connected text nodes for suggestions
    const nodes = useWorkflowStore((state) => state.nodes);
    const edges = useWorkflowStore((state) => state.edges);
    const connectedTextNodeIds = React.useMemo(() => new Set(
        edges.filter(e => e.target === id).map(e => e.source)
    ), [edges, id]);
    const allTextNodes = React.useMemo(() =>
        nodes.filter(n => n.type === 'text').map((n) => ({ id: n.id, label: getNodeReferenceLabel(n), content: (n.data.text as string) || "" })),
        [nodes]
    );
    const textNodes = React.useMemo(() =>
        allTextNodes.filter(n => connectedTextNodeIds.has(n.id)),
        [allTextNodes, connectedTextNodeIds]
    );

    const handleTextChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
        const val = e.target.value;
        const cursor = e.target.selectionStart;

        updateNodeData(id, { prompt: val });

        const textBeforeCursor = val.slice(0, cursor);
        const lastAt = textBeforeCursor.lastIndexOf('@');

        if (lastAt !== -1) {
            const textAfterAt = textBeforeCursor.slice(lastAt + 1);
            if (!textAfterAt.includes('\n') && !textAfterAt.includes(' ') && textAfterAt.length < 20) {
                setShowSuggestions(true);
                setFilterText(textAfterAt.toLowerCase());
                return;
            }
        }
        setShowSuggestions(false);
    };

    const handlePreviewTextChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
        updateNodeData(id, { previewText: e.target.value.slice(0, 500) });
    };

    const insertSuggestion = (label: string) => {
        const val = (typeof data.prompt === 'string' ? data.prompt : '');
        const cursor = textareaRef.current?.selectionStart || val.length;

        const textBeforeCursor = val.slice(0, cursor);
        const lastAt = textBeforeCursor.lastIndexOf('@');

        if (lastAt !== -1) {
            const newVal = val.slice(0, lastAt) + `@${label} ` + val.slice(cursor);
            updateNodeData(id, { prompt: newVal });
            setShowSuggestions(false);

            setTimeout(() => {
                if (textareaRef.current) {
                    textareaRef.current.focus();
                    const newCursor = lastAt + label.length + 2;
                    textareaRef.current.setSelectionRange(newCursor, newCursor);
                }
            }, 0);
        }
    };

    const currentTypeOption = AUDIO_TYPE_OPTIONS.find(o => o.value === audioType) || AUDIO_TYPE_OPTIONS[0];
    const durationValue = typeof data.duration === "number"
        ? String(data.duration)
        : typeof data.duration === "string"
            ? data.duration.replace(/s$/i, "")
            : "";
    const durationHint = audioType === "music" ? "3-600s" : "0.5-22s";
    const durationMin = audioType === "music" ? 3 : 0.5;
    const durationMax = audioType === "music" ? 600 : 22;
    const durationStep = audioType === "music" ? 1 : 0.1;

    const estimatedCost = useEstimatedCost(currentModelId, "audio", {
        duration: parseFloat(durationValue) || undefined,
    });

    return (
        <NodeWrapper
            nodeId={id}
            title={useWorkflowStore((state) => getNodeReferenceLabelById(state.nodes, id) || "Audio Gen #?")}
            icon={<Music className="w-4 h-4" />}
            selected={selected}
            color="bg-orange-500"
            inputs={[
                { id: "prompt", label: audioType === "voice_design" ? "Voice Prompt" : audioType === "voice_clone" ? "Preview Text" : "Text", type: "text", style: { bottom: '20px' } },
                ...(audioType === "voice_design"
                    ? [{ id: "preview_text", label: "Preview Text", type: "text" as const, style: { bottom: '68px' } }]
                    : []),
                ...(audioType === "voice_clone"
                    ? [{ id: "audio", label: "Source Audio", type: "audio" as const, style: { bottom: '68px' } }]
                    : []),
            ]}
            outputs={[{ id: "audio", label: "Audio", type: "audio" }]}
            contentClassName="relative bg-black rounded-[17px]"
            onDelete={() => deleteElements({ nodes: [{ id }] })}
            onRun={() => runNode(id)}
            onClear={output ? () => clearNodeOutput(id) : undefined}
            isRunning={isRunning}
            executionStatus={data.executionStatus as "queued" | "running" | "completed" | "failed" | null}
            executionError={(data.executionError as string | null | undefined) ?? null}
            estimatedCost={estimatedCost}
        >
            <div className="relative bg-muted/30 group/audio transition-all duration-300 ease-in-out w-[320px] rounded-[17px]">

                {/* Top Section: Audio Player */}
                <div className="relative h-[120px] flex items-center justify-center p-4">
                    {output && !isRunning ? (
                        <>
                            <audio
                                src={output}
                                controls
                                className="w-full pointer-events-none select-none"
                                style={{ filter: 'drop-shadow(0 4px 6px rgba(0, 0, 0, 0.3))' }}
                            />

                            {/* Download button */}
                            <button
                                onClick={handleDownload}
                                className="absolute top-3 right-3 w-8 h-8 bg-black/60 backdrop-blur-md border border-white/10 rounded-full flex items-center justify-center text-white/90 hover:bg-black/80 hover:text-white transition-all z-30"
                            >
                                <Download className="w-4 h-4" />
                            </button>

                            {/* Voice ID badge (voice design / voice clone) */}
                            {voiceId && (
                                <button
                                    onClick={() => {
                                        navigator.clipboard.writeText(voiceId);
                                    }}
                                    title={`Voice ID: ${voiceId} (click to copy)`}
                                    className="absolute bottom-2 left-3 right-3 flex items-center gap-1.5 bg-orange-500/15 backdrop-blur-md border border-orange-400/25 rounded-lg px-2.5 py-1.5 text-[10px] text-orange-300 hover:bg-orange-500/25 transition-all z-30 cursor-pointer truncate"
                                >
                                    <Wand2 className="w-3 h-3 flex-shrink-0" />
                                    <span className="font-mono truncate">{voiceId}</span>
                                </button>
                            )}
                        </>
                    ) : isRunning ? (
                        <div className="flex flex-col items-center justify-center text-center">
                            <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center mb-3 text-primary">
                                <Loader2 className="w-6 h-6 animate-spin" />
                            </div>
                            <p className="text-xs font-medium text-muted-foreground">
                                Generating {audioType === "music" ? "music" : audioType === "sfx" ? "sound effect" : audioType === "voice_design" ? "voice design" : "voice clone"}...
                            </p>
                        </div>
                    ) : (
                        <div className="flex items-center justify-center text-muted-foreground/50">
                            {audioType === "music" ? <Music className="w-8 h-8" /> : audioType === "sfx" ? <Volume2 className="w-8 h-8" /> : audioType === "voice_design" ? <Wand2 className="w-8 h-8" /> : <AudioWaveform className="w-8 h-8" />}
                        </div>
                    )}
                </div>

                {/* Divider Line */}
                <div className={cn("h-px bg-gradient-to-r from-transparent via-white/20 to-transparent transition-all duration-300", output ? "opacity-0 group-hover/audio:opacity-100" : "")} />

                {/* Bottom Section: Text Input & Controls */}
                <div className="relative bg-black/20 rounded-b-[17px]">
                    {/* Suggestions Popup */}
                    {showSuggestions && textNodes.length > 0 && (
                        <div className="absolute bottom-full left-4 mb-2 z-50 w-48 bg-popover text-popover-foreground rounded-md border shadow-md overflow-hidden animate-in fade-in zoom-in-95 duration-100">
                            <div className="px-2 py-1.5 text-xs font-semibold text-muted-foreground bg-muted/50 border-b">
                                Suggested Inputs
                            </div>
                            <div className="max-h-[120px] overflow-y-auto p-1">
                                {textNodes
                                    .filter(n => n.label.toLowerCase().includes(filterText) || n.content.toLowerCase().includes(filterText))
                                    .map((node) => (
                                        <button
                                            key={node.id}
                                            className="w-full text-left px-2 py-1.5 text-xs rounded-sm hover:bg-accent hover:text-accent-foreground cursor-pointer flex items-center justify-between group/item"
                                            onClick={() => insertSuggestion(node.label)}
                                        >
                                            <span className="font-medium text-primary">{node.label}</span>
                                            <span className="text-[10px] text-muted-foreground truncate max-w-[80px] opacity-70 group-hover/item:opacity-100">
                                                {node.content.slice(0, 15)}...
                                            </span>
                                        </button>
                                    ))}
                            </div>
                        </div>
                    )}

                    {/* Text Input Layer */}
                    <div className={cn("relative z-10 transition-all duration-300", output ? "opacity-0 group-hover/audio:opacity-100 focus-within:opacity-100" : "")}>
                        <HighlightedTextarea
                            textareaRef={textareaRef}
                            className="w-full min-h-[100px] bg-transparent border-none px-4 pb-2 pt-4 text-sm font-medium placeholder:text-white/50 focus-visible:outline-none resize-none overflow-y-auto leading-relaxed text-white nodrag nowheel pointer-events-auto"
                            placeholder={PLACEHOLDER_MAP[audioType]}
                            value={typeof data.prompt === 'string' ? data.prompt : ''}
                            onChange={handleTextChange}
                            onKeyDown={(e) => e.stopPropagation()}
                        />
                        {audioType === "voice_design" && (
                            <textarea
                                className="w-full h-[72px] bg-white/3 border-t border-white/10 px-4 py-3 text-xs font-medium placeholder:text-white/40 focus-visible:outline-none resize-none overflow-y-auto leading-relaxed text-white nodrag nowheel pointer-events-auto"
                                placeholder="Preview text for this generated voice (max 500 characters)..."
                                value={typeof data.previewText === 'string' ? data.previewText : ''}
                                maxLength={500}
                                onChange={handlePreviewTextChange}
                                onKeyDown={(e) => e.stopPropagation()}
                            />
                        )}
                    </div>

                    {/* Controls Bar */}
                    <div className="relative z-20 px-3 pb-3 flex items-center gap-2 opacity-0 group-hover/audio:opacity-100 focus-within:opacity-100 transition-all duration-300 translate-y-2 group-hover/audio:translate-y-0 focus-within:translate-y-0">
                        {/* Audio Type Selector */}
                        <div className="relative flex-shrink-0" ref={typeMenuRef}>
                            <button
                                onClick={() => {
                                    setShowTypeMenu(!showTypeMenu);
                                    setShowModelMenu(false);
                                }}
                                className={cn(
                                    "flex items-center gap-1.5 h-7 bg-black/40 backdrop-blur-sm border border-white/10 rounded-full px-3 text-white/90 hover:bg-black/60 transition-colors cursor-pointer",
                                    showTypeMenu && "bg-black/80 border-white/20"
                                )}
                            >
                                {currentTypeOption.icon}
                                <span className="text-[10px] font-medium">{currentTypeOption.label}</span>
                                <ChevronDown className="w-2.5 h-2.5 text-white/50 flex-shrink-0" />
                            </button>

                            <AnimatePresence>
                                {showTypeMenu && (
                                    <motion.div
                                        initial={{ opacity: 0, y: 4, scale: 0.96 }}
                                        animate={{ opacity: 1, y: 0, scale: 1 }}
                                        exit={{ opacity: 0, y: 4, scale: 0.96 }}
                                        transition={{ duration: 0.12 }}
                                        className="absolute bottom-full left-0 mb-2 w-48 bg-black/90 backdrop-blur-xl border border-white/10 rounded-xl shadow-2xl overflow-hidden z-50 pointer-events-auto flex flex-col"
                                    >
                                        <div className="px-3 py-2 text-[10px] font-semibold text-white/50 uppercase tracking-wider border-b border-white/10 bg-black/40">
                                            Audio Type
                                        </div>
                                        <div className="flex flex-col p-1 nodrag nowheel">
                                            {AUDIO_TYPE_OPTIONS.map((opt) => (
                                                <button
                                                    key={opt.value}
                                                    onClick={(e) => {
                                                        e.stopPropagation();
                                                        const nextCategory = AUDIO_TYPE_TO_CATEGORY[opt.value];
                                                        const nextModels = models.filter(
                                                            (m) => m.type === "audio" && m.category === nextCategory && !m.coming_soon
                                                        );
                                                        updateNodeData(id, {
                                                            audioType: opt.value,
                                                            model: nextModels.length > 0 ? nextModels[0].id : undefined,
                                                            ...(opt.value === "music" || opt.value === "sfx" ? {} : { duration: undefined }),
                                                        });
                                                        setShowTypeMenu(false);
                                                    }}
                                                    className={cn(
                                                        "w-full text-left px-2.5 py-2 text-[11px] rounded-lg hover:bg-white/10 cursor-pointer flex flex-col gap-0.5 transition-colors",
                                                        audioType === opt.value && "bg-white/15 text-white font-medium"
                                                    )}
                                                >
                                                    <div className="flex items-center gap-1.5">
                                                        <span className={cn(audioType === opt.value ? "text-white" : "text-white/70")}>{opt.icon}</span>
                                                        <span className={cn(audioType !== opt.value && "text-white/80")}>
                                                            {opt.label}
                                                        </span>
                                                    </div>
                                                    <span className="text-[9px] text-white/40 pl-4">{opt.description}</span>
                                                </button>
                                            ))}
                                        </div>
                                    </motion.div>
                                )}
                            </AnimatePresence>
                        </div>

                        {/* Model Selector */}
                        {audioModels.length > 0 && (
                            <div className="relative flex-shrink-0" ref={modelMenuRef}>
                                <button
                                    onClick={() => {
                                        setShowModelMenu(!showModelMenu);
                                        setShowTypeMenu(false);
                                    }}
                                    className={cn(
                                        "flex items-center gap-1.5 h-7 bg-black/40 backdrop-blur-sm border border-white/10 rounded-full px-3 text-white/90 hover:bg-black/60 transition-colors cursor-pointer max-w-[140px]",
                                        showModelMenu && "bg-black/80 border-white/20"
                                    )}
                                >
                                    <span className="text-[10px] font-medium truncate">{currentModelDisplayName}</span>
                                    <ChevronDown className="w-2.5 h-2.5 text-white/50 flex-shrink-0" />
                                </button>

                                <AnimatePresence>
                                    {showModelMenu && (
                                        <motion.div
                                            initial={{ opacity: 0, y: 4, scale: 0.96 }}
                                            animate={{ opacity: 1, y: 0, scale: 1 }}
                                            exit={{ opacity: 0, y: 4, scale: 0.96 }}
                                            transition={{ duration: 0.12 }}
                                            className="absolute bottom-full left-0 mb-2 w-52 bg-black/90 backdrop-blur-xl border border-white/10 rounded-xl shadow-2xl overflow-hidden z-50 pointer-events-auto flex flex-col"
                                        >
                                            <div className="px-3 py-2 text-[10px] font-semibold text-white/50 uppercase tracking-wider border-b border-white/10 bg-black/40">
                                                Model
                                            </div>
                                            <div className="max-h-[200px] overflow-y-auto flex flex-col p-1 nodrag nowheel">
                                                {audioModels.map((m) => (
                                                    <button
                                                        key={m.id}
                                                        onClick={(e) => {
                                                            e.stopPropagation();
                                                            updateNodeData(id, { model: m.id });
                                                            setShowModelMenu(false);
                                                        }}
                                                        className={cn(
                                                            "w-full text-left px-2.5 py-2 text-[11px] rounded-lg hover:bg-white/10 cursor-pointer flex flex-col gap-0.5 transition-colors",
                                                            currentModelId === m.id && "bg-white/15 text-white font-medium"
                                                        )}
                                                    >
                                                        <div className="flex items-center justify-between">
                                                            <span className={cn(currentModelId !== m.id && "text-white/80")}>
                                                                {m.name}
                                                            </span>
                                                            <span className="text-[9px] text-white/40">
                                                                {m.tier === 'premium' ? '★' : m.tier === 'mid' ? '◆' : '○'}
                                                            </span>
                                                        </div>
                                                        <span className="text-[9px] text-white/40">{m.provider}</span>
                                                    </button>
                                                ))}
                                                {comingSoonModels.map((m) => (
                                                    <div
                                                        key={m.id}
                                                        className="w-full text-left px-2.5 py-2 text-[11px] rounded-lg opacity-40 cursor-not-allowed flex flex-col gap-0.5"
                                                    >
                                                        <div className="flex items-center justify-between">
                                                            <span className="text-white/50">{m.name}</span>
                                                            <span className="text-[8px] text-white/30 uppercase">Soon</span>
                                                        </div>
                                                        <span className="text-[9px] text-white/30">{m.provider}</span>
                                                    </div>
                                                ))}
                                            </div>
                                        </motion.div>
                                    )}
                                </AnimatePresence>
                            </div>
                        )}
                        {audioModels.length === 0 && (
                            <div className="flex items-center h-7 bg-black/30 border border-white/10 rounded-full px-3 text-[10px] text-white/45">
                                No model
                            </div>
                        )}

                        {/* Duration input (optional for music/SFX; blank lets fal infer from prompt) */}
                        {(audioType === "music" || audioType === "sfx") && (
                            <div className="flex items-center gap-1.5 h-7 bg-black/40 backdrop-blur-sm border border-white/10 rounded-full px-3 text-white/90 hover:bg-black/60 transition-colors focus-within:bg-black/80 focus-within:border-white/20">
                                <Clock className="w-3 h-3 text-white/70 flex-shrink-0" />
                                <input
                                    type="number"
                                    min={durationMin}
                                    max={durationMax}
                                    step={durationStep}
                                    placeholder="auto"
                                    value={durationValue}
                                    onChange={(e) => updateNodeData(id, { duration: e.target.value })}
                                    onKeyDown={(e) => e.stopPropagation()}
                                    className="w-10 bg-transparent text-[10px] font-medium text-white placeholder:text-white/40 focus:outline-none nodrag nowheel [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                                />
                                <span className="text-[10px] font-medium text-white/55">s</span>
                                <span className="text-[9px] text-white/35 hidden min-[430px]:inline">{durationHint}</span>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </NodeWrapper>
    );
});

AudioGenNode.displayName = "AudioGenNode";
