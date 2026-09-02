export function displayPeriodKey(type: string, key: string): string {
  if (type !== "weekly") return key;

  const match = key.match(/^(\d{4})-W(\d{2})$/);
  if (!match) return key;

  const year = Number(match[1]);
  const week = Number(match[2]);
  // ISO week 1 is the week containing January 4, starting on Monday.
  const jan4 = new Date(year, 0, 4);
  const jan4Day = jan4.getDay() || 7;
  const monday = new Date(year, 0, 4 - jan4Day + 1 + (week - 1) * 7);
  const sunday = new Date(monday);
  sunday.setDate(monday.getDate() + 6);
  const format = (date: Date) => `${date.getMonth() + 1}/${date.getDate()}`;

  return `${year}年第${week}周 · ${format(monday)}—${format(sunday)}`;
}
