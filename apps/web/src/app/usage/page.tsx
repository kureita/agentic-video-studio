"use client";

import { useEffect, useState } from "react";
import { format } from "date-fns";
import { Coins, Loader2, Fingerprint, Clock, Activity, Video, Image as ImageIcon, MessageSquare, Music, CheckCircle2, Plus } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { AddCreditsModal } from "@/components/billing/add-credits-modal";

type ActionType = "ai_chat" | "video_gen" | "image_gen" | "audio_gen" | "render";

interface UsageLog {
    _id: string;
    action_type: ActionType;
    tokens_used?: number;
    credits_deducted: number;
    metadata: Record<string, unknown>;
    created_at: string;
}

const ACTION_LABELS: Record<ActionType, { label: string, icon: React.ReactNode, color: string }> = {
    ai_chat: { label: "AI Assistant", icon: <MessageSquare className="w-4 h-4" />, color: "bg-muted text-foreground/80" },
    video_gen: { label: "Video Generation", icon: <Video className="w-4 h-4" />, color: "bg-muted text-foreground/80" },
    image_gen: { label: "Image Generation", icon: <ImageIcon className="w-4 h-4" />, color: "bg-muted text-foreground/80" },
    audio_gen: { label: "Voiceover", icon: <Music className="w-4 h-4" />, color: "bg-muted text-foreground/80" },
    render: { label: "Final Export", icon: <CheckCircle2 className="w-4 h-4" />, color: "bg-muted text-foreground/80" },
};

import { useAuth0 } from "@auth0/auth0-react";

export default function UsageDashboard() {
    const { getAccessTokenSilently, user } = useAuth0();
    const [logs, setLogs] = useState<UsageLog[]>([]);
    const [balance, setBalance] = useState<number | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [isCreditsModalOpen, setIsCreditsModalOpen] = useState(false);

    useEffect(() => {
        const fetchData = async () => {
            if (!user?.sub) return;

            try {
                const token = await getAccessTokenSilently();
                const config = {
                    headers: {
                        Authorization: `Bearer ${token}`
                    }
                };

                const [balanceRes, usageRes] = await Promise.all([
                    api.get("/api/billing/balance", config),
                    api.get("/api/billing/usage", { ...config, params: { limit: 100 } })
                ]);

                setBalance(balanceRes.data.balance);
                setLogs(usageRes.data.logs);
            } catch (error) {
                console.error("Failed to fetch billing data:", error);
            } finally {
                setIsLoading(false);
            }
        };

        fetchData();
    }, [getAccessTokenSilently, user?.sub]);

    if (isLoading) {
        return (
            <div className="flex items-center justify-center min-h-[60vh] w-full">
                <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
            </div>
        );
    }

    return (
        <div className="w-full flex justify-center pb-20">
            <div className="container max-w-5xl py-10 space-y-8 px-4 sm:px-6">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border/40 pb-6">
                    <div>
                        <h1 className="text-3xl font-bold tracking-tight">Usage & Billing</h1>
                        <p className="text-muted-foreground mt-2">Manage your credits and view your generation history.</p>
                    </div>
                    <Button
                        onClick={() => setIsCreditsModalOpen(true)}
                        className="shadow-sm transition-all whitespace-nowrap"
                    >
                        <Plus className="w-4 h-4 mr-2" />
                        Add Credits
                    </Button>
                </div>

                <div className="grid gap-6 md:grid-cols-3">
                    <Card className="shadow-sm border-border/50 hover:border-border transition-colors">
                        <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0 relative z-10">
                            <CardTitle className="text-sm font-medium">Available Credits</CardTitle>
                            <div className="p-2 bg-muted rounded-full">
                                <Coins className="w-4 h-4 text-primary" />
                            </div>
                        </CardHeader>
                        <CardContent className="relative z-10">
                            <div className="text-4xl font-bold tracking-tight">{balance?.toLocaleString() || 0}</div>
                            <p className="text-xs text-muted-foreground mt-2 font-medium">
                                Current active balance
                            </p>
                        </CardContent>
                    </Card>

                    <Card className="shadow-sm border-border/50 hover:border-border transition-colors">
                        <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
                            <CardTitle className="text-sm font-medium">Generations</CardTitle>
                            <div className="p-2 bg-muted rounded-full">
                                <Activity className="w-4 h-4 text-muted-foreground" />
                            </div>
                        </CardHeader>
                        <CardContent>
                            <div className="text-3xl font-bold tracking-tight">{logs.filter(l => l.action_type !== 'ai_chat').length}</div>
                            <p className="text-xs text-muted-foreground mt-1">
                                Total media assets created
                            </p>
                        </CardContent>
                    </Card>

                    <Card className="shadow-sm border-border/50 hover:border-border transition-colors">
                        <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
                            <CardTitle className="text-sm font-medium">AI Interactions</CardTitle>
                            <div className="p-2 bg-muted rounded-full">
                                <Fingerprint className="w-4 h-4 text-muted-foreground" />
                            </div>
                        </CardHeader>
                        <CardContent>
                            <div className="text-3xl font-bold tracking-tight">{logs.filter(l => l.action_type === 'ai_chat').length}</div>
                            <p className="text-xs text-muted-foreground mt-1">
                                Total prompts and chats
                            </p>
                        </CardContent>
                    </Card>
                </div>

                <Card className="shadow-sm border-border/50">
                    <CardHeader className="pb-3">
                        <CardTitle className="text-lg flex items-center gap-2">
                            <Coins className="w-5 h-5 text-muted-foreground" />
                            Pricing Rates
                        </CardTitle>
                        <CardDescription>
                            How your credits are consumed
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mt-2">
                            <div className="flex flex-col items-start gap-1 p-4 rounded-lg bg-muted/40 border border-border/50 hover:bg-muted/60 transition-colors">
                                <div className="text-xs font-medium flex items-center gap-1.5 mb-1 text-foreground/80">
                                    <MessageSquare className="w-3.5 h-3.5" /> AI Assistant
                                </div>
                                <div className="text-lg font-bold">1 <span className="text-xs font-normal text-muted-foreground mr-1">credit</span></div>
                                <div className="text-[10px] text-muted-foreground uppercase tracking-wider font-semibold">Per 10K Tokens</div>
                            </div>

                            <div className="flex flex-col items-start gap-1 p-4 rounded-lg bg-muted/40 border border-border/50 hover:bg-muted/60 transition-colors">
                                <div className="text-xs font-medium flex items-center gap-1.5 mb-1 text-foreground/80">
                                    <ImageIcon className="w-3.5 h-3.5" /> Image Gen
                                </div>
                                <div className="text-lg font-bold">1 <span className="text-xs font-normal text-muted-foreground mr-1">credit</span></div>
                                <div className="text-[10px] text-muted-foreground uppercase tracking-wider font-semibold">Per Image</div>
                            </div>

                            <div className="flex flex-col items-start gap-1 p-4 rounded-lg bg-muted/40 border border-border/50 hover:bg-muted/60 transition-colors">
                                <div className="text-xs font-medium flex items-center gap-1.5 mb-1 text-foreground/80">
                                    <Music className="w-3.5 h-3.5" /> Text-to-Speech
                                </div>
                                <div className="text-lg font-bold">2 <span className="text-xs font-normal text-muted-foreground mr-1">credits</span></div>
                                <div className="text-[10px] text-muted-foreground uppercase tracking-wider font-semibold">Per Usage</div>
                            </div>

                            <div className="flex flex-col items-start gap-1 p-4 rounded-lg bg-muted/40 border border-border/50 hover:bg-muted/60 transition-colors">
                                <div className="text-xs font-medium flex items-center gap-1.5 mb-1 text-foreground/80">
                                    <Video className="w-3.5 h-3.5" /> Video Gen
                                </div>
                                <div className="text-lg font-bold">10 <span className="text-xs font-normal text-muted-foreground mr-1">credits</span></div>
                                <div className="text-[10px] text-muted-foreground uppercase tracking-wider font-semibold">Per Generation</div>
                            </div>

                            <div className="flex flex-col items-start gap-1 p-4 rounded-lg bg-muted/40 border border-border/50 hover:bg-muted/60 transition-colors">
                                <div className="text-xs font-medium flex items-center gap-1.5 mb-1 text-foreground/80">
                                    <CheckCircle2 className="w-3.5 h-3.5" /> Final Export
                                </div>
                                <div className="text-lg font-bold">20 <span className="text-xs font-normal text-muted-foreground mr-1">credits</span></div>
                                <div className="text-[10px] text-muted-foreground uppercase tracking-wider font-semibold">Per Video</div>
                            </div>
                        </div>
                    </CardContent>
                </Card>

                <Card className="shadow-sm">
                    <CardHeader>
                        <CardTitle>Usage History</CardTitle>
                        <CardDescription>A detailed breakdown of your credit usage over time.</CardDescription>
                    </CardHeader>
                    <CardContent>
                        {logs.length === 0 ? (
                            <div className="text-center py-10 text-muted-foreground text-sm border-t">
                                No usage history found. Start creating!
                            </div>
                        ) : (
                            <Table>
                                <TableHeader>
                                    <TableRow>
                                        <TableHead>Type</TableHead>
                                        <TableHead>Details</TableHead>
                                        <TableHead>Date</TableHead>
                                        <TableHead className="text-right">Credits</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {logs.map((log) => {
                                        const actionConfig = ACTION_LABELS[log.action_type] || { label: "Unknown", icon: <Activity className="w-4 h-4" />, color: "bg-muted text-muted-foreground" };

                                        return (
                                            <TableRow key={log._id}>
                                                <TableCell>
                                                    <div className="flex items-center gap-2">
                                                        <div className={`p-1.5 rounded-md ${actionConfig.color}`}>
                                                            {actionConfig.icon}
                                                        </div>
                                                        <span className="font-medium text-xs sm:text-sm">{actionConfig.label}</span>
                                                    </div>
                                                </TableCell>
                                                <TableCell className="max-w-[200px] sm:max-w-[300px] truncate text-xs sm:text-sm text-muted-foreground">
                                                    {log.action_type === "ai_chat" && log.metadata?.prompt ? (
                                                        <span title={String(log.metadata.prompt)}>&quot;{String(log.metadata.prompt)}&quot;</span>
                                                    ) : log.metadata?.project_id ? (
                                                        <span className="font-mono text-xs">Project: {String(log.metadata.project_id).substring(0, 8)}...</span>
                                                    ) : (
                                                        <span>System Process</span>
                                                    )}

                                                    {log.tokens_used && (
                                                        <Badge variant="default" className="ml-2 text-[10px] scale-90 origin-left">
                                                            {log.tokens_used.toLocaleString()} tokens
                                                        </Badge>
                                                    )}
                                                </TableCell>
                                                <TableCell className="text-xs text-muted-foreground">
                                                    <div className="flex items-center gap-1.5">
                                                        <Clock className="w-3 h-3" />
                                                        {format(new Date(log.created_at), "MMM d, h:mm a")}
                                                    </div>
                                                </TableCell>
                                                <TableCell className="text-right">
                                                    <div className="inline-flex items-center gap-1 font-medium text-red-500/90 text-sm">
                                                        -{log.credits_deducted}
                                                    </div>
                                                </TableCell>
                                            </TableRow>
                                        );
                                    })}
                                </TableBody>
                            </Table>
                        )}
                    </CardContent>
                </Card>
            </div>

            <AddCreditsModal
                open={isCreditsModalOpen}
                onOpenChange={setIsCreditsModalOpen}
                onSuccess={(newBalance) => {
                    setBalance(newBalance);
                }}
            />
        </div>
    );
}
