"""Busy-Wi-Fi message through the REAL sign-in code (not the emulator shortcut): the browser is given exactly the
refusal Google's sign-up service sends when too many new accounts come from one connection, and the page must show
the busy-Wi-Fi message and keep retrying. No Firebase project is needed: firebase-config.js is replaced with a dummy
config and Google's sign-up endpoint is answered by the test.
Usage: python3 tests/wifi_real.py <base_url> <screenshot_dir>"""
import asyncio, sys, os, re, json
from playwright.async_api import async_playwright
BASE, OUT = sys.argv[1].rstrip("/") + "/", sys.argv[2]
CHROME = os.environ.get("CHROME", "/opt/pw-browsers/chromium-1194/chrome-linux/chrome")
R = []
def check(name, ok, detail=""):
    R.append(bool(ok)); print(("PASS " if ok else "FAIL ") + name + ((" — " + str(detail)) if detail != "" else ""), flush=True)
FAKE_CONFIG = """window.WD_FIREBASE_CONFIG={apiKey:"AIzaTEST-not-a-real-key",authDomain:"wd-test.firebaseapp.com",databaseURL:"https://wd-test-default-rtdb.firebaseio.com",projectId:"wd-test",appId:"1:1:web:1"};"""
# Error bodies in the format Google's Identity Toolkit returns them.
REFUSALS = {
    "TOO_MANY_ATTEMPTS_TRY_LATER": {"error": {"code": 400, "message": "TOO_MANY_ATTEMPTS_TRY_LATER : Too many sign-up attempts from this IP address. Try again later.", "errors": [{"message": "TOO_MANY_ATTEMPTS_TRY_LATER", "domain": "global", "reason": "invalid"}]}},
    "QUOTA_EXCEEDED": {"error": {"code": 400, "message": "QUOTA_EXCEEDED : Exceeded quota for creating account.", "errors": [{"message": "QUOTA_EXCEEDED", "domain": "global", "reason": "invalid"}]}},
}
async def wt(pg, sel, pat, secs=15):
    for _ in range(int(secs * 5)):
        try:
            t = await pg.locator(sel).first.text_content(timeout=200) or ""
            if re.search(pat, t): return t
        except Exception: pass
        await asyncio.sleep(200/1000)
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROME)
        for name, body in REFUSALS.items():
            ctx = await b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
            pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
            calls = []
            await ctx.route("**/firebase-config.js", lambda r: r.fulfill(status=200, content_type="application/javascript", body=FAKE_CONFIG))
            def make(body):
                async def signup(route):
                    calls.append(route.request.url); await route.fulfill(status=400, content_type="application/json", body=json.dumps(body))
                return signup
            signup = make(body)
            await ctx.route("https://identitytoolkit.googleapis.com/**", signup)
            await ctx.route("https://*.firebaseio.com/**", lambda r: r.abort())
            await pg.clock.install()
            await pg.goto(BASE + "index.html?room=ABCD")
            msg = await wt(pg, "#main", r"Too many new players|Couldn't connect")
            check(f"[{name}] the real sign-in code asked Google to create an account", len(calls) >= 1 and "accounts:signUp" in calls[0], calls[:1])
            check(f"[{name}] phone shows the busy-Wi-Fi message (use mobile data + Try again)", msg and "Too many new players" in msg and "mobile data" in msg, (msg or "")[:90])
            if name == "TOO_MANY_ATTEMPTS_TRY_LATER": await pg.screenshot(path=f"{OUT}/busy_wifi_real.png")
            n = len(calls); await pg.locator("button:has-text('Try again')").click(); await asyncio.sleep(1500/1000)
            check(f"[{name}] Try again asks Google again (and shows the message again while still refused)", len(calls) > n and await wt(pg, "#main", r"Too many new players", 5), len(calls) - n)
            n = len(calls); await pg.clock.run_for(31000); await asyncio.sleep(1500/1000)
            check(f"[{name}] it retries by itself after 30 s", len(calls) > n, len(calls) - n)
            check(f"[{name}] no page errors", not errs, errs[:2])
            await ctx.close()
        print("%d of %d checks passed" % (sum(R), len(R))); await b.close()
asyncio.run(main())
