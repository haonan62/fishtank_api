# Backlog

Things to come back to after going live, newest thinking first. Nothing here blocks the launch.

## Accounts

- **Move authentication to Keycloak**, on its own larger VM (Keycloak idles at about 1 GB, plus its Postgres).
  This is also the plan for forgotten passwords: accounts have no email address and there is no reset, not even
  by an admin, so until then a lost password means a lost account. The terms say so. The plan:
  - Fishtank speaks only standard OIDC, so the provider can change. Keycloak brokers Google and other providers.
  - Flask does the login (authorization code with PKCE) and keeps its HttpOnly session cookie and csrf check,
    the browser never holds a token. It keeps the refresh token encrypted and renews every few minutes,
    so a role removed in Keycloak ends within minutes.
  - Authorization stays in Fishtank: it reads a role such as `fishtank-admin` from the token (the claim is a setting).
    API clients send Keycloak access tokens, checked for signature, issuer, audience (needs an audience mapper) and expiry.
  - The `user` table stays, tanks, suggestions and the audit log point to it. It gains the provider's subject, loses
    the password. A new user picks a username when the provider's is an email, shared tanks show the owner's name.
  - Without a provider configured the app runs for visitors only, so the quick start keeps working.
  - Catalogue and visitor tanks keep working when Keycloak is down, `/readyz` does not depend on it.
  - Keycloak's database needs its own backups, losing it loses every user's link to their tanks.
  - Do it before real users sign up: their accounts have no email to match on, and Keycloak cannot read
    Werkzeug's password hashes.
  - Steps: a realm committed as config (client, role, mappers, brute force protection, Google), then the backend
    behind a setting, then the ui (login redirect, username step, account page), then the switch (roles from the token,
    removing passwords, `create-admin`, `set-role` and role editing in the admin users page), then deploying it.
  - Sessions, roles and the login dialog are the parts that change (`fishtank/api/auth.py`, `fishtank/api/common.py`,
    `fishtank/models/user.py`, `frontend/src/auth/`, `frontend/src/components/AuthDialog.tsx`).

## Mobile apps

The web ui installs as an app and browses the catalogue offline. Next, iOS and Android apps built with Capacitor,
the same React ui in a native shell, so one codebase serves the web and both stores. If Apple refuses it as a repackaged
website (App Store guideline 4.2), React Native (Expo) is the fallback, it reuses `src/api/` and `src/lib/`.

- **Needs on the Mac:** Xcode (not only the command line tools), Android Studio, Node 22 or newer for Capacitor 8.
  Store accounts: Apple about $99 a year, Google Play $25 once. New personal Play accounts run a closed test first.
- **Before the shell:** a configurable api address (the app is not served by Flask), share links built from the site's
  public address instead of `window.location.origin`, and login with the bearer token the api already has,
  kept in the phone's secure storage, since cookies do not work well inside an app.
- **The shell:** `ios/` and `android/` projects under `frontend/`; the native share sheet, haptics, safe areas, and
  shared tank links that open the app (universal links / app links). The admin portal stays on the web.
- **To pass review, it does more than the website:** offline catalogue (done), native sharing, links into the app.
  Offline tanks would need the compatibility rules ported from `fishtank/simulation/` to TypeScript.
- **Store listing:** icons and splash screens, screenshots, Apple's privacy labels and Google's data safety form,
  and the privacy page updated. The apps stay free, without ads or purchases, for the non-commercial picture licences.
- **With Keycloak:** the app logs in through the system browser (authorization code with PKCE). Offering Google
  login in the iOS app likely means offering Sign in with Apple too (guideline 4.8), Keycloak can broker it.

## Catalogue

- **Get catalogue updates to the live site.** Changes to `data/fish.db` only reach a database created after them,
  so fixes and new pictures need a way to reach a database that already exists.
- **Check for broken pictures.** Every picture is linked from another site, a scheduled check would find the dead ones.
- **Fish without a picture.** 120 fish have none and still show by default. Sort them last, or hide them until an admin
  adds a photo (the admin fish list has a "Without a photo" filter).

## Running it

- **Load test the catalogue.** One process answers 8 clients asking for the catalogue at once in about 1.6 s each,
  because its 650 KB of json is compressed again on every request. Keeping the compressed answer should help.
- **Copy backups off the server.** Weekly backups stay on the same disk as the database, so they protect from mistakes
  and damage to the file, not from losing the server.

## Sharing

- **Link previews.** Every page has the same title and description, so shared tank links look the same in chat apps.
