# Wildlife Detectives Live – Djéké Triangle (multiplayer)

A Kahoot-style, multiplayer version of the Wildlife Detectives camera-trap quiz, for an outreach booth at a zoo. Camera-trap videos from the Djéké Triangle (Republic of Congo) play on a **big screen**. Players answer at the same time on **their own phones** or on **booth iPads** (a Settings switch).

This repo is **completely separate** from the single-iPad game (repo `jhzeiglertowey/djeke_outreach_project`, file `wildlife-detectives-djeke-triangle.html`). The two share no code and no saved data, though this game reuses ideas, wording and styling from that one. Read that repo's `CLAUDE.md` and `docs/chat-history.md` for the background on the original game's design decisions.

**Keep this file up to date** (user request, 2026-10-16). After every meaningful change, record what was built, the decisions made and their reasons, and how to test. If context runs out, this file is the memory.

## User decisions (2026-10-16)

- **Connection:** over the internet, via **Google Firebase** (Realtime Database + Anonymous Auth, free "Spark" plan). Only answers and scores travel over the network. **Videos never leave the big-screen device**, so nothing is streamed and the footage isn't published.
- **Devices:** a Settings switch chooses **visitors' phones** (they scan a QR code) or **booth iPads** (fixed devices that stay joined between games).
- **Questions per clip:** "Which animal?" (4 choices), then "What is it doing?" (behaviors from the researcher's list). The "other animals" question from the original game is left out.
- **Scoring:** **correctness only**, with no speed bonus.
- **Names:** **random animal names** (e.g. "Swift Leopard"), with a reroll button. Players can't type names, so nothing inappropriate appears on the big screen.
- **Repository:** **public** (`jhzeiglertowey/wildlife-detectives-live`). The user wants it to keep working after they leave WashU, so it can't depend on student GitHub Pro. The phone page is hosted on **GitHub Pages** from this public repo. No videos, answers or player data are stored in the repo.
- Claude's GitHub app can't create repositories. The user created this one by hand.

## Working with the user

- They're a non-developer researcher who runs the booth. Explain changes in plain language and say what to test on real devices.
- When you make a judgment call, point it out so they can overrule it.
- Keep it simple and reliable for a one-day event over anything heavy or fragile.
- The user does the steps that need their own accounts: creating the Firebase project, pasting its config, and turning on GitHub Pages. Give click-by-click instructions.

## Status

- 2026-10-16: repository created (public); first full version built and tested against the Firebase emulator (`tests/e2e.py` 48/48, `tests/booth.py` 16/16).
- **Waiting on the user:** creating the Firebase project and pasting its settings into `firebase-config.js` (README "One-time setup"), and turning on GitHub Pages (Settings → Pages → `main` / root). Until `firebase-config.js` is filled in, the pages say Firebase isn't set up.
- **Not yet tested:** a real Firebase project, real phones and iPads, H.264 clips (the sandbox Chromium can't play them; tests use VP9 WebM).

## Files

- `host.html`: big screen. Views: `home`, `settings`, `pin`, `lobby`, `play` (phases `watch` / `question` / `reveal` / `board`), `final`.
- `index.html`: player page (phones and booth iPads).
- `common.js` (`WD.*`): shared by both pages:
  - DOM helpers (`el`, `$`);
  - default lists (`DEF_BEHAVIORS`, `DEF_SPECIES`, the same as the single-iPad game);
  - `randomName()`, answer tiles (`TILES`: colour and shape), and scoring (`scoreBehaviors`);
  - room codes, the Firebase connection (`connect`, `watchConnection`), player links (`playerUrl`) and the QR code (`qrSvg`).
- `style.css`: shared look (always light mode, same palette as the single-iPad game).
- `firebase-config.js`: the user's Firebase web config (`window.WD_FIREBASE_CONFIG`), with `PASTE_...` placeholders until set up.
- `database.rules.json`: security rules, pasted by the user into the Firebase console. **Keep it in sync with the data model.**
- `lib/`: vendored Firebase compat SDK 11.10.0 (app, auth, database) and qrcode-generator 2.0.4 (`lib/LICENSES.md`).
- `logo.png`: GTAP / Congo Goualougo-Mondika logo (copied from the single-iPad game).
- `tests/`: Playwright end-to-end tests against the emulator (`tests/README.md`).

## How it works

### Big screen = authority
- The big screen opens and closes questions, holds the official answers, computes all scores and writes each player's result.
- Official answers are **only sent at reveal time** (`game.correct`), so a player can't read them early from the database.

### Storage on the big screen
- IndexedDB `wdlive_v1` has three stores:
  - `clips`: `{id, name, blob, active, order, answer:{species, noAnimal, behaviors}}`;
  - `kv`: the `settings` record;
  - `games`: one record per finished game, with players, scores and per-answer rows for the CSVs.
- **Videos never leave this device.** Writes resolve only after the transaction commits, so "✓ Saved" is never shown for a failed save. `navigator.storage.persist()` is requested.

### Firebase data (Realtime Database)
- Each big-screen device keeps one 4-letter room code (`cfg.room`, letters without I/O), claimed with `meta.host = its uid`.
- All data lives under `rooms/<CODE>/`:
  - `meta`: `{host, mode, created}`;
  - `game`: written only by the host. Fields: `{id, total, mode, phase, clip, qkey, kind, title, choices, multi, open, seconds, startedAt, correct, counts, top}`. The phases are `lobby`, `watch`, `question`, `reveal`, `board`, `final` and `closed`;
  - `players/<uid>`: `{name, game, t}`, written by the player. It has `onDisconnect().remove()`, and the player rewrites it on reconnect;
  - `answers/<gameId>/<qkey>/<uid>`: a string. For the animal question it's the choice; for behaviors it's a JSON array. A player can write it only for the open question, only once, and only for themselves (rules);
  - `results/<uid>`: `{game, score, rank, of, clip, last:{pts, animalOk, animal, bPts, bExact, noAnimal}}`, written by the host after each clip.
- **Firebase keys can't contain `. # $ / [ ]`**, and behavior names like "Feeding/foraging" contain `/`. So answer counts are sent as **lists in choice order** (`counts.animal[i]`, `counts.behavior[i]`), never keyed by name. This bug was found in testing.
- **Auth:** anonymous sign-in in production. In emulator tests (`?emu=1`, only accepted on localhost) the pages use `useEmulator` + `mockUserToken`, with `uid` from the URL.

### Game flow (host `runClips()`)
- For each clip:
  - **watch**: the clip plays once with sound, up to `watchMax` s, and the phones say "Watch the big screen";
  - **question** "Which animal is this?": 4 tiles, the right animal plus 3 random from the animal list (never "Other / unsure"). For an empty clip, "No animal visible" is the right answer;
  - **question** "What is it doing?": every behavior from the list, pick all that apply, then Done. It's skipped for empty clips;
  - **reveal** (`secsReveal`), then the **board** (top 5, `secsBoard`; not after the last clip). Then **final** (podium, QR to congo-apes.org).
- A question closes when its timer runs out or **every connected player has answered**. After closing, the answers are re-read once so a last-moment answer still counts.
- **Next ▶** (or Space / →) skips the current wait. "Move on automatically" off means reveal and board wait for Next.
- **One `<video>` element is reused for every clip** (iPads limit how many can play at once). The **Start game** tap unlocks sound. If sound is still refused, the clip plays muted with a "🔊 Tap for sound" button.
- **Screen Wake Lock** is requested during a game.

### Scoring (correctness only, user decision)
- Animal right: **100**.
- Behaviors: **100 × correct picks ÷ (correct + wrong + missed)**, the same formula as the single-iPad game. Exactly right scores 100.
- So a clip is worth 200 at most, or 100 for an empty clip. There's no speed bonus.
- Rank = 1 + the number of players with a higher score, so ties share a rank.

### Devices (Settings → "Players use")
- **Visitors' phones:**
  - The lobby shows a QR code with the join link (`?room=CODE`) and the room code.
  - Phones join as soon as they open the page.
  - After the final screen, "Play again" joins the next game.
- **Booth iPads:**
  - Each iPad is set up once with the link `?room=CODE&booth=1` (QR code in Settings). It remembers this in `localStorage` (`wd_booth`, `wd_booth_room`).
  - Between games it shows **Tap to play**: iPads never join by themselves, so idle iPads don't hold up "everyone answered".
  - The final screen resets after 25 s.
  - A small footer link (double tap) turns booth mode off.
- **"Learn more" on the player's final screen (user decision 2026-10-16):** booth iPads show a **QR code** to congo-apes.org; personal phones show a **tappable link** instead. The big screen's final screen always shows the QR code.
- **Player names:**
  - Random "Adjective Animal" names (Congo species), unique within the game. A "🎲 New name" button appears in the lobby.
  - The name is kept in `localStorage` (`wd_last`), so a reload mid-game keeps the same name and score.

### Results / CSV (on the big screen only)
- `wildlife_detectives_live_players_<date>.csv`: one row per player per game.
- `wildlife_detectives_live_answers_<date>.csv`: one row per player per clip, with the answer, the correct answer and the points.
- "Reset count & answers" (double tap) clears all stored games.

## Testing

- See `tests/README.md`. Short version:
  - run the emulator jar directly on port 9000;
  - PUT `database.rules.json` to `/.settings/rules.json?ns=demo-wd` with `Authorization: Bearer owner`;
  - serve the repo with `python3 -m http.server 8080`;
  - run `tests/e2e.py` and `tests/booth.py`.
- In the cloud sandbox, `firebase emulators:start` fails to load rules because the CLI's traffic goes through the outbound proxy. Running the jar directly avoids it.
- `--noproxy '*'` is needed for curl to reach localhost.
- Sandbox Chromium is at `/opt/pw-browsers/chromium-1194/chrome-linux/chrome`. It has no H.264, so test clips are VP9 WebM.
- Safari-engine check: WebKitGTK 2.52 is available (see the single-iPad repo's CLAUDE.md for how to run it; snapshots need `python3-gi-cairo`).
- After editing, extract each page's last `<script>` and run `node --check` on it, then run both test files.
