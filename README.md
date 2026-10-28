# Wildlife Detectives Live 🐾

A Kahoot-style, multiplayer camera-trap quiz from the Djéké Triangle (Republic of Congo), for outreach events.

- **Big screen** (`host.html`, on a laptop, TV or iPad): plays the camera-trap clips and shows the questions, answers and leaderboard.
- **Players**: everyone answers at the same time, either on **their own phones** (they scan a QR code) or on **booth iPads**. You choose which in Settings.
- **For each clip:** "Which animal is this?" (4 choices), then "What is it doing?" (pick all that apply). Points are for correct answers only; speed doesn't matter.
- **Privacy:** videos are stored only on the big-screen device and are never uploaded. Players get random animal names (like "Swift Leopard"), so no personal information is collected.

This is a separate game from the single-iPad version (`djeke_outreach_project`).

---

## One-time setup (about 15 minutes)

You need a **Google account** for Firebase, the free service that passes answers between the phones and the big screen. Use an account that will outlast your time at university, such as a lab or project account, so the game keeps working after you leave.

### 1. Create a Firebase project
1. Go to <https://console.firebase.google.com> and sign in.
2. Click **Create a project** (or **Add project**). Name it, for example, `wildlife-detectives-live`.
3. Google Analytics isn't needed, so you can turn it off. Click **Create project**.

### 2. Create the database
1. In the left menu, open **Build → Realtime Database**, then click **Create Database**.
2. Pick a location near you (e.g. *United States*), then choose **Start in locked mode**, then **Enable**.
3. Open the **Rules** tab. Delete everything in the box and paste in the whole contents of [`database.rules.json`](database.rules.json) from this repository. Click **Publish**.
4. At the top of the **Data** tab, copy the database address. It looks like `https://wildlife-detectives-live-default-rtdb.firebaseio.com` (or ends in `.firebasedatabase.app`).

### 3. Turn on anonymous sign-in
1. In the left menu, open **Build → Authentication**, then click **Get started**.
2. On the **Sign-in method** tab, choose **Anonymous**, switch it **on** and click **Save**.

Players never see a sign-in screen. This just gives each device a private ID, so nobody can answer for someone else.

### 4. Register the web app and copy its settings
1. Open **Project settings → General**. The ⚙ gear next to **Project Overview** leads there, or use the direct link <https://console.firebase.google.com/project/_/settings/general>. (Google moves things around; you can also click **Project Overview** and look for **+ Add app** or the **`</>`** icon.)
2. Under **Your apps**, click the **`</>`** (Web) button. Give it a nickname (e.g. `game`), leave "Firebase Hosting" unticked, and click **Register app**.
3. You'll see a block of code with `firebaseConfig`. Copy these values: `apiKey`, `authDomain`, `projectId` and `appId`, plus the database address from step 2.4 if `databaseURL` isn't in the block.
4. Put them into [`firebase-config.js`](firebase-config.js), replacing each `PASTE_...`. You can also send them to Claude to do it for you. These values aren't secret: Firebase web settings are public by design, and the database rules are what protect the game.

### 5. Turn on the web address (GitHub Pages)
1. On GitHub, open this repository, then **Settings → Pages**.
2. Under **Build and deployment**, choose **Source: Deploy from a branch**, **Branch: `main`**, folder **`/ (root)`**, and click **Save**.
3. After a minute or two, the game is live at:
   - **Players:** <https://jhzeiglertowey.github.io/wildlife-detectives-live/>
   - **Big screen:** <https://jhzeiglertowey.github.io/wildlife-detectives-live/host.html>

---

## Running a game

1. **On the big-screen device**, open the big-screen address above. A laptop with Chrome or Edge, connected to a TV, works best.
2. **⚙ Settings:**
   - **Players use:** *Visitors' own phones* or *Booth iPads*.
   - **Camera-trap clips:** add your videos (MP4 works everywhere), and press **Set answers** on each one.
   - **Game options:** clips per game, timers, shuffle, and whether to move on automatically.
3. Press **▶ New game**.
   - **Phones:** visitors scan the QR code, and their name pops up on the big screen.
   - **Booth iPads:** players tap **Tap to play** on an iPad.
4. Press **Start game ▶**. Each clip plays on the big screen, then the questions appear on the phones or iPads. **Next ▶** (or the space bar) skips ahead at any time.
5. At the end, a podium shows the top 3. On the final screen, booth iPads show a QR code to congo-apes.org, and phones show a link.
6. **Results:** Settings → Results → **Download players (CSV)** and **Download answers (CSV)**. Results are kept only on the big-screen device, so download them after each event.

### Setting up booth iPads (once per iPad)
1. In Settings, choose **Booth iPads**. A set-up QR code and link appear.
2. On each iPad, scan the code with the Camera app, or type the link into Safari.
3. In Safari, tap **Share → Add to Home Screen**, and open the game from that icon from then on. Between games, the iPad shows **Tap to play**.

If you ever press **New room code** in Settings, set the iPads up again with the new link.

### Good to know
- **Internet:** the big screen and every phone or iPad need internet (Wi-Fi or mobile data). Only answers and scores travel over it, never videos.
- **Free limits:** Firebase's free plan allows **about 100 devices connected at once**, which is plenty for a booth.
- **Busy zoo Wi-Fi:** Google limits how many *new* players can join from one internet connection (about 100 per hour). If that's reached, phones show **"Too many new players right now"** and ask the visitor to switch to mobile data. They join as soon as they tap **Try again**, and the page also retries by itself every 30 seconds. Booth iPads and phones on mobile data aren't affected.
- **Leave Authentication's "Automatic clean-up" off.** It would delete the big screen's and booth iPads' IDs between events, so the iPads would need setting up again.
- **Keep the big screen awake.** The game asks the screen to stay on, but on an iPad also set Settings → Display → Auto-Lock to Never.
- **iPad as the big screen:** Safari may delete stored videos from websites you haven't opened for 7 days. Add the big-screen page to the Home Screen and open it from there, or use a laptop.
- **Before an event**, do a full practice game with a few real phones.

---

## For developers

- Plain HTML/CSS/JavaScript with no build step. Libraries are vendored in `lib/` (see `lib/LICENSES.md`).
- `host.html`: big screen (IndexedDB for clips/settings/results; it runs the game and computes the scores).
- `index.html`: player page.
- `common.js`: shared helpers.
- `database.rules.json`: security rules.
- Tests use the Firebase Local Emulator Suite and Playwright: see [`tests/README.md`](tests/README.md).
- Project notes and decisions: [`CLAUDE.md`](CLAUDE.md).
