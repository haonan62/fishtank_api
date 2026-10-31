import {
  DndContext,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  TouchSensor,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from '@dnd-kit/core'
import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { Link, useNavigate, useParams } from 'react-router'

import { ApiError, api } from '../api/client'
import type { Compatibility, Fish, Fishtank, TankSize } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { Aquarium } from '../components/Aquarium'
import { FishArt } from '../components/FishArt'
import { FishPanel } from '../components/FishDetail'
import { FishPicker, ResidentList, SizeDialog, TankName, VisitorBanner, WaterPanel, type Resident } from '../components/TankParts'
import { useToast } from '../components/Toasts'
import { Badge, Button, ConfirmDialog, EmptyState, ErrorNotice, LoadingBlock, buttonClasses } from '../components/ui'
import { useCatalogue } from '../lib/catalogue'
import { alarmTitle, displayName } from '../lib/fish'
import { useMediaQuery } from '../lib/useMediaQuery'
import { forgetVisitorTank, rememberVisitorTank, setLastTankKey } from '../lib/visitorTanks'
import { useBuildTank } from './Home'

function TankDropZone({ children, alarm }: { children: ReactNode; alarm: number }) {
  const { setNodeRef, isOver } = useDroppable({ id: 'tank' })
  return (
    <div ref={setNodeRef} className="relative">
      {/* a new key restarts the shake each time a fish is refused */}
      <div key={alarm} className={alarm ? 'animate-shake' : ''}>
        {children}
      </div>
      {isOver && (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center rounded-3xl border-4 border-dashed border-white/80 bg-white/10">
          <span className="rounded-full bg-ink/70 px-4 py-2 text-sm font-medium text-white">Drop to add</span>
        </div>
      )}
    </div>
  )
}

export function TankWorkspace() {
  const { key = '' } = useParams()
  const { user, openDialog } = useAuth()
  const { fish: catalogue, byId, lookup } = useCatalogue()
  const toast = useToast()
  const navigate = useNavigate()
  const { build, busy: building } = useBuildTank()

  const [tank, setTank] = useState<Fishtank | null>(null)
  const [missing, setMissing] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [compatibility, setCompatibility] = useState<Compatibility | null>(null)
  const [checking, setChecking] = useState(false)
  const [busy, setBusy] = useState(false)
  const [alarm, setAlarm] = useState(0)
  const [openFish, setOpenFish] = useState<Fish | null>(null)
  const [dragging, setDragging] = useState<Fish | null>(null)
  const [editingSize, setEditingSize] = useState(false)
  const [confirmingDelete, setConfirmingDelete] = useState(false)
  const [pickerOpen, setPickerOpen] = useState(false)
  // one picker at a time, two would register the same drag targets
  const wide = useMediaQuery('(min-width: 1024px)')

  const refreshCompatibility = useCallback(async () => {
    setChecking(true)
    try {
      setCompatibility(await api.compatible(key))
    } catch {
      // without the answer every fish stays selectable, the api still checks each add
    } finally {
      setChecking(false)
    }
  }, [key])

  useEffect(() => {
    setTank(null)
    setMissing(false)
    setLoadError(null)
    api
      .getTank(key)
      .then((loaded) => {
        setTank(loaded)
        setLastTankKey(loaded.key)
        if (!loaded.saved && !user) rememberVisitorTank(loaded.key)
        refreshCompatibility()
      })
      .catch((reason) => {
        if (reason instanceof ApiError && reason.status === 404) {
          setMissing(true)
          forgetVisitorTank(key)
        } else setLoadError(reason instanceof Error ? reason.message : String(reason))
      })
  }, [key, user, refreshCompatibility])

  // fish retired since they were added are not in the catalogue, they are looked up one by one
  useEffect(() => {
    tank?.fish.filter((entry) => !byId.has(entry.id)).forEach((entry) => lookup(entry.id))
  }, [tank, byId, lookup])

  const residents: Resident[] = useMemo(
    () =>
      (tank?.fish ?? []).flatMap((entry) => {
        const fish = byId.get(entry.id)
        return fish ? [{ fish, count: entry.count }] : []
      }),
    [tank, byId],
  )

  const incompatible = useMemo(
    () => new Map((compatibility?.incompatible ?? []).map((entry) => [entry.id, entry.reason])),
    [compatibility],
  )

  const change = async (action: 'add' | 'remove', ids: number[]) => {
    if (!tank || ids.length === 0) return
    setBusy(true)
    try {
      const updated = action === 'add' ? await api.addFish(tank.key, ids) : await api.removeFish(tank.key, ids)
      setTank(updated)
      refreshCompatibility()
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : String(reason)
      const refused = reason instanceof ApiError && (reason.status === 422 || reason.status === 409)
      if (refused) setAlarm((current) => current + 1)
      toast({ tone: 'danger', title: refused ? alarmTitle(message, byId.get(ids[0]!)) : 'Something went wrong', detail: message })
    } finally {
      setBusy(false)
    }
  }

  const addOne = (fish: Fish) => change('add', [fish.id])
  const setCount = (fish: Fish, count: number) => {
    const current = tank?.fish.find((entry) => entry.id === fish.id)?.count ?? 0
    const difference = count - current
    if (difference > 0) change('add', Array(difference).fill(fish.id))
    else if (difference < 0) change('remove', Array(-difference).fill(fish.id))
  }

  const update = async (changes: { name?: string | null; size?: TankSize }) => {
    if (!tank) return
    try {
      setTank(await api.updateTank(tank.key, changes))
    } catch (reason) {
      toast({ tone: 'danger', title: 'Could not change the tank', detail: reason instanceof Error ? reason.message : undefined })
    }
  }

  const save = async () => {
    if (!tank) return
    try {
      setTank(await api.saveTank(tank.key))
      forgetVisitorTank(tank.key)
      toast({ tone: 'success', title: 'Saved to your tanks' })
    } catch (reason) {
      toast({ tone: 'danger', title: 'Could not save the tank', detail: reason instanceof Error ? reason.message : undefined })
    }
  }

  const remove = async () => {
    if (!tank) return
    setBusy(true)
    try {
      await api.deleteTank(tank.key)
      forgetVisitorTank(tank.key)
      toast({ tone: 'info', title: `${tank.name ?? 'The tank'} was removed` })
      navigate('/my-tanks')
    } catch (reason) {
      toast({ tone: 'danger', title: 'Could not remove the tank', detail: reason instanceof Error ? reason.message : undefined })
      setBusy(false)
    }
  }

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 150, tolerance: 6 } }),
    useSensor(KeyboardSensor),
  )
  const onDragStart = (event: DragStartEvent) => setDragging(byId.get(event.active.data.current?.fishId) ?? null)
  const onDragEnd = (event: DragEndEvent) => {
    setDragging(null)
    const fishId = event.active.data.current?.fishId as number | undefined
    const from = event.active.data.current?.from
    if (fishId === undefined) return
    if (from === 'picker' && event.over?.id === 'tank') change('add', [fishId])
    if (from === 'tank' && event.over?.id === 'picker') change('remove', [fishId])
  }

  if (missing) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-16 sm:px-6">
        <EmptyState
          title="This tank is not here anymore"
          action={
            <Button onClick={build} busy={building}>
              Build a new tank
            </Button>
          }
        >
          A tank built without an account is removed a day after its last change, and a saved tank can only be opened by its
          owner.
        </EmptyState>
      </div>
    )
  }
  if (loadError) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-16 sm:px-6">
        <ErrorNotice message={loadError} onRetry={() => navigate(0)} />
      </div>
    )
  }
  if (!tank) return <LoadingBlock label="Filling the tank…" />

  const picker = (
    <FishPicker
      fish={catalogue}
      incompatible={incompatible}
      checking={checking}
      busy={busy}
      canDrag={wide}
      onAdd={addOne}
      onOpen={setOpenFish}
    />
  )

  return (
    <DndContext sensors={sensors} onDragStart={onDragStart} onDragEnd={onDragEnd} onDragCancel={() => setDragging(null)}>
      <div className="mx-auto max-w-[96rem] px-4 py-6 sm:px-6">
        <div className="mb-5 flex flex-wrap items-center gap-3">
          <TankName tank={tank} onRename={(name) => update({ name })} />
          <button
            type="button"
            onClick={() => setEditingSize(true)}
            className="rounded-full border border-line px-3 py-1 text-sm text-muted hover:text-ink"
            title="Change the size"
          >
            {tank.size.length} × {tank.size.width} × {tank.size.height} cm
          </button>
          {tank.saved ? <Badge tone="ok">Saved</Badge> : <Badge tone="warn">Not saved</Badge>}
          <div className="ml-auto flex gap-2">
            {user && (
              <Link to="/my-tanks" className={buttonClasses('ghost', 'sm')}>
                All my tanks
              </Link>
            )}
            <Button variant="secondary" size="sm" onClick={() => setConfirmingDelete(true)}>
              Remove tank
            </Button>
          </div>
        </div>

        <div className="mb-5">
          <VisitorBanner tank={tank} loggedIn={user !== null} onSave={save} onSignUp={() => openDialog('register', 'Create an account to keep this tank.')} />
        </div>

        <div className="grid gap-6 lg:grid-cols-[300px_minmax(0,1fr)] xl:grid-cols-[320px_minmax(0,1fr)_300px]">
          {/* the picker is a column on wide screens and a sheet on phones */}
          {wide && <aside className="sticky top-20 h-[calc(100dvh-12rem)] min-h-[32rem] lg:row-span-2 xl:row-span-1">{picker}</aside>}

          <div className="min-w-0 space-y-6">
            <TankDropZone alarm={alarm}>
              <Aquarium
                entries={residents}
                className="h-[22rem] sm:h-[28rem]"
                overlay={
                  residents.length === 0 && (
                    <div className="absolute inset-0 flex items-center justify-center p-6 text-center">
                      <p className="max-w-xs rounded-2xl bg-white/70 px-5 py-4 text-sm text-ink backdrop-blur dark:bg-black/40 dark:text-white">
                        {wide ? (
                          <>
                            Drag a fish here, or press <strong>+</strong> next to it.
                          </>
                        ) : (
                          <>
                            Press <strong>Add fish</strong> to pick your first fish.
                          </>
                        )}
                      </p>
                    </div>
                  )
                }
              />
            </TankDropZone>
            <Button className="w-full lg:hidden" onClick={() => setPickerOpen(true)}>
              + Add fish
            </Button>
            <ResidentList residents={residents} busy={busy} onCount={setCount} onOpen={setOpenFish} />
          </div>

          <aside className="space-y-6 lg:col-start-2 xl:sticky xl:top-20 xl:col-start-3 xl:row-start-1 xl:self-start">
            <WaterPanel residents={residents} />
            <p className="px-1 text-xs leading-relaxed text-muted">
              Fish that would not get along with everyone in the tank are greyed out in the list. Their reason shows below their
              name.
            </p>
          </aside>
        </div>
      </div>

      {pickerOpen && !wide && (
        <div className="fixed inset-0 z-30 flex flex-col justify-end bg-ink/30" onMouseDown={(event) => event.target === event.currentTarget && setPickerOpen(false)}>
          <div className="animate-rise-in flex h-[80dvh] flex-col rounded-t-3xl bg-surface p-4 shadow-[var(--shadow-pop)]">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="font-display text-lg">Add fish</h2>
              <Button variant="ghost" size="sm" onClick={() => setPickerOpen(false)}>
                Done
              </Button>
            </div>
            <div className="min-h-0 flex-1">{picker}</div>
          </div>
        </div>
      )}

      <DragOverlay dropAnimation={{ duration: 220, easing: 'ease-out' }}>
        {dragging && (
          <div className="flex items-center gap-2 rounded-full bg-surface py-1 pr-4 pl-1 shadow-[var(--shadow-pop)]">
            <span className="flex h-9 w-12 items-center justify-center rounded-full bg-surface-2">
              <FishArt fish={dragging} className="w-10" />
            </span>
            <span className="text-sm font-medium">{displayName(dragging)}</span>
          </div>
        )}
      </DragOverlay>

      <FishPanel fish={openFish} onClose={() => setOpenFish(null)} />
      {editingSize && <SizeDialog size={tank.size} onClose={() => setEditingSize(false)} onSave={(size) => update({ size })} />}
      <ConfirmDialog
        open={confirmingDelete}
        title="Remove this tank?"
        confirmLabel="Remove tank"
        danger
        busy={busy}
        onConfirm={remove}
        onClose={() => setConfirmingDelete(false)}
      >
        {tank.name ?? 'This tank'} and its {tank.fish.reduce((total, entry) => total + entry.count, 0)} fish will be gone for good.
      </ConfirmDialog>
    </DndContext>
  )
}
