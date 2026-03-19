"use client";

import { useSearchParams, useRouter } from "next/navigation";
import FlowEditor from "@/components/workflow/flow-editor";
import { Suspense, useEffect, useState, useRef } from "react";
import { Loader2, GitFork } from "lucide-react";

import { WorkflowHeader } from "@/components/workflow/header";
import { useWorkflowStore } from "@/lib/workflow-store";
import { workflowApi } from "@/lib/workflow-api";
import { toast } from "sonner";

function WorkflowEditorContent() {
    const searchParams = useSearchParams();
    const router = useRouter();
    const id = searchParams.get("id");
    const [workflowId, setWorkflowId] = useState<string | null>(null);
    const [isForking, setIsForking] = useState(false);
    const forkAttempted = useRef(false);

    // Auto-save
    useEffect(() => {
        const interval = setInterval(() => {
            const { isDirty, saveWorkflow, isPublicView } = useWorkflowStore.getState();
            if (isDirty && !isPublicView) {
                saveWorkflow();
            }
        }, 3000);
        return () => clearInterval(interval);
    }, []);

    useEffect(() => {
        if (!id) return;

        // Try loading the workflow; if 404, fork it
        const tryLoadOrFork = async () => {
            try {
                await useWorkflowStore.getState().loadWorkflow(id);
                setWorkflowId(id);
            } catch (err: unknown) {
                const status = (err as { response?: { status?: number } })?.response?.status;

                if (status === 404 && !forkAttempted.current) {
                    forkAttempted.current = true;
                    setIsForking(true);
                    try {
                        const res = await workflowApi.fork(id);
                        const newId = res.data.id;
                        toast.success("Workflow copied to your account");
                        router.replace(`/dashboard/workflow/?id=${newId}`);
                    } catch {
                        toast.error("This workflow is not available");
                        router.replace("/dashboard/");
                    } finally {
                        setIsForking(false);
                    }
                } else {
                    toast.error("Failed to load workflow");
                }
            }
        };

        tryLoadOrFork();
    }, [id, router]);

    if (isForking) {
        return (
            <div className="flex h-full items-center justify-center">
                <div className="flex flex-col items-center gap-3">
                    <GitFork className="w-6 h-6 text-primary animate-pulse" />
                    <p className="text-sm text-muted-foreground">Copying workflow to your account...</p>
                </div>
            </div>
        );
    }

    if (!workflowId) {
        return (
            <div className="flex h-full items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
        );
    }

    return (
        <div className="flex flex-col h-[100dvh]">
            <WorkflowHeader />
            <div className="flex-1 relative overflow-hidden">
                <FlowEditor workflowId={workflowId} />
            </div>
        </div>
    );
}

export default function WorkflowPage() {
    return (
        <Suspense fallback={
            <div className="flex h-full items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
        }>
            <WorkflowEditorContent />
        </Suspense>
    );
}
