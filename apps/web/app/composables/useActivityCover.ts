/** Ground cover of a Plot's Activities with the explanation behind each colour (Product rule: always answer "why"). */
export function useActivityCover(activities: () => Activity[]) {
  const { t } = useI18n()
  const { day } = useFormat()

  const coverAt = computed(() => coverTimeline(activities()))

  function why(cover: Cover): string {
    const since = cover.since ? { since: cover.since.title, sinceDate: day(cover.since.date) } : {}
    const text = cover.phase === 'crop'
      ? t('app.activities.cover.crop', {
          ...since,
          progress: Math.round((cover.progress ?? 0) * 100),
          harvest: cover.harvest!.title,
          harvestDate: day(cover.harvest!.date)
        })
      : t(`app.activities.cover.${cover.phase}`, since)
    return t('app.activities.cover.why', { why: text })
  }

  /** Background and explanation of one Activity: cover at its date, or priority for undated Tasks. */
  function look(activity: Activity, percent = 50): { background: string, why: string } {
    if (!activity.date) {
      return {
        background: priorityBackground(activity.priority),
        why: t('app.activities.cover.undated', { priority: t(`app.tasks.priority.${activity.priority}`) })
      }
    }
    const cover = coverAt.value(isoToDay(activity.date))
    const origin = activity.origin
      ? ` · ${t('app.activities.origin', {
        year: activity.harvestYear!,
        field: activity.origin.fieldNumber,
        plot: activity.origin.plotNumber,
        overlap: Math.round(activity.origin.overlap * 100)
      })}`
      : ''
    return { background: tint(cover.color, percent), why: why(cover) + origin }
  }

  return { coverAt, why, look }
}
