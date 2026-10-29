"""Screen sizes: plays one game (emulator) and, at every screen, photographs the big screen at TV / laptop / iPad sizes and
several phone sizes, checking that nothing sticks out sideways and that the important button can be reached without scrolling.
Usage: python3 tests/sizes.py <base_url> <clips_dir> <screenshot_dir>"""
import asyncio, sys, os, re
from playwright.async_api import async_playwright
BASE, CLIPS, OUT = sys.argv[1].rstrip("/") + "/", sys.argv[2], sys.argv[3]
CHROME = os.environ.get("CHROME", "/opt/pw-browsers/chromium-1194/chrome-linux/chrome")
HOST_SIZES = {"tv1080": (1920, 1080), "laptop": (1366, 768), "ipadL": (1180, 820), "ipadP": (820, 1180)}
PHONE_SIZES = {"se320": (320, 568), "iphone375": (375, 667), "iphone390": (390, 844), "max430": (430, 932), "ipad820": (820, 1180)}
EXTRA_PLAYERS = 15
R = []; ISSUES = []
def check(name, ok, detail=""):
    R.append(bool(ok)); print(("PASS " if ok else "FAIL ") + name + ((" — " + str(detail)) if detail != "" else ""), flush=True)
async def wt(pg, sel, pat, secs=30):
    for _ in range(int(secs * 5)):
        try:
            t = await pg.locator(sel).first.text_content(timeout=500) or ""
            if re.search(pat, t): return t
        except Exception: pass
        await asyncio.sleep(0.2)
LAYOUT = """(sel)=>{var o={overflowX:document.documentElement.scrollWidth-innerWidth};
  if(sel){var e=document.querySelector(sel);if(!e)o.button='missing';else{var r=e.getBoundingClientRect();o.button=Math.round(r.bottom-innerHeight);o.buttonRight=Math.round(r.right-innerWidth)}}
  /* text clipped inside tiles/chips/buttons */
  o.clipped=[...document.querySelectorAll('#main .tile,#main .chip,#main .btn,#main .pname,#main .bitem')].filter(e=>e.scrollWidth>e.clientWidth+2).map(e=>e.textContent.trim().slice(0,30)).slice(0,4);
  return o}"""
async def shoot(pg, sizes, tag, button):
    for name, (w, h) in sizes.items():
        await pg.set_viewport_size({"width": w, "height": h}); await pg.wait_for_timeout(450)
        await pg.evaluate("window.scrollTo(0,0)")
        L = await pg.evaluate(LAYOUT, button)
        await pg.screenshot(path=f"{OUT}/{tag}_{name}.png")
        probs = []
        if L["overflowX"] > 1: probs.append(f"page is {L['overflowX']}px too wide")
        if button and L.get("button") == "missing": probs.append(f"{button} missing")
        elif button and (L["button"] > 0 or L.get("buttonRight", 0) > 0): probs.append(f"{button} needs scrolling ({L['button']}px below)")
        if L["clipped"]: probs.append("text cut off: " + ", ".join(L["clipped"]))
        if probs: ISSUES.append(f"{tag} @ {name} {w}x{h}: " + "; ".join(probs))
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROME, args=["--autoplay-policy=no-user-gesture-required"])
        host = await (await b.new_context(viewport={"width": 1920, "height": 1080})).new_page(); errs = []; host.on("pageerror", lambda e: errs.append(str(e)))
        await host.goto(BASE + "host.html?emu=1&uid=sizehost"); room = re.search(r"room ([A-Z]{4})", await wt(host, "#connText", r"room [A-Z]{4}")).group(1)
        await host.click("#gear"); await host.set_input_files("input[type=file]", [f"{CLIPS}/clip1.webm", f"{CLIPS}/clip2.webm"]); await wt(host, "#amsg", r"Added 2")
        for idx, (sp, bh) in enumerate([("Red river hog", ["Feeding/foraging", "Curiosity towards camera"]), ("Western lowland gorilla", ["Fearful towards camera"])]):
            await host.locator(".clip").nth(idx).locator("button:has-text('Set answers')").click(); await host.wait_for_timeout(200)
            bx = host.locator(".clip").nth(idx); await bx.locator("select").select_option(sp)
            for x in bh: await bx.locator(".grid .chip", has_text=x).click()
            await bx.locator("button:text-is('Save answers')").click(); await host.wait_for_timeout(1300)
        for k, v in {"secsAnimal": 120, "secsBehavior": 120, "watchMax": 60}.items(): await host.fill(f"#o_{k}", str(v))
        await host.uncheck("#o_shuffle"); await host.uncheck("#o_autoAdvance"); await host.locator(".card:has(#o_secsAnimal) button:text-is('Save')").click(); await host.wait_for_timeout(300)
        await host.evaluate("window.scrollTo(0,0)"); await shoot(host, HOST_SIZES, "host_settings", None)
        await host.locator("button:text-is('← Back')").click(); await host.wait_for_timeout(300)
        await shoot(host, HOST_SIZES, "host_home", "#newGame")
        await host.click("#newGame"); await host.wait_for_timeout(800)
        phones = {}
        for name, (w, h) in PHONE_SIZES.items():
            pg = await (await b.new_context(viewport={"width": w, "height": h}, device_scale_factor=2)).new_page(); pg.on("pageerror", lambda e: errs.append(str(e)))
            await pg.goto(BASE + f"index.html?room={room}&emu=1&uid=size_{name}"); phones[name] = pg
        code = await (await b.new_context(viewport={"width": 320, "height": 568})).new_page(); await code.goto(BASE + "index.html?emu=1&uid=sizecode"); await code.wait_for_timeout(800)
        await shoot(code, {"se320": (320, 568), "iphone390": (390, 844)}, "phone_code", "button.go")
        extra = []
        for i in range(EXTRA_PLAYERS):
            pg = await (await b.new_context(viewport={"width": 390, "height": 844})).new_page(); await pg.goto(BASE + f"index.html?room={room}&emu=1&uid=sizex{i}"); extra.append(pg)
        await wt(host, "#pcount", rf"{len(phones) + EXTRA_PLAYERS} players", 40)
        async def phones_shoot(tag, button):
            for name, pg in phones.items():
                w, h = PHONE_SIZES[name]; await shoot(pg, {name: (w, h)}, tag, button)
        await shoot(host, HOST_SIZES, "host_lobby", "#startBtn"); await phones_shoot("phone_lobby", None)
        await host.set_viewport_size({"width": 1920, "height": 1080}); await host.click("#startBtn"); await host.wait_for_timeout(1500)
        await shoot(host, HOST_SIZES, "host_watch", ".ctrl .btn.big"); await phones_shoot("phone_watch", None)
        if (await host.locator(".ctrl .btn.big").text_content()).startswith("Next"): await host.locator(".ctrl .btn.big").click()   # skip the rest of the clip
        await wt(phones["iphone390"], "#main", r"Which animal is this", 20); await host.wait_for_timeout(800)
        await shoot(host, HOST_SIZES, "host_animal", ".ctrl .btn.big"); await phones_shoot("phone_animal", ".tile:last-of-type")
        allp = list(phones.values()) + extra
        for k, pg in enumerate(allp):
            t = await wt(pg, "#main", r"Which animal is this", 20)
            await pg.locator(".tile").first.click()
        await wt(phones["iphone390"], "#main", r"What is it doing", 20); await host.wait_for_timeout(800)
        await shoot(host, HOST_SIZES, "host_behavior", ".ctrl .btn.big"); await phones_shoot("phone_behavior", "#main button.btn.big")
        for pg in allp: await wt(pg, "#main", r"What is it doing", 20); await pg.locator(".chip").first.click(); await pg.locator("button:has-text('Done')").click()
        await wt(host, ".qtitle", r"It's a", 20); await host.wait_for_timeout(800)
        await shoot(host, HOST_SIZES, "host_reveal", ".ctrl .btn.big"); await phones_shoot("phone_reveal", None)
        await host.locator(".ctrl .btn.big").click(); await wt(host, "#main", r"Leaderboard", 10); await host.wait_for_timeout(800)
        await shoot(host, HOST_SIZES, "host_board", ".ctrl .btn.big"); await phones_shoot("phone_board", None)
        await host.locator(".ctrl .btn.big").click(); await host.wait_for_timeout(800)   # leave the leaderboard
        if (await host.locator(".ctrl .btn.big").text_content()).startswith("Next"): await host.locator(".ctrl .btn.big").click()   # skip clip 2's watch
        await wt(phones["iphone390"], "#main", r"Which animal is this", 20)
        for pg in allp: await wt(pg, "#main", r"Which animal is this", 20); await pg.locator(".tile").first.click()
        await wt(phones["iphone390"], "#main", r"What is it doing", 20)
        for pg in allp: await wt(pg, "#main", r"What is it doing", 20); await pg.locator(".chip").first.click(); await pg.locator("button:has-text('Done')").click()
        await wt(host, ".qtitle", r"It's a", 20); await host.locator(".ctrl .btn.big").click()
        await wt(host, "#main", r"Great job", 15); await host.wait_for_timeout(6000)   # let the confetti finish
        await shoot(host, HOST_SIZES, "host_final", ".ctrl .btn.big"); await phones_shoot("phone_final", None)
        print("\n".join("ISSUE " + x for x in ISSUES) or "no layout issues found")
        check("no layout issues at any size", not ISSUES, len(ISSUES))
        check("no page errors", not errs, errs[:3])
        print("%d of %d checks passed" % (sum(R), len(R))); await b.close()
asyncio.run(main())
