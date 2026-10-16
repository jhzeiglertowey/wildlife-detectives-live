"""Booth-iPad mode, QR codes, early close, reload mid-game. Same setup as e2e.py.
Usage: python3 tests/booth.py <base_url> <clips_dir> <work_dir>"""
import asyncio, sys, os, re, time
import cv2
from playwright.async_api import async_playwright
BASE, CLIPS, WORK = sys.argv[1].rstrip("/") + "/", sys.argv[2], sys.argv[3]
CHROME = os.environ.get("CHROME", "/opt/pw-browsers/chromium-1194/chrome-linux/chrome")
R = []
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
async def scan(locator, name):
    path = os.path.join(WORK, name + ".png"); await locator.screenshot(path=path)
    img = cv2.imread(path); img = cv2.copyMakeBorder(img, 40, 40, 40, 40, cv2.BORDER_CONSTANT, value=(255, 255, 255))
    data, _, _ = cv2.QRCodeDetector().detectAndDecode(img); return data

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROME, args=["--autoplay-policy=no-user-gesture-required"])
        hc = await b.new_context(viewport={"width": 1280, "height": 800})
        host = await hc.new_page(); errs = []; host.on("pageerror", lambda e: errs.append(str(e)))
        await host.goto(BASE + "host.html?emu=1&uid=host2")
        conn = await wait_text(host, "#connText", r"room [A-Z]{4}"); room = re.search(r"room ([A-Z]{4})", conn).group(1)
        await host.click("#gear"); await host.wait_for_timeout(300)
        await host.set_input_files("input[type=file]", [f"{CLIPS}/clip1.webm", f"{CLIPS}/clip2.webm"])
        await wait_text(host, "#amsg", r"Added 2 of 2")
        for idx, (sp, bh) in enumerate([("Leopard", "Resting"), ("Duiker", "Feeding/foraging")]):
            await host.locator(".clip").nth(idx).locator("button:has-text('Set answers')").click(); await host.wait_for_timeout(200)
            box = host.locator(".clip").nth(idx); await box.locator("select").select_option(sp); await box.locator(".grid .chip", has_text=bh).click()
            await box.locator("button:text-is('Save answers')").click(); await host.wait_for_timeout(1300)
        for k, v in {"secsAnimal": 20, "secsBehavior": 20, "watchMax": 5, "secsReveal": 3, "secsBoard": 2}.items(): await host.fill(f"#o_{k}", str(v))
        await host.uncheck("#o_shuffle"); await host.locator(".card:has(#o_secsAnimal) button:text-is('Save')").click(); await host.wait_for_timeout(300)

        # booth mode + set-up QR
        await host.locator(".radio .chip", has_text="Booth iPads").click(); await host.wait_for_timeout(500)
        setup_url = (await host.locator(".card .url").first.text_content()).strip()
        qr = await scan(host.locator(".radio + .row svg").first, "setup_qr")
        check("booth set-up QR code scans to the set-up link", qr == setup_url and "booth=1" in qr and f"room={room}" in qr, qr)
        await host.locator("button:text-is('← Back')").click(); await host.wait_for_timeout(300)
        hint = await host.locator(".home .hint").last.text_content()
        check("home screen says players use the booth iPads", "booth iPads" in hint, hint)

        # two booth iPads, set up once from the link, then reopened without it
        ipads = []
        for i in range(2):
            c = await b.new_context(viewport={"width": 820, "height": 1180}); pg = await c.new_page(); pg.on("pageerror", lambda e: errs.append(str(e)))
            await pg.goto(setup_url.replace("emu=1", f"emu=1&uid=ipad{i+1}")); await pg.wait_for_timeout(600)
            await pg.goto(BASE + f"index.html?emu=1&uid=ipad{i+1}"); ipads.append(pg)
        w = await wait_text(ipads[0], "#main", r"Waiting for the next game", 10)
        check("booth iPad remembers its room after reopening, and waits for a game", w)
        await host.click("#newGame"); await host.wait_for_timeout(800)
        lob = await host.locator(".join").text_content()
        check("lobby says to grab a booth iPad (no QR code)", "Grab a booth iPad" in lob and await host.locator(".join svg").count() == 0, lob[:60])
        t = await wait_text(ipads[0], "#main", r"Tap to play", 10)
        check("booth iPads show 'Tap to play' (they don't join by themselves)", t and await wait_text(ipads[1], "#main", r"Tap to play", 5))
        await ipads[0].locator("button:has-text('Tap to play')").click()
        cnt = await wait_text(host, "#pcount", r"1 player", 10)
        check("only the iPad that was tapped joins", cnt)

        # start: one player, answering right away closes the question early
        await host.click("#startBtn")
        await wait_text(ipads[0], "#main", r"Which animal is this", 20); await ipads[0].wait_for_timeout(300)
        t0 = time.time(); await ipads[0].locator(".tile", has_text="Leopard").click()
        nxt = await wait_text(ipads[0], "#main", r"What is it doing", 8)
        check("question closes early once every player has answered (not after 20 s)", nxt and time.time() - t0 < 5, round(time.time() - t0, 1))
        # reload mid-game: same name, score kept
        name_before = (await ipads[0].locator("#me").text_content() or "")
        await ipads[0].locator(".chip", has_text="Resting").click(); await ipads[0].locator("button:has-text('Done')").click()
        rv = await wait_text(ipads[0], "#main", r"\+200 points", 10)
        check("iPad gets +200 for clip 1", rv)
        await ipads[0].reload()
        back = await wait_text(ipads[0], "#me", r"\d+ pts", 10)
        check("after reloading mid-game: same name and score kept", back and name_before.split("200")[0].strip() in back and "200 pts" in back, (name_before, back))
        await wait_text(ipads[0], "#main", r"Which animal is this", 25); await ipads[0].wait_for_timeout(300)
        await ipads[0].locator(".tile", has_text="Duiker").click()
        await wait_text(ipads[0], "#main", r"What is it doing", 8); await ipads[0].locator(".chip", has_text="Feeding").click(); await ipads[0].locator("button:has-text('Done')").click()
        fin = await wait_text(ipads[0], "#main", r"Great job", 20)
        check("booth iPad final screen: 400 points", fin and "400 points" in fin, (fin or "")[:90])
        qr2 = await scan(ipads[0].locator(".qr svg"), "booth_final_qr")
        check("booth iPad final screen shows a QR code to congo-apes.org (no link)", qr2 == "https://congo-apes.org/" and await ipads[0].locator("#main a").count() == 0, qr2)
        hq = await scan(host.locator(".qrcard svg"), "host_final_qr")
        check("big screen final QR scans to congo-apes.org", hq == "https://congo-apes.org/", hq)
        # play again -> iPads show Tap to play again
        await host.locator("button:has-text('Play again')").click(); await host.wait_for_timeout(1000)
        again = await wait_text(ipads[0], "#main", r"Tap to play", 10)
        check("next game: the iPad is ready for the next player ('Tap to play')", again)

        # phone mode: lobby QR scans to the join link; final screen has a tappable link
        await host.locator("button:text-is('Cancel')").click(); await host.wait_for_timeout(500)
        await host.click("#gear"); await host.locator(".radio .chip", has_text="Visitors").click(); await host.wait_for_timeout(300)
        await host.locator("button:text-is('← Back')").click(); await host.click("#newGame"); await host.wait_for_timeout(800)
        jq = await scan(host.locator(".join svg"), "lobby_qr")
        check("lobby QR scans to the phone link with the room code", f"room={room}" in jq and "booth" not in jq and "index.html" in jq, jq)
        pc = await b.new_context(viewport={"width": 390, "height": 844}); ph = await pc.new_page(); ph.on("pageerror", lambda e: errs.append(str(e)))
        await ph.goto(jq.replace("emu=1", "emu=1&uid=phone1")); await wait_text(ph, ".name", r"\w", 10)
        await host.click("#startBtn")
        for sp, bh in [("Leopard", "Resting"), ("Duiker", "Feeding")]:
            await wait_text(ph, "#main", r"Which animal is this", 25); await ph.wait_for_timeout(300); await ph.locator(".tile", has_text=sp).click()
            await wait_text(ph, "#main", r"What is it doing", 8); await ph.locator(".chip", has_text=bh).click(); await ph.locator("button:has-text('Done')").click()
        await wait_text(ph, "#main", r"Great job", 20)
        href = await ph.locator("#main a").get_attribute("href")
        check("phone final screen has a tappable congo-apes.org link (no QR code)", href == "https://congo-apes.org/" and await ph.locator("#main svg").count() == 0, href)
        await ph.screenshot(path=os.path.join(WORK, "phone_final.png")); await ipads[0].screenshot(path=os.path.join(WORK, "ipad_final.png"))
        check("no page errors", not errs, errs[:3])
        print("%d of %d checks passed" % (sum(R), len(R)))
        await b.close()
asyncio.run(main())
