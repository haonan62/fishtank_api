import { useEffect, useRef, useState } from 'react'
import { Link, NavLink, Outlet, useNavigate } from 'react-router'

import { useAuth } from '../auth/AuthContext'
import { AuthDialog } from './AuthDialog'
import { buttonClasses } from './ui'

export function Logo() {
  return (
    <Link to="/" className="flex shrink-0 items-center gap-2 font-display text-xl" aria-label="Fishtank home">
      <img src="/favicon.svg" alt="" className="size-7" />
      <span className="hidden sm:inline">Fishtank</span>
    </Link>
  )
}

const navClasses = ({ isActive }: { isActive: boolean }) =>
  `rounded-lg px-2.5 py-2 text-sm font-medium whitespace-nowrap transition-colors sm:px-3 ${isActive ? 'bg-brand-soft text-brand-strong' : 'text-muted hover:text-ink'}`

function UserMenu() {
  const { user, logout } = useAuth()
  const [open, setOpen] = useState(false)
  const menu = useRef<HTMLDivElement>(null)
  const navigate = useNavigate()

  useEffect(() => {
    if (!open) return
    const close = (event: MouseEvent) => !menu.current?.contains(event.target as Node) && setOpen(false)
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [open])

  if (!user) return null
  return (
    <div ref={menu} className="relative">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        aria-haspopup="menu"
        className="flex items-center gap-2 rounded-full border border-line py-1 pr-3 pl-1 text-sm hover:bg-surface-2"
      >
        <span className="flex size-7 items-center justify-center rounded-full bg-brand text-sm font-semibold text-on-brand uppercase">
          {user.username[0]}
        </span>
        <span className="hidden max-w-32 truncate sm:inline">{user.username}</span>
      </button>
      {open && (
        <div role="menu" className="absolute right-0 z-20 mt-2 w-48 rounded-xl border border-line bg-surface p-1 shadow-[var(--shadow-pop)]">
          <p className="px-3 py-2 text-xs text-muted">
            Logged in as <span className="font-medium text-ink">{user.username}</span>
            {user.role === 'admin' && ' · admin'}
          </p>
          <Link
            to="/account"
            role="menuitem"
            onClick={() => setOpen(false)}
            className="block w-full rounded-lg px-3 py-2 text-left text-sm hover:bg-surface-2"
          >
            Account
          </Link>
          <button
            type="button"
            role="menuitem"
            onClick={async () => {
              setOpen(false)
              await logout()
              navigate('/')
            }}
            className="w-full rounded-lg px-3 py-2 text-left text-sm hover:bg-surface-2"
          >
            Log out
          </button>
        </div>
      )}
    </div>
  )
}

export function Layout() {
  const { user, ready, openDialog } = useAuth()
  return (
    <div className="flex min-h-dvh flex-col">
      <header className="sticky top-0 z-20 border-b border-line bg-bg/85 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-7xl items-center gap-2 px-4 sm:gap-4 sm:px-6">
          <Logo />
          <nav className="flex items-center gap-0.5 sm:ml-6 sm:gap-1">
            <NavLink to="/fish" className={navClasses}>
              Fish
            </NavLink>
            <NavLink to="/my-tanks" className={navClasses}>
              My tanks
            </NavLink>
            {user?.role === 'admin' && (
              <NavLink to="/admin" className={navClasses}>
                Admin
              </NavLink>
            )}
          </nav>
          <div className="ml-auto flex items-center gap-2">
            {ready && !user && (
              <>
                <button type="button" onClick={() => openDialog('login')} className={buttonClasses('ghost', 'sm')}>
                  Log in
                </button>
                <button type="button" onClick={() => openDialog('register')} className={`${buttonClasses('primary', 'sm')} hidden sm:inline-flex`}>
                  Sign up
                </button>
              </>
            )}
            <UserMenu />
          </div>
        </div>
      </header>
      <main className="flex-1">
        <Outlet />
      </main>
      <Footer />
      <AuthDialog />
    </div>
  )
}

// FishBase's licence asks for its data to be credited and linked where it is shown
export function Footer() {
  return (
    <footer className="border-t border-line">
      <div className="mx-auto max-w-7xl px-4 py-8 text-xs leading-relaxed text-muted sm:px-6">
        <p>
          Fish data from{' '}
          <a href="https://www.fishbase.se" target="_blank" rel="noreferrer" className="underline hover:text-ink">
            FishBase
          </a>{' '}
          (Froese &amp; Pauly, 2025, CC BY-NC 4.0) and{' '}
          <a href="https://en.aqua-fish.net/" target="_blank" rel="noreferrer" className="underline hover:text-ink">
            aqua-fish.net
          </a>
          . Photos are credited to their photographers, from FishBase.
        </p>
      </div>
    </footer>
  )
}
