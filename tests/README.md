# Tests

The tests run the real pages in Chromium (Playwright) against the **Firebase Realtime Database Emulator**, with the real security rules loaded. Each simulated device gets its own browser context and its own user ID (`?emu=1&uid=...`). The pages only accept `?emu=1` when served from `localhost`/`127.0.0.1`.

## Setup

```bash
npm install firebase-tools          # once; provides the emulator
npx firebase setup:emulators:database
# Run the emulator jar directly. On machines whose outbound traffic goes through a proxy, `firebase emulators:start`
# can fail to load the rules, because the CLI sends them through the proxy.
java -jar ~/.cache/firebase/emulators/firebase-database-emulator-v*.jar --port 9000 &
curl -s --noproxy '*' -X PUT "http://127.0.0.1:9000/.settings/rules.json?ns=demo-wd" \
     -H "Authorization: Bearer owner" --data-binary @database.rules.json
python3 -m http.server 8080 --bind 127.0.0.1 &      # serve the repo root
```

Test clips: any short videos the browser can play. For example (VP9/WebM, because the sandbox Chromium has no H.264):

```bash
for n in 1 2 3; do ffmpeg -f lavfi -i testsrc2=size=640x360:rate=25:duration=4 -f lavfi -i sine=duration=4 \
  -c:v libvpx-vp9 -c:a libopus -shortest clips/clip$n.webm; done
```

## Run

```bash
python3 tests/e2e.py   http://127.0.0.1:8080/ clips downloads   # big screen + 3 phones, full game, scoring, CSVs, security rules
python3 tests/booth.py http://127.0.0.1:8080/ clips work        # booth-iPad mode, QR codes (decoded with OpenCV), early close, reload mid-game
python3 tests/ui.py    http://127.0.0.1:8080/ clips shots       # jungle decor, button animations, scroll position, no needless redraws, Reduce Motion
python3 tests/wifi.py  http://127.0.0.1:8080/ shots             # busy-Wi-Fi message, Try again, automatic retry (simulated with ?failauth=1)
python3 tests/wifi_real.py http://127.0.0.1:8080/ shots          # same, through the real sign-in code, with Google's actual refusal responses (no emulator needed)
```

`booth.py` needs `opencv-python` to decode the QR codes.
