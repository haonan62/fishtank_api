import { useState } from 'react'
import { useNavigate } from 'react-router'

import { ApiError, api } from '../api/client'
import type { Fish, Fishtank } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { alarmTitle, displayName } from '../lib/fish'
import { tankTitle, useMyTanks } from '../lib/useMyTanks'
import { lastTankKey, rememberVisitorTank, setLastTankKey } from '../lib/visitorTanks'
import { useToast } from './Toasts'
import { Button, LoadingBlock, Modal } from './ui'

// Adds a fish to a tank from anywhere in the catalogue: the tank used last, another tank, or a new one
export function AddToTank({ fish, full = false }: { fish: Fish; full?: boolean }) {
  const [choosing, setChoosing] = useState(false)
  return (
    <>
      <Button onClick={() => setChoosing(true)} className={full ? 'w-full' : ''} disabled={fish.retired}>
        + Add to tank
      </Button>
      {choosing && <TankChooser fish={fish} onClose={() => setChoosing(false)} />}
    </>
  )
}

function TankChooser({ fish, onClose }: { fish: Fish; onClose: () => void }) {
  const { user } = useAuth()
  const { saved, visitor, loading } = useMyTanks()
  const [busyKey, setBusyKey] = useState<string | null>(null)
  const toast = useToast()
  const navigate = useNavigate()
  const lastKey = lastTankKey()

  const tanks = [...saved, ...visitor].sort((a, b) => Number(b.key === lastKey) - Number(a.key === lastKey))

  const addTo = async (tank: Fishtank | null) => {
    setBusyKey(tank?.key ?? 'new')
    try {
      const target = tank ?? (await api.createTank())
      if (!target.saved) rememberVisitorTank(target.key)
      setLastTankKey(target.key)
      await api.addFish(target.key, [fish.id])
      toast({ tone: 'success', title: `${displayName(fish)} joined ${tankTitle(target)}` })
      onClose()
      navigate(`/tanks/${target.key}`)
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : String(reason)
      toast({
        tone: 'danger',
        title: reason instanceof ApiError && reason.status === 422 ? alarmTitle(message, fish) : 'Could not add the fish',
        detail: message,
      })
    } finally {
      setBusyKey(null)
    }
  }

  return (
    <Modal open onClose={onClose} title={`Add ${displayName(fish)} to…`}>
      {loading ? (
        <LoadingBlock label="Finding your tanks…" />
      ) : (
        <div className="space-y-2">
          {tanks.map((tank) => (
            <button
              key={tank.key}
              type="button"
              disabled={busyKey !== null}
              onClick={() => addTo(tank)}
              className="flex w-full items-center justify-between gap-3 rounded-xl border border-line px-4 py-3 text-left hover:border-brand hover:bg-brand-soft disabled:opacity-60"
            >
              <span className="min-w-0">
                <span className="block truncate font-medium">{tankTitle(tank)}</span>
                <span className="text-xs text-muted">
                  {tank.fish.reduce((total, entry) => total + entry.count, 0)} fish
                  {tank.key === lastKey && ' · used last'}
                  {!tank.saved && ' · not saved'}
                </span>
              </span>
              <span className="text-sm text-brand">{busyKey === tank.key ? 'Adding…' : 'Add'}</span>
            </button>
          ))}
          <Button variant={tanks.length ? 'secondary' : 'primary'} className="w-full" busy={busyKey === 'new'} disabled={busyKey !== null} onClick={() => addTo(null)}>
            + New tank with this fish
          </Button>
          {!user && tanks.length > 0 && (
            <p className="pt-1 text-center text-xs text-muted">Tanks you build without an account are kept for a day.</p>
          )}
        </div>
      )}
    </Modal>
  )
}
