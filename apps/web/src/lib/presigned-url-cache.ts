/**
 * Presigned URL Cache
 * 
 * Caches presigned S3 URLs in memory with TTL tracking.
 * When a URL is expired (or about to expire within a buffer window),
 * it transparently fetches a fresh presigned URL from the API.
 * 
 * Flow:
 * 1. Components call `getPresignedUrl(rawOrSignedUrl)` 
 * 2. If cached and not expired → return cached signed URL
 * 3. If expired or missing → call /api/workflows/presign to get fresh URL
 * 4. Cache the fresh URL with a TTL
 */

import { api } from "./api";

// Cache entry: stores the presigned URL and when it expires
interface CacheEntry {
    presignedUrl: string;
    expiresAt: number; // Unix timestamp in ms
}

// In-memory cache: rawUrl → CacheEntry
const urlCache = new Map<string, CacheEntry>();

// Pending requests: rawUrl → Promise (dedup concurrent requests for same URL)
const pendingRequests = new Map<string, Promise<string>>();

// Presigned URLs last 1 hour (3600s) from the backend.
// We consider them expired 5 minutes early to prevent edge-case failures.
const TTL_MS = 55 * 60 * 1000; // 55 minutes (5 min buffer before actual 1hr expiry)

/**
 * Strip presigned query params from an S3 URL to get the raw/base URL.
 * This is used as the cache key.
 */
function stripPresignedParams(url: string): string {
    if (!url) return url;
    try {
        const parsed = new URL(url);
        // Check if it has AWS signing params
        if (parsed.searchParams.has("X-Amz-Algorithm")) {
            // Remove all query params to get base URL
            parsed.search = "";
            return parsed.toString();
        }
    } catch {
        // Not a valid URL, return as-is
    }
    return url;
}

/**
 * Check if a URL is an S3 URL (either raw or presigned).
 */
export function isS3Url(url: string): boolean {
    if (!url || typeof url !== "string") return false;
    return url.includes("kureita") && (url.includes("s3") || url.includes("amazonaws.com"));
}

/**
 * Check if a presigned URL is expired or about to expire.
 */
function isExpired(entry: CacheEntry): boolean {
    return Date.now() >= entry.expiresAt;
}

/**
 * Fetch fresh presigned URLs from the backend API.
 */
async function fetchPresignedUrls(urls: string[]): Promise<Record<string, string>> {
    try {
        const response = await api.post<{ urls: Record<string, string> }>("/api/workflows/presign", { urls });
        return response.data.urls;
    } catch (error) {
        console.error("[PresignedUrlCache] Failed to fetch presigned URLs:", error);
        // Return original URLs as fallback
        return Object.fromEntries(urls.map(u => [u, u]));
    }
}

/**
 * Get a presigned URL for an S3 URL.
 * 
 * - Returns the input as-is for non-S3 URLs
 * - Returns cached presigned URL if still valid
 * - Fetches a fresh presigned URL if expired or not cached
 * - Deduplicates concurrent requests for the same URL
 * 
 * @param url - Raw S3 URL or already-presigned URL  
 * @returns Fresh presigned URL
 */
export async function getPresignedUrl(url: string): Promise<string> {
    if (!isS3Url(url)) return url;

    // Use the raw (stripped) URL as the cache key
    const rawUrl = stripPresignedParams(url);

    // Check cache first
    const cached = urlCache.get(rawUrl);
    if (cached && !isExpired(cached)) {
        return cached.presignedUrl;
    }

    // Check if there's already a pending request for this URL
    const pending = pendingRequests.get(rawUrl);
    if (pending) {
        return pending;
    }

    // Fetch fresh presigned URL
    const promise = (async () => {
        try {
            const result = await fetchPresignedUrls([rawUrl]);
            const presignedUrl = result[rawUrl] || url;

            // Cache the result
            urlCache.set(rawUrl, {
                presignedUrl,
                expiresAt: Date.now() + TTL_MS,
            });

            return presignedUrl;
        } finally {
            pendingRequests.delete(rawUrl);
        }
    })();

    pendingRequests.set(rawUrl, promise);
    return promise;
}

/**
 * Get presigned URLs for multiple S3 URLs in a single batch request.
 * More efficient than calling getPresignedUrl individually.
 * 
 * @param urls - Array of raw or presigned S3 URLs
 * @returns Map of original URL → presigned URL
 */
export async function getPresignedUrls(urls: string[]): Promise<Record<string, string>> {
    const result: Record<string, string> = {};
    const urlsToFetch: string[] = [];

    for (const url of urls) {
        if (!isS3Url(url)) {
            result[url] = url;
            continue;
        }

        const rawUrl = stripPresignedParams(url);
        const cached = urlCache.get(rawUrl);

        if (cached && !isExpired(cached)) {
            result[url] = cached.presignedUrl;
        } else {
            urlsToFetch.push(rawUrl);
        }
    }

    if (urlsToFetch.length > 0) {
        const freshUrls = await fetchPresignedUrls(urlsToFetch);

        for (const [rawUrl, presignedUrl] of Object.entries(freshUrls)) {
            // Cache the result
            urlCache.set(rawUrl, {
                presignedUrl,
                expiresAt: Date.now() + TTL_MS,
            });

            // Map back to original URLs
            for (const originalUrl of urls) {
                if (stripPresignedParams(originalUrl) === rawUrl) {
                    result[originalUrl] = presignedUrl;
                }
            }
        }
    }

    return result;
}

/**
 * Invalidate a cached URL, forcing a refresh on next access.
 */
export function invalidateUrl(url: string): void {
    const rawUrl = stripPresignedParams(url);
    urlCache.delete(rawUrl);
}

/**
 * Clear the entire URL cache.
 */
export function clearUrlCache(): void {
    urlCache.clear();
    pendingRequests.clear();
}
