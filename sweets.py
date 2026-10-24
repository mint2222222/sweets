#!/usr/bin/env python3
"""sweets - a plate of desserts slowly spinning in your terminal."""
import argparse
import curses
import math
import random
import time

import models

RAMP = ":;=+*xX#%@"  # desserts: heavy symbols, none shared with the plate
PLATE_RAMP = ".,-~"  # plate and cup: light marks that stay in the background
CAM = math.radians(32)  # how far we look down onto the plate
SV, CV = math.sin(CAM), math.cos(CAM)
_n = math.sqrt(0.55 ** 2 + 0.85 ** 2 + 0.5 ** 2)
LX, LY, LZ = -0.55 / _n, 0.85 / _n, 0.5 / _n  # light from the upper left, in front
_n = math.sqrt(LX ** 2 + (LY + SV) ** 2 + (LZ + CV) ** 2)
HX, HY, HZ = LX / _n, (LY + SV) / _n, (LZ + CV) / _n  # half vector for glossy highlights
_n = math.hypot(LZ, LX)
UX, UZ = LZ / _n, -LX / _n  # light-space axes: U is flat, V = L x U
VX, VY, VZ = LY * UZ, LZ * UX - LX * UZ, -LY * UX
AMB, DIF = 0.22, 0.95
EXPOSURE = 0.78
SG = 30  # shadow map cells per world unit
BIAS = 0.04  # how far behind the nearest surface a point must be to count as shadowed
EDGE = 0.08  # depth jump that gets a dark outline, on top of what a tilted surface does per row
SURFACE = 0.03  # points this close in depth are the same surface
STEPS = 180  # cached frames per full turn
LEFT, RIGHT, TOP, BOTTOM = -1.08, 1.78, 1.0, -0.62  # scene bounds in world units
CUP = (1.42, -0.03, -0.3)
FPS = 15
SPARKLE = ".+*+."
SAVER_SECONDS = 30
EAT_SECONDS = 7.0
BITE = 0.2
SCALE = 1.2  # desserts are modelled a bit small for the plate
HINT = "space next  e eat  r serve again  c clock  s screensaver  +/- speed  q quit"
SIDE, FLOOR = 0, 0  # room kept free for the --peaks curtains and floor
HIDDEN = {"cherrypie"}  # not on the menu; you have to know to ask
PEAKS_LINES = [
    "damn fine cherry pie",
    "and a cup of coffee, black as midnight on a moonless night",
    "diane, the pie at the double r is everything they said it was",
    "the owls are not what they seem",
    "every day, give yourself a present",
    "welcome to twin peaks",
    "diane, i have no idea where this will lead us, but it will be wonderful",
]
OWL = [" ,___,", " (O,O)", " /)_)", '  ""']

ANSI = {"plate": 7, "cream": 7, "crust": 3, "red": 1, "pink": 5, "green": 2, "yellow": 3, "purple": 5,
        "brown": 3, "chocolate": 1, "orange": 3, "white": 7, "dark": 0, "blue": 4}
THEMES = {  # material: (shadowed, lit) xterm-256 colours
    "gruvbox": {"plate": (243, 250), "cream": (246, 229), "crust": (130, 172), "red": (124, 167),
                "pink": (132, 175), "green": (100, 142), "yellow": (172, 214), "purple": (96, 132),
                "brown": (94, 130), "chocolate": (52, 94), "orange": (166, 208), "white": (248, 230),
                "dark": (237, 239), "blue": (24, 109)},
    "amber": {m: (130, 214) for m in models.MATS},
    "green": {m: (28, 46) for m in models.MATS},
    "term": None,  # your terminal's own 16 colours, so it follows whatever theme you run
}


def layout(w, h):
    k = min((w - 2 - 2 * SIDE) / (RIGHT - LEFT), (h - 4 - FLOOR) * 2 / (TOP - BOTTOM), 48)  # cells per world unit
    return k, (w - (RIGHT - LEFT) * k) / 2 - LEFT * k, 1 + TOP * k / 2


def project(x, y, z, c, s, k, ox, oy):
    X, Z = x * c - z * s, x * s + z * c
    return int(ox + X * k), int(oy - (y * CV - Z * SV) * k / 2)


def cast(pts, c, s, smap):
    """shadow map: for each light-space cell, how far toward the light the nearest surface is."""
    for x, y, z, *_ in pts:
        X, Z = x * c - z * s, x * s + z * c
        key = (int((X * UX + Z * UZ) * SG), int((X * VX + y * VY + Z * VZ) * SG))
        d = X * LX + y * LY + Z * LZ
        if d > smap.get(key, -9):
            smap[key] = d


def splat(pts, c, s, k, ox, oy, w, h, zb, lum, cnt, mat, back=False, smap=None):
    """draw points into the z-buffer, lit, with shadows from smap."""
    kh = k / 2
    for x, y, z, nx, ny, nz, alb, gl, m in pts:
        X, Z = x * c - z * s, x * s + z * c
        NX, NZ = nx * c - nz * s, nx * s + nz * c
        facing = ny * SV + NZ * CV
        if facing < 0 and not back:
            continue
        col, row = int(ox + X * k), int(oy - (y * CV - Z * SV) * kh)
        if 0 <= col < w and 0 <= row < h:
            d, i = y * SV + Z * CV, row * w + col
            if d > zb[i] - SURFACE:
                if facing < 0:
                    v = alb * 0.3  # the inside, seen through a bite
                else:
                    dif = NX * LX + ny * LY + NZ * LZ
                    if dif < 0:
                        dif = 0
                    elif smap is not None:
                        key = (int((X * UX + Z * UZ) * SG), int((X * VX + y * VY + Z * VZ) * SG))
                        if smap.get(key, -9) > X * LX + y * LY + Z * LZ + BIAS:
                            dif = 0
                    v = alb * (AMB * (0.6 + 0.4 * ny) + DIF * dif)
                    if gl and dif:
                        sp = NX * HX + ny * HY + NZ * HZ
                        if sp > 0:
                            v += gl * sp ** 24
                if d > zb[i] + SURFACE:  # a new front surface: start over
                    zb[i], lum[i], cnt[i], mat[i] = d, v, 1, m
                else:  # same surface: average, it smooths the speckle
                    lum[i] += v
                    cnt[i] += 1
                    if d > zb[i]:
                        zb[i] = d


def frame(scene, theta, w, h, back=False):
    """render one view: a list of text rows and one colour slot per cell (255 = empty)."""
    k, ox, oy = layout(w, h)
    n, c, s = w * h, math.cos(theta), math.sin(theta)
    zb, lum, cnt, mat, smap = [-9.0] * n, [0.0] * n, [0] * n, bytearray(n), {}
    cast(scene["dessert"], c, s, smap)
    splat(scene["dessert"], c, s, k, ox, oy, w, h, zb, lum, cnt, mat, back, smap)
    splat(scene["plate"], c, s, k, ox, oy, w, h, zb, lum, cnt, mat, smap=smap)
    splat(scene["cup"], 1.0, 0.0, k, ox, oy, w, h, zb, lum, cnt, mat)
    chars, slots, edge, plate = [" "] * n, bytearray(b"\xff" * n), EDGE + 4 / k, models.MAT["plate"]
    for i in range(n):
        if zb[i] > -9:
            v, d = lum[i] / cnt[i], zb[i]
            if any(zb[j] > d + edge for j in (i - 1, i + 1, i - w, i + w) if 0 <= j < n):
                v *= 0.4  # dark outline where something closer overlaps
            ramp = PLATE_RAMP if mat[i] == plate else RAMP
            chars[i] = ramp[min(len(ramp) - 1, int((v * EXPOSURE) ** 0.75 * len(ramp)))]  # gamma: more room for highlights
            slots[i] = mat[i] * 2 + (v > 0.5)
    for i in range(n):  # a blank gap between dessert and plate so they never run together
        if slots[i] // 2 == plate and any(slots[j] != 255 and slots[j] // 2 != plate
                                          for j in (i - 1, i + 1, i - w, i + w) if 0 <= j < n):
            chars[i], slots[i] = " ", 255
    return ["".join(chars[r * w:r * w + w]) for r in range(h)], slots


def plan_bites(pts):
    """greedy bites from the top down until nothing is left. returns bite centres."""
    left, bites = [p[:3] for p in pts[::5]], []
    cur = max(left, key=lambda p: p[1], default=None)
    while left and len(bites) < 60:
        cur = min(left, key=lambda p: (p[0] - cur[0]) ** 2 + (p[1] - cur[1]) ** 2 + (p[2] - cur[2]) ** 2)
        bites.append(cur)
        left = bitten(left, cur)
    return bites


def bitten(pts, b):
    return [p for p in pts if (p[0] - b[0]) ** 2 + (p[1] - b[1]) ** 2 + (p[2] - b[2]) ** 2 > BITE ** 2]


class Table:
    """everything on screen for one dessert, with its cached frames."""

    def __init__(self, dessert_id, w, h, coffee=False):
        self.id, self.w, self.h = dessert_id, w, h
        self.name, self.caption, self.builder, self.phases = models.DESSERTS[dessert_id]
        self.ds = 0.6 / layout(w, h)[0]  # point spacing: a couple of points per cell, averaged
        base, cup = models.Model(self.ds), models.Model(self.ds)
        models.plate(base)
        models.teacup(cup, *CUP, coffee=coffee)
        self.plate, self.cup, self.steam = base.pts, cup.pts, cup.extras["steam"]
        self.models, self.frames, self.eaten = {}, {}, None

    def model(self, phase):
        if phase not in self.models:
            m = models.Model(self.ds / SCALE)
            self.builder(m, phase)
            m.pts = [(x * SCALE, y * SCALE, z * SCALE, *rest) for x, y, z, *rest in m.pts]
            m.extras = {key: [(x * SCALE, y * SCALE, z * SCALE) for x, y, z in v] for key, v in m.extras.items()}
            self.models[phase] = m
        return self.models[phase]

    def eat(self, phase):
        crumbs = models.Model(self.ds, seed=3)
        for _ in range(10):
            crumbs.at(random.uniform(-0.6, 0.6), 0, random.uniform(-0.6, 0.6))
            size = random.uniform(0.015, 0.03)
            crumbs.ellipsoid(size, size * 0.6, size, crumbs.paint("crust", 0.6, 0, 0.4))
        pts = self.model(phase).pts
        self.eaten = {"bites": plan_bites(pts), "done": 0, "pts": pts, "crumbs": crumbs.pts, "phase": phase}

    def render(self, theta, phase, progress=None):
        """progress: None, or how far through eating it we are (0..1). returns the frame and the angle shown."""
        step = round(theta % math.tau / math.tau * STEPS) % STEPS
        if self.eaten:
            e = self.eaten
            phase, bites = e["phase"], len(e["bites"])
            want = min(bites, int(progress * (bites + 1)))
            while e["done"] < want:
                e["pts"] = bitten(e["pts"], e["bites"][e["done"]])
                e["done"] += 1
            pts = (e["pts"] if want < bites else []) + e["crumbs"][:len(e["crumbs"]) * want // max(1, bites)]
            key = (step, phase, want)
        else:
            pts, key = self.model(phase).pts, (step, phase)
        if key not in self.frames:
            if len(self.frames) > 4 * STEPS:
                self.frames.clear()
            scene = {"dessert": pts, "plate": self.plate, "cup": self.cup}
            self.frames[key] = frame(scene, step / STEPS * math.tau, self.w, self.h, back=self.eaten is not None)
        return self.frames[key], step / STEPS * math.tau

    def flames(self, phase):
        return [] if self.eaten else self.model(phase).extras.get("flames", [])


def colours(theme):
    """colour slot (material * 2 + lit) -> curses attribute. all 0 in monochrome."""
    attrs = [0] * 256
    if not theme:  # monochrome: desserts bold, plate dim
        for i, m in enumerate(models.MATS):
            attrs[i * 2] = attrs[i * 2 + 1] = curses.A_DIM if m == "plate" else curses.A_BOLD
        return attrs
    curses.start_color()
    curses.use_default_colors()
    pal = THEMES[theme]
    if pal is None or curses.COLORS < 256:
        many = curses.COLORS >= 16
        pal = {m: (c, c + 8 if many else c) for m, c in ANSI.items()}
        pal["dark"] = (8, 8) if many else (7, 7)
    for i, m in enumerate(models.MATS):
        for lit in (0, 1):
            curses.init_pair(i * 2 + lit + 1, pal[m][lit], -1)
            attrs[i * 2 + lit] = curses.color_pair(i * 2 + lit + 1) | (curses.A_BOLD if lit and curses.COLORS < 16 else 0)
    return attrs


def slot(mat, lit=1):
    return models.MAT[mat] * 2 + lit


def put(scr, y, x, s, attr=0):
    h, w = scr.getmaxyx()
    if 0 <= y < h and 0 <= x < w:
        try:
            scr.addstr(y, x, s[:w - x], attr)
        except curses.error:
            pass  # writing the bottom-right cell raises even though it draws


def blit(scr, rows, slots, attrs, w):
    for r, line in enumerate(rows):
        start = 0
        for c in range(1, w + 1):
            if c == w or slots[r * w + c] != slots[r * w + start]:
                if line[start:c].strip():
                    put(scr, r, start, line[start:c], attrs[slots[r * w + start]])
                start = c


def overlays(scr, rows, table, theta, phase, t, sparkles, attrs, caption, clock, hint):
    h, w = scr.getmaxyx()
    k, ox, oy = layout(w, h)
    c, s = math.cos(theta), math.sin(theta)
    faint = attrs[slot("plate", 0)] or curses.A_DIM
    for x, y, z in table.flames(phase):
        col, row = project(x, y, z, c, s, k, ox, oy)
        put(scr, row, col, "^'*^(^)"[int(t * 9 + x * 50) % 7], attrs[slot("yellow")])
        put(scr, row - 1, col, "' ,`"[int(t * 7 + z * 50) % 4], attrs[slot("orange")])
    sx, sy = project(*table.steam, 1.0, 0.0, k, ox, oy)
    for p, px in enumerate((sx - 1, sx + 2)):
        for r in range(5):  # r = 0 is right above the cup
            wob = math.sin(t * 1.3 - r * 0.9 + p * 2)
            if random.Random(hash((p, r, int(t * 2)))).random() < 0.1 + r * 0.17:
                continue  # wisps thin out as they rise
            put(scr, sy - 1 - r, px + round(wob), "(" if wob > 0 else ")", faint)
    if len(sparkles) < 6 and random.random() < 0.08:
        sparkles.append((random.randint(int(ox - k), int(ox + k)), random.randint(0, max(0, int(oy - 0.3 * k))), t))
    for sp in list(sparkles):
        x, y, born = sp
        step = int((t - born) / 1.5 * len(SPARKLE))
        if step >= len(SPARKLE):
            sparkles.remove(sp)
        elif 0 <= y < h and 0 <= x < w and rows[y][x] == " ":
            put(scr, y, x, SPARKLE[step], attrs[slot("yellow")])
    bottom = int(oy - BOTTOM * k / 2)
    half = round(k * (0.85 + 0.07 * math.sin(t * 0.8)))  # the shadow under the plate breathes
    put(scr, bottom - 1, int(ox) - half, "~" * (2 * half + 1), faint)
    caption = f"~ {caption} ~"
    put(scr, min(h - 2, bottom + 1), (w - len(caption)) // 2, caption, attrs[slot("cream")])
    if clock:
        put(scr, 1, w - 15, time.strftime("~ %H:%M ~"), attrs[slot("cream")])
        put(scr, 2, w - 15, "lofi & sweets", faint)
    if hint:
        put(scr, h - 1, max(0, (w - len(HINT)) // 2), HINT, faint)


def red_room(scr, attrs, t):
    """--peaks: red curtains down both sides and the zigzag floor along the bottom."""
    h, w = scr.getmaxyx()
    k, ox, oy = layout(w, h)
    left, right = int(ox + LEFT * k) - 1, int(ox + RIGHT * k) + 1
    for row in range(h - 1):
        sway = 0.7 * math.sin(t * 0.5 + row * 0.12)
        for col in list(range(0, max(0, left))) + list(range(min(w, right), w)):
            fold = math.sin(col * 1.15 + sway)  # light catches the folds
            put(scr, row, col, " .:|!"[min(4, int((fold + 1) * 2.5))], attrs[slot("red", fold > 0.3)])
    top = int(oy - BOTTOM * k / 2) + 2
    for row in range(top, h - 1):
        line = (" \\/ " if row % 2 else "\\  /") * (w // 4 + 1)  # stacked chevrons
        put(scr, row, 0, line, attrs[slot("plate", 0)] or curses.A_DIM)
    if t % 25 > 20:  # now and then an owl looks out from the curtains
        blink = int(t * 3) % 7 == 0
        for i, part in enumerate(OWL):
            put(scr, 2 + i, 1, part.replace("O,O", "-,-") if blink else part, attrs[slot("cream")])


def run(scr, args, ids, idx):
    curses.curs_set(0)
    scr.nodelay(True)
    attrs = colours(args.color)
    start = last = switched = time.time()
    theta, speed, eat_start, sparkles = 0.0, args.speed, None, []
    clock, saver, table = args.clock, args.screensaver, None
    while True:
        now = time.time()
        t, dt, last = now - start, now - last, now
        key = scr.getch()
        if key in (ord("q"), 27):
            return
        if key == ord(" ") or (saver and now - switched > SAVER_SECONDS):
            idx = random.choice([i for i in range(len(ids)) if i != idx] or [idx]) if saver else (idx + 1) % len(ids)
            switched, table = now, None
        elif key in (ord("+"), ord("=")):
            speed = min(3.0, speed + 0.1)
        elif key in (ord("-"), ord("_")):
            speed = max(0.0, speed - 0.1)
        elif key == ord("c"):
            clock = not clock
        elif key == ord("s"):
            saver, switched = not saver, now
        h, w = scr.getmaxyx()
        if table is None or (table.w, table.h) != (w, h) or key == ord("r"):
            table, eat_start = Table(ids[idx], w, h, coffee=args.peaks), None
        phase = int(t * 1.2) % table.phases
        if key == ord("e") and eat_start is None:
            table.eat(phase)
            eat_start = now
        theta += speed * dt
        progress = None if eat_start is None else (now - eat_start) / EAT_SECONDS
        (rows, slots), shown = table.render(theta, phase, progress)
        caption = table.caption or table.name
        if table.id == "birthday" and args.birthday:
            caption = f"happy birthday, {args.birthday}!"
        if args.peaks:
            caption = PEAKS_LINES[int(t / 9) % len(PEAKS_LINES)]
        if progress is not None and progress >= 1:
            caption = "that's a damn fine cherry pie.   (r for another slice)" if args.peaks else "all gone. *burp*   (r to serve again)"
        scr.erase()
        if args.peaks:
            red_room(scr, attrs, t)
            sparkles.clear()  # no sparkles in the red room
        blit(scr, rows, slots, attrs, w)
        overlays(scr, rows, table, shown, phase, t, sparkles, attrs, caption, clock and not args.peaks, t < 8 and not args.once)
        if args.peaks and clock:
            stamp = time.strftime("diane, %I:%M %p.").replace(" 0", " ").lower().replace("am", "a.m").replace("pm", "p.m")
            put(scr, 0, w - len(stamp) - 2, stamp, attrs[slot("cream")])
        scr.refresh()
        if args.once and theta >= math.tau:
            return
        time.sleep(max(0.0, 1 / FPS - (time.time() - now)))


def main():
    p = argparse.ArgumentParser(prog="sweets", description=__doc__)
    menu = [d for d in models.DESSERTS if d not in HIDDEN]
    p.add_argument("dessert", nargs="?", metavar="dessert",
                   help="which dessert to serve: " + ", ".join(menu))
    p.add_argument("-l", "--list", action="store_true", help="list the desserts")
    p.add_argument("-r", "--random", action="store_true", help="serve a random dessert")
    p.add_argument("-b", "--birthday", nargs="?", const="", metavar="NAME", help="birthday cake, optionally for NAME")
    p.add_argument("-s", "--screensaver", action="store_true", help=f"new dessert every {SAVER_SECONDS}s")
    p.add_argument("-c", "--clock", action="store_true", help="show a clock in the corner")
    p.add_argument("--color", nargs="?", const="gruvbox", choices=list(THEMES),
                   help="colour theme: gruvbox (default), term (your terminal's own palette), amber, green")
    p.add_argument("--peaks", action="store_true", help=argparse.SUPPRESS)  # a damn fine easter egg
    p.add_argument("--once", action="store_true", help="spin one full turn, then exit")
    p.add_argument("--speed", type=float, default=0.35, help="spin speed (default 0.35)")
    args = p.parse_args()

    if args.dessert and args.dessert not in models.DESSERTS:
        p.error(f"no dessert called {args.dessert!r}. try: {', '.join(menu)}")
    if args.list:
        print("\n".join(menu))
        return
    if args.peaks:
        global SIDE, FLOOR
        SIDE, FLOOR, args.clock = 9, 3, True
    want = "birthday" if args.birthday is not None else "cherrypie" if args.peaks else args.dessert
    ids = menu + [want] if want in HIDDEN else menu
    idx = ids.index(want) if want else random.randrange(len(ids)) if args.random else 0
    try:
        curses.wrapper(run, args, ids, idx)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
