import { useEffect, useRef } from 'react'
import { Link } from 'react-router'

import { EmptyState, LoadingBlock, buttonClasses } from '../components/ui'
import { useBuildTank } from './Home'

// /tanks/new builds a tank straight away and opens it, there is nothing to fill in first
export function NewTank() {
  const { build } = useBuildTank()
  const started = useRef(false)
  useEffect(() => {
    if (started.current) return
    started.current = true
    build()
  }, [build])
  return <LoadingBlock label="Filling a new tank…" />
}

export function NotFound() {
  return (
    <div className="mx-auto max-w-2xl px-4 py-16 sm:px-6">
      <EmptyState title="This page swam away" action={<Link to="/" className={buttonClasses()}>Back home</Link>}>
        The address may be mistyped, or the page has moved.
      </EmptyState>
    </div>
  )
}
