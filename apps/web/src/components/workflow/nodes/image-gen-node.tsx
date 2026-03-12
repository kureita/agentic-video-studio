import React, { memo, useState, useRef, useEffect } from "react";
import { NodeProps, useReactFlow } from "@xyflow/react";
import { Image as ImageIcon, ChevronDown, Square, Loader2, Download } from "lucide-react";
import { NodeWrapper } from "@/components/workflow/node-wrapper";
import { HighlightedTextarea } from "@/components/workflow/nodes/highlighted-textarea";
import { S3Image } from "@/components/ui/s3-image";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";

import { useWorkflowStore } from "@/lib/workflow-store";
import { useModels } from "@/lib/use-models";

const DEFAULT_INPUTS: { id: string, label: string, type: "text" | "image" | "video" | "audio", style?: React.CSSProperties }[] = [
    { id: "prompt", label: "Prompt", type: "text", style: { bottom: '108px' } },
    { id: "image", label: "Ref Image", type: "image", style: { bottom: '20px' } }
];

const getCapabilitiesLabel = (capabilities: string[] = []) => {
    const hasT2I = !!capabilities.find(c => c.toLowerCase() === "t2i");
    const hasI2I = !!capabilities.find(c => c.toLowerCase() === "i2i");
    if (hasT2I && hasI2I) return "Text to Image & Image to Image";
    if (hasI2I) return "Image to Image";
    if (hasT2I) return "Text to Image";
    return "";
};

export const ImageGenNode = memo(({ id, selected, data }: NodeProps) => {
    const { deleteElements, updateNodeData } = useReactFlow();
    const ObjectOutputs = useWorkflowStore();
    const { runNode, clearNodeOutput, outputs, runningNodeId } = ObjectOutputs;
    const { models } = useModels();
    const imageModels = models.filter((m) => m.type === "image");

    const isRunning = runningNodeId === id;
    const output = (outputs[id] as string | undefined) || (data.output as string | undefined); // Use store output first, fallback to data.output

    const currentModel = (typeof data.model === 'string' ? data.model : (imageModels.length > 0 ? imageModels[0].name : "FLUX.2 [dev]"));
    const configInputs = DEFAULT_INPUTS;

    const handleDownload = () => {
        if (output) {
            const link = document.createElement('a');
            link.href = output;
            link.download = `generated-image-${Date.now()}.png`;
            link.target = '_blank';
            link.click();
        }
    };

    // Calculate ratio from dimensions if not explicitly set
    const getRatioFromDimensions = (w?: number, h?: number): string => {
        if (!w || !h) return "1:1";
        const r = w / h;
        if (Math.abs(r - 16 / 9) < 0.1) return "16:9";
        if (Math.abs(r - 9 / 16) < 0.1) return "9:16";
        if (Math.abs(r - 4 / 3) < 0.1) return "4:3";
        if (Math.abs(r - 3 / 4) < 0.1) return "3:4";
        return "1:1";
    };

    const ratio = (data.ratio as string) || getRatioFromDimensions(data.width as number, data.height as number);

    // Calculate dimensions based on ratio
    // Base dimension matches NodeWrapper min-width (approximately)
    const BASE_DIM = 300;

    const getDimensions = (r: string) => {
        const [w, h] = r.split(':').map(Number);
        if (!w || !h) return { width: BASE_DIM, height: BASE_DIM };

        if (w > h) {
            // Landscape: Increase width
            return { width: BASE_DIM * (w / h), height: BASE_DIM };
        } else if (h > w) {
            // Portrait: Increase height
            return { width: BASE_DIM, height: BASE_DIM * (h / w) };
        }
        return { width: BASE_DIM, height: BASE_DIM };
    };

    const styles = getDimensions(ratio);

    const [showSuggestions, setShowSuggestions] = React.useState(false);
    const [filterText, setFilterText] = React.useState("");
    const textareaRef = React.useRef<HTMLTextAreaElement>(null);

    const [showModelMenu, setShowModelMenu] = useState(false);
    const [showRatioMenu, setShowRatioMenu] = useState(false);
    const modelMenuRef = useRef<HTMLDivElement>(null);
    const ratioMenuRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        const handleClickOutside = (e: MouseEvent) => {
            if (modelMenuRef.current && !modelMenuRef.current.contains(e.target as Node)) {
                setShowModelMenu(false);
            }
            if (ratioMenuRef.current && !ratioMenuRef.current.contains(e.target as Node)) {
                setShowRatioMenu(false);
            }
        };
        if (showModelMenu || showRatioMenu) {
            document.addEventListener('mousedown', handleClickOutside);
            return () => document.removeEventListener('mousedown', handleClickOutside);
        }
    }, [showModelMenu, showRatioMenu]);

    // Get only connected text nodes for suggestions
    const nodes = useWorkflowStore((state) => state.nodes);
    const edges = useWorkflowStore((state) => state.edges);
    const connectedTextNodeIds = React.useMemo(() => new Set(
        edges.filter(e => e.target === id).map(e => e.source)
    ), [edges, id]);
    const allTextNodes = React.useMemo(() =>
        nodes.filter(n => n.type === 'text').map((n, i) => ({ id: n.id, label: `Text #${i + 1}`, content: (n.data.text as string) || "" })),
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

        // Check for trigger character @
        // We look back from cursor to find the last @
        const textBeforeCursor = val.slice(0, cursor);
        const lastAt = textBeforeCursor.lastIndexOf('@');

        if (lastAt !== -1) {
            // Check if there are invalid chars (like newlines or spaces) between @ and cursor
            const textAfterAt = textBeforeCursor.slice(lastAt + 1);
            if (!textAfterAt.includes('\n') && !textAfterAt.includes(' ') && textAfterAt.length < 20) {
                setShowSuggestions(true);
                setFilterText(textAfterAt.toLowerCase());
                return;
            }
        }
        setShowSuggestions(false);
    };

    const insertSuggestion = (label: string) => {
        const val = (typeof data.prompt === 'string' ? data.prompt : '');
        const cursor = textareaRef.current?.selectionStart || val.length;

        // Find the start of the mention
        const textBeforeCursor = val.slice(0, cursor);
        const lastAt = textBeforeCursor.lastIndexOf('@');

        if (lastAt !== -1) {
            const newVal = val.slice(0, lastAt) + `@${label} ` + val.slice(cursor);
            updateNodeData(id, { prompt: newVal });
            setShowSuggestions(false);

            // Restore focus (timeout to allow render)
            setTimeout(() => {
                if (textareaRef.current) {
                    textareaRef.current.focus();
                    const newCursor = lastAt + label.length + 2; // @ + label + space
                    textareaRef.current.setSelectionRange(newCursor, newCursor);
                }
            }, 0);
        }
    };

    return (
        <NodeWrapper
            title={`Image Generator #${useWorkflowStore((state) =>
                state.nodes
                    .filter(n => n.type === 'imageGen')
                    .findIndex(n => n.id === id) + 1
            )}`}
            icon={<ImageIcon className="w-4 h-4" />}
            selected={selected}
            color="bg-purple-500"
            inputs={configInputs}
            outputs={[{ id: "image", label: "Image", type: "image" }]}
            contentClassName="relative bg-black"
            onDelete={() => deleteElements({ nodes: [{ id }] })}
            onRun={() => runNode(id)}
            onClear={output ? () => clearNodeOutput(id) : undefined}
            isRunning={isRunning}
            executionStatus={data.executionStatus as "queued" | "running" | "completed" | "failed" | null}
        >
            <div
                className="relative bg-muted/30 group/image transition-all duration-300 ease-in-out overflow-hidden"
                style={{
                    width: styles.width,
                    height: styles.height
                }}
            >
                {/* 1. Background Image (Output) */}
                {output && !isRunning && (
                    <>
                        <S3Image
                            src={output}
                            alt="Generated"
                            className="absolute inset-0 w-full h-full object-cover z-0 transition-transform duration-700 group-hover/image:scale-105"
                            fill
                            unoptimized
                            onLoad={(e) => {
                                const img = e.currentTarget;
                                const w = img.naturalWidth;
                                const h = img.naturalHeight;
                                if (!w || !h) return;

                                const currentRatio = (data.ratio as string) || "1:1";
                                const imageRatio = w / h;

                                // Check standard ratios
                                const standards = {
                                    "1:1": 1,
                                    "16:9": 16 / 9,
                                    "9:16": 9 / 16,
                                    "4:3": 4 / 3,
                                    "3:4": 3 / 4
                                };

                                let closest = "1:1";
                                let minDiff = Infinity;

                                Object.entries(standards).forEach(([key, val]) => {
                                    const diff = Math.abs(imageRatio - val);
                                    if (diff < minDiff) {
                                        minDiff = diff;
                                        closest = key;
                                    }
                                });

                                if (closest !== currentRatio && minDiff < 0.1) {
                                    updateNodeData(id, { ratio: closest });
                                }
                            }}
                        />
                        <div className="absolute inset-0 z-0 pointer-events-none transition-opacity duration-300" />

                        {/* Download button */}
                        <button
                            onClick={handleDownload}
                            className="absolute top-3 right-3 w-8 h-8 bg-black/60 backdrop-blur-md border border-white/10 rounded-full flex items-center justify-center text-white/90 hover:bg-black/80 hover:text-white transition-all opacity-0 group-hover/image:opacity-100 z-30"
                        >
                            <Download className="w-4 h-4" />
                        </button>
                    </>
                )}

                {/* 2. Loading Overlay */}
                {isRunning && (
                    <div className="absolute inset-0 z-50 flex flex-col items-center justify-center p-6 text-center bg-background/90 backdrop-blur-sm">
                        <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center mb-3 text-primary">
                            <Loader2 className="w-6 h-6 animate-spin" />
                        </div>
                        <p className="text-xs font-medium text-muted-foreground">Generating image...</p>
                    </div>
                )}

                {/* 3. Text Input Layer (Always Visible) */}
                <div className={`relative z-10 h-full flex flex-col justify-end pb-12 pointer-events-none transition-all duration-300 ${output ? "opacity-0 group-hover/image:opacity-100 focus-within:opacity-100" : ""}`}>
                    {/* Suggestions Popup (pointer-events-auto) */}
                    {showSuggestions && textNodes.length > 0 && (
                        <div className="absolute bottom-16 left-4 z-50 w-48 bg-popover text-popover-foreground rounded-md border shadow-md overflow-hidden animate-in fade-in zoom-in-95 duration-100 pointer-events-auto">
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
                                {textNodes.length === 0 && (
                                    <div className="px-2 py-1.5 text-xs text-muted-foreground italic">No text nodes found</div>
                                )}
                            </div>
                        </div>
                    )}

                    <HighlightedTextarea
                        textareaRef={textareaRef}
                        className="w-full min-h-[80px] bg-transparent border-none px-4 pb-2 pt-4 text-sm font-medium placeholder:text-white/50 focus-visible:outline-none resize-y overflow-y-auto leading-relaxed text-white nodrag nowheel pointer-events-auto drop-shadow-md shadow-black/50"
                        placeholder="Describe the image you want to generate..."
                        value={typeof data.prompt === 'string' ? data.prompt : ''}
                        onChange={handleTextChange}
                        onKeyDown={(e) => e.stopPropagation()}
                    />
                </div>

                {/* Controls Bar - Bottom Left (One Line) */}
                <div className="absolute bottom-3 left-3 right-3 flex items-center gap-1 opacity-0 group-hover/image:opacity-100 transition-all duration-300 translate-y-2 group-hover/image:translate-y-0 z-20">



                    {/* Model Pill */}
                    <div className="relative flex-grow min-w-0 max-w-[140px]" ref={modelMenuRef}>
                        <button
                            onClick={() => {
                                setShowModelMenu(!showModelMenu);
                                setShowRatioMenu(false);
                            }}
                            className={cn(
                                "flex items-center gap-1.5 h-7 w-full bg-black/60 backdrop-blur-md border border-white/10 rounded-full px-2 text-white/90 hover:bg-black/70 transition-colors cursor-pointer",
                                showModelMenu && "bg-black/80 border-white/20"
                            )}
                        >
                            <span className="text-[10px] font-medium truncate flex-grow text-left">{currentModel}</span>
                            <ChevronDown className="w-2.5 h-2.5 text-white/50 flex-shrink-0" />
                        </button>

                        <AnimatePresence>
                            {showModelMenu && (
                                <motion.div
                                    initial={{ opacity: 0, y: 4, scale: 0.96 }}
                                    animate={{ opacity: 1, y: 0, scale: 1 }}
                                    exit={{ opacity: 0, y: 4, scale: 0.96 }}
                                    transition={{ duration: 0.12 }}
                                    className="absolute bottom-full left-0 mb-2 w-48 bg-black/90 backdrop-blur-xl border border-white/10 rounded-xl shadow-2xl overflow-hidden z-50 pointer-events-auto flex flex-col"
                                >
                                    <div className="px-3 py-2 text-[10px] font-semibold text-white/50 uppercase tracking-wider border-b border-white/10 bg-black/40">
                                        Model
                                    </div>
                                    <div className="max-h-[160px] overflow-y-auto flex flex-col p-1 nodrag nowheel">
                                        {imageModels.map(m => (
                                            <button
                                                key={m.id}
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    updateNodeData(id, { model: m.name });
                                                    setShowModelMenu(false);
                                                }}
                                                className={cn(
                                                    "w-full text-left px-2.5 py-1.5 rounded-lg hover:bg-white/10 cursor-pointer flex items-center justify-between transition-colors",
                                                    currentModel === m.name && "bg-white/15 text-white"
                                                )}
                                            >
                                                <div className="flex flex-col gap-0.5">
                                                    <span className={cn("text-[11px] font-medium", currentModel !== m.name && "text-white/80")}>
                                                        {m.name}
                                                    </span>
                                                    {getCapabilitiesLabel(m.capabilities) && (
                                                        <span className="text-white/40 text-[9px] leading-tight">
                                                            {getCapabilitiesLabel(m.capabilities)}
                                                        </span>
                                                    )}
                                                </div>
                                            </button>
                                        ))}
                                        {imageModels.length === 0 && (
                                            <div className="px-3 py-2 text-[11px] text-white/50 italic">No models available</div>
                                        )}
                                    </div>
                                </motion.div>
                            )}
                        </AnimatePresence>
                    </div>

                    {/* Ratio Pill */}
                    <div className="relative flex-shrink-0" ref={ratioMenuRef}>
                        <button
                            onClick={() => {
                                setShowRatioMenu(!showRatioMenu);
                                setShowModelMenu(false);
                            }}
                            className={cn(
                                "flex items-center gap-1.5 h-7 bg-black/60 backdrop-blur-md border border-white/10 rounded-full px-2 text-white/90 hover:bg-black/70 transition-colors cursor-pointer",
                                showRatioMenu && "bg-black/80 border-white/20"
                            )}
                        >
                            <Square className="w-2.5 h-2.5 text-white/70 flex-shrink-0" />
                            <span className="text-[10px] font-medium">{typeof data.ratio === 'string' ? data.ratio : "1:1"}</span>
                            <ChevronDown className="w-2.5 h-2.5 text-white/50 flex-shrink-0" />
                        </button>

                        <AnimatePresence>
                            {showRatioMenu && (
                                <motion.div
                                    initial={{ opacity: 0, y: 4, scale: 0.96 }}
                                    animate={{ opacity: 1, y: 0, scale: 1 }}
                                    exit={{ opacity: 0, y: 4, scale: 0.96 }}
                                    transition={{ duration: 0.12 }}
                                    className="absolute bottom-full right-0 mb-2 w-24 bg-black/90 backdrop-blur-xl border border-white/10 rounded-xl shadow-2xl overflow-hidden z-50 pointer-events-auto flex flex-col"
                                >
                                    <div className="px-3 py-2 text-[10px] font-semibold text-white/50 uppercase tracking-wider border-b border-white/10 bg-black/40">
                                        Ratio
                                    </div>
                                    <div className="flex flex-col p-1 nodrag nowheel">
                                        {["1:1", "16:9", "9:16", "4:3", "3:4"].map((r) => (
                                            <button
                                                key={r}
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    updateNodeData(id, { ratio: r });
                                                    setShowRatioMenu(false);
                                                }}
                                                className={cn(
                                                    "w-full text-left px-2.5 py-1.5 text-[11px] rounded-lg hover:bg-white/10 cursor-pointer transition-colors",
                                                    (typeof data.ratio === 'string' ? data.ratio : "1:1") === r && "bg-white/15 text-white font-medium"
                                                )}
                                            >
                                                <span className={cn((typeof data.ratio === 'string' ? data.ratio : "1:1") !== r && "text-white/80")}>
                                                    {r}
                                                </span>
                                            </button>
                                        ))}
                                    </div>
                                </motion.div>
                            )}
                        </AnimatePresence>
                    </div>

                </div>
            </div>
        </NodeWrapper>
    );
});

ImageGenNode.displayName = "ImageGenNode";
