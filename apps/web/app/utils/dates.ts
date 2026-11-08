/** Today as an ISO calendar date in the browser's time zone, e.g. "2027-03-20". */
export function todayIso(now: Date = new Date()): string {
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60_000)
  return local.toISOString().slice(0, 10)
}

export function addDaysIso(iso: string, days: number): string {
  const [year, month, day] = iso.split('-').map(Number)
  return new Date(Date.UTC(year!, month! - 1, day! + days)).toISOString().slice(0, 10)
}

/** Open Tasks whose due date has passed. Done and discarded Tasks are never overdue. */
export function isOverdue(task: { status: string, due_date: string | null }, today: string): boolean {
  return task.status === 'open' && task.due_date !== null && task.due_date < today
}

/** The Monday of the ISO week `iso` falls in. */
export function weekStartIso(iso: string): string {
  const [year, month, day] = iso.split('-').map(Number)
  const weekday = (new Date(Date.UTC(year!, month! - 1, day!)).getUTCDay() + 6) % 7
  return addDaysIso(iso, -weekday)
}

/** The ISO calendar week number (KW) of a date. */
export function isoWeek(iso: string): number {
  // The week's Thursday decides the year, and week 1 holds January 4th.
  const thursday = addDaysIso(weekStartIso(iso), 3)
  const year = Number(thursday.slice(0, 4))
  const firstThursday = addDaysIso(weekStartIso(`${year}-01-04`), 3)
  const days = (Date.parse(thursday) - Date.parse(firstThursday)) / 86_400_000
  return 1 + Math.round(days / 7)
}
