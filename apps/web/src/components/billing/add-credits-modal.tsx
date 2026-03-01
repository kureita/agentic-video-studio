"use client";

import { useState } from "react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Coins, Loader2, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { useAuth0 } from "@auth0/auth0-react";

interface AddCreditsModalProps {
    open?: boolean;
    onOpenChange?: (open: boolean) => void;
    onSuccess?: (newBalance: number) => void;
    children?: React.ReactNode;
}

export function AddCreditsModal({ open, onOpenChange, onSuccess, children }: AddCreditsModalProps) {
    const { getAccessTokenSilently, user } = useAuth0();
    const [voucherCode, setVoucherCode] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const [isContacting, setIsContacting] = useState(false);

    const handleRedeem = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!voucherCode.trim() || !user?.sub) return;

        setIsLoading(true);
        try {
            const token = await getAccessTokenSilently();
            const response = await api.post("/api/billing/redeem", { code: voucherCode.trim() }, {
                headers: { Authorization: `Bearer ${token}` }
            });

            toast.success("Voucher redeemed successfully!");
            setVoucherCode("");
            onSuccess?.(response.data.balance);
            onOpenChange?.(false);
        } catch (error: unknown) {
            console.error("Redemption error:", error);
            const message = (error as { response?: { data?: { detail?: string } } }).response?.data?.detail || "Failed to redeem voucher. Invalid or already used.";
            toast.error(message);
        } finally {
            setIsLoading(false);
        }
    };

    const handleContactUs = () => {
        setIsContacting(true);
        // Simulate contacting sales
        setTimeout(() => {
            window.location.href = "mailto:hello@kureita.com?subject=Need%20more%20credits";
            setIsContacting(false);
            toast.success("Opening native email client...");
        }, 600);
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            {children && <DialogTrigger asChild>{children}</DialogTrigger>}
            <DialogContent className="sm:max-w-[425px]">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <Coins className="w-5 h-5 text-violet-500" />
                        Get More Credits
                    </DialogTitle>
                    <DialogDescription>
                        Redeem a voucher or contact our team to top up your account balance.
                    </DialogDescription>
                </DialogHeader>

                <div className="grid gap-6 py-4">
                    {/* Voucher Section */}
                    <div className="space-y-4">
                        <form onSubmit={handleRedeem} className="space-y-3">
                            <Label htmlFor="voucher" className="text-sm font-medium">
                                Redeem Voucher
                            </Label>
                            <div className="flex gap-2">
                                <Input
                                    id="voucher"
                                    placeholder="Enter your code (e.g. KUREITA_500)"
                                    value={voucherCode}
                                    onChange={(e) => setVoucherCode(e.target.value)}
                                    className="uppercase font-mono tracking-wider"
                                />
                                <Button type="submit" disabled={!voucherCode.trim() || isLoading}>
                                    {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : "Redeem"}
                                </Button>
                            </div>
                        </form>
                    </div>

                    <div className="relative">
                        <div className="absolute inset-0 flex items-center">
                            <span className="w-full border-t" />
                        </div>
                        <div className="relative flex justify-center text-xs uppercase">
                            <span className="bg-background px-2 text-muted-foreground">Or</span>
                        </div>
                    </div>

                    {/* Contact Sales Section */}
                    <div className="rounded-xl border border-border/50 bg-muted/30 p-4">
                        <div className="flex gap-3 items-start">
                            <div className="mt-0.5 w-8 h-8 rounded-full bg-violet-100 dark:bg-violet-900/30 flex items-center justify-center shrink-0">
                                <Sparkles className="w-4 h-4 text-violet-600 dark:text-violet-400" />
                            </div>
                            <div>
                                <h4 className="text-sm font-semibold mb-1">Need a custom plan?</h4>
                                <p className="text-xs text-muted-foreground mb-3">
                                    Running out of credits often? Contact us for custom enterprise pricing or high-volume packages.
                                </p>
                                <Button
                                    variant="outline"
                                    size="sm"
                                    className="w-full bg-background"
                                    onClick={handleContactUs}
                                    disabled={isContacting}
                                >
                                    {isContacting ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
                                    Contact Sales
                                </Button>
                            </div>
                        </div>
                    </div>
                </div>
            </DialogContent>
        </Dialog>
    );
}
