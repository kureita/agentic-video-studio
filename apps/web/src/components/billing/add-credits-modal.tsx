"use client";

import { useState } from "react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader2 } from "lucide-react";
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
            const response = await api.post("/api/billing/redeem", { code: voucherCode.trim().toUpperCase() }, {
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
            window.location.href = "mailto:hello@kureita.com?subject=Need%20more%20funds";
            setIsContacting(false);
            toast.success("Opening native email client...");
        }, 600);
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            {children && <DialogTrigger asChild>{children}</DialogTrigger>}
            <DialogContent className="sm:max-w-[400px] p-0 gap-0 overflow-hidden">
                {/* Header */}
                <div className="px-6 pt-6 pb-4">
                    <DialogHeader className="space-y-1">
                        <DialogTitle className="text-lg font-semibold tracking-tight">
                            Add Funds
                        </DialogTitle>
                        <DialogDescription className="text-sm text-muted-foreground">
                            Redeem a voucher or contact us for custom plans.
                        </DialogDescription>
                    </DialogHeader>
                </div>

                <div className="px-6 pb-6 space-y-5">
                    {/* Voucher Section */}
                    <form onSubmit={handleRedeem} className="space-y-2.5">
                        <Label htmlFor="voucher" className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                            Voucher Code
                        </Label>
                        <div className="flex gap-2">
                            <Input
                                id="voucher"
                                placeholder="e.g. KUREITA_500"
                                value={voucherCode}
                                onChange={(e) => setVoucherCode(e.target.value)}
                                className="uppercase font-mono text-sm tracking-wider h-9"
                            />
                            <Button
                                type="submit"
                                size="sm"
                                disabled={!voucherCode.trim() || isLoading}
                                className="h-9 px-4 shrink-0"
                            >
                                {isLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : "Redeem"}
                            </Button>
                        </div>
                    </form>

                    {/* Divider */}
                    <div className="relative">
                        <div className="absolute inset-0 flex items-center">
                            <div className="w-full border-t border-border/60" />
                        </div>
                        <div className="relative flex justify-center">
                            <span className="bg-background px-3 text-[11px] uppercase tracking-widest text-muted-foreground/60 font-medium">or</span>
                        </div>
                    </div>

                    {/* Contact Sales */}
                    <div className="rounded-lg border border-border/40 p-4 space-y-3">
                        <div>
                            <h4 className="text-sm font-medium">Need a custom plan?</h4>
                            <p className="text-xs text-muted-foreground mt-1 leading-relaxed">
                                Contact us for enterprise pricing or high-volume packages.
                            </p>
                        </div>
                        <Button
                            variant="outline"
                            size="sm"
                            className="w-full h-9 text-xs font-medium"
                            onClick={handleContactUs}
                            disabled={isContacting}
                        >
                            {isContacting ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-2" /> : null}
                            Contact Sales
                        </Button>
                    </div>
                </div>
            </DialogContent>
        </Dialog>
    );
}
