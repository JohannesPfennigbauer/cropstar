import { describe, expect, it } from 'vitest'
import { addDaysIso, isOverdue, todayIso } from '../app/utils/dates'

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
