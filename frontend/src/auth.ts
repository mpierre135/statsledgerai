export const ALLOWED_EMAIL = (
  import.meta.env.VITE_ALLOWED_EMAIL ?? 'mpierre135@gmail.com'
).toLowerCase()

type EmailHolder = {
  primaryEmailAddress?: { emailAddress?: string | null } | null
  emailAddresses?: { emailAddress?: string | null }[]
}

export function emailsFor(user: EmailHolder | null | undefined): string[] {
  if (!user) return []
  const values = [
    user.primaryEmailAddress?.emailAddress,
    ...(user.emailAddresses ?? []).map((e) => e.emailAddress),
  ]
  return values.filter((v): v is string => Boolean(v)).map((v) => v.toLowerCase())
}

export function isAllowedUser(user: EmailHolder | null | undefined): boolean {
  return emailsFor(user).includes(ALLOWED_EMAIL)
}
