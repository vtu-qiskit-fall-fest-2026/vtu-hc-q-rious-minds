"""Cinematic CarbonWise campus-energy explainer MP4.

Uses bundled cinematic campus artwork, drone-like pan/zoom, animated energy
flows, simulated battery SOC, grid-import comparison and the local QAOA result.
Energy data are illustrative unless verified campus measurements are provided.
"""
from __future__ import annotations
from pathlib import Path
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps
import imageio.v2 as imageio

ROOT = Path(__file__).resolve().parent
ASSET_PATH = ROOT / "static" / "images" / "carbonwise_cinematic_storyboard.png"
OUTPUT_PATH = ROOT / "static" / "generated" / "CarbonWise_VTU_Belagavi_Demo.mp4"
W, H, FPS = 1280, 720, 12
SCENE_CROPS = {
    "campus": (0, 18, 545, 250),
    "solar": (558, 30, 895, 258),
    "storage": (1110, 100, 1480, 260),
    "battery": (300, 325, 545, 615),
    "evening": (555, 340, 870, 540),
    "outro": (1105, 625, 1670, 940),
}
BG = (5, 15, 29)
MINT = (66, 245, 190)
GREEN = (80, 230, 118)
CYAN = (67, 213, 255)
GOLD = (255, 202, 75)
PURPLE = (177, 132, 255)
WHITE = (240, 247, 255)
MUTED = (184, 204, 222)
CORAL = (255, 119, 112)


def _font(size, bold=False):
    candidates = []
    if bold:
        candidates += ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                       "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
                       "C:/Windows/Fonts/seguisb.ttf", "C:/Windows/Fonts/arialbd.ttf"]
    else:
        candidates += ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                       "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
                       "C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf"]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            pass
    return ImageFont.load_default()

F = {"tiny": _font(15), "small": _font(18), "body": _font(21),
     "subtitle": _font(24), "heading": _font(32, True),
     "title": _font(47, True), "metric": _font(42, True),
     "bold": _font(22, True), "medium_bold": _font(26, True)}


def _lerp(a, b, t):
    return a + (b-a) * max(0.0, min(1.0, t))


def _draw_wrapped(draw, text, xy, font, fill, max_width, gap=3):
    words, lines, current = text.split(), [], ""
    for word in words:
        test = (current + " " + word).strip()
        if draw.textbbox((0, 0), test, font=font)[2] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    x, y = xy
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        y += getattr(font, "size", 18) + gap


def _point_on_path(points, t):
    u = max(0.0, min(0.999999, t)) * (len(points)-1)
    i, f = int(u), u-int(u)
    x1, y1 = points[i]
    x2, y2 = points[i+1]
    return int(_lerp(x1, x2, f)), int(_lerp(y1, y2, f))


def _photo_background(source, crop_box, progress, nighttime=False):
    crop = source.crop(crop_box)
    base = ImageOps.fit(crop, (W, H), method=Image.Resampling.LANCZOS,
                        centering=(0.48 + 0.04*progress, 0.48 + 0.025*math.sin(progress*math.pi)))
    zoom = 1.01 + 0.095*progress
    zw, zh = int(W*zoom), int(H*zoom)
    big = base.resize((zw, zh), Image.Resampling.LANCZOS)
    left = int((zw-W)*(0.38 + 0.24*progress))
    top = int((zh-H)*(0.6 - 0.25*progress))
    bg = big.crop((left, top, left+W, top+H)).convert("RGBA")
    tint = Image.new("RGBA", (W, H), (2, 10, 22, 48 if not nighttime else 92))
    bg = Image.alpha_composite(bg, tint)
    if nighttime:
        bg = Image.alpha_composite(bg, Image.new("RGBA", (W,H), (4,15,40,42)))
    shade = Image.new("RGBA", (W,H), (0,0,0,0))
    sd = ImageDraw.Draw(shade)
    sd.rectangle((0, 0, 650, H), fill=(2,10,22,28))
    sd.rectangle((0, H-105, W, H), fill=(2,10,22,105))
    return Image.alpha_composite(bg, shade).convert("RGB")


def _simulated_soc(data, p):
    values = np.asarray(data.get("battery", [35,50,70,85,75,55]), dtype=float)
    if values.size == 0:
        return int(35 + 45*p)
    u = p*(len(values)-1)
    i = int(u); j = min(i+1, len(values)-1)
    return int(np.clip(_lerp(values[i], values[j], u-i), 0, 100))


def _draw_soc_card(d, soc, x, y, width, height, heading):
    d.rounded_rectangle((x,y,x+width,y+height), radius=22, fill=(3,17,31,230), outline=(*MINT,190), width=2)
    d.text((x+24,y+16), heading, font=F["bold"], fill=WHITE)
    bx, by, bw, bh = x+26, y+62, width-52, 24
    d.rounded_rectangle((bx,by,bx+bw,by+bh), radius=10, fill=(22,45,63,255), outline=(85,125,150,200), width=1)
    fw = int((bw-8)*soc/100)
    if fw > 0:
        d.rounded_rectangle((bx+4,by+4,bx+4+fw,by+bh-4), radius=7, fill=(*GREEN,240))
    d.text((bx,by+34), f"{soc}%  SOC", font=F["metric"], fill=MINT)
    d.text((bx,by+83), "Illustrative state of charge • simulated", font=F["tiny"], fill=MUTED)


def _draw_battery_icon(d, x, y, width, height, soc):
    d.rounded_rectangle((x,y,x+width,y+height), radius=20, fill=(3,16,30,225), outline=(*MINT,245), width=4)
    d.rectangle((x+width//3,y-14,x+2*width//3,y+4), fill=(*MINT,235))
    inner=(x+15,y+15,x+width-15,y+height-15)
    d.rounded_rectangle(inner, radius=10, fill=(14,38,51,230), outline=(64,120,140,200), width=1)
    fill_h=int((inner[3]-inner[1]-8)*soc/100)
    d.rounded_rectangle((inner[0]+4,inner[3]-4-fill_h,inner[2]-4,inner[3]-4), radius=6, fill=(*GREEN,230))


def _draw_line_chart(d, data, x, y, width, height, title, progress=1.0):
    d.rounded_rectangle((x,y,x+width,y+height), radius=18, fill=(3,15,28,225), outline=(255,255,255,55), width=1)
    d.text((x+18,y+12), title, font=F["small"], fill=WHITE)
    solar = np.asarray(data.get("solar", []), dtype=float)
    demand = np.asarray(data.get("demand", []), dtype=float)
    if len(solar)<2 or len(demand)<2:
        return
    px, py, pw, ph = x+22, y+48, width-44, height-66
    d.line((px,py+ph,px+pw,py+ph), fill=(255,255,255,65), width=1)
    vmax=max(1.0,float(np.max(solar)),float(np.max(demand)))
    visible=max(2,int(2+(len(solar)-2)*progress))
    for vals,color in [(solar,GOLD),(demand,CYAN)]:
        pts=[]
        for idx,v in enumerate(vals[:visible]):
            pts.append((px+int(idx/(len(vals)-1)*pw), py+ph-int(v/vmax*ph)))
        if len(pts)>1: d.line(pts, fill=(*color,245), width=3)


def _draw_grid_chart(d, data, optimization, x, y, width, height, progress):
    d.rounded_rectangle((x,y,x+width,y+height), radius=20, fill=(3,15,28,232), outline=(*CYAN,155), width=1)
    d.text((x+20,y+15), "GRID IMPORT PROFILE  •  SIMULATED", font=F["small"], fill=WHITE)
    baseline=np.asarray(data.get("grid", []),dtype=float)
    after=baseline.copy()
    if optimization and optimization.get("optimized_grid_profile"):
        candidate=np.asarray(optimization["optimized_grid_profile"],dtype=float)
        if len(candidate)==len(baseline): after=candidate
    if len(baseline)<2: return
    px,py,pw,ph=x+35,y+62,width-60,height-102
    d.line((px,py,px,py+ph),fill=(200,220,240,70),width=1)
    d.line((px,py+ph,px+pw,py+ph),fill=(200,220,240,70),width=1)
    vmax=max(1,float(np.max(baseline)),float(np.max(after)))
    cutoff=max(2,int(1+(len(baseline)-1)*progress))
    for vals,color in [(baseline,CORAL),(after,MINT)]:
        pts=[(px+int(i/(len(vals)-1)*pw),py+ph-int(v/vmax*ph)) for i,v in enumerate(vals[:cutoff])]
        if len(pts)>1: d.line(pts,fill=(*color,245),width=4)
    d.line((x+24,y+height-20,x+58,y+height-20),fill=(*CORAL,255),width=4)
    d.text((x+65,y+height-30),"Baseline",font=F["tiny"],fill=WHITE)
    d.line((x+165,y+height-20,x+199,y+height-20),fill=(*MINT,255),width=4)
    d.text((x+207,y+height-30),"QAOA candidate",font=F["tiny"],fill=WHITE)


def _tech_background(progress, elapsed):
    im=Image.new("RGB",(W,H),BG)
    yy = np.linspace(0.0, 1.0, H, dtype=np.float32)[:, None]
    arr = np.empty((H, W, 3), dtype=np.uint8)
    arr[:, :, 0] = np.broadcast_to((4 + 5*yy).astype(np.uint8), (H, W))
    arr[:, :, 1] = np.broadcast_to((16 + 14*yy).astype(np.uint8), (H, W))
    arr[:, :, 2] = np.broadcast_to((31 + 28*yy).astype(np.uint8), (H, W))
    im = Image.fromarray(arr, mode="RGB")
    d=ImageDraw.Draw(im,"RGBA")
    horizon=365
    for x in range(-400,W+401,60):
        d.line((W//2+(x-W//2)*0.2,horizon,x,H),fill=(45,115,155,58),width=1)
    for k in range(1,12):
        yy=horizon+int((H-horizon)*(k/12)**1.7)
        d.line((0,yy,W,yy),fill=(45,115,155,42),width=1)
    cx,cy=360,390
    for r in [75,115,155]:
        d.ellipse((cx-r,cy-r,cx+r,cy+r),outline=(67,213,255,100),width=2)
    for k in range(6):
        a=elapsed*1.35+k*math.pi/3
        xx=cx+int(115*math.cos(a)); yy=cy+int(65*math.sin(a))
        d.line((cx,cy,xx,yy),fill=(177,132,255,85),width=2)
        d.ellipse((xx-9,yy-9,xx+9,yy+9),fill=(*PURPLE,240),outline=(255,255,255,190),width=1)
    d.ellipse((cx-18,cy-18,cx+18,cy+18),fill=(*CYAN,240))
    d.text((115,600),"QISKIT  •  QAOA  •  LOCAL STATEVECTOR SIMULATION",font=F["tiny"],fill=MUTED)
    return im


def _draw_qaoa_circuit(d, p):
    x0,y0=80,300
    d.rounded_rectangle((48,255,660,590),radius=22,fill=(3,16,32,222),outline=(*PURPLE,155),width=1)
    d.text((80,275),"QAOA CIRCUIT  •  4 BINARY DECISIONS",font=F["small"],fill=WHITE)
    for q in range(4):
        yy=y0+q*64
        d.line((x0,yy,625,yy),fill=(130,175,210,145),width=2)
        d.text((66,yy-12),f"q{q}",font=F["tiny"],fill=MUTED)
        for gi,label in enumerate(["H","COST","RX"]):
            gx=155+gi*145
            d.rounded_rectangle((gx,yy-20,gx+74,yy+20),radius=7,fill=(21,48,78,240),outline=(*[CYAN,PURPLE,MINT][gi],210),width=2)
            d.text((gx+37,yy-10),label,font=F["tiny"],fill=WHITE,anchor="mm")
    xx=int(_lerp(155,590,p))
    d.line((xx,280,xx,500),fill=(66,245,190,110),width=3)


def _draw_qaoa_card(d, optimization, x, y, width, height):
    d.rounded_rectangle((x,y,x+width,y+height),radius=22,fill=(3,16,31,235),outline=(*MINT,180),width=2)
    d.text((x+24,y+18),"OPTIMIZATION RESULT",font=F["bold"],fill=MINT)
    if optimization and optimization.get("success") and optimization.get("qaoa"):
        q=optimization["qaoa"]
        exact=optimization.get("classical_exact",{})
        slots=", ".join(q.get("selected_hours",[])) or "Candidate not available"
        cost=q.get("cost_inr")
        d.text((x+24,y+58),f"Selected discharge slots: {slots}",font=F["small"],fill=WHITE)
        d.text((x+24,y+94),f"Four-slot model cost: ₹{float(cost):,.2f}" if cost is not None else "Four-slot model cost: N/A",font=F["subtitle"],fill=GOLD)
        note = ("Sampled QAOA matched the exact classical optimum for this small instance."
                if optimization.get("qaoa_matches_classical_optimum")
                else "Compared against an exact classical benchmark; no advantage assumed.")
        _draw_wrapped(d,note,(x+24,y+142),F["tiny"],MUTED,width-48,4)
    else:
        d.text((x+24,y+62),"QAOA results unavailable in this video run.",font=F["small"],fill=WHITE)
        d.text((x+24,y+103),"Run the optimizer in the active Python environment first.",font=F["tiny"],fill=MUTED)
    d.text((x+24,y+height-35),"4-slot prototype  •  no quantum advantage claimed",font=F["tiny"],fill=MUTED)


def _render_scene(source, scene_index, p, elapsed, data, optimization, total_seconds):
    crops = ["campus","solar","storage","battery","evening","evening",None,"outro"]
    night = scene_index in (3,4,5)
    bg = _tech_background(p, elapsed) if scene_index == 6 else _photo_background(source, SCENE_CROPS[crops[scene_index]], p, nighttime=night)
    d = ImageDraw.Draw(bg,"RGBA")
    d.rounded_rectangle((34,25,350,69),radius=18,fill=(2,14,26,205),outline=(*MINT,160),width=1)
    d.text((54,35),"CARBON",font=F["bold"],fill=WHITE)
    d.text((143,35),"WISE",font=F["bold"],fill=MINT)
    d.text((220,39),"CAMPUS ENERGY",font=F["tiny"],fill=MUTED)
    d.rounded_rectangle((35,H-25,W-35,H-18),radius=3,fill=(255,255,255,55))
    progress_all = min(1.0,elapsed/total_seconds)
    d.rounded_rectangle((35,H-25,35+int((W-70)*progress_all),H-18),radius=3,fill=(*MINT,230))
    d.text((38,H-55),"AI-GENERATED CAMPUS VISUALS  •  SIMULATED ENERGY DATA  •  NOT LIVE VTU METER DATA",font=F["tiny"],fill=(225,236,246,225))

    titles = [
        ("A CAMPUS. A SMARTER ENERGY PLAN.","Changing solar output. Changing demand. One coordinated schedule."),
        ("01  |  CAPTURE SOLAR ENERGY","Rooftop PV generates clean electricity during daylight hours."),
        ("02  |  STORE THE SURPLUS","Serve campus loads first; store excess solar energy for later."),
        ("03  |  TRACK BATTERY STATE OF CHARGE","Make stored energy visible, not a guess."),
        ("04  |  USE STORED ENERGY AFTER SUNSET","Battery discharge can support demand when solar output falls."),
        ("05  |  MEASURE GRID IMPORT","Compare the baseline with the candidate schedule, hour by hour."),
        ("06  |  QUANTUM-ASSISTED SCHEDULING","A small Qiskit QAOA experiment is benchmarked against exact classical search."),
        ("CARBONWISE","Smarter energy scheduling. A more sustainable campus.")]
    headline, subtitle = titles[scene_index]
    if scene_index != 7:
        d.rounded_rectangle((48,104,625,216),radius=22,fill=(3,14,27,213),outline=(80,230,200,85),width=1)
        d.text((74,123),headline,font=F["medium_bold"],fill=MINT if scene_index in (1,2,6) else WHITE)
        _draw_wrapped(d,subtitle,(74,166),F["small"],MUTED,505,4)
    else:
        d.rounded_rectangle((55,95,1225,405),radius=28,fill=(3,14,27,255),outline=(*MINT,200),width=2)
        d.text((108,142),"CARBON",font=F["title"],fill=WHITE)
        d.text((335,142),"WISE",font=F["title"],fill=MINT)
        d.text((110,215),subtitle,font=F["subtitle"],fill=WHITE)
        d.text((110,267),"Solar when available  •  Store surplus  •  Use it when needed",font=F["small"],fill=MUTED)
        d.text((110,302),"Measure cost  •  Grid imports  •  Solar use  •  Estimated CO₂",font=F["small"],fill=GOLD)

    if scene_index == 0:
        d.rounded_rectangle((910, 34, 1230, 75), radius=15, fill=(2,14,26,205), outline=(255,255,255,60), width=1)
        d.text((930, 45), "AERIAL DRONE-STYLE CONCEPT VIEW", font=F["tiny"], fill=GOLD)
        d.rounded_rectangle((52,488,725,602),radius=22,fill=(2,14,26,211),outline=(255,255,255,60),width=1)
        d.text((82,510),"THE PROBLEM",font=F["bold"],fill=GOLD)
        d.text((82,550),"Solar varies • Demand changes • Grid power costs money",font=F["small"],fill=WHITE)
    elif scene_index == 1:
        path=[(690,330),(770,370),(860,365),(930,420)]
        d.line(path,fill=(255,202,75,70),width=16); d.line(path,fill=(*GOLD,245),width=4)
        for i in range(14):
            pt=_point_on_path(path,(p*1.3+i/14)%1); r=3+(i%3)
            d.ellipse((pt[0]-r-4,pt[1]-r-4,pt[0]+r+4,pt[1]+r+4),fill=(255,202,75,55))
            d.ellipse((pt[0]-r,pt[1]-r,pt[0]+r,pt[1]+r),fill=(*GOLD,230))
        _draw_line_chart(d,data,870,480,350,160,"SOLAR vs CAMPUS DEMAND",p)
    elif scene_index == 2:
        path=[(735,360),(815,390),(890,360),(1000,410)]
        d.line(path,fill=(66,245,190,70),width=16); d.line(path,fill=(*MINT,240),width=4)
        for i in range(16):
            x,y=_point_on_path(path,(p*1.1+i/16)%1)
            d.ellipse((x-6,y-6,x+6,y+6),fill=(*MINT,225))
        _draw_soc_card(d,_simulated_soc(data,p),825,470,385,150,"SURPLUS → BATTERY STORAGE")
    elif scene_index == 3:
        soc=_simulated_soc(data,p)
        _draw_soc_card(d,soc,720,130,475,330,"BATTERY STATE OF CHARGE")
        _draw_battery_icon(d,850,255,185,130,soc)
        d.text((765,500),"Charge level follows the illustrative input series",font=F["tiny"],fill=MUTED)
    elif scene_index == 4:
        path=[(920,440),(830,410),(730,440),(640,410)]
        d.line(path,fill=(66,245,190,70),width=18); d.line(path,fill=(*MINT,245),width=4)
        for i in range(18):
            x,y=_point_on_path(path,(p*1.2+i/18)%1)
            d.ellipse((x-5,y-5,x+5,y+5),fill=(*MINT,225))
        d.rounded_rectangle((745,500,1200,600),radius=20,fill=(4,20,35,220),outline=(*MINT,150),width=1)
        d.text((775,520),"SOLAR LOW → STORED ENERGY CAN SUPPORT LOAD",font=F["small"],fill=MINT)
        d.text((775,557),"Dispatch remains limited by battery capacity and demand.",font=F["tiny"],fill=WHITE)
    elif scene_index == 5:
        _draw_grid_chart(d,data,optimization,690,280,520,310,p)
        d.rounded_rectangle((690,130,1208,238),radius=18,fill=(3,14,27,225),outline=(*CYAN,145),width=1)
        d.text((720,151),"GRID IMPORT: BASELINE vs CANDIDATE",font=F["bold"],fill=CYAN)
        d.text((720,193),"Compare schedules before reporting savings.",font=F["small"],fill=WHITE)
    elif scene_index == 6:
        _draw_qaoa_circuit(d,p); _draw_qaoa_card(d,optimization,720,370,490,235)
    if scene_index not in (0,7):
        d.rounded_rectangle((W-225,30,W-38,72),radius=16,fill=(2,14,26,205),outline=(255,255,255,45),width=1)
        d.text((W-205,41),f"STEP {scene_index:02d} / 06",font=F["small"],fill=GOLD)
    return bg.convert("RGB")


def render_cinematic_video(data: dict, optimization: dict | None, output_path: Path | str = OUTPUT_PATH) -> str:
    """Render the full animated explanation to an MP4 file."""
    if not ASSET_PATH.exists():
        raise FileNotFoundError(f"Required image asset is missing: {ASSET_PATH}")
    source=Image.open(ASSET_PATH).convert("RGB")
    output_path=Path(output_path); output_path.parent.mkdir(parents=True,exist_ok=True)
    durations=[4.5,4.5,4.5,4.5,4.5,5.0,6.0,4.0]
    total_seconds=sum(durations)
    starts=np.cumsum([0.0]+durations[:-1]).tolist()
    total_frames=int(total_seconds*FPS); transition=0.38
    with imageio.get_writer(str(output_path), fps=FPS, codec="libx264",
                            macro_block_size=1,
                            ffmpeg_params=["-preset", "ultrafast", "-crf", "22", "-pix_fmt", "yuv420p", "-movflags", "+faststart"]) as writer:
        for fi in range(total_frames):
            t=fi/FPS
            si=max(i for i,start in enumerate(starts) if start<=t)
            local=t-starts[si]
            p=min(1.0,max(0.0,local/durations[si]))
            frame=_render_scene(source,si,p,t,data,optimization,total_seconds)
            remaining=durations[si]-local
            if si<len(durations)-1 and remaining<transition:
                ni=si+1; npg=min(1.0,max(0.0,(t-starts[ni])/durations[ni]))
                next_frame=_render_scene(source,ni,npg,t,data,optimization,total_seconds)
                frame=Image.blend(frame,next_frame,1.0-remaining/transition)
            if t<0.25:
                frame=Image.blend(Image.new("RGB",(W,H),BG),frame,t/0.25)
            elif t>total_seconds-0.35:
                frame=Image.blend(frame,Image.new("RGB",(W,H),BG),(t-(total_seconds-0.35))/0.35)
            writer.append_data(np.asarray(frame,dtype=np.uint8))
    return str(output_path.resolve())


def generate_video():
    """Flask route entry point: generate video and attempt to include QAOA results."""
    from energy_data import get_energy_data
    data=get_energy_data()
    optimization=None
    try:
        from quantum_optimizer import run_qaoa_optimization
        optimization=run_qaoa_optimization(data)
    except Exception:
        # The explainer remains playable, but does not invent QAOA results.
        optimization=None
    return render_cinematic_video(data,optimization,OUTPUT_PATH)
