#!/usr/bin/env python3
"""Pocket World render farm: render part K of N of a video HTML to an MP4 segment, or its audio mix.
usage: python3 render.py page.html --part K --parts N --fps 30 -o seg.mp4
       python3 render.py page.html --audio -o mix.wav"""
import argparse, base64, functools, http.server, os, subprocess, threading, time
from playwright.sync_api import sync_playwright
ap = argparse.ArgumentParser(); ap.add_argument('page'); ap.add_argument('--part', type=int, default=0); ap.add_argument('--parts', type=int, default=1)
ap.add_argument('--fps', type=int, default=30); ap.add_argument('--audio', action='store_true'); ap.add_argument('--max', type=float, default=0); ap.add_argument('-o', required=True); a = ap.parse_args()
root = os.path.dirname(os.path.abspath(a.page)) or '.'
H = type('Q', (http.server.SimpleHTTPRequestHandler,), {'log_message': lambda *x: None})
srv = http.server.ThreadingHTTPServer(('127.0.0.1', 8765), functools.partial(H, directory=root)); threading.Thread(target=srv.serve_forever, daemon=True).start()
chrome = next((p for p in ['/usr/bin/google-chrome', '/usr/bin/google-chrome-stable', '/usr/bin/chromium'] if os.path.exists(p)), None)
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=chrome, args=['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--autoplay-policy=no-user-gesture-required'])
    pg = b.new_page(viewport={'width': 1920, 'height': 1080}, device_scale_factor=1)
    pg.on('pageerror', lambda e: print('PAGE ERROR', e, flush=True))
    pg.goto(f'http://127.0.0.1:8765/{os.path.basename(a.page)}?ar=16x9', timeout=600000)
    for _ in range(600):
        if pg.evaluate("typeof window.__recStill=='function' && window.__audioReady && window.__audioReady()"): break
        time.sleep(1)
    else: raise SystemExit('page never became ready')
    dur = pg.evaluate('window.__dur()'); print('duration', dur, flush=True)
    if a.audio:
        wav = pg.evaluate(f'window.__mixAudio({a.fps})'); open(a.o, 'wb').write(base64.b64decode(wav)); print('audio ok', flush=True); b.close(); raise SystemExit
    N = int(round((min(dur, a.max) if a.max else dur) * a.fps)); i0, i1 = N * a.part // a.parts, N * (a.part + 1) // a.parts
    print(f'frames {i0}..{i1} of {N}', flush=True)
    ff = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'image2pipe', '-framerate', str(a.fps), '-c:v', 'mjpeg', '-i', '-', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18',
                           '-pix_fmt', 'yuv420p', '-r', str(a.fps), '-g', str(a.fps * 2), a.o + '.tmp.mp4'], stdin=subprocess.PIPE)
    pg.evaluate(f'window.__render({i0 / a.fps})'); t0 = time.time()
    for i in range(i0, i1):
        u = pg.evaluate(f'window.__recStill({i / a.fps})'); ff.stdin.write(base64.b64decode(u.split(',', 1)[1]))
        if (i - i0) % 100 == 0: el = time.time() - t0; print(f'{i - i0}/{i1 - i0} frames · {el / max(1, i - i0):.2f}s/frame', flush=True)
    ff.stdin.close(); assert ff.wait() == 0; os.replace(a.o + '.tmp.mp4', a.o); b.close(); print('done', a.o, flush=True)
