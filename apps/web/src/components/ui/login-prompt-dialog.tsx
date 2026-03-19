"use client";

import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogDescription,
    DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { LogIn } from "lucide-react";
import { useRouter } from "next/navigation";
import { useAuth0 } from "@auth0/auth0-react";
import { useWorkflowStore } from "@/lib/workflow-store";

const SESSION_KEY = "kureita_fork_workflow_id";

interface LoginPromptDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    reason?: string;
}

export function LoginPromptDialog({ open, onOpenChange, reason }: LoginPromptDialogProps) {
    const router = useRouter();
    const { isAuthenticated, loginWithRedirect } = useAuth0();
    const workflowId = useWorkflowStore((s) => s.id);

    const defaultReason = "Sign in to run nodes, use the AI assistant, and create your own workflows.";

    const handleSignIn = () => {
        onOpenChange(false);

        if (workflowId) {
            sessionStorage.setItem(SESSION_KEY, workflowId);
        }

        if (isAuthenticated) {
            // Already logged in — go straight to the authenticated workflow page
            router.push(`/dashboard/workflow/?id=${workflowId}`);
        } else {
            // Trigger Auth0 login — after login, Auth0 redirects to /dashboard/
            // The dashboard page picks up SESSION_KEY and redirects to the workflow
            loginWithRedirect();
        }
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-md">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <LogIn className="w-5 h-5 text-primary" />
                        Sign in to continue
                    </DialogTitle>
                    <DialogDescription>
                        {reason || defaultReason}
                    </DialogDescription>
                </DialogHeader>
                <DialogFooter className="flex-col sm:flex-row gap-2">
                    <Button
                        variant="outline"
                        onClick={() => onOpenChange(false)}
                        className="sm:flex-1"
                    >
                        Keep viewing
                    </Button>
                    <Button
                        onClick={handleSignIn}
                        className="sm:flex-1 gap-2"
                    >
                        <LogIn className="w-4 h-4" />
                        Sign in
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}

export { SESSION_KEY };
