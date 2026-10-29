"""Things going wrong mid-game: the big screen is refreshed during a question (phones are told, the game resumes with
scores kept), a phone loses its connection during a question and comes back, a phone's screen is hidden (locked) and
shown again. Same setup as e2e.py (emulator).
Usage: python3 tests/robust.py <base_url> <clips_dir> <screenshot_dir>"""
import asyncio, sys, os, re, time
from playwright.async_api import async_playwright
BASE, CLIPS, OUT = sys.argv[1].rstrip("/") + "/", sys.argv[2], sys.argv[3]
CHROME = os.environ.get("CHROME", "/opt/pw-browsers/chromium-1194/chrome-linux/chrome")
R = []
def check(name, ok, detail=""):
    R.append(bool(ok)); print(("PASS " if ok else "FAIL ") + name + ((" — " + str(detail)) if detail != "" else ""), flush=True)
async def wt(pg, sel, pat, secs=30):
    for _ in range(int(secs * 5)):
        try:
            t = await pg.locator(sel).first.text_content(timeout=200) or ""
            if re.search(pat, t): return t
        except Exception: pass
        await pg.wait_for_timeout(200)
async def animal(pg, x):
    await wt(pg, "#main", r"Which animal is this", 30); await pg.wait_for_timeout(300)
    await pg.locator(".tile", has_text=x).click()
async def behavior(pg, x):
    await wt(pg, "#main", r"What is it doing", 30); await pg.wait_for_timeout(300)
    await pg.locator(".chip", has_text=x).click(); await pg.locator("button:has-text('Done')").click()
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROME, args=["--autoplay-policy=no-user-gesture-required"])
        hc = await b.new_context(viewport={"width": 1280, "height": 800}); host = await hc.new_page(); errs = []; host.on("pageerror", lambda e: errs.append(str(e)))
        await host.goto(BASE + "host.html?emu=1&uid=robhost"); await wt(host, "#connText", r"room [A-Z]{4}")
        await host.click("#gear"); await host.set_input_files("input[type=file]", [f"{CLIPS}/clip1.webm", f"{CLIPS}/clip2.webm", f"{CLIPS}/clip3.webm"])
        await wt(host, "#amsg", r"Added 3 of 3")
        for idx, (sp, bh) in enumerate([("Leopard", "Resting"), ("Duiker", "Travel"), ("Chimpanzee", "Social")]):
            await host.locator(".clip").nth(idx).locator("button:has-text('Set answers')").click(); await host.wait_for_timeout(200)
            bx = host.locator(".clip").nth(idx); await bx.locator("select").select_option(sp); await bx.locator(".grid .chip", has_text=bh).click()
            await bx.locator("button:text-is('Save answers')").click(); await host.wait_for_timeout(1300)
        for k, v in {"secsAnimal": 12, "secsBehavior": 12, "watchMax": 3, "secsReveal": 2, "secsBoard": 2}.items(): await host.fill(f"#o_{k}", str(v))
        await host.uncheck("#o_shuffle"); await host.locator(".card:has(#o_secsAnimal) button:text-is('Save')").click(); await host.wait_for_timeout(300)
        await host.locator("button:text-is('← Back')").click(); await host.click("#newGame"); await host.wait_for_timeout(800)
        room = (await host.locator(".join .code").text_content()).strip()
        A = await (await b.new_context(viewport={"width": 390, "height": 844})).new_page(); A.on("pageerror", lambda e: errs.append(str(e)))
        Bc = await b.new_context(viewport={"width": 390, "height": 844}); B = await Bc.new_page(); B.on("pageerror", lambda e: errs.append(str(e)))
        await A.goto(BASE + f"index.html?room={room}&emu=1&uid=robA"); await B.goto(BASE + f"index.html?room={room}&emu=1&uid=robB")
        await wt(host, "#pcount", r"2 players", 15); await host.click("#startBtn")

        # clip 1 normally: A right (200), B right animal only (100)
        await animal(A, "Leopard"); await animal(B, "Leopard"); await behavior(A, "Resting"); await behavior(B, "Grooming")
        await wt(A, "#main", r"\+200 points", 30)

        # clip 2: A answers the animal, then the BIG SCREEN IS REFRESHED mid-question
        await animal(A, "Duiker")
        await host.reload()
        away = await wt(A, "#main", r"big screen lost its connection", 15)
        check("big screen refreshed mid-question: phones say it lost its connection (not a frozen question)", away, (away or "")[:60])
        await A.screenshot(path=f"{OUT}/phone_host_away.png")
        box = await wt(host, "#resumeBox", r"interrupted", 15)
        check("after the refresh, the big screen offers 'Resume game' at clip 2 of 3 with 2 players", box and "clip 2 of 3" in box and "2 players" in box, (box or "")[:90])
        await host.screenshot(path=f"{OUT}/host_resume.png")
        await host.click("#resumeBtn")
        w = await wt(A, "#main", r"Watch the big screen", 15)
        check("Resume: the phones come back to the game (clip 2 plays again)", w and "Clip 2 of 3" in w, (w or "")[:60])
        hdr = await A.locator("#me").text_content()
        check("Resume: player A still has 200 points", "200 pts" in hdr, hdr)
        await animal(A, "Duiker")   # A can answer clip 2 again (half-collected answers discarded)

        # B loses its connection during clip 2's animal question, then comes back and answers
        await wt(B, "#main", r"Which animal is this", 30); await B.wait_for_timeout(300)
        await Bc.set_offline(True); await B.wait_for_timeout(4000)
        off = await B.locator("#main").text_content()
        check("phone offline: it says it's reconnecting", "Reconnecting" in off, off[:60])
        await Bc.set_offline(False)
        # While B was offline, A had answered, so the big screen didn't wait for B (by design: one dropped phone mustn't
        # hold up the room) and may already have moved on to "What is it doing?". B answers whatever is current.
        for _ in range(75):   # wait until it has actually reconnected (the "Reconnecting…" line is gone)
            back = await B.locator("#main").text_content()
            if "Reconnecting" not in back and re.search(r"Which animal is this|What is it doing", back): break
            await B.wait_for_timeout(200)
        await B.wait_for_timeout(1500); back = await B.locator("#main").text_content()
        check("phone back online: it shows the current question and can answer it", back, (back or "")[:40])
        missed = "What is it doing" in (back or "")
        if not missed:
            await B.wait_for_timeout(300); await B.locator(".tile", has_text="Duiker").click()
        await behavior(A, "Travel"); await behavior(B, "Travel")
        b2 = 100 if missed else 200
        r2 = await wt(B, "#main", r"\+%d points" % b2, 30)
        check("player B's answers after reconnecting count (+%d for clip 2%s)" % (b2, ", the animal question had closed while it was offline" if missed else ""), r2)

        # clip 3: B's screen is hidden (locked) for a while, then shown again
        await wt(B, "#main", r"Watch the big screen|Which animal", 30)
        await B.evaluate("()=>{Object.defineProperty(document,'visibilityState',{value:'hidden',configurable:true});document.dispatchEvent(new Event('visibilitychange'))}")
        await B.wait_for_timeout(2000)
        await B.evaluate("()=>{Object.defineProperty(document,'visibilityState',{value:'visible',configurable:true});document.dispatchEvent(new Event('visibilitychange'))}")
        await animal(A, "Chimpanzee"); await animal(B, "Chimpanzee"); await behavior(A, "Social"); await behavior(B, "Social")
        fa = await wt(A, "#main", r"You came", 30); fb_ = await wt(B, "#main", r"You came", 10)
        tb = 100 + b2 + 200
        check("game finishes after the refresh: A 600 points, B %d points" % tb, fa and "600 points" in fa and fb_ and "%d points" % tb in fb_, ((fa or "")[:60], (fb_ or "")[:60]))
        await wt(host, "#main", r"Great job", 10)
        pod = await host.locator(".podium").text_content()
        check("big screen podium after resuming shows both players' totals", "600" in pod and str(tb) in pod, pod)
        await host.locator("button:text-is('Done')").click(); await host.wait_for_timeout(500)
        check("after the game, nothing is left to resume", await host.locator("#resumeBox").count() == 0)
        stats = await host.locator(".stats").first.text_content()
        check("the resumed game was saved once in the results (1 game, 2 players)", "1games" in stats.replace(" ", "") and "2players" in stats.replace(" ", ""), stats)
        # End it: interrupt a new game and choose End it instead of Resume
        await host.click("#newGame"); await wt(host, "#pcount", r"2 players", 15); await host.click("#startBtn")
        await wt(A, "#main", r"Which animal is this", 30)
        await host.reload(); await wt(host, "#resumeBox", r"interrupted", 15)
        await host.locator("#resumeBox button:has-text('End it')").click(); await host.locator("#resumeBox button:has-text('Tap again')").click(); await host.wait_for_timeout(1500)
        endA = await wt(A, "#main", r"Waiting for the next game", 10)
        check("'End it' closes the interrupted game: phones go back to waiting", endA and await host.locator("#resumeBox").count() == 0)
        check("no page errors", not errs, errs[:3])
        print("%d of %d checks passed" % (sum(R), len(R))); await b.close()
asyncio.run(main())
