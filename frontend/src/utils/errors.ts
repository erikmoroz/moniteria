/**
 * Extract a user-facing error message from an Axios error response.
 * Falls back to the provided default message if no detail is found.
 */
export function getApiErrorMessage(error: unknown, fallback: string): string {
  const err = error as { response?: { data?: { detail?: string } } }
  return err.response?.data?.detail || fallback
}
