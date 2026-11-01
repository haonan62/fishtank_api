import { useState } from 'react'

import { api } from '../api/client'
import type { Fishtank, SkippedFish } from '../api/types'
import { displayName } from '../lib/fish'
import { useToast } from './Toasts'
import { Button, Modal, inputClasses } from './ui'

export function sharedLink(token: string) {
  return `${window.location.origin}/shared/${token}`
}

// what a copy left out, retired fish cannot be added to tanks anymore
export function skippedDetail(skipped: SkippedFish[]) {
  if (skipped.length === 0) return undefined
  return `Left out, no longer in the catalogue: ${skipped.map((fish) => displayName(fish)).join(', ')}`
}

// A read only link to the tank: whoever has it sees the tank and can copy it, only the owner changes it
export function ShareDialog({ tank, onClose, onChange }: { tank: Fishtank; onClose: () => void; onChange: (tank: Fishtank) => void }) {
  const toast = useToast()
  const [busy, setBusy] = useState(false)
  const [copied, setCopied] = useState(false)

  const run = async (work: () => Promise<Fishtank>) => {
    setBusy(true)
    try {
      onChange(await work())
    } catch (reason) {
      toast({ tone: 'danger', title: 'That did not work', detail: reason instanceof Error ? reason.message : undefined })
    } finally {
      setBusy(false)
    }
  }

  const copyLink = async () => {
    if (!tank.share_token) return
    try {
      await navigator.clipboard.writeText(sharedLink(tank.share_token))
      setCopied(true)
      window.setTimeout(() => setCopied(false), 2000)
    } catch {
      toast({ tone: 'info', title: 'Select the link and copy it yourself' })
    }
  }

  return (
    <Modal open onClose={onClose} title="Share this tank">
      {tank.share_token ? (
        <div className="space-y-4 text-sm">
          <p className="text-muted">
            Anyone with this link sees the tank and can copy it into their own. Only you can change it.
            {!tank.saved && ' The link works until the tank expires, save the tank to keep it.'}
          </p>
          <div className="flex gap-2">
            <input
              readOnly
              value={sharedLink(tank.share_token)}
              onFocus={(event) => event.target.select()}
              aria-label="Link to the shared tank"
              className={inputClasses}
            />
            <Button onClick={copyLink} className="shrink-0">
              {copied ? 'Copied' : 'Copy link'}
            </Button>
          </div>
          <div className="flex justify-between gap-2 border-t border-line pt-4">
            <Button variant="ghost" className="text-danger hover:bg-danger-soft" busy={busy} onClick={() => run(() => api.stopSharingTank(tank.key))}>
              Stop sharing
            </Button>
            <Button variant="secondary" onClick={onClose}>
              Done
            </Button>
          </div>
        </div>
      ) : (
        <div className="space-y-4 text-sm">
          <p className="text-muted">
            Make a link others can open to see this tank and copy it. They cannot change yours, and you can stop sharing at any
            time.
          </p>
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={onClose}>
              Cancel
            </Button>
            <Button busy={busy} onClick={() => run(() => api.shareTank(tank.key))}>
              Make a link
            </Button>
          </div>
        </div>
      )}
    </Modal>
  )
}
