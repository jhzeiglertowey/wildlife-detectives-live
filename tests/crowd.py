"""Crowd test: one big screen and N players (default 30) answering at the same time. Works against the emulator or,
with WD_REAL=1, the real Firebase project. Checks joining, the lobby with many names, everyone answering at once,
the early close, scores/ranks for every player against an independent calculation, the leaderboard and podium.
Usage: [WD_REAL=1] python3 tests/crowd.py <base_url> <clips_dir> <screenshot_dir> [N]"""
import asyncio, sys, os, re, time
from playwright.async_api import async_playwright
BASE, CLIPS, OUT = sys.argv[1].rstrip("/") + "/", sys.argv[2], sys.argv[3]
N = int(sys.argv[4]) if len(sys.argv) > 4 else 30
CHROME = os.environ.get("CHROME", "/opt/pw-browsers/chromium-1194/chrome-linux/chrome")
REAL = os.environ.get("WD_REAL") == "1"
R = []
def check(name, ok, detail=""):
    R.append(bool(ok)); print(("PASS " if ok else "FAIL ") + name + ((" — " + str(detail)) if detail != "" else ""), flush=True)
def emu(uid): return "" if REAL else f"&emu=1&uid={uid}"
async def wt(pg, sel, pat, secs=30):
    for _ in range(int(secs * 5)):
        try:
            t = await pg.locator(sel).first.text_content(timeout=500) or ""
            if re.search(pat, t): return t
        except Exception: pass
        await asyncio.sleep(0.2)
# What each player does: clip answers depend on the player number, so the expected scores are known in advance.
CLIPSET = [("Leopard", ["Resting"]), ("Duiker", ["Travel", "Feeding/foraging"])]
def plan(i, c):
    sp, bh = CLIPSET[c]
    animal_right = (i % 3) != 0                       # 2 in 3 players get the animal
    beh = bh if i % 2 == 0 else bh[:1] + (["Social"] if c == 0 else [])   # even players exact; odd players partial
    return animal_right, beh
def expected(i):
    total = 0
    for c, (sp, bh) in enumerate(CLIPSET):
        ok, beh = plan(i, c)
        hits = [b for b in beh if b in bh]; wrong = [b for b in beh if b not in bh]; missed = [b for b in bh if b not in beh]
        un = len(hits) + len(wrong) + len(missed)
        total += (100 if ok else 0) + (100 if not wrong and not missed else round(100 * len(hits) / un))
    return total
async def main():
    async with async_playwright() as p:
        a = {"executable_path": CHROME, "args": ["--autoplay-policy=no-user-gesture-required"]}
        px = os.environ.get("HTTPS_PROXY")
        if REAL and px: a["proxy"] = {"server": px, "bypass": "127.0.0.1,localhost"}
        b = await p.chromium.launch(**a)
        host = await (await b.new_context(viewport={"width": 1920, "height": 1080})).new_page(); errs = []; host.on("pageerror", lambda e: errs.append("host: " + str(e)))
        await host.goto(BASE + "host.html?" + emu("crowdhost").lstrip("&"))
        room = re.search(r"room ([A-Z]{4})", await wt(host, "#connText", r"room [A-Z]{4}", 45)).group(1)
        await host.click("#gear"); await host.set_input_files("input[type=file]", [f"{CLIPS}/clip1.webm", f"{CLIPS}/clip2.webm"])
        await wt(host, "#amsg", r"Added 2 of 2")
        for idx, (sp, bh) in enumerate(CLIPSET):
            await host.locator(".clip").nth(idx).locator("button:has-text('Set answers')").click(); await host.wait_for_timeout(200)
            bx = host.locator(".clip").nth(idx); await bx.locator("select").select_option(sp)
            for x in bh: await bx.locator(".grid .chip", has_text=x).click()
            await bx.locator("button:text-is('Save answers')").click(); await host.wait_for_timeout(1300)
        for k, v in {"secsAnimal": 30, "secsBehavior": 30, "watchMax": 3, "secsReveal": 4, "secsBoard": 4}.items(): await host.fill(f"#o_{k}", str(v))
        await host.uncheck("#o_shuffle"); await host.locator(".card:has(#o_secsAnimal) button:text-is('Save')").click(); await host.wait_for_timeout(300)
        await host.locator("button:text-is('← Back')").click(); await host.click("#newGame"); await host.wait_for_timeout(800)
        # N phones join (in batches, like people scanning the QR code)
        phones = []
        async def open_phone(i):
            ctx = await b.new_context(viewport={"width": 390, "height": 844}); pg = await ctx.new_page()
            pg.on("pageerror", lambda e, i=i: errs.append(f"phone{i}: " + str(e)))
            await pg.goto(BASE + f"index.html?room={room}" + emu(f"crowd{i}"))
            return pg
        t0 = time.time()
        for s in range(0, N, 10): phones += await asyncio.gather(*[open_phone(i) for i in range(s, min(N, s + 10))])
        ok = await wt(host, "#pcount", rf"^{N} players", 90)
        check(f"all {N} phones joined and the big screen counts {N} players", ok, f"{round(time.time() - t0, 1)} s")
        names = [await pg.locator(".name").text_content() for pg in phones]
        check("every player got a different name", len(set(names)) == N, f"{len(set(names))} unique of {N}")
        await host.screenshot(path=f"{OUT}/crowd_lobby.png")
        await host.click("#startBtn")
        for c, (sp, bh) in enumerate(CLIPSET):
            await asyncio.gather(*[wt(pg, "#main", r"Which animal is this", 40) for pg in phones]); await asyncio.sleep(0.5)
            async def ans_animal(i, pg):
                ok, _ = plan(i, c); tiles = await pg.locator(".tile").all_text_contents()
                pick = sp if ok else next(re.sub(r"^\W+", "", t) for t in tiles if sp not in t)
                await pg.locator(".tile", has_text=pick).click()
            t1 = time.time(); await asyncio.gather(*[ans_animal(i, pg) for i, pg in enumerate(phones)])
            got = await wt(host, "#answered", rf"{N} of {N} answered", 20)
            nxt = await wt(phones[0], "#main", r"What is it doing", 20)
            check(f"clip {c+1}: all {N} answers counted on the big screen, and the question closed early (not after 30 s)", got and nxt and time.time() - t1 < 20, f"{round(time.time() - t1, 1)} s")
            await host.screenshot(path=f"{OUT}/crowd_q{c+1}.png") if c == 0 else None
            await asyncio.gather(*[wt(pg, "#main", r"What is it doing", 20) for pg in phones]); await asyncio.sleep(0.5)
            async def ans_beh(i, pg):
                _, beh = plan(i, c)
                for x in beh: await pg.locator(".chip", has_text=x).click()
                await pg.locator("button:has-text('Done')").click()
            t2 = time.time(); await asyncio.gather(*[ans_beh(i, pg) for i, pg in enumerate(phones)])
            rv = await wt(host, ".qtitle", r"It's a", 25)
            check(f"clip {c+1}: behavior answers from all {N} closed the question early and the answer was revealed", rv and time.time() - t2 < 25, f"{round(time.time() - t2, 1)} s")
            cnt = await host.locator(".tiles .tile.right .count").text_content()
            exp_right = sum(1 for i in range(N) if plan(i, c)[0])
            check(f"clip {c+1}: reveal counts {exp_right} players who picked the right animal", cnt.strip() == str(exp_right), cnt)
            if c == 0:
                await wt(host, "#main", r"Leaderboard", 15); await host.wait_for_timeout(700); await host.screenshot(path=f"{OUT}/crowd_board.png")
        await wt(host, "#main", r"Great job", 30); await host.wait_for_timeout(1000); await host.screenshot(path=f"{OUT}/crowd_final.png")
        finals = await asyncio.gather(*[wt(pg, "#main", r"You came", 20) for pg in phones])
        scores = [int(re.search(r"with (\d+) points", f).group(1)) if f else None for f in finals]
        exp = [expected(i) for i in range(N)]
        bad = [(i, scores[i], exp[i]) for i in range(N) if scores[i] != exp[i]]
        check(f"every one of the {N} players has exactly the expected score", not bad, bad[:5] or f"scores {sorted(set(exp))}")
        ranks = [int(re.search(r"#(\d+) of", f).group(1)) for f in finals if f]
        exp_rank = [1 + sum(1 for e in exp if e > x) for x in exp]
        check("every player's rank is right (ties share a rank)", ranks == exp_rank, (ranks[:8], exp_rank[:8]))
        pod = await host.locator(".podium .s").all_text_contents()
        check("podium shows the top scores", pod and all(str(max(exp)) in x for x in pod[:1]) or str(max(exp)) in "".join(pod), pod)
        if REAL:
            left = await host.evaluate(f"""async()=>{{var d=firebase.database(),r='rooms/{room}/';await d.ref(r+'game').set({{id:'x',phase:'closed',total:1,mode:'phones',open:false}});
              for (const k of ['answers','results','players','game','meta']) await d.ref(r+k).remove(); await new Promise(res=>setTimeout(res,1500));
              return JSON.stringify((await d.ref('rooms/{room}').get()).val())}}""")
            check("test room deleted from the real database afterwards", left == "null", left[:100])
        check("no page errors", not errs, errs[:3])
        print("%d of %d checks passed" % (sum(R), len(R))); await b.close()
asyncio.run(main())
