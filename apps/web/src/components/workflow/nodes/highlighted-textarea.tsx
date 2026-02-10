import React, { useRef, useEffect, useCallback } from "react";
import { cn } from "@/lib/utils";

/**
 * A textarea with a highlight backdrop that visually differentiates
 * @Text #N (and similar node references) from the rest of the text.
 * 
 * Works by layering a transparent div behind a transparent-background textarea.
 * The div renders the same text with highlighted spans, while the textarea handles input.
 */
interface HighlightedTextareaProps {
    value: string;
    onChange: (e: React.ChangeEvent<HTMLTextAreaElement>) => void;
    onKeyDown?: (e: React.KeyboardEvent<HTMLTextAreaElement>) => void;
    placeholder?: string;
    className?: string;
    textareaRef?: React.RefObject<HTMLTextAreaElement | null>;
}

// Regex to match @Text #N, @Image Gen #N, @Video Gen #N etc.
const REF_PATTERN = /@(?:Text|Image Gen|Video Gen|Vision|Editor Agent|Media Upload|Audio Gen)\s*#\d+/g;

function renderHighlightedContent(text: string): React.ReactNode[] {
    const parts: React.ReactNode[] = [];
    let lastIndex = 0;

    const regex = new RegExp(REF_PATTERN.source, 'g');
    let match: RegExpExecArray | null;

    while ((match = regex.exec(text)) !== null) {
        // Push text before match (invisible, just for spacing)
        if (match.index > lastIndex) {
            parts.push(
                <span key={`t-${lastIndex}`} className="text-transparent">
                    {text.slice(lastIndex, match.index)}
                </span>
            );
        }

        // Push highlighted match - visible background
        parts.push(
            <mark
                key={`r-${match.index}`}
                className="bg-blue-500/20 text-transparent rounded-sm px-[1px] mx-[-1px]"
            >
                {match[0]}
            </mark>
        );

        lastIndex = match.index + match[0].length;
    }

    // Push remaining text (invisible)
    if (lastIndex < text.length) {
        parts.push(
            <span key={`t-${lastIndex}`} className="text-transparent">
                {text.slice(lastIndex)}
            </span>
        );
    }

    // Trailing newline fix
    if (text.endsWith('\n') || text === '') {
        parts.push(<span key="trailing">{'\n '}</span>);
    }

    return parts;
}

export function HighlightedTextarea({
    value,
    onChange,
    onKeyDown,
    placeholder,
    className,
    textareaRef: externalRef,
}: HighlightedTextareaProps) {
    const internalRef = useRef<HTMLTextAreaElement>(null);
    const backdropRef = useRef<HTMLDivElement>(null);
    const ref = externalRef || internalRef;

    // Sync scroll between textarea and backdrop
    const syncScroll = useCallback(() => {
        const textarea = ref.current;
        const backdrop = backdropRef.current;
        if (!textarea || !backdrop) return;
        backdrop.scrollTop = textarea.scrollTop;
        backdrop.scrollLeft = textarea.scrollLeft;
    }, [ref]);

    useEffect(() => {
        const textarea = ref.current;
        if (!textarea) return;

        textarea.addEventListener('scroll', syncScroll);
        return () => textarea.removeEventListener('scroll', syncScroll);
    }, [ref, syncScroll]);

    const hasReferences = REF_PATTERN.test(value);

    return (
        <div className="relative">
            {/* Backdrop - renders highlighted references behind the textarea */}
            {hasReferences && (
                <div
                    ref={backdropRef}
                    className={cn(
                        className,
                        "!absolute !inset-0 pointer-events-none whitespace-pre-wrap break-words overflow-hidden z-0"
                    )}
                    aria-hidden="true"
                    style={{ color: 'transparent' }}
                >
                    {renderHighlightedContent(value)}
                </div>
            )}

            {/* Actual textarea - transparent background where references are */}
            <textarea
                ref={ref}
                className={cn(
                    className,
                    "relative z-[1]",
                    hasReferences ? "bg-transparent" : ""
                )}
                value={value}
                onChange={onChange}
                onKeyDown={onKeyDown}
                placeholder={placeholder}
            />
        </div>
    );
}
