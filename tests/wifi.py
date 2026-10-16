"""Busy-Wi-Fi message: when Google refuses new anonymous accounts ("too many requests"), the phone explains what to do,
and joins after Try again or after its automatic retry. Same setup as e2e.py.
Usage: python3 tests/wifi.py <base_url> <screenshot_dir>"""
import asyncio, sys, os, re, time
from playwright.async_api import async_playwright
BASE, OUT = sys.argv[1].rstrip("/") + "/", sys.argv[2]
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
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROME)
        host = await (await b.new_context()).new_page(); errs = []; host.on("pageerror", lambda e: errs.append(str(e)))
        await host.goto(BASE + "host.html?emu=1&uid=wifihost")
        room = re.search(r"room ([A-Z]{4})", await wt(host, "#connText", r"room [A-Z]{4}")).group(1)
        # the host needs a clip to open a lobby; write a minimal game state directly instead (lobby phase)
        await host.evaluate(f"""async()=>{{var d=firebase.database();await d.ref('rooms/{room}/game').set({{id:'gwifi',phase:'lobby',total:1,mode:'phones',open:false,clip:-1}})}}""")
        # 1) message + Try again
        ph = await (await b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)).new_page(); ph.on("pageerror", lambda e: errs.append(str(e)))
        await ph.goto(BASE + f"index.html?room={room}&emu=1&uid=wifi1&failauth=1")
        msg = await wt(ph, "#main", r"Too many new players", 10)
        check("busy Wi-Fi: phone explains the problem and says to use mobile data", msg and "mobile data" in msg and "Try again" in msg, (msg or "")[:120])
        await ph.wait_for_timeout(500); await ph.screenshot(path=f"{OUT}/busy_wifi.png")
        await ph.locator("button:has-text('Try again')").click()
        ok = await wt(ph, "#main", r"You're in", 10)
        check("after Try again, the phone joins the game", ok)
        # 2) automatic retry after 30 s, no tap
        ph2 = await (await b.new_context(viewport={"width": 390, "height": 844})).new_page(); ph2.on("pageerror", lambda e: errs.append(str(e)))
        t0 = time.time(); await ph2.goto(BASE + f"index.html?room={room}&emu=1&uid=wifi2&failauth=1")
        await wt(ph2, "#main", r"Too many new players", 10)
        ok2 = await wt(ph2, "#main", r"You're in", 40)
        check("without a tap, the phone retries by itself after ~30 s and joins", ok2 and 28 < time.time() - t0 < 40, round(time.time() - t0, 1))
        players = await host.evaluate(f"""async()=>Object.keys((await firebase.database().ref('rooms/{room}/players').once('value')).val()||{{}}).length""")
        check("both phones are in the game", players == 2, players)
        check("no page errors", not errs, errs[:3])
        print("%d of %d checks passed" % (sum(R), len(R))); await b.close()
asyncio.run(main())
