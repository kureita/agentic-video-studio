import { Node } from "@xyflow/react";

export const NODE_REFERENCE_LABELS: Record<string, string> = {
    text: "Text",
    upload: "Upload",
    imageGen: "Image Gen",
    audioGen: "Audio Gen",
    videoGen: "Video Gen",
    assistant: "Media Assistant",
    vision: "Media Assistant",
    editorAgent: "Editor Agent",
    mediaUpload: "Media Upload",
};

const getStoredReferenceNumber = (node: Pick<Node, "data">): number | null => {
    const value = (node.data as Record<string, unknown> | undefined)?.referenceNumber;
    return typeof value === "number" && Number.isInteger(value) && value > 0 ? value : null;
};

export function getNodeTypeReferenceLabel(type?: string | null): string {
    return NODE_REFERENCE_LABELS[type || ""] || type || "Node";
}

export function getNodeReferenceNumber(node: Pick<Node, "data">): number | null {
    return getStoredReferenceNumber(node);
}

export function getNodeReferenceLabel(node: Pick<Node, "type" | "data">): string {
    const typeLabel = getNodeTypeReferenceLabel(node.type);
    const referenceNumber = getNodeReferenceNumber(node);
    return `${typeLabel} #${referenceNumber || "?"}`;
}

export function getNodeReferenceLabelById(nodes: Node[], nodeId: string): string | null {
    const node = nodes.find((candidate) => candidate.id === nodeId);
    return node ? getNodeReferenceLabel(node) : null;
}

export function assignStableNodeReferences(nodes: Node[]): Node[] {
    const usedByType = new Map<string, Set<number>>();
    const maxByType = new Map<string, number>();

    return nodes.map((node) => {
        const type = node.type || "unknown";
        const typeHasReferenceLabel = Object.prototype.hasOwnProperty.call(NODE_REFERENCE_LABELS, type);
        if (!typeHasReferenceLabel) return node;

        const used = usedByType.get(type) || new Set<number>();
        usedByType.set(type, used);

        const storedNumber = getStoredReferenceNumber(node);
        let nextNumber = storedNumber;

        if (!nextNumber || used.has(nextNumber)) {
            nextNumber = (maxByType.get(type) || 0) + 1;
            while (used.has(nextNumber)) nextNumber += 1;
        }

        used.add(nextNumber);
        maxByType.set(type, Math.max(maxByType.get(type) || 0, nextNumber));

        if (storedNumber === nextNumber) return node;
        return {
            ...node,
            data: {
                ...(node.data || {}),
                referenceNumber: nextNumber,
            },
        };
    });
}
