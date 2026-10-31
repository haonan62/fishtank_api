import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from 'react'

type Tone = 'info' | 'success' | 'danger'

interface Toast {
  id: number
  tone: Tone
  title: string
  detail?: string
}

interface ToastState {
  show: (toast: Omit<Toast, 'id'>) => void
}

const ToastContext = createContext<ToastState | null>(null)

const TONE_CLASSES: Record<Tone, string> = {
  info: 'border-line bg-surface text-ink',
  success: 'border-ok/30 bg-ok-soft text-ink',
  danger: 'border-danger/40 bg-danger-soft text-ink',
}

const ICONS: Record<Tone, string> = { info: 'ℹ', success: '✓', danger: '!' }

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const nextId = useRef(1)

  const dismiss = useCallback((id: number) => setToasts((current) => current.filter((toast) => toast.id !== id)), [])

  const show = useCallback(
    (toast: Omit<Toast, 'id'>) => {
      const id = nextId.current++
      setToasts((current) => [...current.slice(-2), { ...toast, id }])
      // an alarm stays a little longer, its reason takes time to read
      window.setTimeout(() => dismiss(id), toast.tone === 'danger' ? 8000 : 4000)
    },
    [dismiss],
  )

  const value = useMemo(() => ({ show }), [show])

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div
        aria-live="polite"
        className="pointer-events-none fixed inset-x-4 bottom-4 z-50 flex flex-col items-center gap-2 sm:inset-x-auto sm:right-6 sm:items-end"
      >
        {toasts.map((toast) => (
          <div
            key={toast.id}
            role={toast.tone === 'danger' ? 'alert' : 'status'}
            className={`animate-rise-in pointer-events-auto flex w-full max-w-sm gap-3 rounded-xl border p-4 shadow-[var(--shadow-pop)] ${TONE_CLASSES[toast.tone]}`}
          >
            <span
              aria-hidden
              className={`mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full text-sm font-semibold ${
                toast.tone === 'danger'
                  ? 'bg-danger text-white'
                  : toast.tone === 'success'
                    ? 'bg-ok text-white'
                    : 'bg-brand text-on-brand'
              }`}
            >
              {ICONS[toast.tone]}
            </span>
            <div className="min-w-0 flex-1">
              <p className="font-medium">{toast.title}</p>
              {toast.detail && <p className="mt-1 text-sm text-muted">{toast.detail}</p>}
            </div>
            <button
              type="button"
              onClick={() => dismiss(toast.id)}
              className="-m-1 h-7 w-7 shrink-0 rounded-md text-muted hover:bg-surface-2 hover:text-ink"
              aria-label="Dismiss"
            >
              ×
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  const state = useContext(ToastContext)
  if (!state) throw new Error('useToast needs a ToastProvider')
  return state.show
}
