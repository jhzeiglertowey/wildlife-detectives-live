"""End-to-end test: one big screen + three players, against the Firebase Local Emulator.
Usage: python3 tests/e2e.py <base_url> <clips_dir> <download_dir>
  base_url: where this repo is served, e.g. http://127.0.0.1:8080/   (see tests/README.md)
Needs: Playwright (Chromium) and the Firebase Database Emulator on 127.0.0.1:9000 with database.rules.json loaded."""
import asyncio, sys, csv, io, os, re, time
from playwright.async_api import async_playwright
BASE, CLIPS, DL = sys.argv[1].rstrip("/") + "/", sys.argv[2], sys.argv[3]
CHROME = os.environ.get("CHROME", "/opt/pw-browsers/chromium-1194/chrome-linux/chrome")
R = []
# WD_REAL=1: run against the real Firebase project in firebase-config.js instead of the emulator. Each browser gets its
# own real anonymous account. The browser goes through the outbound proxy if one is set (HTTPS_PROXY).
REAL = os.environ.get("WD_REAL") == "1"
def emu(uid): return "" if REAL else f"emu=1&uid={uid}"
def launch_args():
    a = {"executable_path": CHROME, "args": ["--autoplay-policy=no-user-gesture-required"]}
    px = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    if REAL and px: a["proxy"] = {"server": px, "bypass": "127.0.0.1,localhost"}
    return a
def check(name, ok, detail=""):
    R.append(bool(ok)); print(("PASS " if ok else "FAIL ") + name + ((" — " + str(detail)) if detail != "" else ""), flush=True)

async def wait_text(pg, sel, pattern, secs=30):
    for _ in range(int(secs * 5)):
        try:
            t = await pg.locator(sel).first.text_content(timeout=200) or ""
            if re.search(pattern, t): return t
        except Exception: pass
        await pg.wait_for_timeout(200)
    return None

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(**launch_args())
        hc = await b.new_context(viewport={"width": 1280, "height": 800}, accept_downloads=True)
        host = await hc.new_page(); herr = []; host.on("pageerror", lambda e: herr.append(str(e))); host.on("console", lambda m: print("  [host console]", m.text) if m.type in ("error","warning") else None)
        await host.goto(BASE + "host.html?" + emu("host1"))
        conn = await wait_text(host, "#connText", r"room [A-Z]{4}", 45)
        check("big screen connects and gets a room code", conn, conn)
        room = re.search(r"room ([A-Z]{4})", conn or "room ????").group(1)

        # --- Settings: add clips, set answers, short timers
        await host.click("#gear"); await host.wait_for_timeout(300)
        await host.set_input_files("input[type=file]", [f"{CLIPS}/clip1.webm", f"{CLIPS}/clip2.webm", f"{CLIPS}/clip3.webm"])
        m = await wait_text(host, "#amsg", r"Added \d of 3")
        check("3 clips added", m and "Added 3 of 3" in m, m)
        async def set_answer(idx, species, behaviors, none=False):
            await host.locator(".clip").nth(idx).locator("button:has-text('Set answers'), button:has-text('Answers ✔')").first.click(); await host.wait_for_timeout(200)
            box = host.locator(".clip").nth(idx)
            if none: await box.locator("button:has-text('No animal visible')").click(); await host.wait_for_timeout(200); box = host.locator(".clip").nth(idx)
            else:
                await box.locator("select").select_option(species)
                for bh in behaviors: await box.locator(".grid .chip", has_text=bh).click()
            await box.locator("button:text-is('Save answers')").click(); await host.wait_for_timeout(1300)
        await set_answer(0, "Leopard", ["Resting"])
        await set_answer(1, "Chimpanzee", ["Travel", "Social"])
        await set_answer(2, None, [], none=True)
        tags = await host.locator(".clip .tag").all_text_contents()
        check("all 3 clips show as ready", tags == ["ready"] * 3, tags)
        for k, v in {"secsAnimal": 6, "secsBehavior": 8, "watchMax": 5, "secsReveal": 3, "secsBoard": 2}.items():
            await host.fill(f"#o_{k}", str(v))
        await host.uncheck("#o_shuffle")
        await host.locator(".card:has(#o_secsAnimal) button:text-is('Save')").click(); await host.wait_for_timeout(400)
        check("game options saved", "saved" in (await host.locator("#amsg").text_content() or ""))
        await host.locator("button:text-is('← Back')").click(); await host.wait_for_timeout(300)

        # --- New game, three players join
        await host.click("#newGame"); await host.wait_for_timeout(800)
        code = (await host.locator(".join .code").text_content() or "").strip()
        check("lobby shows the room code and a QR code", code == room and await host.locator(".join svg").count() == 1, code)
        players = []
        for i in range(3):
            c = await b.new_context(viewport={"width": 390, "height": 844})
            pg = await c.new_page(); errs = []; pg.on("pageerror", lambda e, errs=errs: errs.append(str(e)))
            await pg.goto(BASE + f"index.html?room={room}" + ("&" + emu(f"player{i+1}") if not REAL else ""))
            players.append((pg, errs))
        names = []
        for pg, _ in players:
            n = await wait_text(pg, ".name", r"\w+ \w+", 15); names.append(n)
        check("each phone joins with a random animal name", all(names) and len(set(names)) == 3, names)
        cnt = await wait_text(host, "#pcount", r"3 players", 10)
        shown = await host.locator(".pname").all_text_contents()
        check("big screen lists all 3 players", cnt and sorted(shown) == sorted(names), shown)
        # reroll on phone 3
        old = names[2]; await players[2][0].locator("button:has-text('New name')").click(); await players[2][0].wait_for_timeout(800)
        new = await players[2][0].locator(".name").text_content()
        await host.wait_for_timeout(500); shown = await host.locator(".pname").all_text_contents()
        check("New name works and the big screen updates", new != old and new in shown, (old, new))
        names[2] = new

        # --- play
        await host.click("#startBtn")
        w = await wait_text(players[0][0], "#main", r"Watch the big screen", 10)
        check("phones show 'Watch the big screen' while the clip plays", w)
        await host.wait_for_timeout(1000)
        playing = await host.evaluate("()=>{var v=document.querySelector('.vidbox video');return v?{paused:v.paused,t:v.currentTime,muted:v.muted}:null}")
        playing = playing and not playing["paused"] and playing["t"] > 0 and playing
        check("clip plays on the big screen", playing)

        plan = [  # (correct animal, p1 behaviors, p2 animal, p2 behaviors)
            ("Leopard", ["Resting"], "wrong", ["Resting", "Travel"]),
            ("Chimpanzee", ["Travel", "Social"], "wrong", ["Travel"]),
            ("No animal visible", None, "wrong", None)]
        for ci, (ans, p1b, p2a, p2b) in enumerate(plan):
            t = await wait_text(players[0][0], "#main", r"Which animal is this", 20); await players[0][0].wait_for_timeout(300)
            check(f"clip {ci+1}: 'Which animal?' appears on the phones", t)
            tiles = await players[0][0].locator(".tile").all_text_contents()
            check(f"clip {ci+1}: 4 answer choices including the right one", len(tiles) == 4 and any(ans in x for x in tiles), tiles)
            hostTiles = await host.locator(".tiles .tile").all_text_contents()
            check(f"clip {ci+1}: big screen shows the same 4 choices", [re.sub(r"^\W+", "", x) for x in hostTiles] == [re.sub(r"^\W+", "", x) for x in tiles], hostTiles)
            await players[0][0].locator(".tile", has_text=ans).click()
            wrong = [x for x in tiles if ans not in x][0]
            await players[1][0].locator(".tile", has_text=re.sub(r"^\W+", "", wrong)).click()
            s = await wait_text(players[0][0], "#main", r"Answer sent", 5)
            a = await wait_text(host, "#answered", r"2 of 3 answered", 5)
            check(f"clip {ci+1}: phone confirms, big screen counts 2 of 3", s and a, a)
            if p1b is not None:
                t0 = time.time()
                t = await wait_text(players[0][0], "#main", r"What is it doing", 12)
                check(f"clip {ci+1}: 'What is it doing?' appears after the animal timer (~6 s)", t, round(time.time() - t0, 1))
                for bh in p1b: await players[0][0].locator(".chip", has_text=bh).click()
                await players[0][0].locator("button:has-text('Done')").click()
                for bh in p2b: await players[1][0].locator(".chip", has_text=bh).click()
                await players[1][0].locator("button:has-text('Done')").click()
            # player 3 never answers -> "Time's up"
            tu = await wait_text(players[2][0], "#main", r"Time's up|It was|No answer|No animal this time", 14)
            check(f"clip {ci+1}: the player who didn't answer sees time's up / the answer", tu, (tu or "")[:60])
            rv = await wait_text(players[0][0], "#main", r"points", 12)
            exp = 200 if p1b is not None else 100
            check(f"clip {ci+1}: player 1 (all right) gets +{exp}", rv and f"+{exp} points" in rv, (rv or "")[:120])
            rv2 = await players[1][0].locator("#main").text_content()
            exp2 = 50 if p1b is not None else 0
            check(f"clip {ci+1}: player 2 (wrong animal, half the behaviors) gets +{exp2}", f"+{exp2} points" in (rv2 or ""), (rv2 or "")[:120])
            hr = await host.locator(".qtitle").first.text_content()
            check(f"clip {ci+1}: big screen reveals the answer", hr and (ans in hr or "No animal" in hr), hr)
            if ci == 0:
                cnts = await host.locator(".tiles .tile.right .count").text_content()
                check("reveal shows how many picked the right animal (1)", (cnts or "").strip() == "1", cnts)
                # security: a player can't take over the game or answer for someone else
                denied = await players[1][0].evaluate(f"""async()=>{{var d=firebase.database(),out={{}};
                  try{{await d.ref('rooms/{room}/game/phase').set('final');out.game='allowed'}}catch(e){{out.game='denied'}}
                  try{{await d.ref('rooms/{room}/results/player2').set({{score:9999}});out.results='allowed'}}catch(e){{out.results='denied'}}
                  try{{await d.ref('rooms/{room}/answers/x/c0a/player1').set('Leopard');out.other='allowed'}}catch(e){{out.other='denied'}}
                  try{{await d.ref('rooms/{room}/meta').set({{host:'player2',mode:'phones'}});out.meta='allowed'}}catch(e){{out.meta='denied'}}
                  return out}}""")
                check("security rules: players can't change the game, scores, others' answers or the room owner", all(v == "denied" for v in denied.values()), denied)
        fin = await wait_text(host, "#main", r"Great job, detectives", 20)
        check("final podium on the big screen", fin)
        pod = await host.locator(".podium .n").all_text_contents()
        check("podium shows the winner (player 1)", names[0] in pod, pod)
        f1 = await wait_text(players[0][0], "#main", r"You came", 8)
        check("player 1 sees: #1 with 500 points", f1 and "#1" in f1 and "500 points" in f1, (f1 or "")[:100])
        f2 = await players[1][0].locator("#main").text_content()
        check("player 2 sees: #2 with 100 points", "#2" in f2 and "100 points" in f2, f2[:100])

        # --- CSVs
        await host.locator("button:text-is('Done')").click(); await host.wait_for_timeout(400)
        await host.click("#gear"); await host.wait_for_timeout(400)
        files = {}
        for key, label in [("players", "Download players (CSV)"), ("answers", "Download answers (CSV)")]:
            async with host.expect_download() as d: await host.locator(f"button:text-is('{label}')").click()
            dd = await d.value; path = os.path.join(DL, dd.suggested_filename); await dd.save_as(path)
            files[key] = list(csv.reader(io.StringIO(open(path, encoding="utf-8-sig").read())))
        pr = files["players"]
        check("players CSV: 3 players, scores 500/100/0", len(pr) == 4 and sorted(int(r[4]) for r in pr[1:]) == [0, 100, 500], [r[3:7] for r in pr[1:]])
        ar = files["answers"]
        check("answers CSV: 9 rows (3 players × 3 clips)", len(ar) == 10, len(ar) - 1)
        p1rows = [r for r in ar[1:] if r[3] == names[0]]
        check("answers CSV: player 1's clip points are 200, 200, 100", [int(r[10]) for r in p1rows] == [200, 200, 100], [r[10] for r in p1rows])
        stats = await host.locator(".stats").last.text_content()
        check("Settings shows 1 game and 3 players", "1games" in stats.replace(" ", "") and "3players" in stats.replace(" ", ""), stats)

        # --- reload persistence on the big screen
        await host.reload(); await host.wait_for_timeout(1500)
        home = await host.locator(".stats").first.text_content()
        check("after reload: 3 clips ready, 1 game, 3 players", "3clips" in home.replace(" ", "") and "1games" in home.replace(" ", "") and "3players" in home.replace(" ", ""), home)

        if REAL:
            await wait_text(host, "#connText", r"room [A-Z]{4}", 45)   # the reloaded big screen re-registers its room first
            left = await host.evaluate(f"""async()=>{{var d=firebase.database(),r='rooms/{room}/';
              for (const k of ['answers','results','players','game']) await d.ref(r+k).remove();
              await d.ref(r+'meta').remove(); await new Promise(res=>setTimeout(res,1500));
              return JSON.stringify((await d.ref('rooms/{room}').get()).val())}}""")
            check("test room deleted from the real database afterwards", left == "null", left)
        allerr = herr + sum([e for _, e in players], [])
        check("no page errors", not allerr, allerr[:3])
        print("%d of %d checks passed" % (sum(R), len(R)))
        await b.close()
asyncio.run(main())
