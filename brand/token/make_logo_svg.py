#!/usr/bin/env python3
"""True-vector MORM token logo.svg — font-independent (Voronoi polygons + hand-built M path).
Base/Superchain token list requires logo.svg, square, 256x256 preferred."""
import math, random
random.seed(7)

S = 256.0                      # viewBox (square, Superchain preferred)
C = S/2
R = S*0.492                    # coin radius (fills frame, tiny margin)
Rin = S*0.430                  # recessed grille inset
Rmesh = Rin*0.985

# palette from the real 機体 case
NAVY_HI="#3A3F6C"; NAVY="#272B48"; NAVY_LO="#161A2E"; NAVY_DEEP="#0E1020"
HOLE="#0B0C18"; WEB="#2E3352"; WEB_HI="#464C74"
MAG="#EC1E79"; VIO="#6B2CE6"; AMBER="#FCC04F"

# ---------- Voronoi via half-plane (Sutherland–Hodgman) clipping ----------
def clip(poly, a, b):
    """keep the half-plane of points closer to seed a than seed b (perp bisector)."""
    mx,my=(a[0]+b[0])/2,(a[1]+b[1])/2
    nx,ny=a[0]-b[0],a[1]-b[1]          # normal pointing toward a
    out=[]
    n=len(poly)
    for i in range(n):
        cur=poly[i]; nxt=poly[(i+1)%n]
        dc=(cur[0]-mx)*nx+(cur[1]-my)*ny
        dn=(nxt[0]-mx)*nx+(nxt[1]-my)*ny
        if dc>=0: out.append(cur)
        if (dc>=0)!=(dn>=0):
            t=dc/(dc-dn)
            out.append((cur[0]+t*(nxt[0]-cur[0]), cur[1]+t*(nxt[1]-cur[1])))
    return out

# bounding polygon = circle (mesh area) approximated as 96-gon
BOUND=[(C+math.cos(2*math.pi*i/96)*Rmesh, C+math.sin(2*math.pi*i/96)*Rmesh) for i in range(96)]

# blue-noise seeds
pts=[]; tries=0
while len(pts)<150 and tries<8000:
    tries+=1
    ang=random.random()*2*math.pi; rr=math.sqrt(random.random())*Rmesh
    p=(C+math.cos(ang)*rr, C+math.sin(ang)*rr)
    if all((p[0]-q[0])**2+(p[1]-q[1])**2>(S*0.052)**2 for q in pts): pts.append(p)

def centroid(poly):
    return (sum(p[0] for p in poly)/len(poly), sum(p[1] for p in poly)/len(poly))

cells=[]
for i,a in enumerate(pts):
    poly=BOUND[:]
    for j,b in enumerate(pts):
        if i==j: continue
        if (a[0]-b[0])**2+(a[1]-b[1])**2 > (S*0.34)**2: continue  # far seeds can't bound this cell
        poly=clip(poly,a,b)
        if len(poly)<3: break
    if len(poly)>=3: cells.append(poly)

# shrink each cell toward its centroid → gap becomes the navy webbing
GAP=0.128
holes=[]
for poly in cells:
    cx,cy=centroid(poly)
    sp=[(cx+(x-cx)*(1-GAP), cy+(y-cy)*(1-GAP)) for x,y in poly]
    holes.append(sp)

def path(poly):
    d="M "+" L ".join(f"{x:.2f},{y:.2f}" for x,y in poly)+" Z"
    return d

# ---------- hand-built geometric M (pointed-diagonal, font-independent) ----------
Mw=S*0.052                       # not used directly
L=C-S*0.150; Rr=C+S*0.150; T=C-S*0.150; B=C+S*0.150
w=(Rr-L)*0.235; cx=(L+Rr)/2
vy_top=T+(B-T)*0.20; vy_bot=T+(B-T)*0.72
Mpts=[(L,B),(L,T),(L+w,T),(cx,vy_top),(Rr-w,T),(Rr,T),(Rr,B),(Rr-w,B),(cx,vy_bot),(L+w,B)]
Mpath="M "+" L ".join(f"{x:.2f},{y:.2f}" for x,y in Mpts)+" Z"

# LED
lx=cx+S*0.150*2*0.0  # placeholder
lx=C+S*0.300; ly=C-S*0.028; lr=S*0.020

svg=f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {S:.0f} {S:.0f}" width="{S:.0f}" height="{S:.0f}">
<defs>
 <radialGradient id="body" cx="38%" cy="32%" r="80%">
   <stop offset="0%" stop-color="{NAVY_HI}"/>
   <stop offset="55%" stop-color="{NAVY}"/>
   <stop offset="100%" stop-color="{NAVY_LO}"/>
 </radialGradient>
 <radialGradient id="plate" cx="42%" cy="36%" r="75%">
   <stop offset="0%" stop-color="{NAVY}"/>
   <stop offset="100%" stop-color="{NAVY_DEEP}"/>
 </radialGradient>
 <radialGradient id="ember" cx="50%" cy="50%" r="50%">
   <stop offset="0%" stop-color="{VIO}" stop-opacity="0.55"/>
   <stop offset="45%" stop-color="{MAG}" stop-opacity="0.16"/>
   <stop offset="100%" stop-color="{MAG}" stop-opacity="0"/>
 </radialGradient>
 <linearGradient id="mgrad" x1="0" y1="0" x2="0" y2="1">
   <stop offset="0%" stop-color="{MAG}"/>
   <stop offset="100%" stop-color="{VIO}"/>
 </linearGradient>
 <radialGradient id="led" cx="40%" cy="35%" r="65%">
   <stop offset="0%" stop-color="#FFF1D6"/>
   <stop offset="55%" stop-color="{AMBER}"/>
   <stop offset="100%" stop-color="#C77A18"/>
 </radialGradient>
 <linearGradient id="bevel" x1="0" y1="0" x2="1" y2="1">
   <stop offset="0%" stop-color="{WEB_HI}"/>
   <stop offset="50%" stop-color="{NAVY}"/>
   <stop offset="100%" stop-color="{NAVY_DEEP}"/>
 </linearGradient>
 <filter id="glow" x="-60%" y="-60%" width="220%" height="220%">
   <feGaussianBlur stdDeviation="5.5"/>
 </filter>
 <filter id="ledglow" x="-200%" y="-200%" width="500%" height="500%">
   <feGaussianBlur stdDeviation="6"/>
 </filter>
 <clipPath id="mesh"><circle cx="{C}" cy="{C}" r="{Rmesh:.2f}"/></clipPath>
</defs>

<!-- coin body + molded bevel -->
<circle cx="{C}" cy="{C}" r="{R:.2f}" fill="url(#bevel)"/>
<circle cx="{C}" cy="{C}" r="{R-S*0.022:.2f}" fill="url(#body)"/>
<!-- recessed grille plate -->
<circle cx="{C}" cy="{C}" r="{Rin:.2f}" fill="url(#plate)"/>
<circle cx="{C}" cy="{C}" r="{Rin:.2f}" fill="none" stroke="#000" stroke-opacity="0.35" stroke-width="{S*0.010:.2f}"/>

<!-- Voronoi swarm mesh: navy webbing (plate) shows between dark holes -->
<g clip-path="url(#mesh)">
  <rect x="0" y="0" width="{S:.0f}" height="{S:.0f}" fill="{WEB}"/>
'''
for sp in holes:
    svg+=f'  <path d="{path(sp)}" fill="{HOLE}"/>\n'
# webbing top-light: faint highlight overlay via thin strokes on cell edges
for sp in holes:
    svg+=f'  <path d="{path(sp)}" fill="none" stroke="{WEB_HI}" stroke-opacity="0.28" stroke-width="0.5"/>\n'
svg+=f'''  <!-- central ember behind M keeps navy dominant elsewhere -->
  <circle cx="{C}" cy="{C}" r="{Rmesh*0.62:.2f}" fill="url(#ember)"/>
</g>

<!-- amber live LED -->
<circle cx="{lx:.2f}" cy="{ly:.2f}" r="{lr*2.4:.2f}" fill="{AMBER}" opacity="0.45" filter="url(#ledglow)"/>
<circle cx="{lx:.2f}" cy="{ly:.2f}" r="{lr:.2f}" fill="url(#led)"/>

<!-- M monogram (magenta->violet) with glow -->
<path d="{Mpath}" fill="{MAG}" opacity="0.55" filter="url(#glow)"/>
<path d="{Mpath}" fill="#000" opacity="0.30" transform="translate({S*0.006:.2f},{S*0.008:.2f})"/>
<path d="{Mpath}" fill="url(#mgrad)"/>
</svg>
'''
open("logo.svg","w").write(svg)
print("cells",len(cells),"holes",len(holes),"bytes",len(svg))
