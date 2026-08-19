import Image from "next/image";

import { cn } from "@/lib/utils";
import markSrc from "@/public/ebads-mark.png";
import fullLockupSrc from "@/public/ebads-logo-full.png";

const MARK_SIZES = {
  sm: { px: 24, wordmark: "text-sm" },
  md: { px: 32, wordmark: "text-base" },
} as const;

const FULL_WIDTHS = {
  lg: 220,
  xl: 300,
} as const;

interface EbadsLogoProps {
  /** "sm"/"md": the icon mark plus an "EBADS" text wordmark, for compact contexts (sidebar
   * header, nav). "lg"/"xl": the official full lockup image (mark + wordmark + tagline
   * baked in), for prominent brand placements (login screen). */
  size?: keyof typeof MARK_SIZES | keyof typeof FULL_WIDTHS;
  className?: string;
}

// The official EBADS mark (mobile/assets/ebads_logo.png), cropped once into two derived,
// transparent-background variants living in public/: the icon-only emblem for compact
// pairing with our own text, and the full mark+wordmark+tagline lockup for hero placements.
export function EbadsLogo({ size = "md", className }: EbadsLogoProps) {
  if (size === "lg" || size === "xl") {
    const width = FULL_WIDTHS[size];
    return (
      <Image
        src={fullLockupSrc}
        alt="EBADS — Emergency Bed Allocation Decision Support"
        width={width}
        height={Math.round(width * (fullLockupSrc.height / fullLockupSrc.width))}
        className={className}
        priority
      />
    );
  }

  const { px, wordmark } = MARK_SIZES[size];
  return (
    <div className={cn("flex items-center gap-2", className)}>
      <Image src={markSrc} alt="" width={px} height={px} className="shrink-0" priority />
      <span className={cn("font-sans font-bold tracking-tight text-primary", wordmark)}>
        EBADS
      </span>
    </div>
  );
}
