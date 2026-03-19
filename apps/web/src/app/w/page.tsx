"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useState, Suspense } from "react";
import { Loader2, Lock } from "lucide-react";

import FlowEditor from "@/components/workflow/flow-editor";
import { PublicWorkflowHeader } from "@/components/workflow/public-header";
import { useWorkflowStore } from "@/lib/workflow-store";
import { setPresignPublicMode } from "@/lib/presigned-url-cache";

function PublicWorkflowContent() {
    const searchParams = useSearchParams();
    const id = searchParams.get("id");
    const [isInitialized, setIsInitialized] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const { loadPublicWorkflow } = useWorkflowStore();

    useEffect(() => {
        setPresignPublicMode(true);
        return () => setPresignPublicMode(false);
    }, []);

    useEffect(() => {
        if (!id || isInitialized) return;

        loadPublicWorkflow(id)
            .then(() => setIsInitialized(true))
            .catch(() => {
                setError("This workflow is not available or is private.");
                setIsInitialized(true);
            });
    }, [id, isInitialized, loadPublicWorkflow]);

    if (!id) {
        return (
            <div className="flex h-[100dvh] items-center justify-center">
                <div className="flex flex-col items-center gap-4 text-center px-6 max-w-md">
                    <div className="p-4 rounded-full bg-muted">
                        <Lock className="w-8 h-8 text-muted-foreground" />
                    </div>
                    <h2 className="text-lg font-semibold">No workflow specified</h2>
                    <p className="text-sm text-muted-foreground">This link appears to be incomplete.</p>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="flex h-[100dvh] items-center justify-center">
                <div className="flex flex-col items-center gap-4 text-center px-6 max-w-md">
                    <div className="p-4 rounded-full bg-muted">
                        <Lock className="w-8 h-8 text-muted-foreground" />
                    </div>
                    <h2 className="text-lg font-semibold">Workflow not available</h2>
                    <p className="text-sm text-muted-foreground">{error}</p>
                </div>
            </div>
        );
    }

    if (!isInitialized) {
        return (
            <div className="flex h-[100dvh] items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
        );
    }

    return (
        <div className="flex flex-col h-[100dvh]">
            <PublicWorkflowHeader />
            <div className="flex-1 relative overflow-hidden">
                <FlowEditor workflowId={id} />
            </div>
        </div>
    );
}

export default function PublicWorkflowPage() {
    return (
        <Suspense fallback={
            <div className="flex h-[100dvh] items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
        }>
            <PublicWorkflowContent />
        </Suspense>
    );
}
