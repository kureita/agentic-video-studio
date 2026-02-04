import { useCallback, useState } from 'react';
import { Edge, Node } from '@xyflow/react';

type HistoryItem = {
    nodes: Node[];
    edges: Edge[];
};

export const useUndoRedo = (
    initialNodes: Node[],
    initialEdges: Edge[]
) => {
    const [past, setPast] = useState<HistoryItem[]>([]);
    const [future, setFuture] = useState<HistoryItem[]>([]);

    const takeSnapshot = useCallback((nodes: Node[], edges: Edge[]) => {
        setPast((past) => {
            // Limit history size to 50
            const newPast = [...past, { nodes, edges }];
            if (newPast.length > 50) return newPast.slice(newPast.length - 50);
            return newPast;
        });
        setFuture([]);
    }, []);

    const undo = useCallback((currentNodes: Node[], currentEdges: Edge[]) => {
        if (past.length === 0) return null;

        const previous = past[past.length - 1];
        const newPast = past.slice(0, past.length - 1);

        setPast(newPast);
        setFuture((future) => [{ nodes: currentNodes, edges: currentEdges }, ...future]);

        return previous;
    }, [past]);

    const redo = useCallback((currentNodes: Node[], currentEdges: Edge[]) => {
        if (future.length === 0) return null;

        const next = future[0];
        const newFuture = future.slice(1);

        setPast((past) => [...past, { nodes: currentNodes, edges: currentEdges }]);
        setFuture(newFuture);

        return next;
    }, [future]);

    return {
        takeSnapshot,
        undo,
        redo,
        canUndo: past.length > 0,
        canRedo: future.length > 0,
    };
};
