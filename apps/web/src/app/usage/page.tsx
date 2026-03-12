"use client";

import { useEffect, useState } from "react";
import { format } from "date-fns";
import { DollarSign, Loader2, Fingerprint, Clock, Activity, Video, Image as ImageIcon, MessageSquare, Music, CheckCircle2, Plus } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { AddCreditsModal } from "@/components/billing/add-credits-modal";

type ActionType = "ai_chat" | "video_gen" | "image_gen" | "audio_gen" | "render" | "deposit" | "voucher_redeem" | "referral_bonus";

interface UsageLog {
    _id: string;
    action_type: ActionType;
    tokens_used?: number;
    cost_usd: number;
    commission_usd: number;
    total_usd: number;
    model_name?: string;
    provider?: string;
    metadata: Record<string, unknown>;
    created_at: string;
}

const ACTION_LABELS: Record<string, { label: string, icon: React.ReactNode, color: string }> = {
    ai_chat: { label: "AI Assistant", icon: <MessageSquare className="w-4 h-4" />, color: "bg-muted text-foreground/80" },
    video_gen: { label: "Video Generation", icon: <Video className="w-4 h-4" />, color: "bg-muted text-foreground/80" },
    image_gen: { label: "Image Generation", icon: <ImageIcon className="w-4 h-4" />, color: "bg-muted text-foreground/80" },
    audio_gen: { label: "Voiceover", icon: <Music className="w-4 h-4" />, color: "bg-muted text-foreground/80" },
    render: { label: "Final Export", icon: <CheckCircle2 className="w-4 h-4" />, color: "bg-muted text-foreground/80" },
    deposit: { label: "Deposit", icon: <DollarSign className="w-4 h-4" />, color: "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-400" },
    voucher_redeem: { label: "Voucher Redeemed", icon: <DollarSign className="w-4 h-4" />, color: "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-400" },
    referral_bonus: { label: "Referral Bonus", icon: <DollarSign className="w-4 h-4" />, color: "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-400" },
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

    // Calculate total spent (only debits! exclude credits)
    const CREDIT_TYPES = ["deposit", "voucher_redeem", "referral_bonus"];
    const totalSpent = logs
        .filter(log => !CREDIT_TYPES.includes(log.action_type))
        .reduce((sum, log) => sum + Math.abs(log.total_usd || 0), 0);

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
                        <p className="text-muted-foreground mt-2">Track your API costs and view generation history.</p>
                    </div>
                    <Button
                        onClick={() => setIsCreditsModalOpen(true)}
                        className="shadow-sm transition-all whitespace-nowrap"
                    >
                        <Plus className="w-4 h-4 mr-2" />
                        Add Funds
                    </Button>
                </div>

                <div className="grid gap-6 md:grid-cols-3">
                    <Card className="shadow-sm border-border/50 hover:border-border transition-colors">
                        <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0 relative z-10">
                            <CardTitle className="text-sm font-medium">Balance</CardTitle>
                            <div className="p-2 bg-muted rounded-full">
                                <DollarSign className="w-4 h-4 text-primary" />
                            </div>
                        </CardHeader>
                        <CardContent className="relative z-10">
                            <div className="text-4xl font-bold tracking-tight">${balance?.toFixed(2) || "0.00"}</div>
                            <p className="text-xs text-muted-foreground mt-2 font-medium">
                                Available USD balance
                            </p>
                        </CardContent>
                    </Card>

                    <Card className="shadow-sm border-border/50 hover:border-border transition-colors">
                        <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
                            <CardTitle className="text-sm font-medium">Total Spent</CardTitle>
                            <div className="p-2 bg-muted rounded-full">
                                <Activity className="w-4 h-4 text-muted-foreground" />
                            </div>
                        </CardHeader>
                        <CardContent>
                            <div className="text-3xl font-bold tracking-tight">${totalSpent.toFixed(4)}</div>
                            <p className="text-xs text-muted-foreground mt-1">
                                Across {logs.filter(l => !CREDIT_TYPES.includes(l.action_type)).length} generations
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
                            <DollarSign className="w-5 h-5 text-muted-foreground" />
                            How Pricing Works
                        </CardTitle>
                        <CardDescription>
                            You pay actual API cost + 30% commission per generation
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mt-2">
                            <div className="flex flex-col items-start gap-1 p-4 rounded-lg bg-muted/40 border border-border/50 hover:bg-muted/60 transition-colors">
                                <div className="text-xs font-medium flex items-center gap-1.5 mb-1 text-foreground/80">
                                    <MessageSquare className="w-3.5 h-3.5" /> AI Chat
                                </div>
                                <div className="text-sm font-bold">Pay-per-use</div>
                                <div className="text-[10px] text-muted-foreground uppercase tracking-wider font-semibold">Actual LLM cost</div>
                            </div>

                            <div className="flex flex-col items-start gap-1 p-4 rounded-lg bg-muted/40 border border-border/50 hover:bg-muted/60 transition-colors">
                                <div className="text-xs font-medium flex items-center gap-1.5 mb-1 text-foreground/80">
                                    <ImageIcon className="w-3.5 h-3.5" /> Image Gen
                                </div>
                                <div className="text-sm font-bold">Pay-per-use</div>
                                <div className="text-[10px] text-muted-foreground uppercase tracking-wider font-semibold">Actual API cost</div>
                            </div>

                            <div className="flex flex-col items-start gap-1 p-4 rounded-lg bg-muted/40 border border-border/50 hover:bg-muted/60 transition-colors">
                                <div className="text-xs font-medium flex items-center gap-1.5 mb-1 text-foreground/80">
                                    <Music className="w-3.5 h-3.5" /> Audio
                                </div>
                                <div className="text-sm font-bold">Pay-per-use</div>
                                <div className="text-[10px] text-muted-foreground uppercase tracking-wider font-semibold">Actual API cost</div>
                            </div>

                            <div className="flex flex-col items-start gap-1 p-4 rounded-lg bg-muted/40 border border-border/50 hover:bg-muted/60 transition-colors">
                                <div className="text-xs font-medium flex items-center gap-1.5 mb-1 text-foreground/80">
                                    <Video className="w-3.5 h-3.5" /> Video Gen
                                </div>
                                <div className="text-sm font-bold">Pay-per-use</div>
                                <div className="text-[10px] text-muted-foreground uppercase tracking-wider font-semibold">Actual API cost</div>
                            </div>

                            <div className="flex flex-col items-start gap-1 p-4 rounded-lg bg-muted/40 border border-border/50 hover:bg-muted/60 transition-colors">
                                <div className="text-xs font-medium flex items-center gap-1.5 mb-1 text-foreground/80">
                                    <CheckCircle2 className="w-3.5 h-3.5" /> Final Export
                                </div>
                                <div className="text-sm font-bold">$0.05</div>
                                <div className="text-[10px] text-muted-foreground uppercase tracking-wider font-semibold">Flat rate</div>
                            </div>
                        </div>
                    </CardContent>
                </Card>

                <Card className="shadow-sm">
                    <CardHeader>
                        <CardTitle>Usage History</CardTitle>
                        <CardDescription>A detailed breakdown of your costs over time.</CardDescription>
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
                                        <TableHead>Model</TableHead>
                                        <TableHead>Details</TableHead>
                                        <TableHead>Date</TableHead>
                                        <TableHead className="text-right">Cost</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {logs.map((log) => {
                                        const actionConfig = ACTION_LABELS[log.action_type] || { label: "Unknown", icon: <Activity className="w-4 h-4" />, color: "bg-muted text-muted-foreground" };
                                        const isCredit = ["deposit", "voucher_redeem", "referral_bonus"].includes(log.action_type);
                                        const displayValue = Math.abs(log.total_usd || 0).toFixed(4);

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
                                                <TableCell className="text-xs text-muted-foreground">
                                                    {log.model_name && (
                                                        <div className="flex flex-col">
                                                            <span className="font-medium text-foreground/70">{log.model_name}</span>
                                                            {log.provider && <span className="text-[10px] text-muted-foreground">{log.provider}</span>}
                                                        </div>
                                                    )}
                                                </TableCell>
                                                <TableCell className="max-w-[200px] sm:max-w-[300px] truncate text-xs sm:text-sm text-muted-foreground">
                                                    {log.metadata?.prompt ? (
                                                        <span title={String(log.metadata.prompt)}>&quot;{String(log.metadata.prompt)}&quot;</span>
                                                    ) : log.metadata?.project_id ? (
                                                        <span className="font-mono text-xs">Project: {String(log.metadata.project_id).substring(0, 8)}...</span>
                                                    ) : (
                                                        <span>—</span>
                                                    )}

                                                    {log.metadata?.resolution ? (
                                                        <Badge variant="default" className="ml-2 text-[10px] scale-90 origin-left">
                                                            {String(log.metadata.resolution)}
                                                        </Badge>
                                                    ) : null}
                                                    {log.metadata?.ratio ? (
                                                        <Badge variant="default" className="ml-2 text-[10px] scale-90 origin-left">
                                                            {String(log.metadata.ratio)}
                                                        </Badge>
                                                    ) : null}
                                                    {log.metadata?.duration ? (
                                                        <Badge variant="default" className="ml-2 text-[10px] scale-90 origin-left">
                                                            {String(log.metadata.duration)}
                                                        </Badge>
                                                    ) : null}

                                                    {log.tokens_used ? (
                                                        <Badge variant="default" className="ml-2 text-[10px] scale-90 origin-left">
                                                            {log.tokens_used.toLocaleString()} tokens
                                                        </Badge>
                                                    ) : null}
                                                </TableCell>
                                                <TableCell className="text-xs text-muted-foreground">
                                                    <div className="flex items-center gap-1.5">
                                                        <Clock className="w-3 h-3" />
                                                        {format(new Date(log.created_at), "MMM d, h:mm a")}
                                                    </div>
                                                </TableCell>
                                                <TableCell className="text-right">
                                                    <div className={`inline-flex items-center gap-1 font-medium text-sm ${isCredit ? "text-green-600 dark:text-green-400" : "text-red-500/90"}`}>
                                                        {isCredit ? "+" : "-"}${displayValue}
                                                    </div>
                                                    {!isCredit && log.commission_usd > 0 && (
                                                        <div className="text-[10px] text-muted-foreground mt-0.5">
                                                            (API: ${log.cost_usd?.toFixed(4)} + fee: ${log.commission_usd?.toFixed(4)})
                                                        </div>
                                                    )}
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
