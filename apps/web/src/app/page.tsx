"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { Button } from "@/components/ui";
import { 
  ArrowRight, 
  Play, 
  Sparkles, 
  Wand2, 
  Film, 
  Mic2, 
  Palette 
} from "lucide-react";

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-background overflow-hidden">
      {/* Ambient Background */}
      <div className="fixed inset-0 bg-gradient-mesh opacity-60 pointer-events-none" />
      
      {/* Header */}
      <header className="relative z-10">
        <div className="container-wide flex items-center justify-between h-20">
          <Link href="/" className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-foreground flex items-center justify-center">
              <Sparkles className="w-5 h-5 text-background" />
            </div>
            <span className="font-display text-2xl font-semibold tracking-tight">
              Kureita
            </span>
          </Link>
          <div className="flex items-center gap-4">
            <Link href="/dashboard">
              <Button variant="ghost">Dashboard</Button>
            </Link>
            <Link href="/projects/new">
              <Button icon={<ArrowRight className="w-4 h-4" />} iconPosition="right">
                Get Started
              </Button>
            </Link>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <main className="relative z-10">
        <section className="container-wide pt-24 pb-32">
          <div className="max-w-4xl mx-auto text-center">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6 }}
            >
              <span className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-accent-muted text-accent text-sm font-medium mb-8">
                <Wand2 className="w-4 h-4" />
                AI-Powered Video Production
              </span>
            </motion.div>

            <motion.h1
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.1 }}
              className="font-display text-display-lg md:text-display-xl text-foreground mb-6"
            >
              Transform your brand into{" "}
              <span className="text-gradient">cinematic stories</span>
            </motion.h1>

            <motion.p
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.2 }}
              className="text-xl text-foreground-muted max-w-2xl mx-auto mb-12 leading-relaxed"
            >
              Give us your website, and our AI agents will craft compelling promotional 
              videos — from script to screen. No expertise required.
            </motion.p>

            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.3 }}
              className="flex items-center justify-center gap-4"
            >
              <Link href="/projects/new">
                <Button size="lg" icon={<ArrowRight className="w-5 h-5" />} iconPosition="right">
                  Start Creating
                </Button>
              </Link>
              <Button variant="outline" size="lg" icon={<Play className="w-5 h-5" />}>
                Watch Demo
              </Button>
            </motion.div>
          </div>

          {/* Preview Card */}
          <motion.div
            initial={{ opacity: 0, y: 40 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.5 }}
            className="mt-24 max-w-5xl mx-auto"
          >
            <div className="relative rounded-2xl overflow-hidden shadow-elevated border border-border">
              <div className="aspect-video bg-gradient-to-br from-background-secondary to-background-tertiary flex items-center justify-center">
                <div className="text-center">
                  <div className="w-20 h-20 rounded-full bg-foreground/10 flex items-center justify-center mx-auto mb-4">
                    <Play className="w-8 h-8 text-foreground" />
                  </div>
                  <p className="text-foreground-muted">Video preview</p>
                </div>
              </div>
              {/* Floating Elements */}
              <div className="absolute top-6 left-6 glass-elevated rounded-lg px-4 py-3 animate-float">
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                  <span className="text-sm font-medium">AI Generating...</span>
                </div>
              </div>
            </div>
          </motion.div>
        </section>

        {/* Features Section */}
        <section className="container-wide py-24 border-t border-border">
          <div className="text-center mb-16">
            <h2 className="font-display text-display-sm text-foreground mb-4">
              Everything handled by AI
            </h2>
            <p className="text-foreground-muted text-lg max-w-xl mx-auto">
              From research to final render — our agents work together to create your video
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-6">
            {[
              {
                icon: Wand2,
                title: "Story & Script",
                description: "AI analyzes your brand and crafts compelling narratives that resonate with your audience",
              },
              {
                icon: Film,
                title: "Video Generation",
                description: "Powered by Veo 3.1 to create stunning, high-fidelity video clips with natural motion",
              },
              {
                icon: Mic2,
                title: "Voice & Audio",
                description: "Professional voiceovers and sound design using ElevenLabs' natural speech synthesis",
              },
              {
                icon: Palette,
                title: "Visual Design",
                description: "Automatic color grading, typography, and effects that match your brand identity",
              },
              {
                icon: Sparkles,
                title: "Smart Editing",
                description: "Intelligent scene transitions, pacing, and composition using Remotion",
              },
              {
                icon: ArrowRight,
                title: "One-Click Export",
                description: "Export in any format — ready for social media, web, or presentations",
              },
            ].map((feature, index) => (
              <motion.div
                key={feature.title}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5, delay: index * 0.1 }}
                className="group p-8 rounded-2xl bg-surface border border-border hover:border-foreground-subtle transition-all duration-300"
              >
                <div className="w-12 h-12 rounded-xl bg-background-secondary flex items-center justify-center mb-5 group-hover:bg-accent-muted transition-colors">
                  <feature.icon className="w-6 h-6 text-foreground group-hover:text-accent transition-colors" />
                </div>
                <h3 className="text-lg font-semibold text-foreground mb-2">
                  {feature.title}
                </h3>
                <p className="text-foreground-muted leading-relaxed">
                  {feature.description}
                </p>
              </motion.div>
            ))}
          </div>
        </section>

        {/* CTA Section */}
        <section className="container-wide py-24">
          <div className="relative rounded-3xl overflow-hidden">
            <div className="absolute inset-0 bg-foreground" />
            <div className="relative z-10 px-12 py-20 text-center">
              <h2 className="font-display text-display-sm text-background mb-4">
                Ready to create?
              </h2>
              <p className="text-background/70 text-lg mb-8 max-w-md mx-auto">
                Start with your website URL and let our AI handle the rest
              </p>
              <Link href="/projects/new">
                <Button 
                  variant="secondary" 
                  size="lg" 
                  icon={<ArrowRight className="w-5 h-5" />} 
                  iconPosition="right"
                >
                  Create Your First Video
                </Button>
              </Link>
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="relative z-10 border-t border-border py-8">
        <div className="container-wide flex items-center justify-between text-sm text-foreground-subtle">
          <p>© 2026 Kureita. All rights reserved.</p>
          <div className="flex items-center gap-6">
            <Link href="#" className="hover:text-foreground transition-colors">
              Privacy
            </Link>
            <Link href="#" className="hover:text-foreground transition-colors">
              Terms
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}

