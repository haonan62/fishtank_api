import { useState } from 'react'
import { Link, useNavigate } from 'react-router'

import { api } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { Aquarium } from '../components/Aquarium'
import { useToast } from '../components/Toasts'
import { Button, buttonClasses } from '../components/ui'
import { useCatalogue } from '../lib/catalogue'
import { rememberVisitorTank, setLastTankKey } from '../lib/visitorTanks'

// a few well known, peaceful fish swim in the picture on the home page
const SHOWCASE = ['Corydoras adolfoi', 'Paracheirodon innesi', 'Pterophyllum scalare', 'Trichogaster leeri', 'Otocinclus affinis']

export function useBuildTank() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const toast = useToast()
  const [busy, setBusy] = useState(false)
  const build = async () => {
    setBusy(true)
    try {
      const tank = await api.createTank()
      if (!user) rememberVisitorTank(tank.key)
      setLastTankKey(tank.key)
      navigate(`/tanks/${tank.key}`)
    } catch (reason) {
      toast({ tone: 'danger', title: 'Could not create a tank', detail: reason instanceof Error ? reason.message : undefined })
    } finally {
      setBusy(false)
    }
  }
  return { build, busy }
}

export function Home() {
  const { build, busy } = useBuildTank()
  const { fish } = useCatalogue()
  const showcase = fish.filter((entry) => SHOWCASE.includes(entry.scientific_name)).map((entry) => ({ fish: entry, count: 3 }))

  return (
    <div className="mx-auto max-w-7xl px-4 sm:px-6">
      <section className="grid items-center gap-10 py-12 sm:py-20 lg:grid-cols-[1.1fr_1fr]">
        <div>
          <p className="mb-4 text-sm font-medium text-brand">For people who keep tropical fish</p>
          <h1 className="font-display text-4xl leading-[1.1] sm:text-6xl">Find out which fish can share a tank</h1>
          <p className="mt-5 max-w-xl text-lg text-muted">
            Drop fish into a virtual tank. Fishtank checks water temperature, pH, hardness and temperament, and tells
            you straight away when two fish would not get along.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Button onClick={build} busy={busy} className="h-12 px-6 text-base">
              Build a tank
            </Button>
            <Link to="/fish" className={`${buttonClasses('secondary')} h-12 px-6 text-base`}>
              Browse {fish.length ? fish.length.toLocaleString() : ''} fish
            </Link>
          </div>
          <p className="mt-4 text-sm text-muted">No account needed. Sign up any time to keep your tanks.</p>
        </div>
        <Aquarium entries={showcase} className="h-72 sm:h-96" decorative />
      </section>

      <section className="grid gap-4 pb-20 sm:grid-cols-3">
        {[
          ['Pick from the catalogue', 'Search over a thousand species by name, family, temperament or the water you keep.'],
          ['Add them to a tank', 'Drag fish in, or press +. Fish that would not fit in are greyed out before you try.'],
          ['See the water they need', 'The temperature, pH and hardness every fish in the tank is happy with, at a glance.'],
        ].map(([title, text], index) => (
          <div key={title} className="rounded-2xl border border-line bg-surface p-6">
            <span className="flex size-8 items-center justify-center rounded-full bg-brand-soft text-sm font-semibold text-brand-strong">
              {index + 1}
            </span>
            <h2 className="mt-4 font-display text-lg">{title}</h2>
            <p className="mt-1 text-sm text-muted">{text}</p>
          </div>
        ))}
      </section>
    </div>
  )
}
