import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router'

import type { Fish } from '../api/types'
import { FishDetail } from '../components/FishDetail'
import { EmptyState, LoadingBlock, buttonClasses } from '../components/ui'
import { useCatalogue } from '../lib/catalogue'

// A fish on a page of its own, for links from outside the app
export function FishPage() {
  const { id } = useParams()
  const { lookup } = useCatalogue()
  const [fish, setFish] = useState<Fish | null | undefined>(undefined)

  useEffect(() => {
    setFish(undefined)
    lookup(Number(id)).then(setFish)
  }, [id, lookup])

  return (
    <div className="mx-auto max-w-2xl px-4 py-8 sm:px-6">
      <Link to="/fish" className="mb-6 inline-block text-sm text-brand hover:underline">
        ← All fish
      </Link>
      {fish === undefined ? (
        <LoadingBlock />
      ) : fish === null ? (
        <EmptyState title="This fish is not in the catalogue" action={<Link to="/fish" className={buttonClasses()}>Browse fish</Link>} />
      ) : (
        <FishDetail fish={fish} />
      )}
    </div>
  )
}
