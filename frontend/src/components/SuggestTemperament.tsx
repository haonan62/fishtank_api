import { useState, type FormEvent } from 'react'

import { ApiError, api } from '../api/client'
import { CROSS_SPECIES_TEMPERAMENTS, IN_SPECIES_TEMPERAMENTS, type Fish } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { CROSS_SPECIES_TEXT, IN_SPECIES_TEXT, displayName } from '../lib/fish'
import { useToast } from './Toasts'
import { Button, Modal, TextField, inputClasses } from './ui'

type Field = 'in_species_temperament' | 'cross_species_temperament' | 'minimum_size' | 'maximum_size' | 'minimum_group_size' | 'note'

// Users who know a fish help fill in what the catalogue lacks: an admin reviews every suggestion before it counts
export function SuggestTemperament({ fish }: { fish: Fish }) {
  const { user, openDialog } = useAuth()
  const [open, setOpen] = useState(false)
  const [sent, setSent] = useState(false)

  if (sent) {
    return (
      <p className="rounded-xl bg-ok-soft px-4 py-3 text-sm text-ok">
        Thank you. An admin will review your suggestion before it changes the catalogue.
      </p>
    )
  }
  return (
    <>
      <div className="rounded-xl border border-dashed border-line px-4 py-3 text-sm">
        <p className="text-muted">Know this fish? Tell us its temperament, so it can share a tank.</p>
        <Button
          variant="secondary"
          size="sm"
          className="mt-2"
          onClick={() => (user ? setOpen(true) : openDialog('login', 'Log in to suggest what you know about this fish.'))}
        >
          Suggest its temperament
        </Button>
      </div>
      {open && <SuggestionDialog fish={fish} onClose={() => setOpen(false)} onSent={() => setSent(true)} />}
    </>
  )
}

function SuggestionDialog({ fish, onClose, onSent }: { fish: Fish; onClose: () => void; onSent: () => void }) {
  const toast = useToast()
  const [values, setValues] = useState({
    in_species_temperament: 'peaceful',
    cross_species_temperament: 'peaceful',
    minimum_size: fish.minimum_size === null ? '' : String(fish.minimum_size),
    maximum_size: fish.maximum_size === null ? '' : String(fish.maximum_size),
    minimum_group_size: '',
    note: '',
  })
  const [errors, setErrors] = useState<Partial<Record<Field, string>>>({})
  const [busy, setBusy] = useState(false)
  const set = (field: Field) => (value: string) => setValues({ ...values, [field]: value })
  const number = (text: string) => (text.trim() === '' ? null : Number(text))

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    const found: typeof errors = {}
    for (const field of ['minimum_size', 'maximum_size'] as const) {
      if (!/^\d+$/.test(values[field].trim())) found[field] = 'A whole number of centimetres'
    }
    if (!found.minimum_size && !found.maximum_size && Number(values.minimum_size) > Number(values.maximum_size))
      found.minimum_size = 'Larger than the maximum'
    if (values.minimum_group_size.trim() && !/^\d+$/.test(values.minimum_group_size.trim()))
      found.minimum_group_size = 'A whole number'
    setErrors(found)
    if (Object.keys(found).length) return
    setBusy(true)
    try {
      await api.suggestTemperament(fish.id, {
        in_species_temperament: values.in_species_temperament as Fish['in_species_temperament'],
        cross_species_temperament: values.cross_species_temperament as Fish['cross_species_temperament'],
        minimum_size: number(values.minimum_size),
        maximum_size: number(values.maximum_size),
        minimum_group_size: number(values.minimum_group_size),
        note: values.note.trim() || null,
      })
      onSent()
      onClose()
      toast({ tone: 'success', title: 'Suggestion sent', detail: 'An admin reviews it before it changes the catalogue.' })
    } catch (reason) {
      if (reason instanceof ApiError && reason.field && reason.field in values) setErrors({ [reason.field]: reason.message })
      else toast({ tone: 'danger', title: 'Could not send it', detail: reason instanceof Error ? reason.message : undefined })
    } finally {
      setBusy(false)
    }
  }

  const select = (field: 'in_species_temperament' | 'cross_species_temperament', label: string, options: string[], hints: Record<string, string>) => (
    <label className="block">
      <span className="mb-1.5 block text-sm font-medium">{label}</span>
      <select value={values[field]} onChange={(event) => set(field)(event.target.value)} className={inputClasses} aria-invalid={errors[field] ? true : undefined}>
        {options.filter((option) => option !== 'unknown').map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
      <span className={`mt-1.5 block text-xs ${errors[field] ? 'text-danger' : 'text-muted'}`}>{errors[field] ?? hints[values[field]]}</span>
    </label>
  )

  return (
    <Modal open onClose={onClose} title={`What do you know about ${displayName(fish)}?`} width="max-w-lg">
      <form onSubmit={submit} noValidate className="space-y-4">
        {select('cross_species_temperament', 'With other species', CROSS_SPECIES_TEMPERAMENTS, CROSS_SPECIES_TEXT)}
        {select('in_species_temperament', 'With its own kind', IN_SPECIES_TEMPERAMENTS, IN_SPECIES_TEXT)}
        <div className="grid grid-cols-2 gap-3">
          <TextField label="Adult size from (cm)" inputMode="numeric" value={values.minimum_size} onChange={(event) => set('minimum_size')(event.target.value)} error={errors.minimum_size} />
          <TextField label="to (cm)" inputMode="numeric" value={values.maximum_size} onChange={(event) => set('maximum_size')(event.target.value)} error={errors.maximum_size} />
        </div>
        <TextField
          label="Smallest group (optional)"
          inputMode="numeric"
          placeholder="e.g. 6"
          value={values.minimum_group_size}
          onChange={(event) => set('minimum_group_size')(event.target.value)}
          error={errors.minimum_group_size}
          hint="For schooling fish, how many feel safe together"
        />
        <label className="block">
          <span className="mb-1.5 block text-sm font-medium">Where do you know this from? (optional)</span>
          <textarea
            value={values.note}
            maxLength={500}
            rows={3}
            onChange={(event) => set('note')(event.target.value)}
            placeholder="e.g. kept them for years, or a book or website"
            className={`${inputClasses} h-auto py-2`}
          />
          {errors.note && <span className="mt-1.5 block text-xs text-danger">{errors.note}</span>}
        </label>
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" busy={busy}>
            Send suggestion
          </Button>
        </div>
      </form>
    </Modal>
  )
}
