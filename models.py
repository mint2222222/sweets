"""3D dessert models for sweets, built as point clouds the renderer splats.

Each point is (x, y, z, nx, ny, nz, albedo, gloss, material). y is up, the plate top is y = 0
and the plate radius is 1. To add a dessert: write a builder like the ones below and register it
in DESSERTS.
"""
import math
import random

TAU = math.tau
MATS = ["plate", "cream", "crust", "red", "pink", "green", "yellow", "purple",
        "brown", "chocolate", "orange", "white", "dark", "blue"]
MAT = {name: i for i, name in enumerate(MATS)}
SPRINKLES = ["red", "yellow", "green", "blue", "white", "pink"]


def arc(cr, cy, ar, ay, a0, a1, n=10):
    """points on an ellipse arc in the (r, y) profile plane; angles in degrees."""
    return [(cr + ar * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
             cy + ay * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]


def resample(profile, ds):
    """(r, y, normal_r, normal_y) every ds along a profile drawn bottom to top along the outside."""
    out = []
    for (r0, y0), (r1, y1) in zip(profile, profile[1:]):
        seg = math.hypot(r1 - r0, y1 - y0)
        if seg:
            n = max(1, round(seg / ds))
            out += [(r0 + (r1 - r0) * (i + 0.5) / n, y0 + (y1 - y0) * (i + 0.5) / n,
                     (y1 - y0) / seg, -(r1 - r0) / seg) for i in range(n)]
    return out


class Model:
    def __init__(self, ds, seed=7):
        self.pts, self.ds, self.extras = [], ds, {}
        self.rand = random.Random(seed).random
        self.at()

    def at(self, x=0.0, y=0.0, z=0.0, rx=0.0, ry=0.0, rz=0.0):
        """place the parts added next: rotate about z, then x, then y, then move to (x, y, z)."""
        cx, sx, cy, sy, cz, sz = math.cos(rx), math.sin(rx), math.cos(ry), math.sin(ry), math.cos(rz), math.sin(rz)
        rot_z = ((cz, -sz, 0), (sz, cz, 0), (0, 0, 1))
        rot_x = ((1, 0, 0), (0, cx, -sx), (0, sx, cx))
        rot_y = ((cy, 0, sy), (0, 1, 0), (-sy, 0, cy))
        mul = lambda a, b: tuple(tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)) for i in range(3))
        self.rot, self.pos = mul(rot_y, mul(rot_x, rot_z)), (x, y, z)
        return self

    def add(self, x, y, z, nx, ny, nz, mat, alb, gloss):
        (a, b, c), (d, e, f), (g, h, i) = self.rot
        px, py, pz = self.pos
        n = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
        nx, ny, nz = nx / n, ny / n, nz / n
        self.pts.append((a * x + b * y + c * z + px, d * x + e * y + f * z + py, g * x + h * y + i * z + pz,
                         a * nx + b * ny + c * nz, d * nx + e * ny + f * nz, g * nx + h * ny + i * nz,
                         alb, gloss, MAT[mat]))

    def lathe(self, profile, paint, a0=0.0, a1=TAU, ridges=0, depth=0.0):
        """revolve a profile around the y axis; ridges fold it like piped cream."""
        for r, y, nr, ny in resample(profile, self.ds):
            n = max(1, round(abs(a1 - a0) * r / self.ds))
            for j in range(n):
                a = a0 + (a1 - a0) * (j + 0.5) / n
                m = 1 + depth * math.cos(ridges * a)
                k = -depth * ridges * math.sin(ridges * a) / m  # slope of the ridge tilts the normal
                ca, sa = math.cos(a), math.sin(a)
                x, z = r * m * ca, r * m * sa
                self.add(x, y, z, nr * (ca + k * sa), ny, nr * (sa - k * ca), *paint(x, y, z))

    def quad(self, o, u, v, n, paint):
        nu = max(1, round(math.sqrt(sum(c * c for c in u)) / self.ds))
        nv = max(1, round(math.sqrt(sum(c * c for c in v)) / self.ds))
        for i in range(nu):
            for j in range(nv):
                fu, fv = (i + 0.5) / nu, (j + 0.5) / nv
                x, y, z = (o[c] + u[c] * fu + v[c] * fv for c in range(3))
                self.add(x, y, z, *n, *paint(x, y, z))

    def box(self, hx, h, hz, paint, top=True):
        """sits on y = 0, centred on x and z."""
        self.quad((-hx, 0, hz), (2 * hx, 0, 0), (0, h, 0), (0, 0, 1), paint)
        self.quad((hx, 0, -hz), (-2 * hx, 0, 0), (0, h, 0), (0, 0, -1), paint)
        self.quad((hx, 0, hz), (0, 0, -2 * hz), (0, h, 0), (1, 0, 0), paint)
        self.quad((-hx, 0, -hz), (0, 0, 2 * hz), (0, h, 0), (-1, 0, 0), paint)
        if top:
            self.quad((-hx, h, -hz), (2 * hx, 0, 0), (0, 0, 2 * hz), (0, 1, 0), paint)

    def torus(self, big, small, paint, a0=0.0, a1=TAU):
        na = max(3, round(abs(a1 - a0) * (big + small) / self.ds))
        nb = max(3, round(TAU * small / self.ds))
        for i in range(na):
            a = a0 + (a1 - a0) * (i + 0.5) / na
            for j in range(nb):
                b = TAU * (j + 0.5) / nb
                nx, ny, nz = math.cos(b) * math.cos(a), math.sin(b), math.cos(b) * math.sin(a)
                x, y, z = big * math.cos(a) + small * nx, small * ny, big * math.sin(a) + small * nz
                self.add(x, y, z, nx, ny, nz, *paint(x, y, z))

    def ellipsoid(self, rx, ry, rz, paint):
        big = max(rx, ry, rz)
        nt = max(3, round(math.pi * big / self.ds))
        for i in range(nt):
            t = math.pi * (i + 0.5) / nt
            n = max(3, round(TAU * big * math.sin(t) / self.ds))
            for j in range(n):
                p = TAU * (j + 0.5) / n
                ux, uy, uz = math.sin(t) * math.cos(p), math.cos(t), math.sin(t) * math.sin(p)
                self.add(rx * ux, ry * uy, rz * uz, ux / rx, uy / ry, uz / rz, *paint(rx * ux, ry * uy, rz * uz))

    def paint(self, mat, alb, gloss=0.0, grain=0.0):
        r = self.rand
        return lambda x, y, z: (mat, alb * (1 - grain * r()), gloss)


# --- the table setting -------------------------------------------------------------------------

def plate(m):
    def paint(x, y, z):
        r = math.hypot(x, z)
        return "plate", 0.12 if 0.87 < r < 0.9 else 0.22, 0.3  # one thin ring glazed into the rim
    m.lathe([(0.92, -0.06), (1.0, 0.015), (0.99, 0.042), (0.96, 0.05), (0.78, 0.0), (0.0, 0.0)], paint)


def teacup(m, x, y, z, coffee=False):
    china, r = m.paint("plate", 0.62, 0.45), m.rand
    m.at(x, y, z)
    m.lathe([(0.17, 0.0), (0.33, 0.035), (0.32, 0.045), (0.2, 0.025), (0.0, 0.025)], china)  # saucer
    m.lathe([(0.11, 0.025), (0.13, 0.05), (0.2, 0.2), (0.205, 0.215), (0.195, 0.222), (0.12, 0.05)], china)
    drink = ("dark", 0.06, 1.0) if coffee else ("brown", 0.22, 0.9)  # black as midnight, or tea
    m.lathe([(0.177, 0.18), (0.0, 0.18)], lambda *_: (drink[0], drink[1] + 0.04 * r(), drink[2]))
    m.at(x + 0.215, y + 0.13, z, rx=math.pi / 2)
    m.torus(0.055, 0.017, china, -1.9, 1.9)  # handle
    m.extras["steam"] = (x, y + 0.24, z)


# --- desserts ----------------------------------------------------------------------------------

def macaron(m, flavour, alb, filling, size=1.0):

    def paint(x, y, z):
        y /= size
        if 0.075 < y < 0.125:
            return filling, 0.9, 0.15
        if 0.05 < y < 0.15:
            return flavour, alb * 0.6, 0.0  # the ruffled "feet"
        return flavour, alb, 0.25
    profile = (arc(0, 0.05, 0.19, 0.05, -90, 0, 6)
               + [(0.2, 0.06), (0.2, 0.075), (0.175, 0.082), (0.183, 0.1), (0.175, 0.118), (0.2, 0.125), (0.2, 0.14)]
               + arc(0, 0.15, 0.19, 0.06, 0, 90, 6))
    m.lathe([(r * size, y * size) for r, y in profile], paint)


def macarons(m, phase):
    flavours = [("pink", 0.8, "cream"), ("green", 0.7, "cream"), ("yellow", 0.9, "yellow"),
                ("purple", 0.7, "cream"), ("brown", 0.5, "chocolate"), ("orange", 0.8, "cream"),
                ("white", 0.95, "red")]
    spots = [(0.27 * math.cos(a), 0.0, 0.27 * math.sin(a), 0.04, a) for a in (TAU * i / 4 + 0.3 for i in range(4))]
    spots += [(0.12 * math.cos(a), 0.2, 0.12 * math.sin(a), 0.3, a) for a in (TAU * i / 2 + 1.1 for i in range(2))]
    spots += [(0.0, 0.4, 0.02, 0.2, 2.5)]  # x, y, z, tilt, yaw: four on the plate, two on those, one on top
    for i, (x, y, z, tilt, a) in enumerate(spots):
        m.at(x, y, z, rz=tilt, ry=math.pi - a)  # lean outward, off the pile below
        macaron(m, *flavours[i % len(flavours)], 1.3)


def cheesecake(m, phase):
    R, W, H, r = 0.78, 0.8, 0.36, m.rand

    def layers(x, y, z):
        if y < 0.07:
            return "crust", 0.5 * (1 - 0.45 * r()), 0.0  # graham crumbs
        if y > H - 0.035:
            return "red", 0.55 - 0.05 * r(), 0.7  # strawberry glaze
        return "cream", 0.92 - 0.05 * r(), 0.05

    def outside(x, y, z):
        drip = 0.06 * max(0.0, math.sin(9 * math.atan2(z, x))) ** 3
        if y >= H - 0.035 - drip:
            return "red", 0.55 - 0.05 * r(), 0.7
        if y < 0.07:
            return layers(x, y, z)
        return "yellow", 0.72 - 0.08 * r(), 0.0  # baked golden edge

    m.at(-0.5)  # the wedge's centre of mass sits on the plate's centre
    m.lathe([(R, 0.0), (R, H), (0.0, H)], outside, -W / 2, W / 2)
    for a, side in ((W / 2, 1), (-W / 2, -1)):
        m.quad((0, 0, 0), (R * math.cos(a), 0, R * math.sin(a)), (0, H, 0),
               (-math.sin(a) * side, 0, math.cos(a) * side), layers)
    m.at(0.06, H, 0)
    m.lathe([(0.085, 0.0), (0.085, 0.02), (0.07, 0.05), (0.045, 0.08), (0.02, 0.1), (0.0, 0.115)],
            m.paint("white", 0.97, 0.15, 0.04), ridges=8, depth=0.12)  # piped cream
    m.at(0.07, H + 0.07, 0.0, rz=0.25)
    m.lathe([(0.0, 0.0), (0.06, 0.02), (0.085, 0.06), (0.078, 0.1), (0.05, 0.14), (0.0, 0.17)],
            lambda x, y, z: ("yellow", 0.9, 0.0) if r() < 0.07 else ("red", 0.58, 0.6))  # strawberry & seeds
    m.at(-0.12, H, 0.06, ry=0.7)
    m.ellipsoid(0.07, 0.01, 0.03, m.paint("green", 0.6, 0.3))  # mint leaf
    for i in range(5):  # sauce dots across the plate
        a = 0.6 + i * 0.32
        m.at(0.72 * math.cos(a) - 0.25, 0.0, 0.72 * math.sin(a))
        size = 0.05 - i * 0.007
        m.ellipsoid(size, 0.012, size, m.paint("red", 0.5, 0.8))


def tiramisu(m, phase):
    S, H, r = 0.3, 0.4, m.rand

    def layers(x, y, z):
        y += 0.008 * math.sin(x * 25 + z * 19)  # layers are never perfectly flat
        if y > H - 0.02:
            return "chocolate", 0.35 * (1 - 0.5 * r()), 0.0  # cocoa
        if y < 0.1 or 0.18 < y < 0.27:
            return "brown", 0.55 * (1 - 0.35 * r()), 0.05  # coffee-soaked ladyfingers
        return "cream", 0.93 - 0.05 * r(), 0.08  # mascarpone

    m.box(S, H, S, layers)
    m.at(0.07, H, 0.05, ry=0.6)
    m.ellipsoid(0.08, 0.012, 0.035, m.paint("green", 0.6, 0.3))
    for x, z, a in ((-0.12, -0.08, 0.3), (-0.04, -0.16, 1.2)):  # coffee beans
        m.at(x, H + 0.01, z, ry=a)
        m.ellipsoid(0.035, 0.02, 0.025, m.paint("chocolate", 0.3, 0.5))


def pancakes(m, phase):
    r, y, th, R = m.rand, 0.0, 0.1, 0.46

    def cake(x, ly, z):
        if 0.02 < ly < th - 0.02:
            return "yellow", 0.82 - 0.12 * r(), 0.0  # fluffy edge
        return "brown", 0.5 * (1 - 0.3 * r()), 0.05  # golden-brown faces

    for _ in range(4):
        m.at(0.02 * (r() - 0.5), y, 0.02 * (r() - 0.5))
        m.lathe([(0.0, 0.0), (R - 0.03, 0.0)] + arc(R - 0.03, th / 2, 0.03, th / 2, -90, 90, 6) + [(0.0, th)], cake)
        y += th - 0.005
    syrup = m.paint("orange", 0.45, 0.9)
    m.at(0, y, 0)
    m.lathe([(0.3, 0.0), (0.3, 0.012), (0.0, 0.016)], syrup, ridges=7, depth=0.55)  # lobes reach the edge
    for k in range(7):  # drips grow down the side, fall, start again
        a, drip = TAU * k / 7, 0.04 + 0.22 * ((phase / 8 + k * 0.37) % 1)
        m.at((R + 0.025) * math.cos(a), y - drip, (R + 0.025) * math.sin(a))
        m.lathe([(0.0, 0.0)] + arc(0, 0.025, 0.025, 0.025, -90, 0, 4) + [(0.014, drip)], syrup)
    m.at(0.03, y + 0.012, -0.02, ry=0.4)
    m.box(0.08, 0.06, 0.07, m.paint("yellow", 0.97, 0.5))  # butter
    for i in range(8):  # berries on the plate
        a = TAU * i / 8 + 0.2
        m.at(0.66 * math.cos(a), 0.0, 0.66 * math.sin(a))
        if i % 3:
            m.ellipsoid(0.05, 0.045, 0.05, m.paint("blue", 0.35, 0.5, 0.2))
        else:
            m.ellipsoid(0.055, 0.06, 0.055, lambda x, y, z: ("red", 0.55 * (0.7 + 0.3 * math.cos(x * 90) * math.cos(z * 90)), 0.3))


def donut(m, icing, alb, gloss, sprinkles):
    big, small, r = 0.2, 0.095, m.rand
    wave = r() * TAU
    na, nb = round(TAU * (big + small) / m.ds), round(TAU * small / m.ds) + 1
    for i in range(na):
        a = TAU * (i + 0.5) / na
        for j in range(nb):
            b = TAU * (j + 0.5) / nb
            iced = icing and math.sin(b) > -0.25 + 0.2 * math.sin(6 * a + wave)
            rr = small + (0.012 if iced else 0)
            nx, ny, nz = math.cos(b) * math.cos(a), math.sin(b), math.cos(b) * math.sin(a)
            if iced and sprinkles and r() < 0.09:
                paint = SPRINKLES[int(r() * len(SPRINKLES))], 1.0, 0.2
            elif iced:
                paint = icing, alb, gloss
            elif abs(math.sin(b)) < 0.18 and math.cos(b) > 0:
                paint = "yellow", 0.85, 0.0  # the pale ring where it floated in the fryer
            else:
                paint = "brown", 0.55 - 0.1 * r(), gloss if not icing else 0.0
            m.add(big * math.cos(a) + rr * nx, small + rr * ny, big * math.sin(a) + rr * nz, nx, ny, nz, *paint)


def donuts(m, phase):
    m.at(-0.27, 0, 0.12, ry=0.4)
    donut(m, "chocolate", 0.3, 0.8, False)
    m.at(0.27, 0, 0.12, ry=1.3)
    donut(m, None, 0, 0.45, False)  # plain sugar glaze
    m.at(0, 0.12, -0.24, rx=-0.65)
    donut(m, "pink", 0.8, 0.4, True)  # leaning on the other two


def mochi(m, colour, alb):
    r = m.rand

    def paint(x, y, z):
        da = math.atan2(z, x) - math.pi / 2  # face points down local +z
        if abs(y - 0.14) < 0.03 and abs(abs(da) - 0.3) < 0.1:
            return "dark", 0.04, 0.3
        return colour, alb * (1 - 0.06 * r()), 0.15  # dusted with starch
    m.lathe([(0.0, 0.0), (0.16, 0.0)] + arc(0.16, 0.08, 0.08, 0.08, -90, 0, 6) + arc(0, 0.08, 0.24, 0.2, 0, 90, 10), paint)


def mochis(m, phase):
    for p, (colour, alb) in zip((90, 210, 330), (("pink", 0.85), ("green", 0.7), ("white", 0.95))):
        p = math.radians(p)
        m.at(0.3 * math.cos(p), 0, 0.3 * math.sin(p), ry=math.pi / 2 - p)  # each one faces outward
        mochi(m, colour, alb)


def birthday(m, phase):
    R, H, r = 0.52, 0.38, m.rand

    def frosting(x, y, z):
        if y >= H - 0.031:
            if r() < 0.06:
                return SPRINKLES[int(r() * len(SPRINKLES))], 1.0, 0.2
            return "pink", 0.78, 0.6
        drip = 0.1 * max(0.0, math.sin(7 * math.atan2(z, x))) ** 4
        if y > H - 0.05 - drip:
            return "pink", 0.78, 0.6
        return "white", 0.92 - 0.04 * r(), 0.25

    m.lathe([(0.0, 0.0), (R, 0.0), (R, H - 0.03)] + arc(R - 0.03, H - 0.03, 0.03, 0.03, 0, 90, 4) + [(0.0, H)], frosting)
    m.at(0, 0.03, 0)
    m.torus(R + 0.005, 0.03, m.paint("white", 0.95, 0.2, 0.08))  # piped border
    for i in range(12):
        a = TAU * i / 12
        m.at((R - 0.07) * math.cos(a), H, (R - 0.07) * math.sin(a))
        m.lathe([(0.05, 0.0), (0.05, 0.015), (0.035, 0.04), (0.015, 0.055), (0.0, 0.06)],
                m.paint("white", 0.97, 0.15), ridges=6, depth=0.15)
    flames = []
    for i in range(5):
        a = TAU * i / 5
        x, z = 0.24 * math.cos(a), 0.24 * math.sin(a)
        m.at(x, H, z)
        m.lathe([(0.022, 0.0), (0.022, 0.2), (0.0, 0.2)],
                lambda x, y, z: ("red" if int(y * 30 + math.atan2(z, x) * 1.5) % 2 else "white", 0.85, 0.3))
        m.lathe([(0.006, 0.2), (0.006, 0.23), (0.0, 0.23)], m.paint("dark", 0.1))
        flames.append((x, H + 0.26, z))
    m.extras["flames"] = flames


def cherry_pie(m, phase):
    R, W, H, r = 0.78, 0.75, 0.24, m.rand
    c45 = math.sqrt(0.5)

    def filling(x, y, z):
        if y < 0.035:
            return "crust", 0.7 - 0.1 * r(), 0.05
        if y > H - 0.03:
            return "crust", 0.82 - 0.1 * r(), 0.1
        if math.sin(x * 70) * math.sin(y * 90) * math.sin(z * 70) > 0.15:
            return "red", 0.3, 0.9  # whole cherries in the syrup
        return "red", 0.5, 0.8

    def outside(x, y, z):
        if y < H - 0.001:
            return "crust", 0.75 - 0.1 * r(), 0.05
        u, v = (x + z) * c45, (z - x) * c45
        if u % 0.16 < 0.06 or v % 0.16 < 0.06:
            return "crust", 0.88 - 0.06 * r(), 0.1  # lattice
        return "red", 0.4, 0.9  # cherries showing between the strips

    m.at(-0.5)
    m.lathe([(R, 0.0), (R, H), (0.0, H)], outside, -W / 2, W / 2)
    for a, side in ((W / 2, 1), (-W / 2, -1)):
        m.quad((0, 0, 0), (R * math.cos(a), 0, R * math.sin(a)), (0, H, 0),
               (-math.sin(a) * side, 0, math.cos(a) * side), filling)
    m.at(-0.5, H, 0)
    m.torus(R - 0.03, 0.045, lambda x, y, z: ("crust", 0.8 * (0.75 + 0.25 * math.cos(math.atan2(z, x) * 45)), 0.1),
            -W / 2, W / 2)  # crimped edge
    for x, z, lean in ((0.5, 0.42, 0.3), (0.62, 0.3, -0.4)):  # two cherries on the side
        m.at(x, 0.05, z)
        m.ellipsoid(0.055, 0.05, 0.055, m.paint("red", 0.5, 0.9))
        m.at(x, 0.095, z, rz=lean)
        m.lathe([(0.007, 0.0), (0.007, 0.14), (0.0, 0.14)], m.paint("green", 0.4))


# id: (name, caption, builder, animation phases)
DESSERTS = {
    "macarons": ("a pile of macarons", None, macarons, 1),
    "cheesecake": ("strawberry cheesecake", None, cheesecake, 1),
    "tiramisu": ("tiramisu", None, tiramisu, 1),
    "pancakes": ("pancakes with syrup", None, pancakes, 8),
    "donuts": ("donuts", None, donuts, 1),
    "mochi": ("mochi trio", None, mochis, 1),
    "birthday": ("birthday cake", "happy birthday!", birthday, 1),
    "cherrypie": ("cherry pie", None, cherry_pie, 1),
}

