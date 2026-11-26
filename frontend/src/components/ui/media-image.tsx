import Image, { type ImageProps } from "next/image";

/**
 * Product uploads are served by the API reverse proxy at /api/v1/media/.
 * Send those URLs straight from the browser so Next's optimizer doesn't try to
 * fetch them from the frontend container, which has no /api/v1 media route.
 */
export function MediaImage(props: ImageProps) {
  const src = typeof props.src === "string" ? props.src : "";
  const isApiUpload = src.startsWith("/api/v1/media/");

  return <Image {...props} unoptimized={props.unoptimized || isApiUpload} />;
}
