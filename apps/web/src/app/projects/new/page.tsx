"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Header } from "@/components/layout";
import { Button, Card, Input, Textarea } from "@/components/ui";
import { 
  ArrowLeft,
  ArrowRight,
  Globe,
  Sparkles,
  Clock,
  Film,
  Palette,
  Users,
  Check,
  Loader2
} from "lucide-react";
import { projectsApi, CreateProjectData } from "@/lib/api";

const videoStyles = [
  { id: "cinematic", label: "Cinematic", description: "High-end, movie-like quality" },
  { id: "minimal", label: "Minimal", description: "Clean, modern, and simple" },
  { id: "energetic", label: "Energetic", description: "Dynamic and fast-paced" },
  { id: "elegant", label: "Elegant", description: "Sophisticated and premium" },
  { id: "playful", label: "Playful", description: "Fun and creative" },
  { id: "corporate", label: "Corporate", description: "Professional and trustworthy" },
];

const durationOptions = [
  { value: 15, label: "15s", description: "Social media" },
  { value: 30, label: "30s", description: "Standard promo" },
  { value: 60, label: "60s", description: "Detailed story" },
  { value: 90, label: "90s", description: "Full narrative" },
];

export default function NewProjectPage() {
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Form state
  const [websiteUrl, setWebsiteUrl] = useState("");
  const [brandName, setBrandName] = useState("");
  const [description, setDescription] = useState("");
  const [targetAudience, setTargetAudience] = useState("");
  const [videoDuration, setVideoDuration] = useState(30);
  const [style, setStyle] = useState("cinematic");

  const totalSteps = 3;

  const isStep1Valid = websiteUrl.length > 0 && websiteUrl.startsWith("http");

  const handleSubmit = async () => {
    setIsSubmitting(true);
    setError(null);
    
    try {
      const data: CreateProjectData = {
        website_url: websiteUrl,
        brand_name: brandName || undefined,
        description: description || undefined,
        target_audience: targetAudience || undefined,
        video_duration: videoDuration,
        style: style,
      };
      
      const response = await projectsApi.create(data);
      const projectId = response.data.id;
      
      // Start the generation process
      await projectsApi.start(projectId);
      
      // Redirect to project page
      router.push(`/projects/${projectId}`);
    } catch (err: unknown) {
      console.error("Failed to create project:", err);
      const errorMessage = err instanceof Error ? err.message : "Failed to create project. Please try again.";
      setError(errorMessage);
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-background">
      <Header />
      
      <main className="container-narrow py-12">
        {/* Back Button */}
        <Link 
          href="/dashboard" 
          className="inline-flex items-center gap-2 text-foreground-muted hover:text-foreground transition-colors mb-8"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Dashboard
        </Link>

        {/* Header */}
        <div className="text-center mb-12">
          <h1 className="font-display text-display-md text-foreground mb-4">
            Create New Video
          </h1>
          <p className="text-foreground-muted text-lg">
            Tell us about your brand and let AI craft your promo
          </p>
        </div>

        {/* Progress Steps */}
        <div className="flex items-center justify-center gap-4 mb-12">
          {[1, 2, 3].map((s) => (
            <div key={s} className="flex items-center gap-4">
              <div
                className={`w-10 h-10 rounded-full flex items-center justify-center font-medium transition-all ${
                  s < step
                    ? "bg-foreground text-background"
                    : s === step
                    ? "bg-accent text-foreground"
                    : "bg-background-secondary text-foreground-muted"
                }`}
              >
                {s < step ? <Check className="w-5 h-5" /> : s}
              </div>
              {s < totalSteps && (
                <div
                  className={`w-16 h-0.5 ${
                    s < step ? "bg-foreground" : "bg-border"
                  }`}
                />
              )}
            </div>
          ))}
        </div>

        {/* Error Message */}
        {error && (
          <div className="max-w-xl mx-auto mb-6 p-4 rounded-lg bg-red-500/10 border border-red-500/20 text-red-600 text-sm">
            {error}
          </div>
        )}

        {/* Step 1: Website URL */}
        {step === 1 && (
          <div className="max-w-xl mx-auto">
            <Card variant="elevated" className="p-8">
              <div className="w-14 h-14 rounded-2xl bg-accent-muted flex items-center justify-center mb-6">
                <Globe className="w-7 h-7 text-accent" />
              </div>
              
              <h2 className="text-xl font-semibold text-foreground mb-2">
                Enter your website
              </h2>
              <p className="text-foreground-muted mb-8">
                We&apos;ll analyze your website to understand your brand
              </p>

              <div className="space-y-6">
                <Input
                  label="Website URL"
                  placeholder="https://yourbrand.com"
                  value={websiteUrl}
                  onChange={(e) => setWebsiteUrl(e.target.value)}
                  icon={<Globe className="w-4 h-4" />}
                />

                <Input
                  label="Brand Name (optional)"
                  placeholder="Your Brand"
                  value={brandName}
                  onChange={(e) => setBrandName(e.target.value)}
                  hint="We'll auto-detect this if not provided"
                />
              </div>

              <div className="flex justify-end mt-8">
                <Button
                  onClick={() => setStep(2)}
                  disabled={!isStep1Valid}
                  icon={<ArrowRight className="w-4 h-4" />}
                  iconPosition="right"
                >
                  Continue
                </Button>
              </div>
            </Card>
          </div>
        )}

        {/* Step 2: Video Style */}
        {step === 2 && (
          <div className="max-w-3xl mx-auto">
            <Card variant="elevated" className="p-8">
              <div className="flex items-start gap-6 mb-8">
                <div className="w-14 h-14 rounded-2xl bg-accent-muted flex items-center justify-center flex-shrink-0">
                  <Palette className="w-7 h-7 text-accent" />
                </div>
                <div>
                  <h2 className="text-xl font-semibold text-foreground mb-2">
                    Choose your style
                  </h2>
                  <p className="text-foreground-muted">
                    Select the visual style that best represents your brand
                  </p>
                </div>
              </div>

              <div className="grid md:grid-cols-3 gap-4 mb-8">
                {videoStyles.map((s) => (
                  <button
                    key={s.id}
                    type="button"
                    onClick={() => setStyle(s.id)}
                    className={`p-5 rounded-xl border-2 text-left transition-all ${
                      style === s.id
                        ? "border-foreground bg-background-secondary"
                        : "border-border hover:border-foreground-subtle"
                    }`}
                  >
                    <h3 className="font-medium text-foreground mb-1">
                      {s.label}
                    </h3>
                    <p className="text-sm text-foreground-muted">
                      {s.description}
                    </p>
                  </button>
                ))}
              </div>

              {/* Duration */}
              <div className="mb-8">
                <label className="block text-sm font-medium text-foreground mb-3">
                  Video Duration
                </label>
                <div className="flex gap-3">
                  {durationOptions.map((option) => (
                    <button
                      key={option.value}
                      type="button"
                      onClick={() => setVideoDuration(option.value)}
                      className={`flex-1 p-4 rounded-xl border-2 text-center transition-all ${
                        videoDuration === option.value
                          ? "border-foreground bg-background-secondary"
                          : "border-border hover:border-foreground-subtle"
                      }`}
                    >
                      <p className="text-lg font-semibold text-foreground">
                        {option.label}
                      </p>
                      <p className="text-xs text-foreground-muted">
                        {option.description}
                      </p>
                    </button>
                  ))}
                </div>
              </div>

              <div className="flex justify-between">
                <Button
                  variant="ghost"
                  onClick={() => setStep(1)}
                  icon={<ArrowLeft className="w-4 h-4" />}
                >
                  Back
                </Button>
                <Button
                  onClick={() => setStep(3)}
                  icon={<ArrowRight className="w-4 h-4" />}
                  iconPosition="right"
                >
                  Continue
                </Button>
              </div>
            </Card>
          </div>
        )}

        {/* Step 3: Additional Details */}
        {step === 3 && (
          <div className="max-w-xl mx-auto">
            <Card variant="elevated" className="p-8">
              <div className="w-14 h-14 rounded-2xl bg-accent-muted flex items-center justify-center mb-6">
                <Sparkles className="w-7 h-7 text-accent" />
              </div>
              
              <h2 className="text-xl font-semibold text-foreground mb-2">
                Final details
              </h2>
              <p className="text-foreground-muted mb-8">
                Help our AI understand your goals better
              </p>

              <div className="space-y-6">
                <Input
                  label="Target Audience"
                  placeholder="e.g., Tech-savvy millennials, small business owners"
                  value={targetAudience}
                  onChange={(e) => setTargetAudience(e.target.value)}
                  icon={<Users className="w-4 h-4" />}
                />

                <Textarea
                  label="Additional Notes (optional)"
                  placeholder="Any specific messages, promotions, or details you want to highlight..."
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  hint="Our AI will incorporate these into the story"
                />
              </div>

              {/* Summary */}
              <div className="mt-8 p-5 rounded-xl bg-background-secondary">
                <h4 className="text-sm font-medium text-foreground mb-3">
                  Project Summary
                </h4>
                <div className="space-y-2 text-sm">
                  <div className="flex items-center gap-3">
                    <Globe className="w-4 h-4 text-foreground-subtle" />
                    <span className="text-foreground-muted">
                      {websiteUrl || "No URL"}
                    </span>
                  </div>
                  <div className="flex items-center gap-3">
                    <Palette className="w-4 h-4 text-foreground-subtle" />
                    <span className="text-foreground-muted capitalize">
                      {style} style
                    </span>
                  </div>
                  <div className="flex items-center gap-3">
                    <Clock className="w-4 h-4 text-foreground-subtle" />
                    <span className="text-foreground-muted">
                      {videoDuration} seconds
                    </span>
                  </div>
                </div>
              </div>

              <div className="flex justify-between mt-8">
                <Button
                  variant="ghost"
                  onClick={() => setStep(2)}
                  icon={<ArrowLeft className="w-4 h-4" />}
                >
                  Back
                </Button>
                <Button
                  onClick={handleSubmit}
                  disabled={isSubmitting}
                  icon={isSubmitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Film className="w-4 h-4" />}
                >
                  {isSubmitting ? "Creating..." : "Create Video"}
                </Button>
              </div>
            </Card>
          </div>
        )}
      </main>
    </div>
  );
}
