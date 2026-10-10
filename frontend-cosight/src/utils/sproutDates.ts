/** Sprout Social reporting lag — recent days are excluded from analytics. */
export const SPROUT_DATA_LAG_DAYS = 2;

export function sproutMaxEndDate(): string {
  const end = new Date();
  end.setDate(end.getDate() - SPROUT_DATA_LAG_DAYS);
  return end.toISOString().split('T')[0];
}

export function clampSproutRange(range: { start: string; end: string }): { start: string; end: string } {
  const maxEnd = sproutMaxEndDate();
  const end = range.end > maxEnd ? maxEnd : range.end;
  const start = range.start > end ? end : range.start;
  return { start, end };
}

export function sproutLagNote(throughDate?: string): string {
  const through = throughDate ?? sproutMaxEndDate();
  return `Sprout data is shown through ${through} (${SPROUT_DATA_LAG_DAYS}-day sync lag).`;
}
