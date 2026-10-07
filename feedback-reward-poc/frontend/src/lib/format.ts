/** Group a 16-digit Sparks card number as "1234 5678 9012 3456". */
export function fmtSparks(id: string | null | undefined): string {
  if (!id) return ''
  const digits = id.replace(/\D/g, '')
  return digits.replace(/(.{4})/g, '$1 ').trim()
}

export const SPARKS_LENGTH = 16

export function fmtGBP(amount: number): string {
  return new Intl.NumberFormat('en-GB', { style: 'currency', currency: 'GBP' }).format(amount)
}
