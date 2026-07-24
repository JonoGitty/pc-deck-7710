#!/usr/bin/env python3
"""GETTING COOKD — PS1 EDITION. A real polygon renderer on the 192x92 LED grid:
z-buffered flat-shaded triangle meshes (icosphere ball, lathed pins, blocky lime
loser), vertex snapping (the PS1 wobble), distance fog, Bayer-dithered shading
bands, and PS1 replay camera work: chase cam behind the flaming ball -> SLOW-MO
ORBIT around the strike -> the loser tumbles into the lens -> splat, fire, COOKD."""
import os, math, json, random, faulthandler
import os as _os
REPO = _os.path.abspath(_os.path.join(_os.path.dirname(__file__), "..", ".."))
import ledlib as T
faulthandler.dump_traceback_later(900, exit=True)
random.seed(5)

CW, CH = 192, 92
FPS, NF = 16, 200          # 12.5s
BG = (4, 5, 10)
BGROW = bytes(BG) * (CW*CH)

def clamp(v, a, b): return a if v < a else (b if v > b else v)

# ---------------- vec/matrix ----------------
def vsub(a,b): return (a[0]-b[0], a[1]-b[1], a[2]-b[2])
def vadd(a,b): return (a[0]+b[0], a[1]+b[1], a[2]+b[2])
def vmul(a,s): return (a[0]*s, a[1]*s, a[2]*s)
def dot(a,b): return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]
def cross(a,b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def norm(a):
    l = math.sqrt(dot(a,a)) or 1
    return (a[0]/l, a[1]/l, a[2]/l)
def rotx(a):
    c,s = math.cos(a), math.sin(a); return ((1,0,0),(0,c,-s),(0,s,c))
def roty(a):
    c,s = math.cos(a), math.sin(a); return ((c,0,s),(0,1,0),(-s,0,c))
def rotz(a):
    c,s = math.cos(a), math.sin(a); return ((c,-s,0),(s,c,0),(0,0,1))
def mmul(m,n):
    return tuple(tuple(sum(m[i][k]*n[k][j] for k in range(3)) for j in range(3)) for i in range(3))
def mv(m,v):
    return (m[0][0]*v[0]+m[0][1]*v[1]+m[0][2]*v[2],
            m[1][0]*v[0]+m[1][1]*v[1]+m[1][2]*v[2],
            m[2][0]*v[0]+m[2][1]*v[1]+m[2][2]*v[2])
IDENT = ((1,0,0),(0,1,0),(0,0,1))

# ---------------- camera ----------------
class Cam:
    def __init__(self, eye, target, f=95.0):
        self.eye = eye; self.f = f
        fwd = norm(vsub(target, eye))
        right = norm(cross(fwd, (0,1,0)))
        up = cross(right, fwd)
        self.R = (right, up, fwd)
    def view(self, p):
        d = vsub(p, self.eye)
        return (dot(self.R[0], d), dot(self.R[1], d), dot(self.R[2], d))
    def proj(self, p):
        v = self.view(p)
        if v[2] < 0.28: return None
        # PS1 vertex snap: half-pixel grid
        sx = int((96 + self.f * v[0] / v[2]) * 2 + .5) / 2
        sy = int((46 - self.f * v[1] / v[2]) * 2 + .5) / 2
        return (sx, sy, v[2])

LIGHT = norm((-0.45, 0.85, -0.28))
BAYER = ((0.25, 0.75), (1.0, 0.5))
FOG_A, FOG_B = 7.0, 30.0

class FB:
    __slots__ = ("buf", "zb")
    def __init__(self):
        self.buf = bytearray(BGROW)
        self.zb = [1e9]*(CW*CH)
    def tri(self, p0, p1, p2, rgb, shade=1.0, emissive=False):
        (x0,y0,z0),(x1,y1,z1),(x2,y2,z2) = p0,p1,p2
        minx = max(0, int(min(x0,x1,x2))); maxx = min(CW-1, int(max(x0,x1,x2))+1)
        miny = max(0, int(min(y0,y1,y2))); maxy = min(CH-1, int(max(y0,y1,y2))+1)
        if minx > maxx or miny > maxy: return
        d = (y1-y2)*(x0-x2) + (x2-x1)*(y0-y2)
        if abs(d) < 1e-9: return
        invd = 1.0/d
        zmid = (z0+z1+z2)/3
        fog = clamp((zmid - FOG_A)/(FOG_B - FOG_A), 0, 0.92)
        buf, zb = self.buf, self.zb
        for y in range(miny, maxy+1):
            for x in range(minx, maxx+1):
                w0 = ((y1-y2)*(x-x2) + (x2-x1)*(y-y2)) * invd
                if w0 < 0: continue
                w1 = ((y2-y0)*(x-x2) + (x0-x2)*(y-y2)) * invd
                if w1 < 0: continue
                w2 = 1 - w0 - w1
                if w2 < 0: continue
                z = w0*z0 + w1*z1 + w2*z2
                i = y*CW + x
                if z < zb[i]:
                    zb[i] = z
                    # dithered shading bands (PS1 gouraud-on-a-budget)
                    s = shade if emissive else clamp(shade + (BAYER[y&1][x&1]-0.5)*0.22, 0, 1)
                    s = int(s*4+0.5)/4
                    j = i*3
                    buf[j]   = int((rgb[0]*s)*(1-fog) + BG[0]*fog)
                    buf[j+1] = int((rgb[1]*s)*(1-fog) + BG[1]*fog)
                    buf[j+2] = int((rgb[2]*s)*(1-fog) + BG[2]*fog)
    def dot2(self, x, y, r, rgb, z=None):
        x0 = max(0, int(x-r)); x1 = min(CW-1, int(x+r))
        y0 = max(0, int(y-r)); y1 = min(CH-1, int(y+r))
        r2 = r*r
        for yy in range(y0, y1+1):
            for xx in range(x0, x1+1):
                if (xx-x)**2 + (yy-y)**2 <= r2:
                    i = yy*CW + xx
                    if z is None or z < self.zb[i]:
                        j = i*3
                        self.buf[j], self.buf[j+1], self.buf[j+2] = rgb

def draw_mesh(fb, cam, verts, tris, model_r, model_t, base_rgb, emissive=False):
    """tris: list of (i0,i1,i2). flat shade per tri, backface cull."""
    world = [vadd(mv(model_r, v), model_t) for v in verts]
    proj = [cam.proj(w) for w in world]
    for (i0, i1, i2) in tris:
        p0, p1, p2 = proj[i0], proj[i1], proj[i2]
        if p0 is None or p1 is None or p2 is None: continue
        # backface (screen winding)
        if (p1[0]-p0[0])*(p2[1]-p0[1]) - (p1[1]-p0[1])*(p2[0]-p0[0]) <= 0: continue
        if emissive:
            fb.tri(p0, p1, p2, base_rgb, 1.0, True)
        else:
            n = norm(cross(vsub(world[i1], world[i0]), vsub(world[i2], world[i0])))
            lam = clamp(0.24 + 0.76*max(0.0, dot(n, LIGHT)), 0, 1)
            fb.tri(p0, p1, p2, base_rgb, lam)

# ---------------- meshes ----------------
def icosphere():
    t = (1 + 5**.5) / 2
    vs = [(-1,t,0),(1,t,0),(-1,-t,0),(1,-t,0),(0,-1,t),(0,1,t),(0,-1,-t),(0,1,-t),
          (t,0,-1),(t,0,1),(-t,0,-1),(-t,0,1)]
    vs = [norm(v) for v in vs]
    fs = [(0,11,5),(0,5,1),(0,1,7),(0,7,10),(0,10,11),(1,5,9),(5,11,4),(11,10,2),
          (10,7,6),(7,1,8),(3,9,4),(3,4,2),(3,2,6),(3,6,8),(3,8,9),(4,9,5),
          (2,4,11),(6,2,10),(8,6,7),(9,8,1)]
    # one subdivision
    cache = {}
    def mid(a, b):
        k = (min(a,b), max(a,b))
        if k not in cache:
            cache[k] = len(vs); vs.append(norm(vmul(vadd(vs[a], vs[b]), .5)))
        return cache[k]
    out = []
    for a,b,c in fs:
        ab, bc, ca = mid(a,b), mid(b,c), mid(c,a)
        out += [(a,ab,ca),(b,bc,ab),(c,ca,bc),(ab,bc,ca)]
    return vs, out

BALL_V, BALL_T = icosphere()
BALL_R = 0.55

def lathe(profile, segs=8):
    vs, tris = [], []
    n = len(profile)
    for (y, r) in profile:
        for s in range(segs):
            a = s/segs * 2*math.pi
            vs.append((r*math.cos(a), y, r*math.sin(a)))
    for i in range(n-1):
        for s in range(segs):
            a = i*segs + s; b = i*segs + (s+1)%segs
            c = (i+1)*segs + s; d = (i+1)*segs + (s+1)%segs
            tris += [(a,b,c),(b,d,c)]
    vs.append((0, profile[-1][0], 0))
    top = len(vs)-1
    for s in range(segs):
        tris.append(((n-1)*segs + (s+1)%segs, (n-1)*segs + s, top))
    return vs, tris

PIN_V, PIN_T = lathe([(0.0,.14),(0.10,.185),(0.24,.165),(0.38,.10),(0.52,.085),
                      (0.66,.12),(0.80,.125),(0.92,.085),(1.02,.045)])
def pin_color(i): return (235,232,220)

def box(w, h, d):
    x, y, z = w/2, h/2, d/2
    vs = [(-x,-y,-z),(x,-y,-z),(x,y,-z),(-x,y,-z),(-x,-y,z),(x,-y,z),(x,y,z),(-x,y,z)]
    tris = [(0,2,1),(0,3,2),(4,5,6),(4,6,7),(0,1,5),(0,5,4),(2,3,7),(2,7,6),
            (1,2,6),(1,6,5),(0,4,7),(0,7,3)]
    return vs, tris
BOX_V, BOX_T = box(1,1,1)

def draw_box(fb, cam, size, r, t, rgb):
    vs = [(v[0]*size[0], v[1]*size[1], v[2]*size[2]) for v in BOX_V]
    draw_mesh(fb, cam, vs, BOX_T, r, t, rgb)

def draw_loser(fb, cam, pos, body_r, pose_up=True, rgb=(198,255,26)):
    """blocky PS1 figure. pos = feet centre. parts composed with body rotation."""
    def part(size, r_local, t_local, col=rgb):
        rr = mmul(body_r, r_local)
        tt = vadd(pos, mv(body_r, t_local))
        vs = [(v[0]*size[0], v[1]*size[1], v[2]*size[2]) for v in BOX_V]
        draw_mesh(fb, cam, vs, BOX_T, rr, tt, col)
    part((.34,.34,.30), IDENT, (0, 1.55, 0))                       # head
    part((.46,.62,.26), IDENT, (0, 1.02, 0))                       # torso
    aa = -2.4 if pose_up else -0.5
    part((.14,.52,.14), rotz(aa),  ( .33, 1.32, 0))                # arm R
    part((.14,.52,.14), rotz(-aa), (-.33, 1.32, 0))                # arm L
    part((.16,.68,.16), rotz(-.12), ( .14, .36, 0))                # leg R
    part((.16,.68,.16), rotz(.12),  (-.14, .36, 0))                # leg L

# ---------------- LED text + 2D splat ----------------
def draw_word(fb, word, cx, cy, cell, colors):
    x0 = cx - (len(word)*6-1)*cell/2
    for i, ch in enumerate(word):
        col = colors[i] if isinstance(colors, list) else colors
        for ry, row in enumerate(T.F[ch]):
            for rx, v in enumerate(row):
                if v == "1":
                    fb.dot2(x0+(i*6+rx)*cell + cell/2, cy+ry*cell, max(.9, cell*.42), col)

SEGS_SPLAT = [((60,24),(60,24),16),((60,50),(60,92),15),
              ((49,54),(14,20),6.5),((71,54),(106,20),6.5),
              ((53,94),(24,148),7),((67,94),(96,148),7)]
def draw_splat(fb, cx, cy, scale, rgb):
    for a, b, w in SEGS_SPLAT:
        ax, ay = cx+(a[0]-60)*scale, cy+(a[1]-85)*scale
        bx, by = cx+(b[0]-60)*scale, cy+(b[1]-85)*scale
        steps = max(1, int(math.hypot(bx-ax, by-ay)/max(1, w*scale*0.7)))
        for i in range(steps+1):
            t = i/steps
            fb.dot2(ax+(bx-ax)*t, ay+(by-ay)*t, max(1.0, w*scale), rgb)

# ---------------- timeline ----------------
# world-time with slow-mo: normal until 3.4s, 0.22x until 4.6s(world 3.4-3.66), normal after
def world_time(fi):
    t, wt, dt = 0.0, 0.0, 1.0/FPS
    for k in range(fi):
        rate = 0.22 if 3.4 <= wt else 1.0
        if wt > 3.75: rate = 1.0
        wt += dt*rate
        t += dt
    return wt
WT = []
wt = 0.0
for k in range(NF):
    rate = 1.0
    if 3.35 <= wt <= 3.78: rate = 0.2          # slow-mo across the strike
    wt += rate/FPS
    WT.append(wt)

IMPACT_WT = 3.5
pins0 = [(-0.55,20.8),(0,20.8),(0.55,20.8),(-0.28,20.3),(0.28,20.3),(0,19.8),
         (-0.83,21.3),(0.83,21.3),(0,21.3)]
pin_state = [( random.uniform(-1.8,1.8), random.uniform(2.0,4.2), random.uniform(-5.5,2.5),
               norm((random.random()-.5, random.random()-.5, random.random()-.5)),
               random.uniform(4,11)) for _ in pins0]
LOSER0 = (0, 0, 19.3)

particles = []
frames = []
for fi in range(NF):
    wt = WT[fi]
    fb = FB()
    # ---- ball state
    ball_z = 2.0 + min(1.0, wt/IMPACT_WT) * (20.1 - 2.0) if wt < IMPACT_WT else 20.1 + (wt-IMPACT_WT)*6
    ball_pos = (0, BALL_R, ball_z)
    # ---- camera
    if wt < IMPACT_WT - 0.12:
        sway = 0.25*math.sin(wt*1.9)
        eye = (sway, 1.35, ball_z - 2.6)
        tgt = (0, 0.65, ball_z + 3.0)
    elif wt < 4.15:   # slow-mo orbit around the deck
        k = (wt - (IMPACT_WT-0.12)) / (4.15 - (IMPACT_WT-0.12))
        ang = -0.45 + k*1.75
        rad = 3.6 - k*0.7
        eye = (math.sin(ang)*rad, 1.35 + k*0.85, 20.4 - math.cos(ang)*rad)
        tgt = (0, 0.75, 20.4)
    else:             # settle behind the deck for the incoming body
        k = clamp((wt-4.15)/0.4, 0, 1)
        e0 = (math.sin(1.30)*2.9, 2.2, 20.4 - math.cos(1.30)*2.9)
        e1 = (0, 1.45, 14.6)
        eye = (e0[0]+(e1[0]-e0[0])*k, e0[1]+(e1[1]-e0[1])*k, e0[2]+(e1[2]-e0[2])*k)
        tgt = (0, 1.1, 20.4)
    cam = Cam(eye, tgt)

    # ---- lane floor: checker quads + emissive rails
    z0 = max(2.0, eye[2] - 1.0)
    for zi in range(int(z0), int(z0)+26):
        for xi in range(-2, 2):
            shadecol = (14,20,16) if (zi+xi) % 2 == 0 else (9,12,14)
            q = [(xi*0.9, 0, zi), ((xi+1)*0.9, 0, zi), ((xi+1)*0.9, 0, zi+1), (xi*0.9, 0, zi+1)]
            p = [cam.proj(v) for v in q]
            if None in p: continue
            fb.tri(p[0], p[1], p[2], shadecol, 1.0, True)
            fb.tri(p[0], p[2], p[3], shadecol, 1.0, True)
    for lx in (-1.8, 1.8):
        for zi in range(int(z0), int(z0)+26):
            q = [(lx-0.06,0.01,zi),(lx+0.06,0.01,zi),(lx+0.06,0.01,zi+1),(lx-0.06,0.01,zi+1)]
            p = [cam.proj(v) for v in q]
            if None in p: continue
            fog = clamp((((p[0][2]+p[2][2])/2) - FOG_A)/(FOG_B-FOG_A), 0, .9)
            c = (int(18*(1-fog)+BG[0]*fog), int(200*(1-fog)+BG[1]*fog), int(224*(1-fog)+BG[2]*fog))
            fb.tri(p[0], p[1], p[2], c, 1.0, True)
            fb.tri(p[0], p[2], p[3], c, 1.0, True)

    # ---- pins
    for i, (px, pz) in enumerate(pins0):
        if wt < IMPACT_WT:
            draw_mesh(fb, cam, PIN_V, PIN_T, IDENT, (px, 0, pz), pin_color(i))
        else:
            t = wt - IMPACT_WT
            vx, vy, vz, axis, w = pin_state[i]
            x = px + vx*t
            y = max(0.05, vy*t - 4.9*t*t)
            z = pz + vz*t
            ang = w*t
            c, s = math.cos(ang), math.sin(ang)
            ux, uy, uz = axis
            R = ((c+ux*ux*(1-c), ux*uy*(1-c)-uz*s, ux*uz*(1-c)+uy*s),
                 (uy*ux*(1-c)+uz*s, c+uy*uy*(1-c), uy*uz*(1-c)-ux*s),
                 (uz*ux*(1-c)-uy*s, uz*uy*(1-c)+ux*s, c+uz*uz*(1-c)))
            draw_mesh(fb, cam, PIN_V, PIN_T, R, (x, y, z), pin_color(i))

    # ---- the loser
    splat_started = wt >= 4.75
    if not splat_started:
        if wt < IMPACT_WT:
            draw_loser(fb, cam, LOSER0, IDENT, pose_up=True)
        else:
            t = wt - IMPACT_WT
            zpos = 19.3 - t*11.5                     # flying at the camera
            y = 0.4 + 2.6*math.sin(min(1, t/1.1)*math.pi*0.9)
            tumble = mmul(rotx(t*7), rotz(t*3.5))
            draw_loser(fb, cam, (0.15*math.sin(t*5), y, zpos), tumble, pose_up=True)
    else:
        k = wt - 4.75
        slide = k*20
        squash = 1.25 if k < 0.12 else 1.0
        draw_splat(fb, 96, 44 + slide, 0.62*squash, (198,255,26))
        if k < 0.2:
            for _ in range(3):
                a = random.uniform(0, 6.28); r = random.uniform(12, 42)
                x2, y2 = 96+math.cos(a)*r, 44+math.sin(a)*r
                steps = int(r)
                for si in range(steps):
                    tt2 = si/steps
                    fb.dot2(96+(x2-96)*tt2, 44+(y2-44)*tt2, 0.8, (255,255,255))

    # ---- ball rendering + trail
    if wt < IMPACT_WT + 0.3:
        spin = rotx(wt*9)
        vs = [vmul(v, BALL_R) for v in BALL_V]
        draw_mesh(fb, cam, vs, BALL_T, spin, ball_pos, (255,90,31))
        for _ in range(4):
            particles.append([ball_pos[0]+random.uniform(-.15,.15), ball_pos[1]+random.uniform(-.2,.25),
                              ball_pos[2]-random.uniform(.3,.9),
                              random.uniform(-.4,.4), random.uniform(.5,1.8), random.uniform(-2,-0.5),
                              random.randint(5,9),
                              (255,90,31) if random.random()<.7 else (255,224,0)])
    if abs(wt - IMPACT_WT) < 1.0/FPS:
        for _ in range(30):
            particles.append([random.uniform(-1,1), random.uniform(.2,1.5), 20.4,
                              random.uniform(-2.5,2.5), random.uniform(1,5), random.uniform(-2,2),
                              random.randint(6,12), (255,224,0) if random.random()<.5 else (255,90,31)])
    if splat_started and wt < 11.4:
        for _ in range(8):
            particles.append([random.uniform(-1.6,1.6), 0.1, random.uniform(17,21.5),
                              random.uniform(-.2,.2), random.uniform(1.2,2.6), 0,
                              random.randint(6,12),
                              (255,90,31) if random.random()<.6 else (255,224,0)])
    alive = []
    dtw = (WT[fi] - WT[fi-1]) if fi else 1.0/FPS
    for p in particles:
        x, y, z, vx, vy, vz, life, rgb = p
        pr = cam.proj((x, y, z))
        if pr is not None:
            fb.dot2(pr[0], pr[1], max(.8, .05*95/pr[2]), rgb, pr[2])
        p[0] += vx*dtw; p[1] += vy*dtw; p[2] += vz*dtw
        p[4] -= 5*dtw; p[6] -= 1
        if p[6] > 0: alive.append(p)
    particles = alive

    # ---- flash
    if abs(wt - IMPACT_WT) < 0.8/FPS:
        b = fb.buf
        for i in range(len(b)):
            v = b[i] + 190
            b[i] = 255 if v > 255 else v
    # ---- boards
    if wt < 2.6 and int(wt*2) % 2 == 0:
        draw_word(fb, "LAST PLACE", 96, 4, 1.5, (255,224,0))
    if wt >= 5.6:
        on = wt >= 6.3 or int((wt-5.6)*8) % 2 == 0
        if on:
            draw_word(fb, "COOKD", 96, 5, 2.4, [(198,255,26)]*4 + [(255,26,140)])
    # ---- fades
    fade = 1.0
    if fi < 6: fade = fi/6
    if fi > NF-8: fade = (NF-fi)/8
    if fade < 1:
        b = fb.buf
        for i in range(len(b)):
            bg = BGROW[i]
            b[i] = int(bg + (b[i]-bg)*fade)
    frames.append(fb.buf)
    print("frame", fi, flush=True)

print("rendered", NF)
os.makedirs("frames_ps1", exist_ok=True)
for i, px in enumerate(frames):
    with open(f"frames_ps1/f{i:04d}.ppm", "wb") as fh:
        fh.write(f"P6 {CW} {CH} 255\n".encode()); fh.write(bytes(px))
print("wrote PPMs")

# ---- quantise -> app frames JSON
PAL = ["#c6ff1a","#7da300","#3f5200","#12e0ff","#0b6f80","#ff1a8c","#801348",
       "#ffe000","#806f00","#ff5a1f","#b63c10","#5e1d06","#ffffff","#b6b6b6",
       "#5b5b5b","#232a20","#0e1410","#7d8a7a"]
PRGB = [(int(h[1:3],16), int(h[3:5],16), int(h[5:7],16)) for h in PAL]
memo = {}
def q(r, g, b):
    if r+g+b < 24: return -1
    k = (r>>3, g>>3, b>>3)
    v = memo.get(k)
    if v is None:
        best, bd = -1, 1e9
        for i,(pr,pg,pb) in enumerate(PRGB):
            d = (r-pr)**2+(g-pg)**2+(b-pb)**2
            if d < bd: bd, best = d, i
        memo[k] = v = best
    return v
deltas_all, prev = [], [-1]*(CW*CH)
for px in frames:
    cur = [q(px[i*3],px[i*3+1],px[i*3+2]) for i in range(CW*CH)]
    ds, i = [], 0
    while i < CW*CH:
        if cur[i] != prev[i]:
            j, v = i, cur[i]
            while j < CW*CH and cur[j] == v and cur[j] != prev[j]: j += 1
            ds.append([i, j-i, v]); i = j
        else: i += 1
    deltas_all.append(ds); prev = cur
doc = {"cols":CW,"rows":CH,"fps":FPS,"palette":PAL,"frames":deltas_all}
out = REPO + "/assets/getting-cookd-ps1_frames.json"
json.dump(doc, open(out,"w"), separators=(",",":"))
print("wrote", out, os.path.getsize(out)//1024, "kB")
