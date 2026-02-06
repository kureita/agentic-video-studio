"use client";

import { memo, useState } from "react";
import { NodeProps, Handle, Position } from "@xyflow/react";
import { BrainCircuit, Play, Loader2 } from "lucide-react";
import {
    BaseNode,
    BaseNodeHeader,
    BaseNodeContent,
    BaseNodeFooter,
} from "../BaseNode";
import { Button } from "@/components/ui";

interface AtomicLLMData {
    role?: string; // e.g., "Summarizer", "Script Writer"
    systemPrompt?: string;
    output?: string;
    [key: string]: unknown;
}

export const AtomicLLMNode = memo(function AtomicLLMNode({ data }: NodeProps) {
    const nodeData = data as AtomicLLMData;
    const [isProcessing, setIsProcessing] = useState(false);
    const [output, setOutput] = useState(nodeData.output || "");

    const handleRun = async () => {
        setIsProcessing(true);
        // Simulation of processing
        setTimeout(() => {
            setIsProcessing(false);
            setOutput("Generated content would appear here based on input from previous node.");
        }, 1500);
    };

    return (
        <BaseNode status={output ? "success" : "idle"} className="w-[300px]">
            <Handle type="target" position={Position.Left} className="!bg-foreground-subtle !w-3 !h-3" />

            <BaseNodeHeader icon={<BrainCircuit className="w-4 h-4" />}>
                {nodeData.role || "AI Processor"}
            </BaseNodeHeader>

            <BaseNodeContent>
                <div className="space-y-3">
                    <div className="p-2 rounded bg-background-secondary text-xs text-foreground-muted italic border border-border">
                        {nodeData.systemPrompt || "Processes input data..."}
                    </div>

                    {output && (
                        <div className="p-2 rounded bg-emerald-500/10 border border-emerald-500/20 text-xs">
                            {output}
                        </div>
                    )}
                </div>
            </BaseNodeContent>

            <BaseNodeFooter>
                <Button
                    onClick={handleRun}
                    disabled={isProcessing}
                    className="w-full nodrag"
                    size="sm"
                    icon={isProcessing ? <Loader2 className="w-3 h-3 animate-spin" /> : <Play className="w-3 h-3" />}
                >
                    {isProcessing ? "Processing..." : "Run Agent"}
                </Button>
            </BaseNodeFooter>

            <Handle type="source" position={Position.Right} className="!bg-foreground-subtle !w-3 !h-3" />
        </BaseNode>
    );
});
