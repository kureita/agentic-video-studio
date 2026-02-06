"use client";

import { memo, useState, useEffect } from "react";
import { NodeProps } from "@xyflow/react";
import { Building2, ArrowRight, Loader2, Plus, ChevronDown } from "lucide-react";
import {
    BaseNode,
    BaseNodeHeader,
    BaseNodeContent,
    BaseNodeFooter,
    BaseNodeError
} from "./BaseNode";
import { Button, Input } from "@/components/ui";
import { useCanvasStore } from "@/lib/canvas-store";
import { brandsApi, projectsApi, Brand } from "@/lib/api";

interface BrandSelectorNodeData {
    onProceed?: () => void;
    [key: string]: unknown;
}

export const BrandSelectorNode = memo(function BrandSelectorNode({ data }: NodeProps) {
    const nodeData = data as BrandSelectorNodeData;
    const {
        setBrandData,
        setProjectId,
        nodeStatuses,
        setNodeStatus,
        setError,
        errors,
        brandData,
    } = useCanvasStore();

    const [brands, setBrands] = useState<Brand[]>([]);
    const [isLoadingBrands, setIsLoadingBrands] = useState(true);
    const [selectedBrandId, setSelectedBrandId] = useState<string | null>(null);
    const [showDropdown, setShowDropdown] = useState(false);
    const [showNewBrand, setShowNewBrand] = useState(false);
    const [websiteUrl, setWebsiteUrl] = useState("");

    const isLoading = nodeStatuses.brand === "loading";
    const isSuccess = nodeStatuses.brand === "success";
    const isValidUrl = websiteUrl.startsWith("http");

    // Load brands on mount
    useEffect(() => {
        loadBrands();
    }, []);

    const loadBrands = async () => {
        setIsLoadingBrands(true);
        try {
            const response = await brandsApi.list();
            setBrands(response.data.brands);
        } catch (err) {
            console.error("Failed to load brands:", err);
        } finally {
            setIsLoadingBrands(false);
        }
    };

    const handleSelectBrand = async (brand: Brand) => {
        setSelectedBrandId(brand.id);
        setShowDropdown(false);
        setNodeStatus("brand", "loading");
        setError("brand", null);

        try {
            // Set brand data from selected brand
            setBrandData({
                name: brand.name,
                tagline: brand.tagline,
                description: brand.description,
                primary_colors: brand.primary_colors,
                logo_url: brand.logo_url,
                tone: brand.tone,
                products: brand.products,
                unique_selling_points: brand.unique_selling_points,
            });

            // Create a project for this canvas session
            try {
                // Check if we already have a project ID relative to this brand? 
                // For now, always create a new project when a brand is selected to start a flow.
                const projectRes = await projectsApi.create({
                    website_url: brand.website_url || "",
                    brand_name: brand.name,
                    description: brand.description,
                    style: "professional", // Default
                    video_duration: 30, // Default
                });

                setProjectId(projectRes.data.id);
                setNodeStatus("brand", "success");

                if (nodeData?.onProceed) {
                    nodeData.onProceed();
                }
            } catch (projErr) {
                console.error("Failed to create project:", projErr);
                setNodeStatus("brand", "error");
                setError("brand", "Failed to initialize project");
            }
        } catch (err) {
            console.error("Failed to select brand:", err);
            setNodeStatus("brand", "error");
            setError("brand", err instanceof Error ? err.message : "Failed to select brand");
        }
    };

    const handleAnalyzeWebsite = async () => {
        if (!isValidUrl) return;

        setNodeStatus("brand", "loading");
        setError("brand", null);

        try {
            const response = await brandsApi.analyzeWebsite(websiteUrl);
            const brand = response.data;

            // Add to brands list
            setBrands(prev => [brand, ...prev]);
            setSelectedBrandId(brand.id);

            // Set brand data
            setBrandData({
                name: brand.name,
                tagline: brand.tagline,
                description: brand.description,
                primary_colors: brand.primary_colors,
                logo_url: brand.logo_url,
                tone: brand.tone,
                products: brand.products,
                unique_selling_points: brand.unique_selling_points,
            });

            // Create project
            try {
                const projectRes = await projectsApi.create({
                    website_url: brand.website_url || websiteUrl,
                    brand_name: brand.name,
                    description: brand.description,
                    style: "professional",
                    video_duration: 30,
                });

                setProjectId(projectRes.data.id);
                setNodeStatus("brand", "success");
                setShowNewBrand(false);

                if (nodeData?.onProceed) {
                    nodeData.onProceed();
                }
            } catch (projErr) {
                console.error("Failed to create project:", projErr);
                setNodeStatus("brand", "error");
                setError("brand", "Failed to initialize project");
            }
        } catch (err) {
            console.error("Failed to analyze website:", err);
            setNodeStatus("brand", "error");
            setError("brand", err instanceof Error ? err.message : "Failed to analyze website");
        }
    };

    const selectedBrand = brands.find(b => b.id === selectedBrandId);

    return (
        <BaseNode hasInput={false} status={nodeStatuses.brand}>
            <BaseNodeHeader icon={<Building2 className="w-4 h-4" />} status={nodeStatuses.brand}>
                Brand
            </BaseNodeHeader>

            <BaseNodeContent>
                {!isSuccess ? (
                    <>
                        <p className="text-sm text-foreground-muted mb-4">
                            Select an existing brand or create a new one from a website.
                        </p>

                        {!showNewBrand ? (
                            <div className="space-y-3">
                                {/* Brand Selector Dropdown */}
                                <div className="relative">
                                    <button
                                        onClick={() => setShowDropdown(!showDropdown)}
                                        disabled={isLoadingBrands || isLoading}
                                        className="w-full flex items-center justify-between p-3 rounded-lg border border-border hover:border-foreground-subtle bg-background-secondary text-left transition-colors nodrag"
                                    >
                                        <span className={selectedBrand ? "text-foreground" : "text-foreground-muted"}>
                                            {isLoadingBrands
                                                ? "Loading brands..."
                                                : selectedBrand
                                                    ? selectedBrand.name
                                                    : "Select a brand..."}
                                        </span>
                                        <ChevronDown className={`w-4 h-4 text-foreground-subtle transition-transform ${showDropdown ? "rotate-180" : ""}`} />
                                    </button>

                                    {showDropdown && (
                                        <div className="absolute z-10 w-full mt-1 py-1 bg-background border border-border rounded-lg shadow-lg max-h-[200px] overflow-y-auto nowheel">
                                            {brands.length === 0 ? (
                                                <div className="px-3 py-2 text-sm text-foreground-muted">
                                                    No brands yet. Create one below.
                                                </div>
                                            ) : (
                                                brands.map(brand => (
                                                    <button
                                                        key={brand.id}
                                                        onClick={() => handleSelectBrand(brand)}
                                                        className="w-full px-3 py-2 text-left hover:bg-background-secondary text-sm nodrag"
                                                    >
                                                        <span className="font-medium text-foreground">{brand.name}</span>
                                                        {brand.tagline && (
                                                            <span className="text-foreground-muted ml-2">· {brand.tagline}</span>
                                                        )}
                                                    </button>
                                                ))
                                            )}
                                        </div>
                                    )}
                                </div>

                                {/* Divider */}
                                <div className="flex items-center gap-2">
                                    <div className="flex-1 h-px bg-border" />
                                    <span className="text-xs text-foreground-muted">or</span>
                                    <div className="flex-1 h-px bg-border" />
                                </div>

                                {/* Create New Brand Button */}
                                <Button
                                    variant="outline"
                                    onClick={() => setShowNewBrand(true)}
                                    className="w-full nodrag"
                                    icon={<Plus className="w-4 h-4" />}
                                >
                                    Create New Brand from Website
                                </Button>
                            </div>
                        ) : (
                            <div className="space-y-3">
                                <Input
                                    placeholder="https://yourbrand.com"
                                    value={websiteUrl}
                                    onChange={(e) => setWebsiteUrl(e.target.value)}
                                    disabled={isLoading}
                                    className="nodrag"
                                />

                                <div className="flex gap-2">
                                    <Button
                                        variant="ghost"
                                        onClick={() => setShowNewBrand(false)}
                                        disabled={isLoading}
                                        className="flex-1 nodrag"
                                    >
                                        Cancel
                                    </Button>
                                    <Button
                                        onClick={handleAnalyzeWebsite}
                                        disabled={!isValidUrl || isLoading}
                                        className="flex-1 nodrag"
                                        icon={isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <ArrowRight className="w-4 h-4" />}
                                        iconPosition="right"
                                    >
                                        {isLoading ? "Analyzing..." : "Analyze"}
                                    </Button>
                                </div>
                            </div>
                        )}
                    </>
                ) : (
                    // Success state - show selected brand summary
                    <div className="p-3 rounded-lg bg-background-secondary">
                        <div className="flex items-center gap-3">
                            {brandData?.logo_url ? (
                                <img
                                    src={brandData.logo_url}
                                    alt={brandData.name}
                                    className="w-10 h-10 rounded-lg object-cover"
                                />
                            ) : (
                                <div className="w-10 h-10 rounded-lg bg-background flex items-center justify-center">
                                    <Building2 className="w-5 h-5 text-foreground-subtle" />
                                </div>
                            )}
                            <div>
                                <p className="font-medium text-foreground">{brandData?.name}</p>
                                {brandData?.tagline && (
                                    <p className="text-sm text-foreground-muted">{brandData.tagline}</p>
                                )}
                            </div>
                        </div>
                    </div>
                )}
            </BaseNodeContent>

            <BaseNodeError message={errors.brand} />

            {!isSuccess && !showNewBrand && selectedBrand && (
                <BaseNodeFooter>
                    <Button
                        onClick={() => handleSelectBrand(selectedBrand)}
                        disabled={isLoading}
                        className="w-full nodrag"
                        icon={isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <ArrowRight className="w-4 h-4" />}
                        iconPosition="right"
                    >
                        {isLoading ? "Loading..." : "Continue with this Brand"}
                    </Button>
                </BaseNodeFooter>
            )}
        </BaseNode>
    );
});
