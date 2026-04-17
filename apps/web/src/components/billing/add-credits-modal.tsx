"use client";

import { useEffect, useState } from "react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader2, CreditCard } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { useAuth0 } from "@auth0/auth0-react";

interface AddCreditsModalProps {
    open?: boolean;
    onOpenChange?: (open: boolean) => void;
    onSuccess?: (newBalance: number) => void;
    children?: React.ReactNode;
}

type DodoTopupConfig = {
    payments_enabled: boolean;
    environment: string;
    min_usd: number;
    max_usd: number;
};

export function AddCreditsModal({ open, onOpenChange, onSuccess, children }: AddCreditsModalProps) {
    const { getAccessTokenSilently, user } = useAuth0();
    const [voucherCode, setVoucherCode] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const [dodoConfig, setDodoConfig] = useState<DodoTopupConfig | null>(null);
    const [dodoLoading, setDodoLoading] = useState(false);
    const [topupAmount, setTopupAmount] = useState("");
    const [checkoutBusy, setCheckoutBusy] = useState(false);

    useEffect(() => {
        if (!open || !user?.sub) return;
        let cancelled = false;
        (async () => {
            setDodoLoading(true);
            try {
                const token = await getAccessTokenSilently({
                    authorizationParams: { scope: "openid profile email" },
                });
                const res = await api.get<DodoTopupConfig>("/api/billing/dodo/topup-config", {
                    headers: { Authorization: `Bearer ${token}` },
                });
                if (!cancelled) {
                    setDodoConfig(res.data);
                    const { min_usd, max_usd } = res.data;
                    const suggested = Math.min(min_usd, max_usd);
                    setTopupAmount(String(Number.isFinite(suggested) ? suggested : min_usd));
                }
            } catch {
                if (!cancelled) {
                    setDodoConfig({
                        payments_enabled: false,
                        environment: "test_mode",
                        min_usd: 10,
                        max_usd: 500,
                    });
                }
            } finally {
                if (!cancelled) setDodoLoading(false);
            }
        })();
        return () => {
            cancelled = true;
        };
    }, [open, user?.sub, getAccessTokenSilently]);

    const startDodoCheckout = async () => {
        if (!user?.sub || !dodoConfig?.payments_enabled) return;
        const raw = parseFloat(topupAmount.replace(/,/g, ""));
        if (!Number.isFinite(raw)) {
            toast.error("Enter a valid dollar amount.");
            return;
        }
        if (raw < dodoConfig.min_usd || raw > dodoConfig.max_usd) {
            toast.error(`Amount must be between $${dodoConfig.min_usd} and $${dodoConfig.max_usd}.`);
            return;
        }
        setCheckoutBusy(true);
        try {
            const token = await getAccessTokenSilently({
                authorizationParams: { scope: "openid profile email" },
            });
            const profileEmail =
                typeof user?.email === "string" && user.email.trim() ? user.email.trim() : undefined;
            const res = await api.post<{ checkout_url: string }>(
                "/api/billing/dodo/checkout-session",
                { amount_usd: raw, ...(profileEmail ? { customer_email: profileEmail } : {}) },
                { headers: { Authorization: `Bearer ${token}` } }
            );
            window.location.href = res.data.checkout_url;
        } catch (error: unknown) {
            console.error("Dodo checkout error:", error);
            const message =
                (error as { response?: { data?: { detail?: string } } }).response?.data?.detail ||
                "Could not start checkout.";
            toast.error(message);
        } finally {
            setCheckoutBusy(false);
        }
    };

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

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            {children && <DialogTrigger asChild>{children}</DialogTrigger>}
            <DialogContent
                className="sm:max-w-[400px] p-0 gap-0 overflow-hidden"
                onOpenAutoFocus={(e) => e.preventDefault()}
            >
                {/* Header */}
                <div className="px-6 pt-6 pb-4">
                    <DialogHeader className="space-y-1">
                        <DialogTitle className="text-lg font-semibold tracking-tight">
                            Add Funds
                        </DialogTitle>
                        <DialogDescription className="text-sm text-muted-foreground">
                            Top up with a card or redeem a voucher.
                        </DialogDescription>
                    </DialogHeader>
                </div>

                <div className="px-6 pb-6 space-y-5">
                    {dodoLoading ? (
                        <div className="flex items-center gap-2 text-muted-foreground text-xs py-1">
                            <Loader2 className="w-3.5 h-3.5 animate-spin shrink-0" />
                            Loading card checkout…
                        </div>
                    ) : null}
                    {!dodoLoading && dodoConfig?.payments_enabled ? (
                        <div className="space-y-2.5">
                            <Label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                                Pay with card
                            </Label>
                            {dodoConfig.environment === "test_mode" ? (
                                <p className="text-[11px] text-amber-700 dark:text-amber-400/90 leading-snug">
                                    Test mode — use Dodo&apos;s test cards; no real money is charged.
                                </p>
                            ) : null}
                            <p className="text-[11px] text-muted-foreground">
                                USD amount (${dodoConfig.min_usd}–${dodoConfig.max_usd})
                            </p>
                            <div className="flex gap-2">
                                <Input
                                    type="text"
                                    inputMode="decimal"
                                    placeholder={dodoConfig ? dodoConfig.min_usd.toFixed(2) : "10.00"}
                                    value={topupAmount}
                                    onChange={(e) => setTopupAmount(e.target.value)}
                                    className="h-9 font-mono text-sm"
                                    disabled={checkoutBusy}
                                />
                                <Button
                                    type="button"
                                    size="sm"
                                    variant="secondary"
                                    className="h-9 shrink-0 px-3"
                                    disabled={checkoutBusy}
                                    onClick={() => startDodoCheckout()}
                                >
                                    {checkoutBusy ? (
                                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                                    ) : (
                                        <>
                                            <CreditCard className="w-3.5 h-3.5 mr-1.5 opacity-70" />
                                            Pay
                                        </>
                                    )}
                                </Button>
                            </div>
                        </div>
                    ) : null}

                    {!dodoLoading && dodoConfig?.payments_enabled ? (
                        <div className="relative">
                            <div className="absolute inset-0 flex items-center">
                                <div className="w-full border-t border-border/60" />
                            </div>
                            <div className="relative flex justify-center">
                                <span className="bg-background px-3 text-[11px] uppercase tracking-widest text-muted-foreground/60 font-medium">
                                    or
                                </span>
                            </div>
                        </div>
                    ) : null}

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
                </div>
            </DialogContent>
        </Dialog>
    );
}
