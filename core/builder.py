"""
builder_v7.py — Viral Short-Form Video Engine
==============================================
What's new over v6:
  • DURATION bumped to 30 s (max Shorts with full YT algorithm boost)
  • Hook frame: full-bleed image + big bold HOOK text for first 1.8 s
    ("Did you know…" / "BREAKING:" style opener = scroll-stopper)
  • Progress bar crawls along top edge so viewers feel urgency to stay
  • Typewriter effect on body text (letter-by-letter reveal)
  • Animated category badge: scale-bounce + colour pulse on entry
  • "Stat callout" box — if title has digits, isolates the number in a
    large accent box to create a viral shareability anchor
  • Particle system upgraded: 80 particles, mix of circles + star shapes,
    speed variation, soft glow rings around bright ones
  • Vignette overlay darkens corners every frame for cinematic depth
  • Music volume raised to 0.28, with a 0.5 s fade-in to avoid click
  • Bottom CTA pulse: "FOLLOW for more" text pulses in sync with beat
  • All original visual systems retained and extended (glass card,
    shimmer sweeps, Ken Burns, glass border, channel banner)
"""

import os, textwrap, requests, time, random, math, re
from pathlib import Path
from io import BytesIO

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from moviepy.editor import VideoClip, AudioFileClip

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════
W, H        = 1080, 1920
FPS         = 30
DURATION    = 30

FONT_DIR    = Path(__file__).parent / "assets" / "fonts"
OUT_DIR     = Path(__file__).parent / "output"
OUT_DIR.mkdir(exist_ok=True)

CHANNEL_NAME   = "Nano News World"
CHANNEL_HANDLE = "@nanonewsworld"

CARD_TOP_RATIO = 0.44
PAD            = 44
CARD_RADIUS    = 36
BANNER_H       = 152

KB_SCALE_START = 1.06
KB_SCALE_END   = 1.24
KB_PAN_X       = 0.05
KB_PAN_Y       = 0.025

T_HOOK_END  = 1.80
T_CARD_IN   = 1.95
T_BADGE_IN  = 2.20
T_TITLE_IN  = 2.45
T_DIV_IN    = 2.90
T_BODY_IN   = 3.15
T_BANNER_IN = 4.20

# ═══════════════════════════════════════════════════════════════════════════════
# EASING
# ═══════════════════════════════════════════════════════════════════════════════
def ease_out_cubic(t):       return 1 - (1 - t) ** 3
def ease_in_out_cubic(t):
    return 4*t*t*t if t < 0.5 else 1 - (-2*t+2)**3/2
def ease_out_back(t, s=1.4): return 1 + (s+1)*(t-1)**3 + s*(t-1)**2
def ease_out_elastic(t):
    if t <= 0: return 0
    if t >= 1: return 1
    c4 = (2*math.pi) / 3
    return pow(2,-10*t) * math.sin((t*10-0.75)*c4) + 1
def clamp01(v):              return max(0.0, min(1.0, v))
def progress(t, start, dur): return clamp01((t - start) / dur)

# ═══════════════════════════════════════════════════════════════════════════════
# SAFE DRAW
# ═══════════════════════════════════════════════════════════════════════════════
def safe_rounded_rect(draw, box, radius, **kw):
    x0, y0, x1, y1 = box
    if x1 <= x0 + 1 or y1 <= y0 + 1: return
    r = min(radius, (x1-x0)//2, (y1-y0)//2)
    draw.rounded_rectangle([x0,y0,x1,y1], radius=max(1,r), **kw)

def safe_line(draw, pts, **kw):
    try: draw.line(pts, **kw)
    except: pass

# ═══════════════════════════════════════════════════════════════════════════════
# PALETTE
# ═══════════════════════════════════════════════════════════════════════════════
def extract_palette(img):
    small     = img.copy().resize((80,80), Image.LANCZOS).convert("RGB")
    quantized = small.quantize(colors=8, method=Image.Quantize.MEDIANCUT)
    pr        = quantized.getpalette()[:8*3]
    colors    = [(pr[i],pr[i+1],pr[i+2]) for i in range(0,len(pr),3)]
    def sat(c):
        r,g,b=[x/255 for x in c]; mx,mn=max(r,g,b),min(r,g,b)
        return (mx-mn)/mx if mx>0 else 0
    def usable(c):
        lum=.2126*c[0]+.7152*c[1]+.0722*c[2]
        return 40<lum<220
    u=([c for c in colors if usable(c)] or colors)
    accent=max(u,key=sat)
    title=tuple(min(255,int(x*1.35+30)) for x in accent)
    card =tuple(max(0,int(x*0.06))      for x in accent)
    return {"accent":accent,"title":title,"body":(232,228,220),"card":card}

FALLBACK_THEMES=[
    {"accent":(212,175,55), "title":(255,220,100),"body":(232,225,215),"card":(8,6,3)},
    {"accent":(0,210,230),  "title":(100,240,255),"body":(210,235,240),"card":(3,8,15)},
    {"accent":(220,50,50),  "title":(255,110,110),"body":(240,220,220),"card":(10,4,4)},
    {"accent":(170,90,230), "title":(210,150,255),"body":(225,215,240),"card":(8,4,16)},
    {"accent":(40,210,110), "title":(100,250,160),"body":(210,240,220),"card":(3,12,6)},
    {"accent":(230,130,20), "title":(255,175,75), "body":(240,228,210),"card":(14,8,2)},
]

# ═══════════════════════════════════════════════════════════════════════════════
# FONTS
# ═══════════════════════════════════════════════════════════════════════════════
def _font(size, bold=False, serif=False):
    if serif:
        cands=[
            # Hindi/Devanagari-capable fonts (checked first)
            FONT_DIR/("NotoSerifDevanagari-Bold.ttf"  if bold else "NotoSerifDevanagari-Regular.ttf"),
            Path("/usr/share/fonts/truetype/noto/NotoSerifDevanagari-Bold.ttf" if bold
                 else "/usr/share/fonts/truetype/noto/NotoSerifDevanagari-Regular.ttf"),
            FONT_DIR/("NotoSerif-Bold.ttf"      if bold else "NotoSerif-Regular.ttf"),
            FONT_DIR/("PlayfairDisplay-Bold.ttf" if bold else "PlayfairDisplay-Regular.ttf"),
            Path("/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf" if bold
                 else "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf" if bold
                 else "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"),
        ]
    else:
        cands=[
            # Hindi/Devanagari-capable fonts (checked first)
            FONT_DIR/("NotoSansDevanagari-Bold.ttf"  if bold else "NotoSansDevanagari-Regular.ttf"),
            Path("/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf" if bold
                 else "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf"),
            FONT_DIR/("NotoSans-Bold.ttf"   if bold else "NotoSans-Regular.ttf"),
            FONT_DIR/("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
                 else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold
                 else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
        ]
    cands+=[Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
                 else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")]
    for p in cands:
        if p.exists(): return ImageFont.truetype(str(p),size)
    return ImageFont.load_default()

def _fit_font(text_lines, max_w, max_size=72, min_size=36, bold=True, serif=True):
    for size in range(max_size, min_size-1, -2):
        f = _font(size, bold=bold, serif=serif)
        dummy = Image.new("RGB",(1,1))
        d = ImageDraw.Draw(dummy)
        fits = all((d.textbbox((0,0),ln,font=f)[2]-d.textbbox((0,0),ln,font=f)[0]) <= max_w
                   for ln in text_lines)
        if fits: return f, size
    return _font(min_size, bold=bold, serif=serif), min_size

# ═══════════════════════════════════════════════════════════════════════════════
# DOWNLOAD
# ═══════════════════════════════════════════════════════════════════════════════
def _download_image(url):
    if not url or url in ("None",""): return None
    try:
        r=requests.get(url,timeout=15,headers={"User-Agent":"Mozilla/5.0"})
        r.raise_for_status()
        img=Image.open(BytesIO(r.content)).convert("RGB")
        return img if img.size[0]>10 else None
    except Exception as e:
        print(f"    [builder] image download failed: {e}"); return None

def _load_channel_pfp():
    try:
        yt_client_id     = os.environ.get("YT_CLIENT_ID", "")
        yt_client_secret = os.environ.get("YT_CLIENT_SECRET", "")
        yt_refresh_token = os.environ.get("YT_REFRESH_TOKEN", "")
        token_r = requests.post(
            "https://oauth2.googleapis.com/token",
            data={"client_id":yt_client_id,"client_secret":yt_client_secret,
                  "refresh_token":yt_refresh_token,"grant_type":"refresh_token"},
            timeout=10)
        access_token = token_r.json().get("access_token","")
        if not access_token: raise ValueError("No access token")
        ch_r = requests.get(
            "https://www.googleapis.com/youtube/v3/channels",
            params={"part":"snippet","mine":"true"},
            headers={"Authorization":f"Bearer {access_token}"},
            timeout=10)
        thumbnails = ch_r.json()["items"][0]["snippet"]["thumbnails"]
        pfp_url = (thumbnails.get("high") or thumbnails.get("default"))["url"]
        img = _download_image(pfp_url)
        if img:
            img = img.convert("RGBA").resize((64,64), Image.LANCZOS)
            mask = Image.new("L",(64,64),0)
            ImageDraw.Draw(mask).ellipse([0,0,64,64],fill=255)
            img.putalpha(mask)
            print("    [builder] channel PFP fetched from YouTube ✓")
            return img
    except Exception as e:
        print(f"    [builder] PFP fetch failed: {e}")
    pfp_path = Path(__file__).parent / "assets" / "channel_pfp.png"
    if pfp_path.exists():
        img = Image.open(pfp_path).convert("RGBA").resize((64,64), Image.LANCZOS)
        mask = Image.new("L",(64,64),0)
        ImageDraw.Draw(mask).ellipse([0,0,64,64],fill=255)
        img.putalpha(mask)
        return img
    return None

# ═══════════════════════════════════════════════════════════════════════════════
# KEN BURNS
# ═══════════════════════════════════════════════════════════════════════════════
def _ken_burns_frame(img, t):
    p=ease_in_out_cubic(t)
    scale=KB_SCALE_START+(KB_SCALE_END-KB_SCALE_START)*p
    pan_x=int(KB_PAN_X*W*p); pan_y=int(KB_PAN_Y*H*p)
    nw,nh=int(W*scale),int(H*scale)
    resized=img.resize((nw,nh),Image.BILINEAR)
    left=max(0,min(nw-W,(nw-W)//2+pan_x))
    top =max(0,min(nh-H,(nh-H)//2+pan_y))
    return resized.crop((left,top,left+W,top+H))

def _prepare_bg_layers(img):
    iw,ih=img.size
    scale=max(W/iw,H/ih)*KB_SCALE_END*1.05
    nw,nh=int(iw*scale),int(ih*scale)
    bg=img.resize((nw,nh),Image.LANCZOS)
    bg=bg.crop(((nw-W)//2,(nh-H)//2,(nw-W)//2+W,(nh-H)//2+H))
    if HAS_CV2:
        bg_blur=Image.fromarray(cv2.GaussianBlur(np.array(bg),(61,61),0))
    else:
        bg_blur=bg.filter(ImageFilter.GaussianBlur(radius=35))
    sharp_h=int(H*0.54)
    s2=max(W/iw,sharp_h/ih)
    nw2,nh2=int(iw*s2),int(ih*s2)
    sharp=img.resize((nw2,nh2),Image.LANCZOS)
    sharp=sharp.crop(((nw2-W)//2,(nh2-sharp_h)//2,(nw2-W)//2+W,(nh2-sharp_h)//2+sharp_h))
    return bg_blur, sharp, sharp_h

def _composite_bg(bg_blurred, sharp, sharp_h, kb_t):
    animated=_ken_burns_frame(bg_blurred, kb_t)
    dim=Image.new("RGBA",(W,H),(0,0,0,155))
    base=Image.alpha_composite(animated.convert("RGBA"),dim)
    base.paste(sharp.convert("RGBA"),(0,0),sharp.convert("RGBA"))
    fade_h=340
    fade=Image.new("RGBA",(W,fade_h),(0,0,0,0))
    fd=ImageDraw.Draw(fade)
    for i in range(fade_h):
        fd.rectangle([0,i,W,i+1],fill=(0,0,0,int(255*(i/fade_h)**1.6)))
    base.paste(fade,(0,sharp_h-90),fade)
    bot=Image.new("RGBA",(W,H-sharp_h+90),(0,0,0,125))
    base.paste(bot,(0,sharp_h-90),bot)
    return base.convert("RGB")

# ═══════════════════════════════════════════════════════════════════════════════
# VIGNETTE
# ═══════════════════════════════════════════════════════════════════════════════
_VIGNETTE_CACHE = None

def _make_vignette():
    global _VIGNETTE_CACHE
    if _VIGNETTE_CACHE is not None:
        return _VIGNETTE_CACHE
    vig = Image.new("RGBA", (W, H), (0,0,0,0))
    arr = np.zeros((H, W), dtype=np.float32)
    cx, cy = W/2, H/2
    for y in range(0, H, 4):
        for x in range(0, W, 4):
            dx = (x - cx) / cx
            dy = (y - cy) / cy
            dist = math.sqrt(dx*dx + dy*dy) / math.sqrt(2)
            val = dist ** 2.2
            arr[y:y+4, x:x+4] = val
    arr = np.clip(arr * 200, 0, 180).astype(np.uint8)
    vig_arr = np.zeros((H, W, 4), dtype=np.uint8)
    vig_arr[:,:,3] = arr
    _VIGNETTE_CACHE = Image.fromarray(vig_arr, "RGBA")
    return _VIGNETTE_CACHE

# ═══════════════════════════════════════════════════════════════════════════════
# PROGRESS BAR
# ═══════════════════════════════════════════════════════════════════════════════
def _draw_progress_bar(frame, t, accent):
    ar, ag, ab = accent
    filled = int(W * (t / DURATION))
    draw = ImageDraw.Draw(frame)
    draw.rectangle([0, 0, W, 7], fill=(40,40,40,180))
    if filled > 1:
        draw.rectangle([0, 0, filled, 7], fill=(ar, ag, ab, 230))
        for gx in range(min(30, filled)):
            a = int(160 * (1 - gx/30))
            px = filled - gx
            if 0 < px < W:
                draw.rectangle([px, 0, px+2, 7], fill=(255,255,255, a))
    if 4 < filled < W - 4:
        draw.ellipse([filled-5, -2, filled+5, 9],
                     fill=(min(255,ar+100), min(255,ag+100), min(255,ab+100), 255))

# ═══════════════════════════════════════════════════════════════════════════════
# HOOK FRAME
# ═══════════════════════════════════════════════════════════════════════════════
def _build_hook_frame(t, full_bleed, hook_text, accent, particles):
    iw, ih = full_bleed.size
    scale = max(W/iw, H/ih) * 1.06
    nw, nh = int(iw*scale), int(ih*scale)
    bg = full_bleed.resize((nw, nh), Image.LANCZOS)
    bg = bg.crop(((nw-W)//2, (nh-H)//2, (nw-W)//2+W, (nh-H)//2+H))
    frame = bg.convert("RGBA")

    grad = Image.new("RGBA", (W, H), (0,0,0,0))
    gd = ImageDraw.Draw(grad)
    for i in range(H):
        frac = i / H
        alpha = int(200 * frac**1.4)
        gd.rectangle([0, i, W, i+1], fill=(0,0,0,alpha))
    frame = Image.alpha_composite(frame, grad)
    frame = Image.alpha_composite(frame, _make_vignette())

    hook_p = ease_out_back(clamp01(t / 0.55))
    hook_a = int(255 * clamp01(t / 0.40))
    if hook_a > 5:
        draw = ImageDraw.Draw(frame)
        ar, ag, ab = accent
        bright = (min(255,ar+100), min(255,ag+100), min(255,ab+100))
        hook_font_big = _font(90, bold=True, serif=False)
        hook_font_sub = _font(54, bold=False, serif=True)
        lines = textwrap.wrap(hook_text, width=16)[:3]  # No .upper() for Devanagari
        dummy = Image.new("RGB",(1,1))
        dd = ImageDraw.Draw(dummy)
        total_h = sum(dd.textbbox((0,0),l,font=hook_font_big)[3] for l in lines) + 20*(len(lines)-1)
        base_y = H//2 + int(60 * (1-hook_p))
        for i, line in enumerate(lines):
            bbox = dd.textbbox((0,0), line, font=hook_font_big)
            lw = bbox[2]-bbox[0]
            lh = bbox[3]-bbox[1]
            x = (W - lw) // 2
            y = base_y + i*(lh + 20)
            draw.text((x+4, y+4), line, font=hook_font_big, fill=(0,0,0,int(hook_a*0.6)))
            draw.text((x, y), line, font=hook_font_big,
                      fill=(bright[0], bright[1], bright[2], hook_a))
        sub_text = "Tap for full story ↓"
        sub_pulse = 0.6 + 0.4*math.sin(t * 5)
        sub_a = int(200 * sub_pulse * hook_a/255)
        sb = dd.textbbox((0,0), sub_text, font=hook_font_sub)
        sx = (W - (sb[2]-sb[0])) // 2
        sy = base_y + total_h + 50
        draw.text((sx+2, sy+2), sub_text, font=hook_font_sub, fill=(0,0,0, sub_a//2))
        draw.text((sx, sy), sub_text, font=hook_font_sub, fill=(ar, ag, ab, sub_a))

    fade_out_p = clamp01((t - (T_HOOK_END - 0.5)) / 0.5)
    if fade_out_p > 0:
        blackout = Image.new("RGBA", (W, H), (0,0,0, int(255*fade_out_p)))
        frame = Image.alpha_composite(frame, blackout)

    frame = particles.draw(frame.convert("RGB"), t).convert("RGBA")
    return np.array(frame.convert("RGB"))

# ═══════════════════════════════════════════════════════════════════════════════
# STAT CALLOUT
# ═══════════════════════════════════════════════════════════════════════════════
def _extract_stat(title):
    patterns = [
        r'\$[\d,\.]+[BMKbmk]?',
        r'[\d,]+%',
        r'[\d,]+\s*(?:million|billion|trillion|lakh|crore)',
        r'#\d+',
        r'\b\d{4}\b',
        r'\b\d[\d,]*\b',
    ]
    for pat in patterns:
        m = re.search(pat, title, re.IGNORECASE)
        if m:
            val = m.group(0).strip()
            if len(val) >= 2:
                return val
    return None

def _draw_stat_callout(frame, cx0, y, inner_w, stat_text, accent, t, alpha):
    if not stat_text or alpha < 10:
        return y
    draw = ImageDraw.Draw(frame)
    ar, ag, ab = accent
    stat_font  = _font(80, bold=True, serif=False)   # FIX: was 120 — too tall, ate into title space
    dummy = Image.new("RGB",(1,1))
    dd = ImageDraw.Draw(dummy)
    sb = dd.textbbox((0,0), stat_text, font=stat_font)
    sw = sb[2]-sb[0]; sh = sb[3]-sb[1]
    box_pad = 18                                      # FIX: was 24 — tighter padding
    box_w = min(sw + box_pad*2, inner_w)
    box_h = sh + box_pad*2 + 4                        # FIX: was +8
    bx0 = cx0 + (inner_w - box_w) // 2               # FIX: removed erroneous +40 offset
    bx1 = bx0 + box_w
    by0 = y; by1 = y + box_h
    layer = Image.new("RGBA", (W, H), (0,0,0,0))
    ld = ImageDraw.Draw(layer)
    safe_rounded_rect(ld, [bx0,by0,bx1,by1], 16, fill=(ar,ag,ab, int(200*alpha/255)))
    safe_rounded_rect(ld, [bx0,by0,bx1,by0+box_h//2], 16, fill=(255,255,255, int(30*alpha/255)))
    frame.alpha_composite(layer)
    draw = ImageDraw.Draw(frame)
    tx = bx0 + box_pad + (box_w - box_pad*2 - sw)//2
    ty = by0 + box_pad
    draw.text((tx+3,ty+3), stat_text, font=stat_font, fill=(0,0,0,int(100*alpha/255)))
    draw.text((tx,ty), stat_text, font=stat_font, fill=(255,255,255,alpha))
    return by1 + 18

# ═══════════════════════════════════════════════════════════════════════════════
# DIAGONAL SHIMMER
# ═══════════════════════════════════════════════════════════════════════════════
def _diagonal_shimmer(layer, x0, y0, x1, y1, t, period, direction, alpha_max, card_p):
    w = x1 - x0; h = y1 - y0
    if w <= 0 or h <= 0: return
    diag_len = w + h
    band_w   = int(diag_len * 0.18)
    sweep_p  = (t % period) / period
    lead = int(sweep_p * (diag_len + band_w * 2)) - band_w
    d = ImageDraw.Draw(layer)
    for offset in range(band_w):
        alpha = int(alpha_max * card_p * math.sin(math.pi * offset / max(1, band_w - 1)))
        if alpha <= 0: continue
        dp = lead + offset
        if direction == +1:
            xa = x0 + max(0, dp - h); xb = x0 + min(w, dp)
            if xa >= xb: continue
            ya = y0 + dp - (xa - x0); yb = y0 + dp - (xb - x0)
        else:
            xa = x1 - min(w, dp); xb = x1 - max(0, dp - h)
            if xa >= xb: continue
            ya = y0 + dp - (x1 - xa); yb = y0 + dp - (x1 - xb)
        xa=int(max(x0,min(x1,xa))); xb=int(max(x0,min(x1,xb)))
        ya=int(max(y0,min(y1,ya))); yb=int(max(y0,min(y1,yb)))
        if xa < xb:
            d.line([(xa,ya),(xb,yb)], fill=(255,255,255,alpha), width=2)

# ═══════════════════════════════════════════════════════════════════════════════
# GLASS MORPHISM BORDER
# ═══════════════════════════════════════════════════════════════════════════════
def _draw_glass_border(draw, cx0, cy0, cx1, cy1, radius, accent, t, card_p):
    ar, ag, ab = accent
    bright = (min(255,ar+130), min(255,ag+130), min(255,ab+130))
    layers = [(20,0.06),(14,0.12),(9,0.20),(5,0.32),(2,0.52),(1,0.78)]
    for extra, alpha_mul in layers:
        a = int(180 * card_p * alpha_mul)
        if a > 0:
            safe_rounded_rect(draw,
                [cx0-extra//2,cy0-extra//2,cx1+extra//2,cy1+extra//2],
                radius+extra//2, outline=(ar,ag,ab,a), width=2+extra//3)
    safe_rounded_rect(draw,[cx0+1,cy0+1,cx1-1,cy1-1],radius-1,
                      outline=(255,255,255,int(55*card_p)),width=1)
    safe_rounded_rect(draw,[cx0+2,cy0+2,cx1-2,cy1-2],radius-2,
                      outline=(ar,ag,ab,int(40*card_p)),width=1)
    top_w=cx1-cx0; side_h=cy1-cy0; perimeter=2*(top_w+side_h)
    for period,direction,seg_frac,glow_layers,base_alpha in [
        (3.2,+1,0.16,[(14,12),(9,28),(5,65),(2,180)], card_p),
        (2.6,-1,0.10,[(8,8),(5,20),(3,50),(1,120)],   card_p*0.6),
    ]:
        prog_t=(t%period)/period; pos=int(prog_t*perimeter)
        if direction==-1: pos=(perimeter-pos)%perimeter
        seg_len=int(perimeter*seg_frac)
        for gw,ga in glow_layers:
            color=bright+(int(ga*base_alpha),)
            _draw_segment_on_rect(draw,cx0,cy0,cx1,cy1,top_w,side_h,pos,seg_len,color,gw)

def _draw_segment_on_rect(draw,x0,y0,x1,y1,top_w,side_h,pos,seg_len,color,width):
    perimeter=2*(top_w+side_h)
    for dp in range(0,seg_len,3):
        p=(pos+dp)%perimeter
        pt=_perimeter_point(x0,y0,x1,y1,top_w,side_h,p)
        pt2=_perimeter_point(x0,y0,x1,y1,top_w,side_h,(p+3)%perimeter)
        try: draw.line([pt,pt2],fill=color,width=width)
        except: pass

def _perimeter_point(x0,y0,x1,y1,tw,sh,pos):
    if pos<tw: return(x0+pos,y0)
    pos-=tw
    if pos<sh: return(x1,y0+pos)
    pos-=sh
    if pos<tw: return(x1-pos,y1)
    pos-=tw
    return(x0,y1-pos)

# ═══════════════════════════════════════════════════════════════════════════════
# PARTICLES
# ═══════════════════════════════════════════════════════════════════════════════
def _draw_star(draw, cx, cy, r, color):
    pts = []
    for i in range(10):
        angle = math.pi/2 + i * math.pi/5
        radius = r if i % 2 == 0 else r*0.45
        pts.append((cx + radius*math.cos(angle), cy - radius*math.sin(angle)))
    try: draw.polygon(pts, fill=color)
    except: pass

class ParticleSystem:
    def __init__(self, n=80, accent=(200,180,50)):
        self.accent = accent
        self.particles = [{
            "x":     random.uniform(0, W),
            "y":     random.uniform(0, H),
            "vy":    random.uniform(-0.5, -1.4),
            "vx":    random.uniform(-0.4, 0.4),
            "size":  random.uniform(2.5, 7.0),
            "alpha": random.uniform(20, 80),
            "phase": random.uniform(0, math.pi*2),
            "star":  random.random() < 0.25,
            "glow":  random.random() < 0.30,
        } for _ in range(n)]

    def draw(self, canvas, t):
        layer = Image.new("RGBA", (W,H), (0,0,0,0))
        ld = ImageDraw.Draw(layer)
        r, g, b = self.accent
        for p in self.particles:
            x = (p["x"] + p["vx"]*t*60) % W
            y = (p["y"] + p["vy"]*t*60) % H
            a = max(0, min(255, int(p["alpha"] * (0.5+0.5*math.sin(t*1.8+p["phase"])))))
            s = p["size"]
            if p["glow"] and a > 30:
                for gr, ga in [(s*3, a//8), (s*2, a//4)]:
                    ld.ellipse([x-gr,y-gr,x+gr,y+gr], fill=(r,g,b,ga))
            if p["star"]:
                _draw_star(ld, x, y, s, (r,g,b,a))
            else:
                ld.ellipse([x-s,y-s,x+s,y+s], fill=(r,g,b,a))
        return Image.alpha_composite(canvas.convert("RGBA"), layer).convert("RGB")

# ═══════════════════════════════════════════════════════════════════════════════
# TEXT HELPERS
# ═══════════════════════════════════════════════════════════════════════════════
def _draw_text_shadow(draw, pos, text, font, color, shadow_offset=2):
    sx,sy=pos[0]+shadow_offset, pos[1]+shadow_offset
    draw.text((sx+1,sy+1),text,font=font,fill=(0,0,0,70))
    draw.text((sx,sy),text,font=font,fill=(0,0,0,140))
    draw.text(pos,text,font=font,fill=color)

def _draw_gradient_text(base_img, pos, text, font, color_top, color_bot, alpha=255):
    tmp_draw=ImageDraw.Draw(base_img)
    bbox=tmp_draw.textbbox(pos,text,font=font)
    tw=max(1,bbox[2]-bbox[0]); th=max(1,bbox[3]-bbox[1])
    tl=Image.new("RGBA",(tw+4,th+4),(0,0,0,0))
    td=ImageDraw.Draw(tl)
    td.text((2,2),text,font=font,fill=(255,255,255,255))
    grad=Image.new("RGBA",(tw+4,th+4),(0,0,0,0))
    gd=ImageDraw.Draw(grad)
    for row in range(th+4):
        tr=row/max(1,th+3)
        rc=int(color_top[0]+(color_bot[0]-color_top[0])*tr)
        gc=int(color_top[1]+(color_bot[1]-color_top[1])*tr)
        bc=int(color_top[2]+(color_bot[2]-color_top[2])*tr)
        gd.rectangle([0,row,tw+4,row+1],fill=(rc,gc,bc,alpha))
    colored=Image.composite(grad,Image.new("RGBA",grad.size,(0,0,0,0)),tl)
    sh=Image.new("RGBA",base_img.size,(0,0,0,0))
    sd=ImageDraw.Draw(sh)
    sd.text((pos[0]+2,pos[1]+2),text,font=font,fill=(0,0,0,int(55*alpha/255)))
    base_img.paste(sh,(0,0),sh)
    # ── FIX: crop to canvas bounds before pasting — prevents right-edge bleed ──
    paste_x, paste_y = pos[0]-2, pos[1]-2
    crop_x2 = min(tw+4, base_img.width  - paste_x)
    crop_y2 = min(th+4, base_img.height - paste_y)
    if crop_x2 > 0 and crop_y2 > 0:
        colored = colored.crop((0, 0, crop_x2, crop_y2))
        base_img.paste(colored,(paste_x, paste_y), colored)

def _draw_pill_badge(draw, x, y, text, font, bg_color, text_color, alpha=255):
    bbox=draw.textbbox((0,0),text,font=font)
    tw,th=bbox[2]-bbox[0],bbox[3]-bbox[1]
    px,py=16,9
    bx1=x+tw+px*2; by1=y+th+py*2
    r,g,b=bg_color
    safe_rounded_rect(draw,[x,y,bx1,by1],(by1-y)//2,fill=(r,g,b,alpha))
    safe_rounded_rect(draw,[x+1,y+1,bx1-1,y+(by1-y)//2],(by1-y)//2,
                      fill=(255,255,255,int(28*alpha/255)))
    tr,tg,tb=text_color
    draw.text((x+px,y+py),text,font=font,fill=(tr,tg,tb,alpha))
    return bx1+10

def _draw_animated_badge(draw, x, y, text, font, bg_color, text_color, t, badge_p):
    scale = ease_out_elastic(badge_p)
    pulse = 1.0 + 0.04*math.sin(t*5.5)
    effective = scale * pulse
    alpha = int(255 * min(1.0, badge_p*1.5))
    if alpha < 5: return x
    bbox = draw.textbbox((0,0), text, font=font)
    tw,th = bbox[2]-bbox[0], bbox[3]-bbox[1]
    px,py = 18, 10
    bw = tw+px*2; bh = th+py*2
    cx = x + bw//2; cy = y + bh//2
    sx0 = int(cx - bw/2*effective); sx1 = int(cx + bw/2*effective)
    sy0 = int(cy - bh/2*effective); sy1 = int(cy + bh/2*effective)
    r,g,b = bg_color
    safe_rounded_rect(draw,[sx0,sy0,sx1,sy1],(sy1-sy0)//2,fill=(r,g,b,alpha))
    safe_rounded_rect(draw,[sx0+1,sy0+1,sx1-1,sy0+(sy1-sy0)//2],
                      (sy1-sy0)//2, fill=(255,255,255,int(35*alpha/255)))
    glow_a = int(100 * math.sin(t*5.5)**2 * alpha/255)
    if glow_a > 5:
        safe_rounded_rect(draw,[sx0-3,sy0-3,sx1+3,sy1+3],
                          (sy1-sy0)//2+3, outline=(r,g,b,glow_a), width=3)
    tr,tg,tb = text_color
    draw.text((sx0+px,sy0+py), text, font=font, fill=(tr,tg,tb,alpha))
    return sx1 + 12

# ═══════════════════════════════════════════════════════════════════════════════
# TYPEWRITER EFFECT
# ═══════════════════════════════════════════════════════════════════════════════
def _typewriter_text(full_text, t, start_t, chars_per_sec=55):
    elapsed = max(0.0, t - start_t)
    n_visible = int(elapsed * chars_per_sec)
    return full_text[:n_visible]

# ═══════════════════════════════════════════════════════════════════════════════
# CHANNEL BANNER
# ═══════════════════════════════════════════════════════════════════════════════
def _draw_channel_banner(frame, cx0, cy0_card, cy1, cx1,
                          logo, accent, t, alpha, card_p):
    if alpha <= 0: return
    ar,ag,ab=accent
    bright=(min(255,ar+130),min(255,ag+130),min(255,ab+130))
    bx0=cx0; bx1=cx1
    by0=cy1-BANNER_H-12; by1=cy1-12
    if by0>=by1-4: return
    inner_pad_x=44; inner_pad_y=18

    bl=Image.new("RGBA",(W,H),(0,0,0,0))
    bd=ImageDraw.Draw(bl)
    safe_rounded_rect(bd,[bx0,by0,bx1,by1],20,fill=(0,0,0,int(145*card_p*alpha/255)))
    safe_rounded_rect(bd,[bx0,by0,bx1,by1],20,fill=(ar,ag,ab,int(22*card_p*alpha/255)))
    for i in range(30):
        a=int(35*(1-i/30)*card_p*(alpha/255))
        if a>0:
            safe_rounded_rect(bd,[bx0+2,by0+i,bx1-2,by0+i+1],
                              20 if i<20 else 0,fill=(255,255,255,a))
    frame.alpha_composite(bl)
    draw=ImageDraw.Draw(frame)

    div_layers=[(12,10),(8,22),(4,55),(2,110),(1,int(180*alpha/255))]
    for lw,la in div_layers:
        safe_line(draw,[(bx0+CARD_RADIUS,by0),(bx1-CARD_RADIUS,by0)],
                  fill=bright+(la,),width=lw)

    sw1=Image.new("RGBA",(W,H),(0,0,0,0))
    _diagonal_shimmer(sw1,bx0,by0,bx1,by1,t,4.0,+1,22,card_p*(alpha/255))
    frame.alpha_composite(sw1)
    sw2=Image.new("RGBA",(W,H),(0,0,0,0))
    _diagonal_shimmer(sw2,bx0,by0,bx1,by1,t,5.5,-1,16,card_p*(alpha/255))
    frame.alpha_composite(sw2)

    draw=ImageDraw.Draw(frame)
    logo_cx=bx0+inner_pad_x+28; logo_cy=(by0+by1)//2; logo_r=32
    pulse=0.65+0.35*math.sin(t*2.2)
    for ring_r,ring_a in[(logo_r+12,10),(logo_r+7,24),(logo_r+3,50)]:
        draw.ellipse([logo_cx-ring_r,logo_cy-ring_r,logo_cx+ring_r,logo_cy+ring_r],
                     outline=bright+(int(ring_a*pulse*alpha/255),),width=2)
    draw.ellipse([logo_cx-logo_r,logo_cy-logo_r,logo_cx+logo_r,logo_cy+logo_r],
                 fill=(ar,ag,ab,int(210*alpha/255)))
    if logo is not None:
        lr,lg,lb,la_ch=logo.convert("RGBA").split()
        la_ch=la_ch.point(lambda x:int(x*alpha/255))
        lf=Image.merge("RGBA",(lr,lg,lb,la_ch))
        lw2,lh2=lf.size
        frame.paste(lf,(logo_cx-lw2//2,logo_cy-lh2//2),lf)
        draw=ImageDraw.Draw(frame)
    else:
        init_font=_font(34,bold=True,serif=True)
        init=CHANNEL_NAME[0].upper()
        ib=draw.textbbox((0,0),init,font=init_font)
        draw.text((logo_cx-(ib[2]-ib[0])//2,logo_cy-(ib[3]-ib[1])//2-2),
                  init,font=init_font,fill=(10,10,10,int(230*alpha/255)))

    sub_font=_font(26,bold=True)
    sub_text="SUBSCRIBE"
    sub_b=ImageDraw.Draw(frame).textbbox((0,0),sub_text,font=sub_font)
    sub_w_approx=sub_b[2]-sub_b[0]
    right_reserve=sub_w_approx+inner_pad_x+24
    text_x=logo_cx+logo_r+20
    text_max_w=bx1-text_x-right_reserve
    name_font,_=_fit_font([CHANNEL_NAME],text_max_w,max_size=42,min_size=18,bold=True,serif=True)
    handle_font=_font(28,bold=False,serif=False)
    name_h=name_font.size+4; handle_h=handle_font.size+4
    total_h=name_h+handle_h+8
    name_y=(by0+by1)//2-total_h//2; handle_y=name_y+name_h+8

    # ── FIX: pure white channel name — always visible on dark banner ──
    _draw_gradient_text(frame,(text_x,name_y),CHANNEL_NAME,name_font,
                        (255,255,255),(220,220,220),alpha=alpha)
    draw=ImageDraw.Draw(frame)
    # ── FIX: bright handle colour — no longer dim accent-derived ──
    _draw_text_shadow(draw,(text_x,handle_y),CHANNEL_HANDLE,handle_font,
                      (210,210,210,alpha),shadow_offset=1)

    mid_y=(by0+by1)//2
    sub_x=bx1-sub_w_approx-inner_pad_x
    dot_pulse=0.5+0.5*math.sin(t*3.8)
    dot_r=7; dot_cx=sub_x+sub_w_approx//2; dot_cy=mid_y-22
    for gr,ga in[(dot_r+7,10),(dot_r+3,26)]:
        draw.ellipse([dot_cx-gr,dot_cy-gr,dot_cx+gr,dot_cy+gr],
                     outline=bright+(int(ga*dot_pulse*alpha/255),),width=2)
    draw.ellipse([dot_cx-dot_r,dot_cy-dot_r,dot_cx+dot_r,dot_cy+dot_r],
                 fill=bright+(int(220*dot_pulse*alpha/255),))
    draw.text((sub_x+1,mid_y-4),sub_text,font=sub_font,fill=(0,0,0,int(alpha*0.5)))
    draw.text((sub_x,mid_y-5),sub_text,font=sub_font,fill=bright+(alpha,))

# ═══════════════════════════════════════════════════════════════════════════════
# GLASS CARD
# ═══════════════════════════════════════════════════════════════════════════════
def _draw_glass_card(card_layer, cx0, cy0, cx1, cy1, card_color, accent, card_p):
    cd=ImageDraw.Draw(card_layer)
    cr,cg,cb=card_color; ar,ag,ab=accent
    safe_rounded_rect(cd,[cx0,cy0,cx1,cy1],CARD_RADIUS,fill=(cr,cg,cb,int(210*card_p)))
    safe_rounded_rect(cd,[cx0,cy0,cx1,cy1],CARD_RADIUS,fill=(255,255,255,int(12*card_p)))
    safe_rounded_rect(cd,[cx0,cy0,cx1,cy1],CARD_RADIUS,fill=(ar,ag,ab,int(28*card_p)))
    highlight_h=80
    for i in range(highlight_h):
        a=int(55*(1-i/highlight_h)**2*card_p)
        if a<=0: continue
        safe_rounded_rect(cd,[cx0+2,cy0+i,cx1-2,cy0+i+1],
                          CARD_RADIUS if i<CARD_RADIUS else 0,fill=(255,255,255,a))

# ═══════════════════════════════════════════════════════════════════════════════
# CTA PULSE
# ═══════════════════════════════════════════════════════════════════════════════
def _draw_cta_pulse(frame, t, accent, show_after=8.0):
    if t < show_after: return
    ar, ag, ab = accent
    cta_p = clamp01((t - show_after) / 1.2)
    alpha = int(255 * ease_out_cubic(cta_p))
    if alpha < 10: return
    pulse = 0.75 + 0.25 * abs(math.sin(t * math.pi * 1.5))
    alpha = int(alpha * pulse)
    font = _font(38, bold=True, serif=False)
    text = "↑  रोज़ की ख़बरों के लिए Subscribe करें  ↑"
    dummy = Image.new("RGB",(1,1))
    dd = ImageDraw.Draw(dummy)
    bb = dd.textbbox((0,0), text, font=font)
    tw = bb[2]-bb[0]
    tx = (W - tw) // 2
    ty = H - 55
    draw = ImageDraw.Draw(frame)
    draw.text((tx+2, ty+2), text, font=font, fill=(0,0,0,int(alpha*0.5)))
    draw.text((tx, ty), text, font=font,
              fill=(min(255,ar+80), min(255,ag+80), min(255,ab+80), alpha))

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN FRAME BUILDER
# ═══════════════════════════════════════════════════════════════════════════════
def _build_frame(t, bg_base, full_bleed, story, theme, particles,
                 logo, title_lines, body_lines, category, hook_text,
                 stat_text, full_summary):

    if t < T_HOOK_END:
        return _build_hook_frame(t, full_bleed, hook_text, theme["accent"], particles)

    accent      = theme["accent"]
    title_color = theme["title"]
    body_color  = theme["body"]
    card_color  = theme["card"]
    ar, ag, ab  = accent

    frame = _composite_bg(*bg_base, t/DURATION)
    frame = frame.convert("RGBA")
    frame = Image.alpha_composite(frame, _make_vignette())

    cx0=PAD; cx1=W-PAD; cy1=H-32
    cy_full=int(H*CARD_TOP_RATIO)
    card_p=ease_out_back(clamp01(progress(t,T_CARD_IN,T_CARD_IN+0.55)),1.15)
    cy0=int(cy_full+(H-cy_full)*(1-card_p))
    cy0=min(cy0,cy1-120)
    if cy0>=cy1-4:
        frame=particles.draw(frame.convert("RGB"),t).convert("RGBA")
        _draw_progress_bar(frame,t,accent)
        return np.array(frame.convert("RGB"))

    card_layer=Image.new("RGBA",(W,H),(0,0,0,0))
    _draw_glass_card(card_layer,cx0,cy0,cx1,cy1,card_color,accent,card_p)
    _diagonal_shimmer(card_layer,cx0,cy0,cx1,cy1,t,4.2,+1,16,card_p)
    _diagonal_shimmer(card_layer,cx0,cy0,cx1,cy1,t,6.1,-1,10,card_p)
    frame=Image.alpha_composite(frame,card_layer)
    draw=ImageDraw.Draw(frame)

    _draw_glass_border(draw,cx0,cy0,cx1,cy1,CARD_RADIUS,accent,t,card_p)

    inner_x=cx0+40; inner_w=(cx1-cx0)-80
    y=cy0+60; max_y=cy1-BANNER_H-38

    # ── Animated category badge ──
    badge_p=ease_out_elastic(clamp01(progress(t,T_BADGE_IN,0.6)))
    if badge_p>0 and y+44<max_y:
        bf=_font(26,bold=True,serif=False)
        bright_acc=(min(255,ar+60),min(255,ag+60),min(255,ab+60))
        nx=_draw_animated_badge(draw,inner_x,y,category,bf,bright_acc,(10,10,10),t,badge_p)
        src_raw=(story.get("source","") or "News")
        src=src_raw[:22] if len(src_raw)<=22 else src_raw[:20].rsplit(" ",1)[0]
        badge_a=int(255*badge_p)
        if nx+120<cx1-PAD:
            nx=_draw_pill_badge(draw,nx,y,src,bf,(255,255,255),(20,20,20),int(badge_a*0.85))
        wc=len(" ".join(body_lines).split())
        if nx+90<cx1-PAD:
            _draw_pill_badge(draw,nx,y,f"{max(1,wc//30)} MIN",bf,(60,60,60),body_color,int(badge_a*0.75))
        y+=58

    # ── Stat callout ──
    stat_p=ease_out_cubic(clamp01(progress(t,T_BADGE_IN+0.2,0.5)))
    stat_alpha=int(255*stat_p)
    if stat_text and stat_alpha>5:
        y=_draw_stat_callout(frame,inner_x,y,inner_w,stat_text,accent,t,stat_alpha)
        # FIX: removed y+=8 extra padding — _draw_stat_callout already includes +18 gap
    draw=ImageDraw.Draw(frame)

    # ── Title — dynamic font size fits all lines vertically AND horizontally ──
    # FIX: title_max_y reserves just enough space for divider + at least 1 body line.
    # The old -120 guard was double-penalising (max_y already excludes the banner).
    title_body_reserve = 28 + 52  # divider height + one body line minimum
    title_max_y = max_y - title_body_reserve
    title_p=ease_out_cubic(clamp01(progress(t,T_TITLE_IN,0.55)))
    title_alpha=int(255*title_p)
    title_slide=int(36*(1-title_p))
    dummy_d = ImageDraw.Draw(Image.new("RGB",(1,1)))
    for attempt_size in range(78, 24, -2):
        title_font = _font(attempt_size, bold=True, serif=True)
        total_title_h = sum(
            dummy_d.textbbox((0,0),l,font=title_font)[3] -
            dummy_d.textbbox((0,0),l,font=title_font)[1] + 28
            for l in title_lines[:4]
        )
        fits_w = all(
            dummy_d.textbbox((0,0),l,font=title_font)[2] -
            dummy_d.textbbox((0,0),l,font=title_font)[0] <= inner_w
            for l in title_lines[:4]
        )
        if fits_w and y + total_title_h <= title_max_y:
            break
    for line in title_lines[:4]:
        bbox=ImageDraw.Draw(frame).textbbox((0,0),line,font=title_font)
        line_h=bbox[3]-bbox[1]; line_top=bbox[1]
        if y + line_h + 8 > title_max_y: break
        bright_top=tuple(min(255,c+80) for c in title_color)
        bright_bot=tuple(min(255,c+30) for c in title_color)
        _draw_gradient_text(frame,(inner_x+title_slide,y-line_top),line,
                            title_font,bright_top,bright_bot,alpha=title_alpha)
        y+=line_h+28
    y+=20
    draw=ImageDraw.Draw(frame)

    # ── Divider ──
    div_p=ease_out_cubic(clamp01(progress(t,T_DIV_IN,0.4)))
    div_max_w=int(inner_w*0.42); div_w=int(div_max_w*div_p)
    if div_w>2 and y+8<max_y:
        safe_line(draw,[(inner_x,y+4),(inner_x+div_w,y+4)],fill=(0,0,0,int(110*div_p)),width=3)
        safe_line(draw,[(inner_x,y),(inner_x+div_w,y)],fill=accent+(int(240*div_p),),width=3)
        for i in range(min(70,div_w)):
            a=int(155*(1-i/min(70,div_w))*div_p)
            if a: safe_line(draw,[(inner_x+div_w+i,y),(inner_x+div_w+i+1,y)],fill=(ar,ag,ab,a),width=2)
    y+=28

    # ── Body text (typewriter effect) ──
    body_font=_font(43,bold=False,serif=False)
    chars_per_line=max(20,inner_w//24)
    chars_visible = int(max(0, t - T_BODY_IN) * 55)
    body_lines_full=textwrap.wrap(full_summary,width=chars_per_line)[:8]
    chars_drawn=0
    for i,line in enumerate(body_lines_full):
        lp=ease_out_cubic(clamp01(progress(t,T_BODY_IN+i*0.05,0.35)))
        la=int(255*lp); ls=int(16*(1-lp))
        if y+52>max_y:
            if la: draw.text((inner_x,y),"…",font=body_font,fill=body_color+(la,))
            break
        chars_in_line=len(line)
        if chars_drawn >= chars_visible:
            break
        visible_in_line=max(0, chars_visible-chars_drawn)
        display_line=line[:visible_in_line]
        chars_drawn+=chars_in_line+1
        if display_line:
            _draw_text_shadow(draw,(inner_x+ls,y),display_line,
                              body_font,body_color+(la,),shadow_offset=2)
            if visible_in_line<chars_in_line:
                cursor_on=int(t*4)%2==0
                if cursor_on:
                    cb_bbox=draw.textbbox((inner_x,y),display_line,font=body_font)
                    cx_pos=cb_bbox[2]+4
                    draw.rectangle([cx_pos,y+4,cx_pos+3,y+44], fill=accent+(200,))
        y+=52

    # ── Channel banner ──
    banner_p=ease_out_cubic(clamp01(progress(t,T_BANNER_IN,0.5)))
    _draw_channel_banner(frame,cx0,cy0,cy1,cx1,logo,accent,t,
                          alpha=int(255*banner_p),card_p=card_p)

    # ── CTA pulse ──
    _draw_cta_pulse(frame,t,accent,show_after=8.0)

    # ── Particles ──
    frame=particles.draw(frame.convert("RGB"),t).convert("RGBA")

    # ── Progress bar ──
    _draw_progress_bar(frame,t,accent)

    return np.array(frame.convert("RGB"))

# ═══════════════════════════════════════════════════════════════════════════════
# HOOK TEXT GENERATOR
# ═══════════════════════════════════════════════════════════════════════════════
HOOK_PREFIXES = [
    "ब्रेकिंग:", "अभी-अभी:", "क्या आप जानते हैं?", "चौंकाने वाला:",
    "जरूर देखें:", "वायरल:", "ट्रेंडिंग:", "अलर्ट:",
]

def _generate_hook(title, category):
    # Devanagari has no uppercase — use as-is; replace underscores for display
    cat_display = category.replace("_", " ")
    stat = _extract_stat(title)
    if stat:
        return f"{stat} — {cat_display}"
    prefix = random.choice(HOOK_PREFIXES)
    words = title.split()[:6]
    return f"{prefix}\n{' '.join(words)}…"

# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════════════════════
def build_video(story, music_path=None):
    print(f"    [builder] assembling video…")
    img_url=story.get("img_url","")
    if not img_url or img_url in ("None",""):
        print("    [builder] no image URL — skipping"); return None
    img=_download_image(img_url)
    if img is None:
        print("    [builder] image unavailable — skipping"); return None
    try:
        theme=extract_palette(img)
        print(f"    [builder] palette accent={theme['accent']}")
    except Exception:
        theme=random.choice(FALLBACK_THEMES)
        print(f"    [builder] fallback theme accent={theme['accent']}")

    bg_layers=_prepare_bg_layers(img)
    iw,ih=img.size
    scale=max(W/iw,H/ih)*1.06
    nw,nh=int(iw*scale),int(ih*scale)
    full_bleed=img.resize((nw,nh),Image.LANCZOS)
    full_bleed=full_bleed.crop(((nw-W)//2,(nh-H)//2,(nw-W)//2+W,(nh-H)//2+H))

    particles=ParticleSystem(n=80,accent=theme["accent"])
    logo=_load_channel_pfp()
    category=story.get("category","BREAKING").upper()
    full_summary=story.get("summary","")
    title=story["title"]

    title_lines=textwrap.wrap(title,width=20)[:4]  # No .upper() — Devanagari has no uppercase
    body_lines=textwrap.wrap(full_summary,width=34)[:8]
    hook_text=_generate_hook(title,category)
    stat_text=_extract_stat(title)

    print(f"    [builder] hook='{hook_text[:40]}'")
    print(f"    [builder] stat callout={stat_text!r}")
    print(f"    [builder] pre-rendering {DURATION*FPS} frames…")

    frames=[]
    for fi in range(DURATION*FPS):
        frame=_build_frame(
            fi/FPS, bg_layers, full_bleed, story, theme,
            particles, logo, title_lines, body_lines,
            category, hook_text, stat_text, full_summary)
        frames.append(frame)

    def make_frame(t):
        return frames[min(int(t*FPS),len(frames)-1)]

    comp=VideoClip(make_frame,duration=DURATION)

    if music_path and os.path.exists(music_path):
        try:
            audio=AudioFileClip(music_path).subclip(0,DURATION)
            audio=audio.audio_fadein(0.5).audio_fadeout(3).volumex(0.28)
            comp=comp.set_audio(audio)
        except Exception as e:
            print(f"    [builder] audio error: {e}")

    out=OUT_DIR/f"{story['id']}_{int(time.time())}.mp4"
    try:
        comp.write_videofile(str(out),fps=FPS,codec="libx264",
                             audio_codec="aac",bitrate="6000k",
                             preset="fast",verbose=False,logger=None)
        print(f"    [builder] exported → {out.name}")
        return str(out)
    except Exception as e:
        print(f"    [builder] export error: {e}")
        import traceback; traceback.print_exc()
        return None