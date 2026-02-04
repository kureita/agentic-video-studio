"use client";

import {
    Search,
    Upload,
    FolderOpen,
    Type,
    Image as ImageIcon,
    Video,
    Bot,
    Maximize,
    Camera
} from "lucide-react";
import { Input } from "@/components/ui/input";

interface NodeSelectorProps {
    onSelect: (type: string) => void;
    onClose: () => void;
}

export function NodeSelector({ onSelect, onClose }: NodeSelectorProps) {
    const NODE_TYPES = [
        { id: "text", label: "Text", icon: <Type className="w-4 h-4 text-emerald-500" /> },
        { id: "imageGen", label: "Image Generator", icon: <ImageIcon className="w-4 h-4 text-blue-500" /> },
        { id: "videoGen", label: "Video Generator", icon: <Video className="w-4 h-4 text-purple-500" /> },
        { id: "assistant", label: "Assistant", icon: <Bot className="w-4 h-4 text-indigo-500" /> },
        { id: "upscaler", label: "Image Upscaler", icon: <Maximize className="w-4 h-4 text-pink-500" /> },
        { id: "camera", label: "Camera Angle", icon: <Camera className="w-4 h-4 text-orange-500" /> },
    ];

    return (
        <div className="w-64 bg-card border border-border rounded-xl shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-100">

            {/* Header / Search */}
            <div className="p-3 border-b border-border space-y-3">
                <div className="relative">
                    <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                    <Input placeholder="Search" className="pl-8 h-9 text-xs" autoFocus />
                </div>

                <div className="grid grid-cols-2 gap-2">
                    <button className="flex items-center justify-center gap-2 p-2 rounded-md bg-secondary/50 hover:bg-secondary text-xs font-medium transition-colors">
                        <Upload className="w-3 h-3" />
                        Upload
                    </button>
                    <button className="flex items-center justify-center gap-2 p-2 rounded-md bg-secondary/50 hover:bg-secondary text-xs font-medium transition-colors">
                        <FolderOpen className="w-3 h-3" />
                        Media
                    </button>
                </div>
            </div>

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

            {/* Utilities List */}
            <div className="border-t border-border py-2 mt-1">
                <div className="px-3 py-1 text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
                    Utilities
                </div>
                {/* Placeholder for utilities */}
                <div className="px-3 py-2 text-xs text-muted-foreground italic">
                    More tools coming soon...
                </div>
            </div>
        </div>
    );
}
