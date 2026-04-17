export type MediaKind = "image" | "video" | "audio" | "unknown";

const IMAGE_EXT_RE = /\.(jpg|jpeg|png|webp|gif|bmp|svg|heic|heif)(\?|$)/i;
const VIDEO_EXT_RE = /\.(mp4|mov|webm|avi|mkv|m4v)(\?|$)/i;
const AUDIO_EXT_RE = /\.(mp3|wav|ogg|flac|aac|m4a|weba)(\?|$)/i;

function normalize(value: unknown): string {
  return typeof value === "string" ? value.trim().toLowerCase() : "";
}

function safeDecodeUrl(value: string): string {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

export function mediaKindFromMime(mimeType: unknown): MediaKind {
  const mime = normalize(mimeType);
  if (!mime) return "unknown";
  if (mime.startsWith("image/")) return "image";
  if (mime.startsWith("video/")) return "video";
  if (mime.startsWith("audio/")) return "audio";
  return "unknown";
}

export function inferMediaKind(params: {
  mimeType?: unknown;
  assetCategory?: unknown;
  url?: unknown;
  nodeData?: Record<string, unknown> | null;
  nodeType?: unknown;
}): MediaKind {
  const fromMime = mediaKindFromMime(params.mimeType);
  if (fromMime !== "unknown") return fromMime;

  const category = normalize(params.assetCategory);
  if (category.includes("image")) return "image";
  if (category.includes("video")) return "video";
  if (category.includes("audio")) return "audio";

  const nodeMediaType = normalize(params.nodeData?.mediaType);
  if (nodeMediaType === "image" || nodeMediaType === "video" || nodeMediaType === "audio") {
    return nodeMediaType;
  }

  const nodeType = normalize(params.nodeType);
  if (nodeType === "imagegen") return "image";
  if (nodeType === "videogen" || nodeType === "editoragent") return "video";
  if (nodeType === "audiogen") return "audio";

  const rawUrl = normalize(params.url);
  if (!rawUrl) return "unknown";
  const decodedUrl = safeDecodeUrl(rawUrl);

  if (decodedUrl.startsWith("data:image/")) return "image";
  if (decodedUrl.startsWith("data:video/")) return "video";
  if (decodedUrl.startsWith("data:audio/")) return "audio";

  if (IMAGE_EXT_RE.test(decodedUrl)) return "image";
  if (VIDEO_EXT_RE.test(decodedUrl)) return "video";
  if (AUDIO_EXT_RE.test(decodedUrl)) return "audio";

  if (decodedUrl.includes("/image")) return "image";
  if (decodedUrl.includes("/video")) return "video";
  if (decodedUrl.includes("/audio")) return "audio";

  return "unknown";
}
