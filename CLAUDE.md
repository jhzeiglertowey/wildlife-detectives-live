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
- 2026-10-16: added the original game's jungle start screen, button animations and redraw fixes (user requests), plus `tests/ui.py` (18/18). The Safari engine (WebKitGTK 2.52) played full games as a phone and as a booth iPad with no errors.
- 2026-10-16: PR #1 (`claude/live-game`) merged into `main` by the user.
- 2026-10-16: busy-Wi-Fi message (user request, many visitors expected on zoo Wi-Fi), on branch `claude/wifi-limit-message`.
- 2026-10-23: the user created Firebase project `wildlife-detectives-live` and sent its web config, now in `firebase-config.js` (on `claude/wifi-limit-message`). Anonymous sign-in verified working (an account was created over REST).
- 2026-10-23: **tested against the real Firebase project** (after the user allowed `*.firebaseio.com` in the cloud environment's network settings):
  - REST checks: anonymous sign-in works; the rules allow claiming a room and refuse unsigned reads, writes outside `rooms/`, bad room codes and listing all rooms.
  - `WD_REAL=1 tests/e2e.py`: a full game with a Chromium big screen and 3 phones, each with a real anonymous account. 49/49.
  - **Bug found this way and fixed:** after a game ended ("closed"), phones still showing it re-added themselves to `players` when the list was cleared. That was harmless for scoring, because the host filters by game id, but it left stale entries. Phones now only re-add themselves while their game is running (`gameRunning()`: not `final` or `closed`).
  - Earlier test runs left about 3 rooms in the database with only stale `players` entries (random animal names, no meta). They're harmless and can be deleted in the Firebase console (Realtime Database → Data → rooms).
  - Safari engine (WebKitGTK) as the phone, with a Chromium big screen: a full game, #1 with 400 points, the congo-apes.org link, no errors.
  - Test rooms are deleted afterwards. A few anonymous test accounts remain under Authentication → Users (harmless).
  - **Sandbox notes for real-Firebase tests:** launch Chromium with `proxy={"server": HTTPS_PROXY, "bypass": "127.0.0.1,localhost"}`, and trust the agent-proxy CA in `~/.pki/nssdb`. That store was empty: `apt-get install libnss3-tools`, then `certutil -A -d sql:$HOME/.pki/nssdb -n ccr-proxy-ca -t "C,," -i <CA from /root/.ccr/ca-bundle.crt, subject "CCR agent-proxy interception CA">`. TLS checking stays on. For WebKitGTK, set `WebsiteDataManager.set_network_proxy_settings(CUSTOM, NetworkProxySettings.new(HTTPS_PROXY, ["localhost","127.0.0.1"]))`.
- 2026-10-28: PR #2 merged by the user; GitHub Pages turned on (live at https://jhzeiglertowey.github.io/wildlife-detectives-live/). The user allowed `jhzeiglertowey.github.io` in the cloud environment's network settings.
- 2026-10-29: pre-demo checks (the user will show the game to their lab mentor) on branch `claude/pre-demo-checks`:
  - **Big-screen refresh mid-game** (new, `tests/robust.py`): it used to lose the game and leave phones frozen. Now progress is saved at each clip, phones show "The big screen lost its connection" (`game/hostAway` via onDisconnect), and the home screen offers **Resume game** or **End it**.
  - **Bugs found and fixed:**
    - Reconnect detection never worked on either page: `WD.watchConnection` passes the same state object every time, so "was offline" was always false. It's now tracked in a separate `wasOnline`.
    - A phone that lost its connection thought it had left the game, because Firebase runs the phone's `onDisconnect` removal locally at once. It got stuck on "Joining…". `joined` is now `myGame === game.id`, no longer requiring the `players` entry.
    - After a resume, a re-asked question showed "Answer sent". Phones now forget a sent answer when the same question is asked again (new `startedAt`).
- **Not yet tested:** real phones and iPads, H.264 clips (the sandbox Chromium can't play them; tests use VP9 WebM), Google's real new-account limit.

## Files

- `host.html`: big screen. Views: `home`, `settings`, `pin`, `lobby`, `play` (phases `watch` / `question` / `reveal` / `board`), `final`.
- `index.html`: player page (phones and booth iPads).
- `common.js` (`WD.*`): shared by both pages:
  - DOM helpers (`el`, `$`);
  - default lists (`DEF_BEHAVIORS`, `DEF_SPECIES`, the same as the single-iPad game);
  - `randomName()`, answer tiles (`TILES`: colour and shape), and scoring (`scoreBehaviors`);
  - room codes, the Firebase connection (`connect`, `watchConnection`), player links (`playerUrl`) and the QR code (`qrSvg`).
- `style.css`: shared look (always light mode, same palette as the single-iPad game), the jungle CSS and the button animations.
- `jungle.js`: the jungle decor markup (vines, foliage, corner leaves, butterflies), **copied unchanged from the single-iPad game**. It's injected into `<body>` on load and shown with `WD.decor(true)`.
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

### Busy Wi-Fi (user request 2026-10-16)
- Google limits how many **new** anonymous accounts one internet connection (IP address) can create per hour, roughly 100. Many visitors joining over the zoo Wi-Fi share one public IP.
- When `signInAnonymously()` fails like that, `WD.rateLimited(e)` matches `auth/too-many-requests` / quota errors. The phone then shows "Too many new players right now", asks the player to turn off Wi-Fi and use mobile data, and shows a **Try again** button. It also retries by itself every 30 s.
- Any other connection failure shows "Couldn't connect" with Try again, plus the same 30 s auto-retry.
- `WD.connect()` can be called again after a failure: it skips `initializeApp` and `useEmulator` when the app already exists.
- Booth iPads and the big screen reuse their IDs, so they aren't affected. Phones on mobile data have their own IPs.
- **Leave Firebase Authentication's "Automatic clean-up" (deleting anonymous accounts older than 30 days) OFF** (advised to the user). Stored anonymous accounts cost nothing and don't limit sessions. Clean-up would delete the big screen's ID between events, so it would lose ownership of its room code (`claimRoom()` then picks a new one) and the booth iPads would need setting up again. Don't upgrade to Identity Platform.
- Test hook: `?failauth=N` (emulator only) makes the first N connection attempts fail with `auth/too-many-requests` (`tests/wifi.py`).
- `tests/wifi_real.py` runs the **real** sign-in code (not the emulator shortcut). It swaps in a dummy `firebase-config.js` and answers Google's `identitytoolkit.googleapis.com/v1/accounts:signUp` request with Google's actual refusal bodies: `TOO_MANY_ATTEMPTS_TRY_LATER` (the SDK maps it to `auth/too-many-requests`) and `QUOTA_EXCEEDED` (not mapped by the SDK; matched by its message). For both, the page shows the busy-Wi-Fi message, Try again asks Google again, and it retries by itself after 30 s (10/10, 2026-10-23). Google's real limit itself can't be triggered without the user's project and more than 100 new accounts.

### Surviving problems mid-game (2026-10-29)
- **Big screen refreshed, crashed or offline:**
  - `saveProgress(i)` writes `localStorage.wd_progress` at the start of each clip: game id, room, clip ids, next clip, names, scores, answered, rows, questions, maxScore. It's cleared at the final screen and by End game.
  - `loadProgress()` accepts it only for the same room, within 6 h, and if all its clips still exist.
  - Home shows "⚠ A game was interrupted… ▶ Resume game / End it" (`#resumeBox`):
    - `resumeGame()` rebuilds `G`, deletes `answers/<gameId>` (half-collected answers for the interrupted clip), re-attaches the players listener and runs `runClips(next)`. The interrupted clip replays from the start.
    - `abandonGame()` sets the game to `closed`.
- **Phones while the big screen is away:** `armAway()` registers `game/hostAway` = true as an onDisconnect when play starts. Phones show "⏸ The big screen lost its connection" during lobby/watch/question/reveal/board. On reconnect, the host sets it false and re-arms (onDisconnect fires once); `setGame()` overwrites it anyway.
- **Phone loses its connection:**
  - It shows "Reconnecting…" over the current screen, and stays in the game (`joined = myGame === game.id`).
  - Back online, `watchConnection` (with a separate `wasOnline`) rewrites `players/<uid>`.
  - The big screen doesn't wait for disconnected phones: "everyone answered" counts only the connected ones, so a phone that drops may miss a question. That's by design.

### Videos in Safari's engine (tested 2026-10-29 in WebKitGTK 2.52, H.264 High + AAC, 1280×720)
- H.264/AAC MP4 decodes and plays in the Safari engine: a full 6 s clip at 1280×720 inside a game.
- **This container's WebKitGTK/GStreamer playback fails at random:** roughly 40% of loads give `MEDIA_ERR_SRC_NOT_SUPPORTED` (4). That happens for a Blob in memory or from IndexedDB, labelled or not, and the pattern changes run to run. It is not a game bug. Judge real playback on an iPad or Mac.
- **Defensive changes kept:**
  - `urlFor()` and `checkPlayable()` play from a Blob that always carries a video type (`typedBlob`/`videoType`, from the file or its name). A Blob read back from IndexedDB in WebKit has `type` "".
  - `ensureLoaded(c)` at the start of each clip: if the stored copy doesn't load within 4 s, it copies this one clip into memory (`arrayBuffer` → new Blob) and tries again for 8 s. Only the current clip is held in memory (`memUrl`). If it still fails, `G.videoProblem` shows the "couldn't play" note and the questions still run.
- **Private Browsing:** WebKit refuses to store videos in IndexedDB in a private session (the transaction aborts). The add-clip error message and the README say to use a normal window.

### Results / CSV (on the big screen only)
- `wildlife_detectives_live_players_<date>.csv`: one row per player per game.
- `wildlife_detectives_live_answers_<date>.csv`: one row per player per clip, with the answer, the correct answer and the points.
- "Reset count & answers" (double tap) clears all stored games.

### Look and feel (user requests 2026-10-16: "same as the original game")
- **Jungle decor** is shown on the screens where nothing is being asked:
  - big screen: `home`, `lobby`, `final`;
  - phone: code entry, waiting, "Tap to play"/joining, lobby, final.
- It's **hidden during clips and questions** so nothing distracts. `WD.decor(on)` toggles `#jungle` and `#main.decor`, and sets `--hdr` so the vines hang from the opaque top bar.
- On wide screens the big screen's lobby and final get 110px side margins, so the vines show beside the cards.
- **Button feedback** (same as the original):
  - every button, answer tile and chip shrinks while pressed (CSS `:active` scale .94);
  - it "pops" when tapped (`WD.pop`, from a capture-phase click listener in `common.js`). If the redraw shows the same screen, `WD.afterRender(sameScreen)` re-applies the pop to the button in the same position;
  - main buttons (New game, Start game, Play again, Tap to play, Join) have `.btn.go` and pulse;
  - results bounce in (`.verdict`, `.bounce`);
  - finished screens drop a confetti shower (`WD.confetti`);
  - Save buttons flash "✓ Saved" (`flash()`), and double-tap buttons turn orange (`.btn.armed`) and disarm after 4 s.
  - All of it is off under `prefers-reduced-motion`.
- **No screen jumping:**
  - **Big screen:** `render()` reads `scrollY` **before** emptying `#main` and restores it when redrawing the same view, so Settings stays put when its buttons redraw it. A different view starts at the top.
  - **Phones:** `render()` builds the new screen off-page (`draw()`), compares its HTML with what's showing (ignoring the timer bar's width), and **only swaps it in if it changed**. Database updates arrive often (other players joining or answering, clock offset). Rebuilding every time restarted the pop-in animations (flicker, washed-out screenshots) and could swallow a tap that landed mid-redraw. `screenKey()` decides "same screen" (scroll kept) versus a new screen (scroll to top, confetti on final).
- **Podium medals follow the rank**, so tied players get the same medal.

## Testing

- See `tests/README.md`. Short version:
  - run the emulator jar directly on port 9000;
  - PUT `database.rules.json` to `/.settings/rules.json?ns=demo-wd` with `Authorization: Bearer owner`;
  - serve the repo with `python3 -m http.server 8080`;
  - run `tests/e2e.py`, `tests/booth.py`, `tests/ui.py`, `tests/wifi.py`, `tests/wifi_real.py` and `tests/robust.py`.
- In the cloud sandbox, `firebase emulators:start` fails to load rules because the CLI's traffic goes through the outbound proxy. Running the jar directly avoids it.
- `--noproxy '*'` is needed for curl to reach localhost.
- Sandbox Chromium is at `/opt/pw-browsers/chromium-1194/chrome-linux/chrome`. It has no H.264, so test clips are VP9 WebM.
- Safari-engine check: WebKitGTK 2.52 is available (see the single-iPad repo's CLAUDE.md for how to run it; snapshots need `python3-gi-cairo`).
- After editing, extract each page's last `<script>` and run `node --check` on it, then run all four test files.
- **Safari engine (WebKitGTK)** harness: a Chromium big screen drives the game, and a WebKitGTK window plays as a phone or booth iPad (`index.html?room=CODE&emu=1&uid=...`). The harness injects JS that answers and reports, and snapshots are taken with `get_snapshot` (needs `python3-gi-cairo`). Run it under `xvfb-run` with `/usr/bin/python3.12`. The scripts lived in the session scratchpad (not in the repo); rebuild them from this description if needed.
