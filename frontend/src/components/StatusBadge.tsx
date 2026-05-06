interface Props {
  status: string
  pulse?: boolean
}

const PULSE_STATUSES = new Set(['running', 'claimed', 'busy', 'online'])

export function StatusBadge({ status, pulse }: Props) {
  const shouldPulse = pulse ?? PULSE_STATUSES.has(status)
  return (
    <span className={`badge badge-${status}`}>
      {shouldPulse && (
        <span className="relative flex h-2 w-2">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-current opacity-50" />
          <span className="relative inline-flex h-2 w-2 rounded-full bg-current" />
        </span>
      )}
      {status}
    </span>
  )
}
