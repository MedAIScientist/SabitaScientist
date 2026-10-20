/** Storage is reserved in GiB (2^30 bytes) — the unit Curator's refusal and estimates use. */
export const GIB = 1024 ** 3

/** Bytes for a typed GiB amount, or null when the text is not a positive number. */
export function gibToBytes(text: string): number | null {
  const value = Number(text.trim().replace(',', '.'))
  if (!text.trim() || !Number.isFinite(value) || value <= 0) return null
  return Math.ceil(value * GIB)
}

/** "3.5 GiB" — one decimal, so a reservation reads back as it was typed. */
export function formatGib(bytes: number): string {
  return `${(bytes / GIB).toFixed(1).replace(/\.0$/, '')} GiB`
}
