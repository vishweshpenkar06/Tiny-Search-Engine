import { z } from 'zod'

export const searchQuerySchema = z.string()
  .min(1, 'Query cannot be empty')
  .max(200, 'Query is too long (max 200 characters)')
  .regex(/^[a-zA-Z0-9\s\-"'\.]+$/, 'Invalid characters in query. Only alphanumeric characters, spaces, hyphens, quotes, and dots are allowed.')
  .transform(val => val.trim())

export function validateQuery(query: unknown) {
  return searchQuerySchema.safeParse(query)
}
