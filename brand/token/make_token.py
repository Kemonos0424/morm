#!/usr/bin/env python3
"""MORM token symbol — deep-indigo case body + Voronoi swarm mesh + magenta/violet M + amber LED."""
import numpy as np, math, random
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops

RES = 2048                     # render resolution (final downsampled to 1024/512)
random.seed(7); np.random.seed(7)

# ---- palette pulled from the real 機体 (case) ----
NAVY_HI   = (58, 63, 108)      # lit rim / top-left highlight
NAVY      = (39, 43, 72)       # #272B48 body case color (main)
NAVY_LO   = (22, 25, 46)       # shadow side
NAVY_DEEP = (14, 16, 32)       # deep recess
HOLE      = (10, 11, 24)       # mesh hole interior
VIOLET    = (107, 44, 230)     # brand violet #6B2CE6
MAGENTA   = (236, 30, 121)     # brand magenta #EC1E79
LOGO_MAG  = (205, 108, 206)    # device logo magenta-violet
AMBER     = (252, 192, 79)     # live LED

def lerp(a,b,t): return tuple(int(a[i]+(b[i]-a[i])*t) for i in range(3))

C = RES/2.0

# ================= radial / directional shading helpers =================
yy, xx = np.mgrid[0:RES, 0:RES].astype(np.float32)
dx = xx - C; dy = yy - C
dist = np.sqrt(dx*dx + dy*dy)
# light from upper-left (like the product render)
lx, ly = -0.62, -0.78
ndir = (dx*lx + dy*ly) / (dist + 1e-6)   # -1..1, +1 toward light

# ================= 1. COIN BODY (case) =================
img = Image.new("RGBA",(RES,RES),(0,0,0,0))
R = RES*0.470                              # coin radius
# base body radial gradient (center slightly lighter)
tg = np.clip(dist / R, 0, 1)
body = np.zeros((RES,RES,3),np.float32)
for i in range(3):
    body[...,i] = NAVY[i] + (NAVY_HI[i]-NAVY[i])*(1-tg)*0.5 + (NAVY_LO[i]-NAVY[i])*(tg**1.6)*0.9
# directional sheen across the molded surface
sheen = (ndir*0.5+0.5)
body += ((sheen[...,None]-0.45) * np.array([26,26,34]))
body = np.clip(body,0,255)

alpha = np.clip((R-dist)*1.4+0.5,0,1)      # AA disk edge

# outer bevel ring (molded case edge): bright top-left, dark bottom-right
ring = np.clip(1-np.abs(dist-(R-RES*0.012))/(RES*0.020),0,1)
bev = ndir*ring
body += bev[...,None]*np.array([70,72,86])
body -= np.clip(-bev,0,1)[...,None]*ring[...,None]*np.array([40,42,60])
# thin dark outline at very edge
edge = np.clip(1-np.abs(dist-R)/ (RES*0.006),0,1)
body -= edge[...,None]*np.array([30,32,48])
body = np.clip(body,0,255)

# recessed top-face plate (grille inset), like the device's mesh panel
Rin = RES*0.408
inset = dist < Rin
# inner shadow ring around the inset
insh = np.clip(1-np.abs(dist-Rin)/(RES*0.026),0,1) * (dist<Rin+RES*0.03)
body -= insh[...,None]*np.array([26,28,40])
# slightly darker plane inside the inset
plate = np.clip((Rin-dist)/ (RES*0.02),0,1)*inset
body = np.where(inset[...,None], body*0.90 + np.array(NAVY_DEEP)*0.10, body)
body = np.clip(body,0,255)

# ================= 2. VORONOI SWARM MESH =================
# seed points across the inset (denser, organic). Poisson-ish via jittered rings + random.
pts=[]
Rmesh = Rin*0.985
# random blue-noise-ish
tries=0
while len(pts)<170 and tries<6000:
    tries+=1
    a=random.random()*2*math.pi; r=math.sqrt(random.random())*Rmesh
    px=C+math.cos(a)*r; py=C+math.sin(a)*r
    if all((px-q[0])**2+(py-q[1])**2 > (RES*0.031)**2 for q in pts):
        pts.append((px,py))
seeds=np.array(pts,np.float32)

# nearest + second nearest seed distance (loop seeds, keep two mins)
d1=np.full((RES,RES),1e9,np.float32); d2=np.full((RES,RES),1e9,np.float32)
lab=np.zeros((RES,RES),np.int32)
for i,(sx,sy) in enumerate(seeds):
    dd=(xx-sx)**2+(yy-sy)**2
    upd = dd<d1
    d2=np.where(upd, d1, np.minimum(d2,dd))
    lab=np.where(upd, i, lab)
    d1=np.where(upd, dd, d1)
d1=np.sqrt(d1); d2=np.sqrt(d2)
boundary = d2-d1                      # small near cell walls
WALL = RES*0.0120                     # half wall thickness
wall = np.clip((WALL-boundary)/(RES*0.004),0,1)   # 1 on wall, 0 in hole

mesh_area = dist < Rmesh
# holes = interior of cells; carve them into the plate with depth shading
hole = (1-wall)*mesh_area
# hole depth: darker toward hole center (use boundary as proxy for depth)
depth = np.clip(boundary/(RES*0.026),0,1)*hole
holecol = np.zeros((RES,RES,3),np.float32)
for i in range(3):
    holecol[...,i]=lerp(NAVY_DEEP,HOLE,1)[i]
# faint violet/magenta glow rising from inside the swarm holes
glowpos = np.clip((dist)/(Rmesh),0,1)
under = np.clip(depth,0,1)
holemix = holecol.copy()
# subtle under-glow — concentrated as a soft ember core behind the M so the
# NAVY case colour stays dominant across the field (rim reads pure navy)
core = np.exp(-((dist/(Rmesh*0.46))**2))          # tight central falloff
uglow = np.clip(core,0,1)*under
holemix[...,0]+=uglow*30; holemix[...,1]+=uglow*4; holemix[...,2]+=uglow*44
holemix=np.clip(holemix,0,255)

# wall shading: top edge of each wall catches light -> use ndir for bevel on walls
wallcol = body.copy()
walllit = wall*(ndir*0.5+0.5)
wallcol += (walllit[...,None]-wall[...,None]*0.42)*np.array([46,48,58])
wallcol = np.clip(wallcol,0,255)

# composite mesh over body inside mesh_area
comp = body.copy()
m = (hole)[...,None]
comp = comp*(1-m) + holemix*m
w = (wall*mesh_area)[...,None]
comp = comp*(1-w) + wallcol*w
comp = np.clip(comp,0,255)

body = comp

# put body into image with alpha
arr = np.dstack([body.astype(np.uint8), (alpha*255).astype(np.uint8)])
coin = Image.fromarray(arr,"RGBA")
img = Image.alpha_composite(img, coin)

# ================= 3. CENTER M MONOGRAM (magenta->violet, glowing) =================
def load_font(sz):
    for p in ["/System/Library/Fonts/Supplemental/Arial Black.ttf",
              "/System/Library/Fonts/HelveticaNeue.ttc",
              "/System/Library/Fonts/Helvetica.ttc"]:
        try: return ImageFont.truetype(p, sz)
        except: pass
    return ImageFont.load_default()

# M mask
Msz=int(RES*0.60)
font=load_font(Msz)
mmask=Image.new("L",(RES,RES),0)
md=ImageDraw.Draw(mmask)
# center the glyph
bbox=md.textbbox((0,0),"M",font=font)
mw=bbox[2]-bbox[0]; mh=bbox[3]-bbox[1]
mx=C-mw/2-bbox[0]; my=C-mh/2-bbox[1]
md.text((mx,my),"M",font=font,fill=255)
mnp=np.array(mmask,np.float32)/255.0

# gradient fill magenta(top) -> violet(bottom) with a bright core
gg=np.clip((yy-(C-mh/2))/mh,0,1)
Mcol=np.zeros((RES,RES,3),np.float32)
for i in range(3):
    Mcol[...,i]=MAGENTA[i]+(VIOLET[i]-MAGENTA[i])*gg
# add top sheen highlight on the M
Mcol += (1-gg)[...,None]*np.array([30,20,10])
Mcol=np.clip(Mcol,0,255)
Mrgba=np.dstack([Mcol.astype(np.uint8),(mnp*255).astype(np.uint8)])
Mimg=Image.fromarray(Mrgba,"RGBA")

# glow: blurred magenta version behind
glow=Image.new("RGBA",(RES,RES),(0,0,0,0))
gd=ImageDraw.Draw(glow)
gmask=mmask.filter(ImageFilter.GaussianBlur(RES*0.020))
garr=np.array(gmask,np.float32)/255.0
gcol=np.dstack([np.full((RES,RES),MAGENTA[0],np.uint8),
                np.full((RES,RES),40,np.uint8),
                np.full((RES,RES),MAGENTA[2],np.uint8),
                (np.clip(garr*0.85,0,1)*255).astype(np.uint8)])
glowimg=Image.fromarray(gcol,"RGBA")
# clip glow+M to coin
coinmask=Image.fromarray((alpha*255).astype(np.uint8),"L")
glowimg.putalpha(ImageChops.multiply(glowimg.split()[3],coinmask))
img=Image.alpha_composite(img,glowimg)

# subtle emboss: dark drop under M for engraved-on-case feel
shadow=mmask.filter(ImageFilter.GaussianBlur(RES*0.006))
sh=np.array(shadow,np.float32)/255.0
shimg=Image.fromarray(np.dstack([np.zeros((RES,RES,3),np.uint8),
       (np.clip(sh*0.5,0,1)*255).astype(np.uint8)]),"RGBA")
shimg=ImageChops.offset(shimg,int(RES*0.004),int(RES*0.005))
shimg.putalpha(ImageChops.multiply(shimg.split()[3],coinmask))
img=Image.alpha_composite(img,shimg)
img=Image.alpha_composite(img,Mimg)

# ================= 4. AMBER LIVE LED =================
led=Image.new("RGBA",(RES,RES),(0,0,0,0))
ld=ImageDraw.Draw(led)
lxp,lyp=C+RES*0.300, C-RES*0.028
rr=RES*0.020
# glow
gl=Image.new("RGBA",(RES,RES),(0,0,0,0))
ImageDraw.Draw(gl).ellipse([lxp-rr*3,lyp-rr*3,lxp+rr*3,lyp+rr*3],fill=AMBER+(120,))
gl=gl.filter(ImageFilter.GaussianBlur(RES*0.012))
img=Image.alpha_composite(img,gl)
ld.ellipse([lxp-rr,lyp-rr,lxp+rr,lyp+rr],fill=AMBER+(255,))
ld.ellipse([lxp-rr*0.4,lyp-rr*0.55,lxp+rr*0.2,lyp+rr*0.05],fill=(255,240,210,255))
img=Image.alpha_composite(img,led)

# ================= 5. ENGRAVED EDGE MICRO-TEXT RING =================
ringtxt="MORM · THE SWARM FOR EVERY FRAME · "
rf=load_font(int(RES*0.028))
Rt=R*0.955
ov=Image.new("RGBA",(RES,RES),(0,0,0,0))
n=len(ringtxt)*2
for i,ch in enumerate(ringtxt*2):
    ang=-math.pi/2 + i/(len(ringtxt)*2)*2*math.pi
    tx=C+math.cos(ang)*Rt; ty=C+math.sin(ang)*Rt
    ci=Image.new("RGBA",(int(RES*0.05),int(RES*0.05)),(0,0,0,0))
    cd=ImageDraw.Draw(ci)
    cd.text((ci.width/2,ci.height/2),ch,font=rf,fill=(150,155,190,150),anchor="mm")
    ci=ci.rotate(-math.degrees(ang)-90,resample=Image.BICUBIC,center=(ci.width/2,ci.height/2))
    ov.alpha_composite(ci,(int(tx-ci.width/2),int(ty-ci.height/2)))
ov.putalpha(ImageChops.multiply(ov.split()[3],coinmask))
img=Image.alpha_composite(img,ov)

# ================= OUTPUT =================
out=img
for size,fn in [(1024,"morm-token-1024.png"),(512,"morm-token-512.png"),(256,"morm-token-256.png")]:
    out.resize((size,size),Image.LANCZOS).save(fn)
print("done", seeds.shape[0], "cells")
