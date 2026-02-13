"use client";

import { useSearchParams } from "next/navigation";
import FlowEditor from "@/components/workflow/flow-editor";
import { Suspense, useEffect, useState } from "react";
import { Loader2 } from "lucide-react";

import { WorkflowHeader } from "@/components/workflow/header";
import { useWorkflowStore } from "@/lib/workflow-store";

function WorkflowEditorContent() {
    const searchParams = useSearchParams();
    const id = searchParams.get("id");
    const [workflowId, setWorkflowId] = useState<string | null>(null);

    // Auto-save
    useEffect(() => {
        const interval = setInterval(() => {
            const { isDirty, saveWorkflow } = useWorkflowStore.getState();
            if (isDirty) {
                saveWorkflow();
            }
        }, 3000);
        return () => clearInterval(interval);
    }, []);

    useEffect(() => {
        if (id) {
            setWorkflowId(id);
        }
    }, [id]);

    if (!workflowId) {
        return (
            <div className="flex h-full items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
        );
    }

    return (
        <div className="flex flex-col h-screen">
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
