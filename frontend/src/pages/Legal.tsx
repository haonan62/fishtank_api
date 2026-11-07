import type { ReactNode } from 'react'

const CONTACT = 'https://github.com/haonan62/fishtank_api/issues'

function Page({ title, updated, children }: { title: string; updated: string; children: ReactNode }) {
  return (
    <article className="mx-auto max-w-2xl px-4 py-10 sm:px-6">
      <h1 className="font-display text-3xl">{title}</h1>
      <p className="mt-1 text-sm text-muted">Last updated {updated}</p>
      <div className="mt-6 space-y-3 leading-relaxed [&_h2]:mt-8 [&_h2]:font-display [&_h2]:text-xl [&_ul]:list-disc [&_ul]:space-y-2 [&_ul]:pl-5">
        {children}
      </div>
    </article>
  )
}

function Contact() {
  return (
    <a href={CONTACT} target="_blank" rel="noreferrer" className="text-brand hover:underline">
      open an issue on the project's GitHub page
    </a>
  )
}

export function Privacy() {
  return (
    <Page title="Privacy" updated="7 November 2026">
      <p>Fishtank is a non-commercial hobby project. It keeps as little about you as it can, shows no ads, uses no analytics and sells nothing.</p>

      <h2>What is kept</h2>
      <ul>
        <li>
          <strong className="font-medium">Your account</strong>, if you make one: your username and a hash of your password. No email address is asked for.
        </li>
        <li>
          <strong className="font-medium">Your tanks.</strong> A visitor's tank is removed 24 hours after its last change, a tank in an account stays until you remove it. Anyone with a share link can see that tank until you stop sharing it.
        </li>
        <li>
          <strong className="font-medium">Your suggestions</strong> for fish, and the note you add. Admins review them, and they stay without your name after you remove your account. The activity log keeps the usernames of admins next to the changes they made.
        </li>
        <li>
          <strong className="font-medium">IP addresses</strong>, to limit failed logins, new accounts and new visitor tanks. They are removed about once a week. The web server's logs also hold them for a short time, to keep the site running.
        </li>
      </ul>

      <h2>Cookies and browser storage</h2>
      <p>
        Two cookies keep you logged in and protect your account from forged requests, they last up to 30 days and only exist once you log in. Your browser also remembers the tanks you made as a visitor. None of this tracks you across sites.
      </p>

      <h2>Pictures come from other sites</h2>
      <p>
        Fish pictures are loaded directly from where they are hosted, such as FishBase, Wikimedia Commons and iNaturalist. Your browser asks those sites for each picture, so they see your IP address, as they would for any visitor. Fonts are served by Fishtank itself.
      </p>

      <h2>Backups</h2>
      <p>The database is backed up weekly and the last few backups are kept, so data you removed is gone from backups within about a month.</p>

      <h2>Your choices</h2>
      <p>
        You can remove your tanks and your whole account yourself, on your account page. For anything else, <Contact />. Please do not put personal details in the issue.
      </p>
    </Page>
  )
}

export function Terms() {
  return (
    <Page title="Terms" updated="7 November 2026">
      <p>Fishtank is a free, non-commercial hobby project. By using it you accept these terms.</p>

      <h2>A guide, not advice</h2>
      <p>
        Compatibility results, warnings and stocking figures are estimates from public data, and some of it is incomplete or wrong. Check before you buy or move a living animal. Fishtank comes as is, with no guarantee, and is not responsible for what happens in your tank.
      </p>

      <h2>Your account</h2>
      <ul>
        <li>Keep your password safe. There is no password reset yet, so a lost password can mean a lost account.</li>
        <li>Do not attack, overload or scrape the site, or use it to harm others.</li>
        <li>Suggestions you send may be used in the catalogue, please only send what you know to be true. Accounts that misuse the site can be removed.</li>
      </ul>

      <h2>The site may change</h2>
      <p>This is a hobby project, it can change or stop at any time. Weekly backups limit what can be lost, but do not rely on Fishtank as the only copy of anything important.</p>

      <h2>Data and pictures</h2>
      <p>
        The site's code is under the MIT License. Fish data and pictures are not: they belong to FishBase, aqua-fish.net and the credited photographers, many under non-commercial licences. Please check each licence before you reuse them. If you own a picture and want it removed, <Contact />.
      </p>
    </Page>
  )
}
