import { useState, type FormEvent } from 'react'

import { ApiError, api } from '../../api/client'
import type { Fish, Picture, PictureInput } from '../../api/types'
import { useToast } from '../../components/Toasts'
import { Button, ConfirmDialog, TextField, inputClasses } from '../../components/ui'

// licences that let a picture be shown with a credit, the list helps admins pick, any other can be typed
const LICENCES = ['CC0', 'Public domain', 'CC BY 4.0', 'CC BY-SA 4.0', 'CC BY-NC 4.0', 'CC BY-NC-SA 4.0', 'CC BY 2.0', 'CC BY-SA 3.0']
const SOURCES = ['Wikimedia Commons', 'iNaturalist', 'Flickr', 'GBIF', 'Own photo']

type Field = keyof PictureInput
const EMPTY = { url: '', source_url: '', licence: 'CC BY 4.0', source: 'Wikimedia Commons', author: '' }

// The pictures of a fish, the first is the one the catalogue shows. Admins link pictures they found, with their credit
export function FishPictures({ fish, onChange }: { fish: Fish; onChange: (fish: Fish) => void }) {
  const toast = useToast()
  const [adding, setAdding] = useState(false)
  const [values, setValues] = useState(EMPTY)
  const [errors, setErrors] = useState<Partial<Record<Field, string>>>({})
  const [preview, setPreview] = useState<'loading' | 'loaded' | 'failed'>('loading')
  const [busy, setBusy] = useState(false)
  const [removing, setRemoving] = useState<Picture | null>(null)

  const set = (field: Field) => (value: string) => {
    setValues({ ...values, [field]: value })
    if (field === 'url') setPreview('loading')
  }

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    const found: typeof errors = {}
    for (const field of ['url', 'source_url'] as const) {
      if (!/^https:\/\/\S+$/.test(values[field].trim())) found[field] = 'An https:// address'
    }
    if (!values.licence.trim()) found.licence = 'Required'
    if (!values.source.trim()) found.source = 'Required'
    if (!found.url && preview !== 'loaded') found.url = 'This address does not show an image'
    setErrors(found)
    if (Object.keys(found).length) return
    setBusy(true)
    try {
      onChange(await api.addPicture(fish.id, { ...values, author: values.author.trim() || null }))
      toast({ tone: 'success', title: 'Picture added' })
      setValues(EMPTY)
      setAdding(false)
    } catch (reason) {
      if (reason instanceof ApiError && reason.field && reason.field in EMPTY) setErrors({ [reason.field]: reason.message })
      else toast({ tone: 'danger', title: 'Could not add the picture', detail: reason instanceof Error ? reason.message : undefined })
    } finally {
      setBusy(false)
    }
  }

  const remove = async () => {
    if (!removing) return
    setBusy(true)
    try {
      onChange(await api.removePicture(fish.id, removing.id))
      toast({ tone: 'info', title: 'Picture removed' })
    } catch (reason) {
      toast({ tone: 'danger', title: 'Could not remove the picture', detail: reason instanceof Error ? reason.message : undefined })
    } finally {
      setBusy(false)
      setRemoving(null)
    }
  }

  const url = values.url.trim()

  return (
    <section className="rounded-2xl border border-line bg-surface p-5 sm:p-6">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="font-display text-lg">Pictures</h2>
        <span className="text-sm text-muted">{fish.pictures.length || 'None yet'}</span>
      </div>
      <p className="mt-1 text-sm text-muted">The first picture is the one the catalogue shows. Every picture is shown with its credit.</p>

      {fish.pictures.length > 0 && (
        <ul className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2">
          {fish.pictures.map((picture, index) => (
            <li key={picture.id} className="overflow-hidden rounded-xl border border-line">
              <img src={picture.url} alt="" loading="lazy" className="aspect-[4/3] w-full bg-surface-2 object-cover" />
              <div className="flex items-start justify-between gap-2 p-3 text-xs">
                <div className="min-w-0">
                  {index === 0 && <p className="mb-0.5 font-medium text-brand-strong">Shown in the catalogue</p>}
                  <p className="text-muted">{picture.credit}</p>
                  <a href={picture.source_url} target="_blank" rel="noreferrer" className="text-brand hover:underline">
                    Source page ↗
                  </a>
                </div>
                <button
                  type="button"
                  onClick={() => setRemoving(picture)}
                  className="shrink-0 rounded-md px-2 py-1 text-muted hover:bg-danger-soft hover:text-danger"
                  aria-label={`Remove the picture by ${picture.author ?? 'an unknown author'}`}
                >
                  Remove
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}

      {!adding ? (
        <Button variant="secondary" className="mt-4" onClick={() => setAdding(true)}>
          + Add a picture
        </Button>
      ) : (
        <form onSubmit={submit} noValidate className="mt-5 space-y-4 border-t border-line pt-5">
          <p className="text-sm text-muted">
            Link a picture whose licence lets others show it with a credit, e.g. from Wikimedia Commons, iNaturalist or Flickr.
          </p>
          <div className="grid gap-4 sm:grid-cols-[1fr_160px] lg:grid-cols-1 xl:grid-cols-[1fr_180px]">
            <div className="space-y-4">
              <TextField
                label="Image address"
                placeholder="https://upload.wikimedia.org/…/fish.jpg"
                value={values.url}
                onChange={(event) => set('url')(event.target.value)}
                error={errors.url}
                hint="The address of the image itself, it ends in .jpg or .png"
              />
              <TextField
                label="Page of the picture"
                placeholder="https://commons.wikimedia.org/wiki/File:…"
                value={values.source_url}
                onChange={(event) => set('source_url')(event.target.value)}
                error={errors.source_url}
                hint="Where people find who made it and its licence"
              />
            </div>
            <div className="flex aspect-[4/3] items-center justify-center overflow-hidden rounded-xl bg-surface-2 text-center text-xs text-muted sm:aspect-auto lg:aspect-[4/3] xl:aspect-auto">
              {url.startsWith('https://') ? (
                <>
                  <img
                    key={url}
                    src={url}
                    alt="Preview"
                    onLoad={() => setPreview('loaded')}
                    onError={() => setPreview('failed')}
                    className={preview === 'loaded' ? 'size-full object-cover' : 'hidden'}
                  />
                  {preview === 'loading' && <span>Loading…</span>}
                  {preview === 'failed' && <span className="px-2 text-danger">No image at this address</span>}
                </>
              ) : (
                <span className="px-2">The preview shows here</span>
              )}
            </div>
          </div>
          <div className="grid gap-4 sm:grid-cols-3 lg:grid-cols-1 xl:grid-cols-3">
            <TextField label="Author (optional)" value={values.author} onChange={(event) => set('author')(event.target.value)} error={errors.author} />
            <label className="block">
              <span className="mb-1.5 block text-sm font-medium">Licence</span>
              <input list="picture-licences" value={values.licence} onChange={(event) => set('licence')(event.target.value)} className={inputClasses} aria-invalid={errors.licence ? true : undefined} />
              <datalist id="picture-licences">
                {LICENCES.map((licence) => (
                  <option key={licence} value={licence} />
                ))}
              </datalist>
              {errors.licence && <span className="mt-1.5 block text-xs text-danger">{errors.licence}</span>}
            </label>
            <label className="block">
              <span className="mb-1.5 block text-sm font-medium">From</span>
              <input list="picture-sources" value={values.source} onChange={(event) => set('source')(event.target.value)} className={inputClasses} aria-invalid={errors.source ? true : undefined} />
              <datalist id="picture-sources">
                {SOURCES.map((source) => (
                  <option key={source} value={source} />
                ))}
              </datalist>
              {errors.source && <span className="mt-1.5 block text-xs text-danger">{errors.source}</span>}
            </label>
          </div>
          <p className="text-xs text-muted">
            Shown as: {values.author.trim() || 'Unknown author'}, {values.licence.trim() || 'licence'}, via {values.source.trim() || 'source'}
          </p>
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => { setAdding(false); setErrors({}) }}>
              Cancel
            </Button>
            <Button type="submit" busy={busy}>
              Add picture
            </Button>
          </div>
        </form>
      )}

      <ConfirmDialog
        open={removing !== null}
        title="Remove this picture?"
        confirmLabel="Remove picture"
        danger
        busy={busy}
        onConfirm={remove}
        onClose={() => setRemoving(null)}
      >
        The fish no longer shows it. The picture itself stays where it is hosted.
      </ConfirmDialog>
    </section>
  )
}
