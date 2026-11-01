import { useRef, useState, type ChangeEvent } from 'react'
import { Link } from 'react-router'

import { api } from '../../api/client'
import type { ImportResult } from '../../api/types'
import { useToast } from '../../components/Toasts'
import { Badge, Button } from '../../components/ui'
import { fieldLabel, orderedChanges, showValue } from '../../lib/fishFields'
import { useAdminData } from './AdminLayout'

const MAX_BYTES = 2 * 1024 * 1024

// Many fish at once as a spreadsheet: export, edit, then import. Every import is checked first and shown,
// nothing changes until the admin applies it, and then every row changes or none
export function AdminImport() {
  const { changed } = useAdminData()
  const toast = useToast()
  const input = useRef<HTMLInputElement>(null)
  const [exporting, setExporting] = useState<'all' | 'review' | null>(null)
  const [fileName, setFileName] = useState<string | null>(null)
  const [csv, setCsv] = useState<string | null>(null)
  const [result, setResult] = useState<ImportResult | null>(null)
  const [busy, setBusy] = useState(false)

  const exportFish = async (which: 'all' | 'review') => {
    setExporting(which)
    try {
      await api.exportFish(which === 'review')
    } catch (reason) {
      toast({ tone: 'danger', title: 'Could not export', detail: reason instanceof Error ? reason.message : undefined })
    } finally {
      setExporting(null)
    }
  }

  const check = async (text: string) => {
    setBusy(true)
    try {
      setResult(await api.importFish(text, true))
    } catch (reason) {
      setResult(null)
      toast({ tone: 'danger', title: 'This file cannot be imported', detail: reason instanceof Error ? reason.message : undefined })
    } finally {
      setBusy(false)
    }
  }

  const choose = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    if (file.size > MAX_BYTES) {
      toast({ tone: 'danger', title: 'This file is larger than 2 MB' })
      return
    }
    const text = await file.text()
    setFileName(file.name)
    setCsv(text)
    await check(text)
  }

  const apply = async () => {
    if (!csv) return
    setBusy(true)
    try {
      const applied = await api.importFish(csv, false)
      setResult(applied)
      if (applied.applied) {
        changed()
        toast({ tone: 'success', title: `${applied.changed} fish changed`, detail: 'Each change is in the activity log.' })
      }
    } catch (reason) {
      toast({ tone: 'danger', title: 'Nothing was changed', detail: reason instanceof Error ? reason.message : undefined })
    } finally {
      setBusy(false)
    }
  }

  const rows = result?.rows.filter((row) => row.error || Object.keys(row.changes).length > 0) ?? []

  return (
    <div className="mx-auto max-w-5xl space-y-8">
      <header>
        <h1 className="font-display text-3xl">Import / export</h1>
        <p className="mt-1 text-sm text-muted">
          Work on many fish at once in a spreadsheet. Export, edit the cells, save as CSV and import it here. Only the columns in
          the file change, an empty cell clears an optional field.
        </p>
      </header>

      <section className="rounded-2xl border border-line bg-surface p-5">
        <h2 className="font-display text-lg">1. Export</h2>
        <div className="mt-3 flex flex-wrap gap-2">
          <Button variant="secondary" busy={exporting === 'review'} onClick={() => exportFish('review')}>
            Fish that need review
          </Button>
          <Button variant="secondary" busy={exporting === 'all'} onClick={() => exportFish('all')}>
            Every fish
          </Button>
        </div>
        <p className="mt-2 text-xs text-muted">
          Keep the id column, it says which fish a row is. You can delete the columns you are not changing.
        </p>
      </section>

      <section className="rounded-2xl border border-line bg-surface p-5">
        <h2 className="font-display text-lg">2. Import</h2>
        <input ref={input} type="file" accept=".csv,text/csv" onChange={choose} className="hidden" aria-label="CSV file to import" />
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <Button variant="secondary" busy={busy && !result} onClick={() => input.current?.click()}>
            Choose a CSV file
          </Button>
          {fileName && <span className="text-sm text-muted">{fileName}</span>}
        </div>

        {result && (
          <div className="mt-5 space-y-4">
            <div className="flex flex-wrap items-center gap-2 text-sm">
              {result.applied ? (
                <Badge tone="ok">Imported</Badge>
              ) : result.errors > 0 ? (
                <Badge tone="danger">{result.errors} {result.errors === 1 ? 'row has' : 'rows have'} errors, fix them and choose the file again</Badge>
              ) : result.changed === 0 ? (
                <Badge>Nothing to change</Badge>
              ) : (
                <Badge tone="brand">Checked, ready to import</Badge>
              )}
              <span className="text-muted">
                {result.rows.length} rows · {result.changed} fish {result.applied ? 'changed' : 'would change'}
              </span>
            </div>

            {rows.length > 0 && (
              <div className="max-h-[32rem] overflow-auto rounded-xl border border-line">
                <table className="w-full min-w-[640px] text-left text-sm">
                  <thead className="sticky top-0 border-b border-line bg-surface text-xs text-muted">
                    <tr>
                      <th scope="col" className="px-3 py-2 font-medium">Row</th>
                      <th scope="col" className="px-3 py-2 font-medium">Fish</th>
                      <th scope="col" className="px-3 py-2 font-medium">Changes</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line">
                    {rows.map((row) => (
                      <tr key={row.row} className={row.error ? 'bg-danger-soft/50' : ''}>
                        <td className="px-3 py-2 align-top text-muted tabular-nums">{row.row}</td>
                        <td className="px-3 py-2 align-top">
                          {row.id !== null && row.scientific_name ? (
                            <Link to={`/admin/fish/${row.id}`} className="hover:text-brand-strong">
                              {row.scientific_name}
                            </Link>
                          ) : (
                            <span className="text-muted">{row.id ?? '—'}</span>
                          )}
                        </td>
                        <td className="px-3 py-2 align-top">
                          {row.error ? (
                            <span className="text-danger">
                              {row.field && <strong className="font-medium">{fieldLabel(row.field)}: </strong>}
                              {row.error}
                            </span>
                          ) : (
                            <ul className="space-y-0.5">
                              {orderedChanges(row.changes).map(([field, change]) => (
                                <li key={field}>
                                  <span className="text-muted">{fieldLabel(field)}:</span> {showValue(change.from)} →{' '}
                                  <strong className="font-medium">{showValue(change.to)}</strong>
                                </li>
                              ))}
                            </ul>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {!result.applied && result.errors === 0 && result.changed > 0 && (
              <div className="flex items-center justify-end gap-3">
                <span className="text-sm text-muted">Every row changes, or none if something goes wrong.</span>
                <Button busy={busy} onClick={apply}>
                  Import {result.changed} {result.changed === 1 ? 'change' : 'changes'}
                </Button>
              </div>
            )}
          </div>
        )}
      </section>
    </div>
  )
}
