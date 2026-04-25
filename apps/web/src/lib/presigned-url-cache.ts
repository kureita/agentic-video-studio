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
import { publicWorkflowApi } from "./workflow-api";

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

let _publicMode = false;

/** Switch presign requests between authenticated and public endpoints. */
export function setPresignPublicMode(enabled: boolean) {
    _publicMode = enabled;
}

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
 * Uses the public endpoint when in public mode (no auth required).
 *
 * Throws on failure so callers can avoid caching the fallback as if it were
 * a fresh signature (a failed lookup must not poison the cache for 55 min).
 */
async function fetchPresignedUrls(urls: string[]): Promise<Record<string, string>> {
    if (_publicMode) {
        const response = await publicWorkflowApi.presign(urls);
        return response.data.urls;
    }
    const response = await api.post<{ urls: Record<string, string> }>("/api/workflows/presign", { urls });
    return response.data.urls;
}

// Coalesce concurrent fetches across all callers into a single batched POST,
// so that 24 nodes calling getPresignedUrl in the same tick produce 1 request
// instead of 24. Without this, Lambda throttles and returns 503.
let _pendingBatch: {
    urls: Set<string>;
    promise: Promise<Record<string, string>>;
    resolve: (value: Record<string, string>) => void;
    reject: (reason: unknown) => void;
} | null = null;

function scheduleBatchFetch(urls: string[]): Promise<Record<string, string>> {
    if (!_pendingBatch) {
        let resolve!: (value: Record<string, string>) => void;
        let reject!: (reason: unknown) => void;
        const promise = new Promise<Record<string, string>>((res, rej) => {
            resolve = res;
            reject = rej;
        });
        const batch = { urls: new Set<string>(), promise, resolve, reject };
        _pendingBatch = batch;
        // Flush after the current microtask so all synchronous getPresignedUrl
        // calls in the same render cycle land in this batch.
        queueMicrotask(() => {
            _pendingBatch = null;
            const urlList = Array.from(batch.urls);
            fetchPresignedUrls(urlList).then(batch.resolve, batch.reject);
        });
    }
    for (const u of urls) _pendingBatch.urls.add(u);
    return _pendingBatch.promise;
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

    // Fetch fresh presigned URL via the shared batch
    const promise = (async () => {
        try {
            const result = await scheduleBatchFetch([rawUrl]);
            const presignedUrl = result[rawUrl];

            if (!presignedUrl) {
                // Server didn't return a signature for this URL. Don't cache —
                // a future call should retry rather than be locked into a bad
                // value for 55 minutes.
                return url;
            }

            urlCache.set(rawUrl, {
                presignedUrl,
                expiresAt: Date.now() + TTL_MS,
            });
            return presignedUrl;
        } catch (err) {
            // Network/CORS/5xx — don't cache the failure. Return the original
            // URL so the image at least attempts to load with whatever signature
            // it already had, and the next render can retry.
            console.error("[PresignedUrlCache] Failed to fetch presigned URL:", err);
            return url;
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
        let freshUrls: Record<string, string> = {};
        try {
            freshUrls = await scheduleBatchFetch(urlsToFetch);
        } catch (err) {
            console.error("[PresignedUrlCache] Batch presign failed:", err);
        }

        for (const rawUrl of urlsToFetch) {
            const presignedUrl = freshUrls[rawUrl];
            // Only cache successes — a missing/empty signature means the
            // request failed and should be retried later, not pinned for 55 min.
            if (presignedUrl) {
                urlCache.set(rawUrl, {
                    presignedUrl,
                    expiresAt: Date.now() + TTL_MS,
                });
            }
            for (const originalUrl of urls) {
                if (stripPresignedParams(originalUrl) === rawUrl) {
                    result[originalUrl] = presignedUrl || originalUrl;
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
