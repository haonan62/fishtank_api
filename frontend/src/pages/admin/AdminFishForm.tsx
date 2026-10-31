import { useEffect, useMemo, useRef, useState, type FormEvent, type ReactNode } from 'react'
import { Link, useNavigate, useParams } from 'react-router'

import { ApiError, api } from '../../api/client'
import { CROSS_SPECIES_TEMPERAMENTS, IN_SPECIES_TEMPERAMENTS, type Fish, type FishInput } from '../../api/types'
import { useToast } from '../../components/Toasts'
import { Badge, Button, ConfirmDialog, EmptyState, LoadingBlock, TextField, inputClasses } from '../../components/ui'
import { CROSS_SPECIES_TEXT, IN_SPECIES_TEXT, displayName } from '../../lib/fish'
import { FishCard } from '../Catalogue'
import { useAdminData } from './AdminLayout'

// The form keeps every value as typed, as text, and turns it into api values on saving
type FieldName =
  | 'scientific_name'
  | 'common_name'
  | 'family_name'
  | 'minimum_size'
  | 'maximum_size'
  | 'minimum_ph'
  | 'maximum_ph'
  | 'minimum_water_hardness'
  | 'maximum_water_hardness'
  | 'minimum_temperature'
  | 'maximum_temperature'
  | 'reproduce_method'
  | 'origin'
  | 'in_species_temperament'
  | 'cross_species_temperament'
  | 'fishtank_position'
  | 'fishbase_spec_code'
  | 'data_source'

type Values = Record<FieldName, string>
type Errors = Partial<Record<FieldName, string>>

type Kind = 'text' | 'integer' | 'number' | 'choice'

// the same rules as the api, see FISH_FIELDS in fishtank/api/fish.py
const FIELDS: Record<FieldName, { kind: Kind; required: boolean }> = {
  scientific_name: { kind: 'text', required: true },
  common_name: { kind: 'text', required: false },
  family_name: { kind: 'text', required: true },
  minimum_size: { kind: 'integer', required: false },
  maximum_size: { kind: 'integer', required: false },
  minimum_ph: { kind: 'number', required: true },
  maximum_ph: { kind: 'number', required: true },
  minimum_water_hardness: { kind: 'integer', required: true },
  maximum_water_hardness: { kind: 'integer', required: true },
  minimum_temperature: { kind: 'integer', required: true },
  maximum_temperature: { kind: 'integer', required: true },
  reproduce_method: { kind: 'text', required: false },
  origin: { kind: 'text', required: false },
  in_species_temperament: { kind: 'choice', required: true },
  cross_species_temperament: { kind: 'choice', required: true },
  fishtank_position: { kind: 'text', required: false },
  fishbase_spec_code: { kind: 'integer', required: false },
  data_source: { kind: 'text', required: true },
}

const RANGES: { min: FieldName; max: FieldName; label: string; lowest: number; highest: number | null }[] = [
  { min: 'minimum_size', max: 'maximum_size', label: 'Size', lowest: 1, highest: null },
  { min: 'minimum_ph', max: 'maximum_ph', label: 'pH', lowest: 0, highest: 14 },
  { min: 'minimum_water_hardness', max: 'maximum_water_hardness', label: 'Hardness', lowest: 0, highest: null },
  { min: 'minimum_temperature', max: 'maximum_temperature', label: 'Temperature', lowest: 0, highest: 45 },
]

const POSITIONS = ['Top levels', 'Middle levels', 'Bottom levels']

const EMPTY: Values = {
  scientific_name: '',
  common_name: '',
  family_name: '',
  minimum_size: '',
  maximum_size: '',
  minimum_ph: '',
  maximum_ph: '',
  minimum_water_hardness: '',
  maximum_water_hardness: '',
  minimum_temperature: '',
  maximum_temperature: '',
  reproduce_method: '',
  origin: '',
  in_species_temperament: 'unknown',
  cross_species_temperament: 'unknown',
  fishtank_position: '',
  fishbase_spec_code: '',
  data_source: 'manual entry',
}

function valuesOf(fish: Fish): Values {
  const values = { ...EMPTY }
  for (const name of Object.keys(FIELDS) as FieldName[]) {
    const value = fish[name]
    values[name] = value === null || value === undefined ? '' : String(value)
  }
  return values
}

function parse(name: FieldName, text: string): string | number | null {
  const trimmed = text.trim()
  if (trimmed === '') return null
  const kind = FIELDS[name].kind
  if (kind === 'integer' || kind === 'number') return Number(trimmed)
  return trimmed
}

export function validate(values: Values): Errors {
  const errors: Errors = {}
  for (const [name, { kind, required }] of Object.entries(FIELDS) as [FieldName, (typeof FIELDS)[FieldName]][]) {
    const text = values[name].trim()
    if (!text) {
      if (required) errors[name] = 'Required'
      continue
    }
    if (kind === 'text' && text.length > 100) errors[name] = 'At most 100 characters'
    if (kind === 'integer' && !/^-?\d+$/.test(text)) errors[name] = 'A whole number'
    if (kind === 'number' && !Number.isFinite(Number(text))) errors[name] = 'A number'
  }
  for (const range of RANGES) {
    if (errors[range.min] || errors[range.max]) continue
    const low = parse(range.min, values[range.min]) as number | null
    const high = parse(range.max, values[range.max]) as number | null
    if ((low === null) !== (high === null)) errors[low === null ? range.min : range.max] = 'Give both, or neither'
    else if (low !== null && high !== null) {
      if (low > high) errors[range.min] = 'Larger than the maximum'
      else if (low < range.lowest || (range.highest !== null && high > range.highest))
        errors[range.min] = `Between ${range.lowest} and ${range.highest ?? 'any'}`
    }
  }
  if (values.cross_species_temperament !== 'unknown' && !values.minimum_size.trim() && !errors.minimum_size) {
    errors.minimum_size = 'Needed once the temperament is known, the check compares sizes'
  }
  return errors
}

// a new fish sends every field, a change only the fields that changed
function payloadOf(values: Values, initial: Values | null): FishInput {
  const payload: Record<string, string | number | null> = {}
  for (const name of Object.keys(FIELDS) as FieldName[]) {
    if (initial && values[name].trim() === initial[name].trim()) continue
    payload[name] = parse(name, values[name])
  }
  return payload as FishInput
}

function previewOf(values: Values, fish: Fish | null): Fish {
  const number = (name: FieldName, fallback: number) => {
    const value = parse(name, values[name])
    return typeof value === 'number' && Number.isFinite(value) ? value : fallback
  }
  return {
    id: fish?.id ?? 0,
    scientific_name: values.scientific_name.trim() || 'Scientific name',
    common_name: values.common_name.trim() || null,
    family_name: values.family_name.trim() || 'Family',
    minimum_size: values.minimum_size ? number('minimum_size', 0) : null,
    maximum_size: values.maximum_size ? number('maximum_size', 0) : null,
    minimum_ph: number('minimum_ph', 0),
    maximum_ph: number('maximum_ph', 0),
    minimum_water_hardness: number('minimum_water_hardness', 0),
    maximum_water_hardness: number('maximum_water_hardness', 0),
    minimum_temperature: number('minimum_temperature', 0),
    maximum_temperature: number('maximum_temperature', 0),
    reproduce_method: values.reproduce_method || null,
    origin: values.origin || null,
    in_species_temperament: values.in_species_temperament as Fish['in_species_temperament'],
    cross_species_temperament: values.cross_species_temperament as Fish['cross_species_temperament'],
    fishtank_position: values.fishtank_position || null,
    fishbase_spec_code: null,
    data_source: values.data_source,
    fishbase_url: fish?.fishbase_url ?? null,
    retired: fish?.retired ?? false,
    pictures: fish?.pictures ?? [],
  }
}

function Section({ title, description, children }: { title: string; description?: string; children: ReactNode }) {
  return (
    <section className="rounded-2xl border border-line bg-surface p-5 sm:p-6">
      <h2 className="font-display text-lg">{title}</h2>
      {description && <p className="mt-1 text-sm text-muted">{description}</p>}
      <div className="mt-5 grid gap-4 sm:grid-cols-2">{children}</div>
    </section>
  )
}

function Select({ label, value, onChange, options, hint, error }: { label: string; value: string; onChange: (value: string) => void; options: { value: string; label: string }[]; hint?: string; error?: string }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-medium">{label}</span>
      <select value={value} onChange={(event) => onChange(event.target.value)} aria-invalid={error ? true : undefined} className={inputClasses}>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      {(error || hint) && <span className={`mt-1.5 block text-xs ${error ? 'text-danger' : 'text-muted'}`}>{error || hint}</span>}
    </label>
  )
}

export function AdminFishForm() {
  const { id } = useParams()
  const editing = id !== undefined
  const { fish: allFish, loading, changed } = useAdminData()
  const fish = editing ? (allFish.find((entry) => entry.id === Number(id)) ?? null) : null
  const navigate = useNavigate()
  const toast = useToast()

  const initial = useMemo(() => (fish ? valuesOf(fish) : null), [fish])
  const [values, setValues] = useState<Values>(EMPTY)
  const [errors, setErrors] = useState<Errors>({})
  const [touched, setTouched] = useState(false)
  const [saving, setSaving] = useState(false)
  const [lifecycleBusy, setLifecycleBusy] = useState(false)
  const [confirmingDelete, setConfirmingDelete] = useState(false)
  const form = useRef<HTMLFormElement>(null)

  // load the fish into the form once, a save then keeps what the admin sees
  const loadedId = useRef<number | null>(null)
  useEffect(() => {
    if (!editing) {
      setValues(EMPTY)
      loadedId.current = null
    } else if (fish && loadedId.current !== fish.id) {
      setValues(valuesOf(fish))
      loadedId.current = fish.id
    }
    setErrors({})
    setTouched(false)
  }, [editing, fish])

  const dirty = initial ? (Object.keys(FIELDS) as FieldName[]).some((name) => values[name].trim() !== initial[name].trim()) : touched
  useEffect(() => {
    if (!dirty) return
    const warn = (event: BeforeUnloadEvent) => event.preventDefault()
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [dirty])

  const set = (name: FieldName) => (value: string) => {
    setTouched(true)
    const next = { ...values, [name]: value }
    setValues(next)
    // once the admin tried to save, errors follow the typing
    if (Object.keys(errors).length) setErrors(validate(next))
  }

  const focusField = (name: string) =>
    window.setTimeout(() => form.current?.querySelector<HTMLElement>(`[data-field="${name}"] input, [data-field="${name}"] select`)?.focus(), 0)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    const found = validate(values)
    setErrors(found)
    const first = Object.keys(found)[0]
    if (first) {
      focusField(first)
      return
    }
    setSaving(true)
    try {
      const saved = editing && fish ? await api.updateFish(fish.id, payloadOf(values, initial)) : await api.createFish(payloadOf(values, null))
      changed(saved)
      loadedId.current = null
      toast({ tone: 'success', title: editing ? `${displayName(saved)} saved` : `${displayName(saved)} added to the catalogue` })
      if (!editing) navigate(`/admin/fish/${saved.id}`, { replace: true })
    } catch (reason) {
      if (reason instanceof ApiError && reason.field && reason.field in FIELDS) {
        setErrors({ [reason.field]: reason.message })
        focusField(reason.field)
      } else {
        toast({ tone: 'danger', title: 'Could not save the fish', detail: reason instanceof Error ? reason.message : undefined })
      }
    } finally {
      setSaving(false)
    }
  }

  const lifecycle = async (action: 'retire' | 'restore' | 'delete') => {
    if (!fish) return
    setLifecycleBusy(true)
    try {
      if (action === 'delete') {
        await api.deleteFish(fish.id)
        changed()
        toast({ tone: 'info', title: `${displayName(fish)} was removed` })
        navigate('/admin/fish', { replace: true })
        return
      }
      const updated = action === 'retire' ? await api.retireFish(fish.id) : await api.restoreFish(fish.id)
      changed(updated)
      toast({
        tone: 'success',
        title: action === 'retire' ? `${displayName(fish)} is retired` : `${displayName(fish)} is back in the catalogue`,
      })
    } catch (reason) {
      toast({ tone: 'danger', title: 'That did not work', detail: reason instanceof Error ? reason.message : undefined })
    } finally {
      setLifecycleBusy(false)
      setConfirmingDelete(false)
    }
  }

  if (editing && loading && !fish) return <LoadingBlock />
  if (editing && !fish) {
    return <EmptyState title="No such fish" action={<Link to="/admin/fish" className="text-brand hover:underline">Back to the list</Link>} />
  }

  const field = (name: FieldName, label: string, extra: { hint?: string; inputMode?: 'numeric' | 'decimal'; placeholder?: string } = {}) => (
    <div data-field={name}>
      <TextField
        label={`${label}${FIELDS[name].required ? '' : ' (optional)'}`}
        value={values[name]}
        onChange={(event) => set(name)(event.target.value)}
        error={errors[name]}
        hint={extra.hint}
        inputMode={extra.inputMode}
        placeholder={extra.placeholder}
      />
    </div>
  )

  const pair = (min: FieldName, max: FieldName, label: string, unit: string, decimal = false) => (
    <>
      {field(min, `Lowest ${label}${unit}`, { inputMode: decimal ? 'decimal' : 'numeric' })}
      {field(max, `Highest ${label}${unit}`, { inputMode: decimal ? 'decimal' : 'numeric' })}
    </>
  )

  const tanks = fish?.fishtank_count ?? 0

  return (
    <div className="mx-auto max-w-6xl">
      <Link to={fish && !fish.retired && fish.cross_species_temperament === 'unknown' ? '/admin/review' : '/admin/fish'} className="text-sm text-brand hover:underline">
        ← Back to the list
      </Link>
      <header className="mt-3 mb-6 flex flex-wrap items-center gap-3">
        <h1 className="font-display text-3xl">{fish ? displayName(fish) : 'Add a fish'}</h1>
        {fish && (fish.retired ? <Badge>Retired</Badge> : <Badge tone="ok">In catalogue</Badge>)}
        {fish && <span className="text-sm text-muted">#{fish.id}</span>}
      </header>

      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_300px]">
        <form ref={form} onSubmit={submit} noValidate className="space-y-6">
          {fish && tanks > 0 && (
            <p className="rounded-xl bg-warn-soft px-4 py-3 text-sm text-warn">
              {tanks} tank{tanks === 1 ? ' keeps' : 's keep'} this fish. They are not checked again after a change, so a change may leave
              fish together that would not be let in now.
            </p>
          )}

          <Section title="Identity">
            {field('scientific_name', 'Scientific name', { placeholder: 'Corydoras adolfoi' })}
            {field('common_name', 'Common name', { placeholder: "Adolfo's catfish" })}
            {field('family_name', 'Family', { placeholder: 'Callichthyidae' })}
            <Select
              label="Level in the tank (optional)"
              value={values.fishtank_position}
              onChange={set('fishtank_position')}
              options={[{ value: '', label: 'Not known' }, ...POSITIONS.map((position) => ({ value: position, label: position }))]}
            />
          </Section>

          <Section title="Water" description="The ranges the fish is happy in. Two fish can share a tank only where their ranges overlap.">
            {pair('minimum_temperature', 'maximum_temperature', 'temperature', ' (°C)')}
            {pair('minimum_ph', 'maximum_ph', 'pH', '', true)}
            {pair('minimum_water_hardness', 'maximum_water_hardness', 'hardness', ' (dGH)')}
          </Section>

          <Section title="Behaviour and size" description="A fish with an unknown temperament can only be kept alone. Once it is known, the fish needs a size too.">
            <div data-field="cross_species_temperament">
              <Select
                label="With other species"
                value={values.cross_species_temperament}
                onChange={set('cross_species_temperament')}
                options={CROSS_SPECIES_TEMPERAMENTS.map((value) => ({ value, label: value }))}
                hint={CROSS_SPECIES_TEXT[values.cross_species_temperament as keyof typeof CROSS_SPECIES_TEXT]}
                error={errors.cross_species_temperament}
              />
            </div>
            <div data-field="in_species_temperament">
              <Select
                label="With its own kind"
                value={values.in_species_temperament}
                onChange={set('in_species_temperament')}
                options={IN_SPECIES_TEMPERAMENTS.map((value) => ({ value, label: value }))}
                hint={IN_SPECIES_TEXT[values.in_species_temperament as keyof typeof IN_SPECIES_TEXT]}
                error={errors.in_species_temperament}
              />
            </div>
            {pair('minimum_size', 'maximum_size', 'size', ' (cm)')}
          </Section>

          <Section title="More about it">
            {field('origin', 'Origin', { placeholder: 'South America' })}
            {field('reproduce_method', 'Breeding', { placeholder: 'Spawning' })}
            {field('fishbase_spec_code', 'FishBase species code', { inputMode: 'numeric', hint: 'Links the fish to its FishBase page' })}
            {editing ? (
              <div>
                <span className="mb-1.5 block text-sm font-medium">Data source</span>
                <p className="flex h-10 items-center text-sm text-muted">{values.data_source}</p>
              </div>
            ) : (
              field('data_source', 'Data source', { hint: 'Where the facts come from' })
            )}
          </Section>

          <div className="sticky bottom-0 -mx-4 flex items-center justify-end gap-3 border-t border-line bg-bg/90 px-4 py-4 backdrop-blur sm:mx-0 sm:rounded-2xl sm:border">
            {dirty && <span className="mr-auto text-sm text-muted">Unsaved changes</span>}
            <Link to="/admin/fish" className="text-sm text-muted hover:text-ink">
              Cancel
            </Link>
            <Button type="submit" busy={saving} disabled={editing && !dirty}>
              {editing ? 'Save changes' : 'Add fish'}
            </Button>
          </div>
        </form>

        <aside className="space-y-6 lg:sticky lg:top-8 lg:self-start">
          <div>
            <h2 className="mb-3 text-xs font-semibold tracking-wide text-muted uppercase">Preview</h2>
            <div className="pointer-events-none">
              <FishCard fish={previewOf(values, fish)} onOpen={() => undefined} />
            </div>
          </div>

          {fish && (
            <section className="rounded-2xl border border-line bg-surface p-5">
              <h2 className="font-display text-lg">Lifecycle</h2>
              <p className="mt-1 text-sm text-muted">
                In {tanks} tank{tanks === 1 ? '' : 's'}.{' '}
                {fish.retired ? 'Retired: out of the catalogue, tanks keep it.' : 'In the catalogue, anyone can add it.'}
              </p>
              <div className="mt-4 space-y-2">
                {fish.retired ? (
                  <Button variant="secondary" className="w-full" busy={lifecycleBusy} onClick={() => lifecycle('restore')}>
                    Restore to the catalogue
                  </Button>
                ) : (
                  <Button variant="secondary" className="w-full" busy={lifecycleBusy} onClick={() => lifecycle('retire')}>
                    Retire
                  </Button>
                )}
                <Button
                  variant="ghost"
                  className="w-full text-danger hover:bg-danger-soft"
                  disabled={tanks > 0 || lifecycleBusy}
                  onClick={() => setConfirmingDelete(true)}
                >
                  Remove for good
                </Button>
                {tanks > 0 && <p className="text-xs text-muted">A fish living in tanks cannot be removed. Retire it instead.</p>}
              </div>
            </section>
          )}
        </aside>
      </div>

      <ConfirmDialog
        open={confirmingDelete}
        title={`Remove ${fish ? displayName(fish) : 'this fish'}?`}
        confirmLabel="Remove for good"
        danger
        busy={lifecycleBusy}
        onConfirm={() => lifecycle('delete')}
        onClose={() => setConfirmingDelete(false)}
      >
        The fish and its pictures are removed from the database. This cannot be undone. To only hide it, retire it instead.
      </ConfirmDialog>
    </div>
  )
}
