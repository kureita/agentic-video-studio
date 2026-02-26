import React, { memo } from "react";
import { NodeProps, useReactFlow } from "@xyflow/react";
import { Music, Loader2, Download, ChevronDown } from "lucide-react";
import { NodeWrapper } from "@/components/workflow/node-wrapper";
import { useWorkflowStore } from "@/lib/workflow-store";

export const AudioGenNode = memo(({ id, selected, data }: NodeProps) => {
    const { deleteElements, updateNodeData } = useReactFlow();
    const { runNode, clearNodeOutput, outputs, runningNodeId } = useWorkflowStore();

    const isRunning = runningNodeId === id;
    const output = (outputs[id] as string | undefined) || (data.output as string | undefined);

    const handleDownload = () => {
        if (output) {
            const link = document.createElement('a');
            link.href = output;
            link.download = `generated-audio-${Date.now()}.mp3`;
            link.target = '_blank';
            link.click();
        }
    };

    const textareaRef = React.useRef<HTMLTextAreaElement>(null);
    const [showSuggestions, setShowSuggestions] = React.useState(false);
    const [filterText, setFilterText] = React.useState("");

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

    return (
        <NodeWrapper
            title={`Audio Generator #${useWorkflowStore((state) =>
                state.nodes
                    .filter(n => n.type === 'audioGen')
                    .findIndex(n => n.id === id) + 1
            )}`}
            icon={<Music className="w-4 h-4" />}
            selected={selected}
            color="bg-orange-500"
            inputs={[
                { id: "prompt", label: "Text", type: "text", style: { bottom: '20px' } }
            ]}
            outputs={[{ id: "audio", label: "Audio", type: "audio" }]}
            contentClassName="relative bg-black"
            onDelete={() => deleteElements({ nodes: [{ id }] })}
            onRun={() => runNode(id)}
            onClear={output ? () => clearNodeOutput(id) : undefined}
            isRunning={isRunning}
            executionStatus={data.executionStatus as "queued" | "running" | "completed" | "failed" | null}
        >
            <div className="relative bg-muted/30 group/audio transition-all duration-300 ease-in-out overflow-hidden w-[320px]">

                {/* Top Section: Audio Player */}
                <div className="relative h-[120px] flex items-center justify-center p-4">
                    {output && !isRunning ? (
                        <>
                            <audio
                                src={output}
                                controls
                                className="w-full"
                                style={{ filter: 'drop-shadow(0 4px 6px rgba(0, 0, 0, 0.3))' }}
                            />

                            {/* Download button */}
                            <button
                                onClick={handleDownload}
                                className="absolute top-3 right-3 w-8 h-8 bg-black/60 backdrop-blur-md border border-white/10 rounded-full flex items-center justify-center text-white/90 hover:bg-black/80 hover:text-white transition-all z-30"
                            >
                                <Download className="w-4 h-4" />
                            </button>
                        </>
                    ) : isRunning ? (
                        <div className="flex flex-col items-center justify-center text-center">
                            <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center mb-3 text-primary">
                                <Loader2 className="w-6 h-6 animate-spin" />
                            </div>
                            <p className="text-xs font-medium text-muted-foreground">Generating audio...</p>
                        </div>
                    ) : (
                        <div className="flex items-center justify-center text-muted-foreground/50">
                            <Music className="w-8 h-8" />
                        </div>
                    )}
                </div>

                {/* Divider Line */}
                <div className="h-px bg-gradient-to-r from-transparent via-white/20 to-transparent" />

                {/* Bottom Section: Text Input & Controls */}
                <div className="relative bg-black/20">
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

                    {/* Text Input */}
                    <textarea
                        ref={textareaRef}
                        className="w-full min-h-[100px] bg-transparent border-none px-4 py-3 text-sm font-medium placeholder:text-white/50 focus-visible:outline-none resize-none overflow-y-auto leading-relaxed text-white nodrag nowheel"
                        placeholder="Enter text to convert to speech..."
                        value={typeof data.prompt === 'string' ? data.prompt : ''}
                        onChange={handleTextChange}
                        onKeyDown={(e) => e.stopPropagation()}
                    />

                    {/* Controls Bar */}
                    <div className="px-3 pb-3 flex items-center gap-2">
                        {/* Voice Selector */}
                        <div className="relative h-7 flex items-center gap-1.5 bg-black/40 backdrop-blur-sm border border-white/10 rounded-full px-3 text-white/90 hover:bg-black/60 transition-colors flex-grow">
                            <Music className="w-3 h-3 text-white/70" />
                            <span className="text-[10px] font-medium truncate">{typeof data.voice === 'string' ? data.voice : "Rachel"}</span>
                            <ChevronDown className="w-2.5 h-2.5 text-white/50 flex-shrink-0" />
                            <select
                                className="absolute inset-0 opacity-0 cursor-pointer"
                                value={typeof data.voice === 'string' ? data.voice : "Rachel"}
                                onChange={(e) => updateNodeData(id, { voice: e.target.value })}
                            >
                                <option value="Rachel">Rachel</option>
                                <option value="Adam">Adam</option>
                                <option value="Antoni">Antoni</option>
                                <option value="Arnold">Arnold</option>
                                <option value="Bella">Bella</option>
                                <option value="Domi">Domi</option>
                                <option value="Elli">Elli</option>
                                <option value="Josh">Josh</option>
                                <option value="Sam">Sam</option>
                            </select>
                        </div>
                    </div>
                </div>
            </div>
        </NodeWrapper>
    );
});

AudioGenNode.displayName = "AudioGenNode";
