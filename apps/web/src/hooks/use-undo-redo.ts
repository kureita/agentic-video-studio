import { useCallback, useRef } from 'react';
import { Edge, Node } from '@xyflow/react';

type HistoryItem = {
    nodes: Node[];
    edges: Edge[];
};

/**
 * Action-based undo/redo hook.
 * 
 * Instead of recording every state change (which causes gradual undo on drags),
 * this records snapshots only when explicitly triggered before discrete actions
 * (add node, delete, connect, etc.) and on drag-end.
 */
export const useUndoRedo = () => {
    const pastRef = useRef<HistoryItem[]>([]);
    const futureRef = useRef<HistoryItem[]>([]);
    // Use a simple counter to force re-renders when history changes
    const updateRef = useRef(0);

    /**
     * Take a snapshot of the current state BEFORE an action.
     * Call this right before you perform a destructive action.
     */
    const takeSnapshot = useCallback((nodes: Node[], edges: Edge[]) => {
        const last = pastRef.current[pastRef.current.length - 1];

        // Deduplicate: don't push if state is identical to last snapshot
        if (last) {
            const nodesMatch =
                last.nodes.length === nodes.length &&
                last.nodes.every((n, i) => {
                    const curr = nodes[i];
                    return (
                        n.id === curr.id &&
                        n.position.x === curr.position.x &&
                        n.position.y === curr.position.y &&
                        n.type === curr.type
                    );
                });
            const edgesMatch =
                last.edges.length === edges.length &&
                last.edges.every((e, i) => {
                    const curr = edges[i];
                    return (
                        e.id === curr.id &&
                        e.source === curr.source &&
                        e.target === curr.target
                    );
                });
            if (nodesMatch && edgesMatch) return;
        }

        // Deep clone via structured clone to avoid reference sharing
        const snapshot: HistoryItem = {
            nodes: JSON.parse(JSON.stringify(nodes)),
            edges: JSON.parse(JSON.stringify(edges)),
        };

        pastRef.current = [...pastRef.current.slice(-49), snapshot];
        futureRef.current = [];
        updateRef.current++;
    }, []);

    const undo = useCallback((currentNodes: Node[], currentEdges: Edge[]) => {
        if (pastRef.current.length === 0) return null;

        const previous = pastRef.current[pastRef.current.length - 1];
        pastRef.current = pastRef.current.slice(0, -1);

        // Push current state to future
        futureRef.current = [
            {
                nodes: JSON.parse(JSON.stringify(currentNodes)),
                edges: JSON.parse(JSON.stringify(currentEdges)),
            },
            ...futureRef.current,
        ];
        updateRef.current++;

        return previous;
    }, []);

    const redo = useCallback((currentNodes: Node[], currentEdges: Edge[]) => {
        if (futureRef.current.length === 0) return null;

        const next = futureRef.current[0];
        futureRef.current = futureRef.current.slice(1);

        // Push current state to past
        pastRef.current = [
            ...pastRef.current,
            {
                nodes: JSON.parse(JSON.stringify(currentNodes)),
                edges: JSON.parse(JSON.stringify(currentEdges)),
            },
        ];
        updateRef.current++;

        return next;
    }, []);

    return {
        takeSnapshot,
        undo,
        redo,
        canUndo: pastRef.current.length > 0,
        canRedo: futureRef.current.length > 0,
    };
};
