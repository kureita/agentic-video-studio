"use client";

import {
    Type,
    Image as ImageIcon,
    Video,
    Eye,
    Clapperboard,
    Upload,
    Music
} from "lucide-react";

interface NodeSelectorProps {
    onSelect: (type: string) => void;
    onClose: () => void;
}

export function NodeSelector({ onSelect }: NodeSelectorProps) {
    const NODE_TYPES = [
        { id: "text", label: "Text", icon: <Type className="w-4 h-4 text-emerald-500" /> },
        { id: "imageGen", label: "Image Generator", icon: <ImageIcon className="w-4 h-4 text-blue-500" /> },
        { id: "audioGen", label: "Audio Generator", icon: <Music className="w-4 h-4 text-orange-500" /> },
        { id: "videoGen", label: "Video Generator", icon: <Video className="w-4 h-4 text-purple-500" /> },
        { id: "vision", label: "Vision", icon: <Eye className="w-4 h-4 text-indigo-500" /> },
        { id: "editorAgent", label: "Editor Agent", icon: <Clapperboard className="w-4 h-4 text-purple-600" /> },
        { id: "mediaUpload", label: "Asset", icon: <Upload className="w-4 h-4 text-blue-600" /> },
    ];

    return (
        <div className="w-64 bg-card border border-border rounded-xl shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-100">
            {/* Nodes List */}
            <div className="py-2">
                <div className="px-3 py-1 text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
                    Nodes
                </div>
                <div className="space-y-0.5 px-1">
                    {NODE_TYPES.map((node) => (
                        <button
                            key={node.id}
                            className="w-full flex items-center gap-3 px-3 py-2 rounded-md hover:bg-accent text-sm text-foreground text-left transition-colors"
                            onClick={() => onSelect(node.id)}
                        >
                            <div className="p-1 rounded bg-secondary/50">
                                {node.icon}
                            </div>
                            <span>{node.label}</span>
                        </button>
                    ))}
                </div>
            </div>
        </div>
    );
}
