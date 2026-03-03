/**
 * React hook for using presigned S3 URLs in components.
 * 
 * Automatically handles:
 * - Detecting S3 URLs
 * - Returning cached presigned URLs
 * - Refreshing expired presigned URLs
 * - Loading states during URL fetching
 * - Error recovery with retry
 */

import { useState, useEffect, useCallback, useRef } from "react";
import { getPresignedUrl, isS3Url, invalidateUrl } from "./presigned-url-cache";

interface UsePresignedUrlResult {
    url: string | null;
    isLoading: boolean;
    error: string | null;
    refresh: () => void;
}

/**
 * Hook to get a presigned URL for a given source URL.
 * 
 * Usage:
 * ```tsx
 * const { url, isLoading } = usePresignedUrl(s3Url);
 * return isLoading ? <Spinner /> : <img src={url} />;
 * ```
 * 
 * @param sourceUrl - Raw S3 URL, presigned URL, or non-S3 URL
 * @returns Object with the presigned URL, loading state, and error
 */
export function usePresignedUrl(sourceUrl: string | null | undefined): UsePresignedUrlResult {
    const [url, setUrl] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [refreshCount, setRefreshCount] = useState(0);
    const mountedRef = useRef(true);

    useEffect(() => {
        mountedRef.current = true;
        return () => { mountedRef.current = false; };
    }, []);

    useEffect(() => {
        if (!sourceUrl) {
            setUrl(null);
            setIsLoading(false);
            setError(null);
            return;
        }

        // Non-S3 URLs (data URIs, blob URLs, etc.) pass through immediately
        if (!isS3Url(sourceUrl)) {
            setUrl(sourceUrl);
            setIsLoading(false);
            setError(null);
            return;
        }

        let cancelled = false;
        setIsLoading(true);
        setError(null);

        getPresignedUrl(sourceUrl)
            .then((presignedUrl) => {
                if (!cancelled && mountedRef.current) {
                    setUrl(presignedUrl);
                    setIsLoading(false);
                }
            })
            .catch((err) => {
                if (!cancelled && mountedRef.current) {
                    console.error("[usePresignedUrl] Failed to get presigned URL:", err);
                    setError(err?.message || "Failed to get presigned URL");
                    // Fall back to the original URL
                    setUrl(sourceUrl);
                    setIsLoading(false);
                }
            });

        return () => { cancelled = true; };
    }, [sourceUrl, refreshCount]);

    const refresh = useCallback(() => {
        if (sourceUrl) {
            invalidateUrl(sourceUrl);
        }
        setRefreshCount((c) => c + 1);
    }, [sourceUrl]);

    return { url, isLoading, error, refresh };
}
