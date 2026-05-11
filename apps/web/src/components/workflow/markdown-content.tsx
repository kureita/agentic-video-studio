"use client";

import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { cn } from "@/lib/utils";
import {
    Type,
    Image as ImageIcon,
    Video,
    Eye,
    Clapperboard,
    Upload,
    Music,
} from "lucide-react";

// ============================================
// Reference pattern matching
// ============================================

// Regex to match @Text #N, @Image Gen #N, @Video Gen #N etc.
const REF_PATTERN = /@(?:Text|Image Gen|Video Gen|Vision|Media Assistant|Editor Agent|Media Upload|Upload|Audio Gen)\s*#\d+/g;

function getRefIcon(ref: string) {
    if (ref.startsWith("@Text")) return <Type className="w-2.5 h-2.5" />;
    if (ref.startsWith("@Image Gen")) return <ImageIcon className="w-2.5 h-2.5" />;
    if (ref.startsWith("@Video Gen")) return <Video className="w-2.5 h-2.5" />;
    if (ref.startsWith("@Vision")) return <Eye className="w-2.5 h-2.5" />;
    if (ref.startsWith("@Editor Agent")) return <Clapperboard className="w-2.5 h-2.5" />;
    if (ref.startsWith("@Media Assistant")) return <Eye className="w-2.5 h-2.5" />;
    if (ref.startsWith("@Media Upload") || ref.startsWith("@Upload")) return <Upload className="w-2.5 h-2.5" />;
    if (ref.startsWith("@Audio Gen")) return <Music className="w-2.5 h-2.5" />;
    return <Type className="w-2.5 h-2.5" />;
}

function getRefColor(ref: string) {
    if (ref.startsWith("@Text")) return "bg-blue-500/15 text-blue-400 border-blue-500/25";
    if (ref.startsWith("@Image Gen")) return "bg-purple-500/15 text-purple-400 border-purple-500/25";
    if (ref.startsWith("@Video Gen")) return "bg-emerald-500/15 text-emerald-400 border-emerald-500/25";
    if (ref.startsWith("@Vision")) return "bg-amber-500/15 text-amber-400 border-amber-500/25";
    if (ref.startsWith("@Editor Agent")) return "bg-rose-500/15 text-rose-400 border-rose-500/25";
    if (ref.startsWith("@Media Assistant")) return "bg-indigo-500/15 text-indigo-400 border-indigo-500/25";
    if (ref.startsWith("@Media Upload") || ref.startsWith("@Upload")) return "bg-cyan-500/15 text-cyan-400 border-cyan-500/25";
    if (ref.startsWith("@Audio Gen")) return "bg-orange-500/15 text-orange-400 border-orange-500/25";
    return "bg-blue-500/15 text-blue-400 border-blue-500/25";
}

// ============================================
// HighlightedReferences - Inline reference highlighting
// ============================================

/**
 * Renders text with highlighted inline reference badges for @NodeType #N patterns.
 * Use this for lightweight reference-only highlighting (no markdown).
 */
export function HighlightedReferences({
    text,
    className,
}: {
    text: string;
    className?: string;
}) {
    const parts: React.ReactNode[] = [];
    let lastIndex = 0;

    const regex = new RegExp(REF_PATTERN.source, "g");
    let match: RegExpExecArray | null;

    while ((match = regex.exec(text)) !== null) {
        // Push text before match
        if (match.index > lastIndex) {
            parts.push(
                <span key={`t-${lastIndex}`}>
                    {text.slice(lastIndex, match.index)}
                </span>
            );
        }

        const refText = match[0];

        // Push highlighted reference badge
        parts.push(
            <span
                key={`r-${match.index}`}
                className={cn(
                    "inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md text-[11px] font-medium border align-baseline",
                    "transition-colors duration-150",
                    getRefColor(refText)
                )}
            >
                {getRefIcon(refText)}
                <span>{refText.slice(1)}</span>
            </span>
        );

        lastIndex = match.index + match[0].length;
    }

    // Push remaining text
    if (lastIndex < text.length) {
        parts.push(
            <span key={`t-${lastIndex}`}>
                {text.slice(lastIndex)}
            </span>
        );
    }

    // If no references found, just return the text
    if (parts.length === 0) {
        return <span className={className}>{text}</span>;
    }

    return <span className={className}>{parts}</span>;
}

// ============================================
// Process text to highlight references within markdown text nodes
// ============================================

function processTextWithReferences(text: string): React.ReactNode {
    const regex = new RegExp(REF_PATTERN.source, "g");
    const parts: React.ReactNode[] = [];
    let lastIndex = 0;
    let match: RegExpExecArray | null;

    while ((match = regex.exec(text)) !== null) {
        if (match.index > lastIndex) {
            parts.push(text.slice(lastIndex, match.index));
        }

        const refText = match[0];
        parts.push(
            <span
                key={`ref-${match.index}`}
                className={cn(
                    "inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md text-[11px] font-medium border align-baseline",
                    "transition-colors duration-150",
                    getRefColor(refText)
                )}
            >
                {getRefIcon(refText)}
                <span>{refText.slice(1)}</span>
            </span>
        );

        lastIndex = match.index + match[0].length;
    }

    if (lastIndex < text.length) {
        parts.push(text.slice(lastIndex));
    }

    if (parts.length === 0) return text;
    return <>{parts}</>;
}

// ============================================
// MarkdownContent - Full markdown + reference highlighting
// ============================================

/**
 * Renders markdown content with syntax highlighting for code blocks,
 * tables, lists, etc. Also highlights @NodeType #N references as inline badges.
 */
export function MarkdownContent({
    content,
    className,
    size = "sm",
}: {
    content: string;
    className?: string;
    size?: "xs" | "sm";
}) {
    const textSize = size === "xs" ? "text-[11px]" : "text-[13px]";
    const headingBase = size === "xs" ? "text-[12px]" : "text-[14px]";

    return (
        <div className={cn("markdown-content", className)}>
            <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                    // Headings
                    h1: ({ children }) => (
                        <h1 className={cn(headingBase, "font-bold mt-3 mb-1.5 text-foreground")}>
                            {children}
                        </h1>
                    ),
                    h2: ({ children }) => (
                        <h2 className={cn(headingBase, "font-semibold mt-2.5 mb-1 text-foreground")}>
                            {children}
                        </h2>
                    ),
                    h3: ({ children }) => (
                        <h3 className={cn(textSize, "font-semibold mt-2 mb-1 text-foreground")}>
                            {children}
                        </h3>
                    ),

                    // Paragraphs - intercept text children to highlight references
                    p: ({ children }) => (
                        <p className={cn(textSize, "leading-relaxed mb-2 last:mb-0")}>
                            {React.Children.map(children, (child) => {
                                if (typeof child === "string") {
                                    return processTextWithReferences(child);
                                }
                                return child;
                            })}
                        </p>
                    ),

                    // Inline code
                    code: ({ children, className: codeClassName }) => {
                        // Check if this is a code block (has language class) or inline code
                        const isBlock = codeClassName?.startsWith("language-");
                        if (isBlock) {
                            return (
                                <code className={cn(codeClassName, "block")}>
                                    {children}
                                </code>
                            );
                        }
                        return (
                            <code className="px-1 py-0.5 rounded bg-muted/80 text-[11px] font-mono text-foreground/80 border border-border/30">
                                {children}
                            </code>
                        );
                    },

                    // Code blocks
                    pre: ({ children }) => (
                        <pre className="my-2 p-3 rounded-lg bg-muted/50 border border-border/30 overflow-x-auto text-[11px] font-mono leading-relaxed">
                            {children}
                        </pre>
                    ),

                    // Lists
                    ul: ({ children }) => (
                        <ul className={cn(textSize, "list-disc pl-4 mb-2 space-y-0.5")}>
                            {children}
                        </ul>
                    ),
                    ol: ({ children }) => (
                        <ol className={cn(textSize, "list-decimal pl-4 mb-2 space-y-0.5")}>
                            {children}
                        </ol>
                    ),
                    li: ({ children }) => (
                        <li className="leading-relaxed">
                            {React.Children.map(children, (child) => {
                                if (typeof child === "string") {
                                    return processTextWithReferences(child);
                                }
                                return child;
                            })}
                        </li>
                    ),

                    // Bold / Italic
                    strong: ({ children }) => (
                        <strong className="font-semibold text-foreground">{children}</strong>
                    ),
                    em: ({ children }) => (
                        <em className="italic">{children}</em>
                    ),

                    // Links
                    a: ({ href, children }) => (
                        <a
                            href={href}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-blue-400 hover:text-blue-300 underline underline-offset-2 decoration-blue-400/30 hover:decoration-blue-300/50 transition-colors"
                        >
                            {children}
                        </a>
                    ),

                    // Blockquotes
                    blockquote: ({ children }) => (
                        <blockquote className="border-l-2 border-violet-500/30 pl-3 my-2 text-muted-foreground/80 italic">
                            {children}
                        </blockquote>
                    ),

                    // Tables
                    table: ({ children }) => (
                        <div className="my-2 overflow-x-auto rounded-lg border border-border/30">
                            <table className="w-full text-[11px]">
                                {children}
                            </table>
                        </div>
                    ),
                    thead: ({ children }) => (
                        <thead className="bg-muted/40 border-b border-border/30">
                            {children}
                        </thead>
                    ),
                    th: ({ children }) => (
                        <th className="px-3 py-1.5 text-left font-semibold text-foreground/80">
                            {children}
                        </th>
                    ),
                    td: ({ children }) => (
                        <td className="px-3 py-1.5 border-t border-border/20">
                            {children}
                        </td>
                    ),

                    // Horizontal rule
                    hr: () => (
                        <hr className="my-3 border-border/30" />
                    ),
                }}
            >
                {content}
            </ReactMarkdown>
        </div>
    );
}
