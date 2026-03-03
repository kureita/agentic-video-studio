/**
 * S3Image - A drop-in replacement for next/image that handles presigned S3 URLs.
 *
 * Automatically:
 * - Detects S3 URLs and fetches presigned versions
 * - Refreshes expired URLs on load error (403)
 * - Passes through non-S3 URLs (data URIs, blob URLs, etc.) directly
 * - Shows a subtle loading state while fetching presigned URLs
 */

"use client";

import React, { useState, useCallback } from "react";
import Image, { ImageProps } from "next/image";
import { usePresignedUrl } from "@/lib/use-presigned-url";
import { isS3Url } from "@/lib/presigned-url-cache";

interface S3ImageProps extends Omit<ImageProps, "src"> {
    src: string | null | undefined;
    fallback?: React.ReactNode;
}

export function S3Image({ src, fallback, alt, ...props }: S3ImageProps) {
    const { url, isLoading, refresh } = usePresignedUrl(src);
    const [retryCount, setRetryCount] = useState(0);
    const maxRetries = 2;

    const handleError = useCallback(() => {
        // If it's an S3 URL and we haven't exceeded retries, refresh the presigned URL
        if (src && isS3Url(src) && retryCount < maxRetries) {
            console.log(`[S3Image] Image load failed, refreshing presigned URL (retry ${retryCount + 1}/${maxRetries})`);
            setRetryCount((c) => c + 1);
            refresh();
        }
    }, [src, retryCount, refresh]);

    // Reset retry count when src changes
    React.useEffect(() => {
        setRetryCount(0);
    }, [src]);

    if (!url || isLoading) {
        return fallback || null;
    }

    return (
        <Image
            src={url}
            alt={alt || ""}
            onError={handleError}
            {...props}
        />
    );
}

export default S3Image;
