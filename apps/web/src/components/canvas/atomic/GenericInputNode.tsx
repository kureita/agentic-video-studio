"use client";

import { memo, useState } from "react";
import { NodeProps, Handle, Position } from "@xyflow/react";
import { Link, FileText, Upload } from "lucide-react";
import {
    BaseNode,
    BaseNodeHeader,
    BaseNodeContent,
} from "../BaseNode";
import { Textarea } from "@/components/ui";

interface GenericInputData {
    label?: string;
    inputType?: "text" | "url";
    value?: string;
    placeholder?: string;
    [key: string]: unknown;
}

export const GenericInputNode = memo(function GenericInputNode({ data, id }: NodeProps) {
    const nodeData = data as GenericInputData;
    const [value, setValue] = useState(nodeData.value || "");

    const inputType = nodeData.inputType || "text";
    const label = nodeData.label || (inputType === "url" ? "Source URL" : "Input Text");

    const Icon = inputType === "url" ? Link : FileText;

    const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
        setValue(e.target.value);
        // In a real app, we'd update the node data in the store here
        data.value = e.target.value;
    };

    return (
        <BaseNode status={value ? "success" : "idle"} className="w-[300px]">
            <BaseNodeHeader icon={<Icon className="w-4 h-4" />}>
                {label}
            </BaseNodeHeader>

            <BaseNodeContent>
                <div className="space-y-2">
                    <Textarea
                        value={value}
                        onChange={handleChange}
                        placeholder={nodeData.placeholder || (inputType === "url" ? "https://example.com/article" : "Enter text here...")}
                        className="min-h-[80px] text-xs resize-none bg-background-secondary border-border"
                    />
                </div>
            </BaseNodeContent>

            {/* Source handle only (it's an input) */}
            <Handle type="source" position={Position.Right} className="!bg-foreground-subtle !w-3 !h-3" />
        </BaseNode>
    );
});
