import { z } from 'zod'

// Each document lives as content/legal/<locale>/<id>.md; self-hosted instances replace these files.
export const LEGAL_DOCUMENTS = ['imprint', 'privacy'] as const
export type LegalDocument = typeof LEGAL_DOCUMENTS[number]

export const legalSchema = z.object({
  title: z.string().min(1),
  description: z.string().min(1),
  updated: z.date()
})
