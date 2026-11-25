import Image, { type ImageProps } from "next/image";

/**
 * API-served uploads need to reach the backend's media route directly. The
 * Next.js optimizer runs in the frontend container, which does not own that
 * route, so optimize ordinary images but bypass optimization for API uploads.
 */
export function MediaImage(props: ImageProps) {
  const src = typeof props.src === "string" ? props.src : "";
  const isApiUpload = src.startsWith("/api/v1/media/");

  return <Image {...props} unoptimized={props.unoptimized || isApiUpload} />;
}
