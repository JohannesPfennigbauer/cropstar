import { describe, expect, it } from 'vitest'
import { addDaysIso, isOverdue, isoWeek, todayIso, weekStartIso } from '../app/utils/dates'

describe('dates', () => {
  it('formats today as an ISO calendar date', () => {
    expect(todayIso(new Date(2027, 2, 20, 23, 30))).toBe('2027-03-20')
  })

  it('adds days across month ends', () => {
    expect(addDaysIso('2027-03-29', 7)).toBe('2027-04-05')
  })

  it('treats only open Tasks with a past due date as overdue', () => {
    expect(isOverdue({ status: 'open', due_date: '2027-03-19' }, '2027-03-20')).toBe(true)
    expect(isOverdue({ status: 'open', due_date: '2027-03-20' }, '2027-03-20')).toBe(false)
    expect(isOverdue({ status: 'done', due_date: '2027-03-01' }, '2027-03-20')).toBe(false)
    expect(isOverdue({ status: 'open', due_date: null }, '2027-03-20')).toBe(false)
  })
})

describe('calendar weeks', () => {
  it('start on Monday', () => {
    expect(weekStartIso('2026-11-08')).toBe('2026-11-02')
    expect(weekStartIso('2026-11-09')).toBe('2026-11-09')
  })

  it('are numbered as in the ISO calendar', () => {
    expect(isoWeek('2026-11-08')).toBe(45)
    expect(isoWeek('2026-01-01')).toBe(1)
    expect(isoWeek('2027-01-01')).toBe(53)
    expect(isoWeek('2024-12-30')).toBe(1)
  })
})
