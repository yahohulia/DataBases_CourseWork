"""Знімок Swagger UI з виконаним запитом (Try it out -> Execute) через Chrome DevTools Protocol."""
import asyncio
import base64
import json
import subprocess
import sys
import time
import urllib.request

import websockets

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PORT = 9333


async def main(op_id, params, out, height):
    proc = subprocess.Popen([CHROME, "--headless=new", f"--remote-debugging-port={PORT}",
                             "--disable-gpu", "--hide-scrollbars", "--window-size=1280,900",
                             "--user-data-dir=" + sys.argv[0] + ".profile", "about:blank"])
    try:
        for _ in range(50):
            try:
                tabs = json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json"))
                break
            except Exception:
                time.sleep(0.2)
        ws_url = [t for t in tabs if t["type"] == "page"][0]["webSocketDebuggerUrl"]
        async with websockets.connect(ws_url, max_size=50_000_000) as ws:
            n = 0

            async def cmd(method, **p):
                nonlocal n
                n += 1
                await ws.send(json.dumps({"id": n, "method": method, "params": p}))
                while True:
                    msg = json.loads(await ws.recv())
                    if msg.get("id") == n:
                        return msg.get("result", {})

            async def js(expr):
                r = await cmd("Runtime.evaluate", expression=expr, awaitPromise=True)
                return r.get("result", {}).get("value")

            await cmd("Emulation.setDeviceMetricsOverride", width=1280, height=height,
                      deviceScaleFactor=1, mobile=False)
            await cmd("Page.navigate", url=f"http://127.0.0.1:8000/docs#/{op_id}")
            await asyncio.sleep(4)
            sel = f"#operations-{op_id}"
            await js(f"document.querySelector('{sel} .opblock-summary-control').click()")
            await asyncio.sleep(1)
            await js(f"document.querySelector('{sel} .try-out__btn').click()")
            await asyncio.sleep(1)
            for name, value in params.items():
                await js(f"""(() => {{
                    const el = document.querySelector('{sel} tr[data-param-name="{name}"] input');
                    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
                    setter.call(el, '{value}');
                    el.dispatchEvent(new Event('input', {{bubbles: true}}));
                    el.dispatchEvent(new Event('change', {{bubbles: true}}));
                }})()""")
            await asyncio.sleep(0.5)
            await js(f"document.querySelector('{sel} .execute').click()")
            await asyncio.sleep(3)
            # прокрутка до операції
            await js(f"window.scrollTo(0, document.querySelector('{sel}').getBoundingClientRect().top + window.scrollY - 10)")
            await asyncio.sleep(1)
            shot = await cmd("Page.captureScreenshot", format="png")
            with open(out, "wb") as f:
                f.write(base64.b64decode(shot["data"]))
    finally:
        proc.terminate()


if __name__ == "__main__":
    op, params, out, h = sys.argv[1], json.loads(sys.argv[2]), sys.argv[3], int(sys.argv[4])
    asyncio.run(main(op, params, out, h))
