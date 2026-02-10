import { memo, useRef, useEffect } from "react";
import { NodeProps, useReactFlow, NodeResizer } from "@xyflow/react";

export const CommentNode = memo(({ id, selected, data }: NodeProps) => {
    const { updateNodeData, deleteElements } = useReactFlow();
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    const text = typeof data.text === "string" ? data.text : "";
    const color = typeof data.color === "string" ? data.color : "#fbbf24"; // amber-400

    // Auto-resize textarea
    useEffect(() => {
        if (textareaRef.current) {
            textareaRef.current.style.height = "auto";
            textareaRef.current.style.height = textareaRef.current.scrollHeight + "px";
        }
    }, [text]);

    return (
        <>
            <NodeResizer
                isVisible={selected}
                minWidth={150}
                minHeight={80}
                lineStyle={{ borderColor: color, borderWidth: 1 }}
                handleStyle={{ backgroundColor: color, width: 8, height: 8, borderRadius: 2 }}
            />
            <div
                className="relative group/comment min-w-[150px] min-h-[80px] h-full"
                style={{
                    backgroundColor: color + "18",
                    borderLeft: `3px solid ${color}`,
                    borderRadius: "4px",
                    padding: "8px 10px",
                }}
            >
                {/* Delete button */}
                <button
                    className="absolute -top-2 -right-2 w-5 h-5 rounded-full bg-destructive text-destructive-foreground text-[10px] flex items-center justify-center opacity-0 group-hover/comment:opacity-100 transition-opacity z-10"
                    onClick={() => deleteElements({ nodes: [{ id }] })}
                >
                    ×
                </button>

                {/* Color dots */}
                <div className="absolute top-1.5 right-2 flex gap-1 opacity-0 group-hover/comment:opacity-100 transition-opacity">
                    {["#fbbf24", "#f87171", "#60a5fa", "#34d399", "#c084fc", "#9ca3af"].map((c) => (
                        <button
                            key={c}
                            className="w-3 h-3 rounded-full border border-white/30 hover:scale-125 transition-transform"
                            style={{ backgroundColor: c }}
                            onClick={() => updateNodeData(id, { color: c })}
                        />
                    ))}
                </div>

                <textarea
                    ref={textareaRef}
                    className="w-full h-full bg-transparent border-none outline-none resize-none text-xs leading-relaxed placeholder:text-muted-foreground/50 nodrag nowheel"
                    style={{ color: "hsl(var(--foreground))" }}
                    placeholder="Add a comment..."
                    value={text}
                    onChange={(e) => updateNodeData(id, { text: e.target.value })}
                    onKeyDown={(e) => e.stopPropagation()}
                />
            </div>
        </>
    );
});

CommentNode.displayName = "CommentNode";
