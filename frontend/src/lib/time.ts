// the api sends times in UTC as 2026-10-31T08:24:28Z

export function timeAgo(iso: string, now = Date.now()) {
  const seconds = Math.round((now - Date.parse(iso)) / 1000)
  if (seconds < 60) return 'just now'
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) return `${minutes} min ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours} h ago`
  const days = Math.round(hours / 24)
  if (days < 30) return `${days} day${days === 1 ? '' : 's'} ago`
  return new Date(iso).toLocaleDateString()
}

export function timeLeft(iso: string, now = Date.now()) {
  const minutes = Math.max(0, Math.round((Date.parse(iso) - now) / 60000))
  if (minutes < 60) return `${minutes} min`
  const hours = Math.floor(minutes / 60)
  return `${hours} h ${minutes % 60} min`
}
