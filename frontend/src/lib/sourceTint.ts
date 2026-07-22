// ② A color system, not a color — the deterministic per-source tint. A stable string hash
// maps each News source name to one of a small, desaturated ramp (all inside the accent teal's
// lightness/chroma envelope), so provenance reads at a glance without ever adding loudness or
// implying "live" data. Text color only; costs nothing in assets.
const SOURCE_TINTS = [
  "text-source-0",
  "text-source-1",
  "text-source-2",
  "text-source-3",
  "text-source-4",
  "text-source-5",
];

export function sourceTint(name: string): string {
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = (hash * 31 + name.charCodeAt(i)) | 0;
  }
  return SOURCE_TINTS[Math.abs(hash) % SOURCE_TINTS.length];
}
