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
