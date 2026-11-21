import type { SVGProps } from "react";
import feather from "feather-icons";

const DEFAULT_PROPS = {
  xmlns: "http://www.w3.org/2000/svg",
  width: 16,
  height: 16,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 2,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};

export type FeatherIconName = keyof typeof feather.icons | (string & {});

export interface FeatherIconProps extends SVGProps<SVGSVGElement> {
  name: FeatherIconName;
  size?: number;
}

export function FeatherIcon({
  name,
  size = 16,
  className = "",
  ...props
}: FeatherIconProps) {
  const iconsDict = feather.icons as Record<
    string,
    { contents: string } | undefined
  >;
  const iconData = iconsDict[name] ?? iconsDict["circle"];

  return (
    <svg
      {...DEFAULT_PROPS}
      width={size}
      height={size}
      className={`inline-block shrink-0 ${className}`.trim()}
      aria-hidden="true"
      {...props}
      dangerouslySetInnerHTML={{ __html: iconData ? iconData.contents : "" }}
    />
  );
}

export function getPortIconName(
  portType: string,
  media?: string | null,
): FeatherIconName {
  if (media) {
    if (media.startsWith("image/")) return "image";
    if (media.startsWith("audio/")) return "music";
    if (media === "application/pdf") return "file-text";
    if (media === "text/csv") return "table";
    if (media === "text/markdown") return "book-open";
  }
  switch (portType) {
    case "str":
      return "type";
    case "int":
    case "float":
      return "hash";
    case "bool":
      return "toggle-left";
    case "json":
    case "dict":
    case "list":
      return "code";
    case "file":
      return "file";
    case "directory":
      return "folder";
    default:
      return "circle";
  }
}

export function getPortIconColor(portType: string): string {
  switch (portType) {
    case "str":
      return "#38c172";
    case "int":
    case "float":
      return "#00d8ff";
    case "bool":
      return "#ffa726";
    case "json":
    case "dict":
    case "list":
      return "#d946ef";
    case "file":
      return "#2680eb";
    case "directory":
      return "#ecc94b";
    default:
      return "#b0b0b0";
  }
}
