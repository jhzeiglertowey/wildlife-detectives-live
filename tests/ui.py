"""Look-and-feel checks: jungle decor on the right screens, button animations, Settings keeping its scroll position,
phones not redrawing when nothing changed, Reduce Motion. Same setup as e2e.py.
Usage: python3 tests/ui.py <base_url> <clips_dir> <screenshot_dir>"""
import asyncio, sys, os, re
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
JUNGLE = "()=>!document.getElementById('jungle').classList.contains('hide')&&document.getElementById('main').classList.contains('decor')"
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROME, args=["--autoplay-policy=no-user-gesture-required"])
        host = await (await b.new_context(viewport={"width": 1280, "height": 800})).new_page(); errs = []; host.on("pageerror", lambda e: errs.append(str(e)))
        await host.goto(BASE + "host.html?emu=1&uid=uihost"); await wt(host, "#connText", r"room")
        check("big screen home: jungle decor shown", await host.evaluate(JUNGLE))
        await host.screenshot(path=f"{OUT}/host_home.png")
        # Settings: no jungle; add 6 clips so the page scrolls
        await host.click("#gear"); await host.wait_for_timeout(300)
        check("Settings: no jungle decor", not await host.evaluate(JUNGLE))
        await host.set_input_files("input[type=file]", [f"{CLIPS}/clip{n}.webm" for n in (1, 2, 3, 1, 2, 3)])
        await wt(host, "#amsg", r"Added 6 of 6")
        # scroll position is kept when buttons redraw the panel
        await host.locator(".clip").nth(5).scroll_into_view_if_needed(); await host.mouse.wheel(0, 300); await host.wait_for_timeout(300)
        y0 = await host.evaluate("scrollY")
        moves = []
        for label, loc in [("In game", host.locator(".clip").nth(5).locator("button:has-text('In game')")),
                           ("Remove (first tap)", host.locator(".clip").nth(5).locator("button:has-text('Remove')")),
                           ("Set answers", host.locator(".clip").nth(4).locator("button:has-text('Set answers')")),
                           ("Cancel", host.locator(".clip").nth(4).locator("button:text-is('Cancel')"))]:
            before = await host.evaluate("scrollY"); box = await loc.bounding_box()
            await loc.click(); await host.wait_for_timeout(400)
            after = await host.evaluate("scrollY"); box2 = await loc.bounding_box() if await loc.count() else None
            moves.append((label, before, after))
        check("Settings keeps its scroll position when buttons redraw it", y0 > 300 and all(abs(a - b2) < 2 for _, b2, a in moves), moves)
        # pop is re-applied to the redrawn button
        btn = host.locator(".clip").nth(3).locator("button:has-text('In game')")
        await btn.click(); await host.wait_for_timeout(60)
        cls = await host.locator(".clip").nth(3).locator("button:has-text('Not in game')").get_attribute("class")
        check("the tapped button pops even though the panel was redrawn", "pop" in (cls or ""), cls)
        await host.wait_for_timeout(500)
        press = await host.evaluate("""()=>{var r=[...document.styleSheets].flatMap(s=>{try{return [...s.cssRules]}catch(e){return []}}).map(r=>r.cssText).join(' ');
           return /\\.btn:not\\(:disabled\\):active/.test(r)&&/scale\\(0?\\.94\\)/.test(r)}""")
        check("buttons, tiles and chips shrink while pressed (CSS)", press)
        # set answers for 2 clips, make the game short
        for idx, (sp, bh) in enumerate([("Leopard", "Resting"), ("Duiker", "Travel")]):
            await host.locator(".clip").nth(idx).locator("button:has-text('Set answers')").click(); await host.wait_for_timeout(200)
            bx = host.locator(".clip").nth(idx); await bx.locator("select").select_option(sp); await bx.locator(".grid .chip", has_text=bh).click()
            await bx.locator("button:text-is('Save answers')").click(); await host.wait_for_timeout(1300)
        for k, v in {"secsAnimal": 15, "secsBehavior": 15, "watchMax": 3, "secsReveal": 3, "secsBoard": 2, "clipsPerGame": 2}.items(): await host.fill(f"#o_{k}", str(v))
        await host.uncheck("#o_shuffle"); await host.locator(".card:has(#o_secsAnimal) button:text-is('Save')").click(); await host.wait_for_timeout(300)
        await host.locator("button:text-is('← Back')").click(); await host.wait_for_timeout(300)
        anim = await host.evaluate("getComputedStyle(document.getElementById('newGame')).animationName")
        check("'New game' button pulses", anim == "goPulse", anim)
        await host.click("#newGame"); await host.wait_for_timeout(800)
        check("lobby: jungle decor shown", await host.evaluate(JUNGLE))
        room = (await host.locator(".join .code").text_content()).strip()
        # phone: code screen + lobby with jungle; no redraws while others join
        ph = await (await b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)).new_page(); ph.on("pageerror", lambda e: errs.append(str(e)))
        await ph.goto(BASE + "index.html?emu=1&uid=uicode"); await ph.wait_for_timeout(500)
        check("phone code-entry screen: jungle decor shown", await ph.evaluate(JUNGLE)); await ph.screenshot(path=f"{OUT}/phone_code.png")
        await ph.goto(BASE + f"index.html?room={room}&emu=1&uid=uiphone"); await wt(ph, ".name", r"\w")
        check("phone lobby: jungle decor shown", await ph.evaluate(JUNGLE)); await ph.wait_for_timeout(600); await ph.screenshot(path=f"{OUT}/phone_lobby.png")
        await ph.evaluate("()=>{window.__swaps=0;new MutationObserver(m=>{window.__swaps+=m.filter(x=>x.type==='childList').length}).observe(document.getElementById('main'),{childList:true})}")
        others = []
        for i in range(3):
            o = await (await b.new_context(viewport={"width": 390, "height": 844})).new_page(); await o.goto(BASE + f"index.html?room={room}&emu=1&uid=uiother{i}"); others.append(o)
        await wt(host, "#pcount", r"4 players", 15); await ph.wait_for_timeout(800)
        sw = await ph.evaluate("window.__swaps")
        check("phone doesn't redraw while other players join (no flicker)", sw == 0, sw)
        await host.screenshot(path=f"{OUT}/host_lobby.png")
        await host.click("#startBtn")
        await wt(ph, "#main", r"Which animal is this", 20); await ph.wait_for_timeout(300)
        check("question screen: no jungle decor (nothing distracting)", not await ph.evaluate(JUNGLE) and not await host.evaluate(JUNGLE))
        await ph.evaluate("()=>{window.__swaps=0}")
        await others[0].locator(".tile").first.click(); await others[1].locator(".tile").first.click(); await ph.wait_for_timeout(1500)
        sw = await ph.evaluate("window.__swaps")
        check("phone's answer buttons aren't redrawn while others answer (taps can't get lost)", sw == 0, sw)
        await ph.locator(".tile", has_text="Leopard").click(); await others[2].locator(".tile").first.click()
        await wt(ph, "#main", r"What is it doing", 15); await ph.wait_for_timeout(300)
        await ph.locator(".chip", has_text="Resting").click(); await ph.wait_for_timeout(60)
        cls = await ph.locator(".chip", has_text="Resting").get_attribute("class")
        check("tapped chip pops and stays ticked", "pop" in cls and "on" in cls, cls)
        await ph.locator("button:has-text('Done')").click()
        for o in others: await o.locator(".chip").first.click(); await o.locator("button:has-text('Done')").click()
        rv = await wt(ph, "#main", r"points", 15)
        bounce = await ph.evaluate("(()=>{var e=document.querySelector('#main .bounce');return e?getComputedStyle(e).animationName:null})()")
        check("result emoji bounces in", bounce == "bounceIn", bounce)
        for clip in range(1):
            await wt(ph, "#main", r"Which animal is this", 25); await ph.wait_for_timeout(300)
            await ph.locator(".tile", has_text="Duiker").click()
            for o in others: await o.locator(".tile").first.click()
            await wt(ph, "#main", r"What is it doing", 15); await ph.wait_for_timeout(300)
            await ph.locator(".chip", has_text="Travel").click(); await ph.locator("button:has-text('Done')").click()
            for o in others: await o.locator(".chip").first.click(); await o.locator("button:has-text('Done')").click()
        await wt(host, "#main", r"Great job", 20); await host.wait_for_timeout(400)
        conf = await host.evaluate("document.querySelectorAll('.confetti i').length")
        check("big screen final: jungle decor + confetti", await host.evaluate(JUNGLE) and conf > 20, conf)
        await host.screenshot(path=f"{OUT}/host_final.png")
        await wt(ph, "#main", r"Great job", 10); await ph.wait_for_timeout(300)
        check("phone final: jungle decor + confetti", await ph.evaluate(JUNGLE) and await ph.evaluate("document.querySelectorAll('.confetti i').length") > 20)
        await ph.wait_for_timeout(1500); await ph.screenshot(path=f"{OUT}/phone_final.png")
        # Reduce Motion
        rm = await (await b.new_context(viewport={"width": 1280, "height": 800}, reduced_motion="reduce")).new_page()
        await rm.goto(BASE + "host.html?emu=1&uid=uihost"); await wt(rm, "#connText", r"room"); await rm.wait_for_timeout(300)
        r = await rm.evaluate("""()=>({go:getComputedStyle(document.getElementById('newGame')).animationName,
            vine:getComputedStyle(document.querySelector('#jungle .vine')).animationName, bfly:getComputedStyle(document.querySelector('#jungle .bfly')).animationName})""")
        check("Reduce Motion: no pulsing button, still vines and butterflies", all(v == "none" for v in r.values()), r)
        check("no page errors", not errs, errs[:3])
        print("%d of %d checks passed" % (sum(R), len(R)))
        await b.close()
asyncio.run(main())
