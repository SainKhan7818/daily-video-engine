"""Daily Video Engine (FITNESS) — single-file build. Paste into GitHub as dve.py.

Upgrade: every video is now an on-screen WORKOUT GUIDE. The captions show the
day's exercise chart (name + sets x reps) revealed one by one, and the voiceover
reads the chart out. Part 1 = the main lifts, Part 2 = the accessory/finisher.
Footage keywords are derived from the ACTUAL exercises, so clips are relevant and
Part 1 / Part 2 pull different footage.
"""
import os, sys, math, json, glob, random, datetime, subprocess, asyncio, re
import requests, numpy as np
from PIL import Image
import edge_tts

# --- API keys (read from environment / GitHub Secrets) ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "").strip()

# --- Video format ---
WIDTH = 1080
HEIGHT = 1920
FPS = 30

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

TTS_VOICE = "en-US-AndrewMultilingualNeural"
TTS_RATE = "+6%"
TTS_PITCH = "+0Hz"

# ======================================================================
# 7-DAY SPLIT with a real workout chart per part.
# Each exercise: name, sets, reps (display), kw (Pexels search term).
# P1 = main lifts (morning), P2 = accessories/finisher (evening).
# ======================================================================
def E(name, sets, reps, kw):
    return {"name": name, "sets": sets, "reps": reps, "kw": kw}

BODY_PARTS = [
    {
        "key": "chest", "label": "Chest Day", "emoji": "\U0001F4AA",
        "p1": [E("Bench Press", 4, "10", "barbell bench press"),
               E("Incline Dumbbell Press", 3, "12", "incline dumbbell press"),
               E("Weighted Dips", 3, "10", "chest dips gym")],
        "p2": [E("Cable Fly", 3, "15", "cable chest fly"),
               E("Incline Cable Fly", 3, "12", "cable fly gym"),
               E("Push-Ups", 3, "MAX", "push up exercise")],
    },
    {
        "key": "back", "label": "Back Day", "emoji": "\U0001F53B",
        "p1": [E("Deadlift", 4, "6", "deadlift gym"),
               E("Pull-Ups", 3, "10", "pull up bar workout"),
               E("Barbell Row", 3, "10", "barbell row back")],
        "p2": [E("Lat Pulldown", 3, "12", "lat pulldown machine"),
               E("Seated Cable Row", 3, "12", "seated cable row"),
               E("Face Pull", 3, "15", "face pull cable")],
    },
    {
        "key": "legs", "label": "Leg Day", "emoji": "\U0001F9B5",
        "p1": [E("Back Squat", 4, "8", "barbell squat gym"),
               E("Leg Press", 3, "12", "leg press machine"),
               E("Romanian Deadlift", 3, "10", "romanian deadlift")],
        "p2": [E("Walking Lunges", 3, "12", "walking lunges gym"),
               E("Leg Curl", 3, "15", "leg curl machine"),
               E("Calf Raise", 4, "20", "calf raise gym")],
    },
    {
        "key": "shoulders", "label": "Shoulder Day", "emoji": "\U0001F3CB",
        "p1": [E("Overhead Press", 4, "10", "overhead press barbell"),
               E("Lateral Raise", 3, "15", "dumbbell lateral raise"),
               E("Arnold Press", 3, "12", "arnold press dumbbell")],
        "p2": [E("Front Raise", 3, "12", "front raise dumbbell"),
               E("Rear Delt Fly", 3, "15", "rear delt fly"),
               E("Upright Row", 3, "12", "upright row barbell")],
    },
    {
        "key": "arms", "label": "Arm Day", "emoji": "\U0001F4AA",
        "p1": [E("Barbell Curl", 4, "10", "barbell bicep curl"),
               E("Close-Grip Bench", 3, "10", "close grip bench press"),
               E("Hammer Curl", 3, "12", "hammer curl dumbbell")],
        "p2": [E("Tricep Pushdown", 3, "15", "tricep pushdown cable"),
               E("Preacher Curl", 3, "12", "preacher curl"),
               E("Overhead Extension", 3, "12", "overhead tricep extension")],
    },
    {
        "key": "core", "label": "Core Day", "emoji": "\U0001F525",
        "p1": [E("Hanging Leg Raise", 3, "15", "hanging leg raise"),
               E("Cable Crunch", 3, "15", "cable crunch abs"),
               E("Plank", 3, "60s", "plank exercise")],
        "p2": [E("Russian Twist", 3, "20", "russian twist abs"),
               E("Bicycle Crunch", 3, "20", "bicycle crunch"),
               E("Ab Wheel Rollout", 3, "12", "ab wheel rollout")],
    },
    {
        "key": "fullbody", "label": "Full-Body & Cardio", "emoji": "\U000026A1",
        "p1": [E("Clean & Press", 4, "8", "clean and press barbell"),
               E("Kettlebell Swing", 3, "15", "kettlebell swing"),
               E("Goblet Squat", 3, "12", "goblet squat")],
        "p2": [E("Burpees", 3, "15", "burpees workout"),
               E("Mountain Climbers", 3, "30s", "mountain climbers exercise"),
               E("Jump Rope", 3, "60s", "jump rope workout")],
    },
]

BASE_TAGS = ["gym", "fitness", "workout", "gymtok", "fitfam", "bodybuilding",
             "gymmotivation", "fitnessmotivation", "training", "shorts", "reels"]


def todays_bodypart():
    return BODY_PARTS[datetime.date.today().weekday() % len(BODY_PARTS)]


def current_part():
    env = os.environ.get("VIDEO_PART", "").strip()
    if env in ("1", "2"):
        return int(env)
    return 1 if datetime.datetime.utcnow().hour < 11 else 2


def pick_topic():
    bp = todays_bodypart()
    part = current_part()
    exercises = bp["p1"] if part == 1 else bp["p2"]
    print(f"[topics] {bp['label']} | Part {part} | {len(exercises)} exercises")
    return bp, part, exercises


# ======================================================================
# SCRIPT + SEO — the voiceover reads out the chart.
# ======================================================================

def _spoken_reps(sets, reps):
    if reps.upper() == "MAX":
        return f"{sets} sets to failure"
    if reps.endswith("s"):
        return f"{sets} sets of {reps[:-1]} seconds"
    return f"{sets} sets of {reps}"


def _script(bp, part, exercises):
    label = bp["label"]
    lines = []
    if part == 1:
        lines.append(f"It's {label}. Part one, the main lifts.")
    else:
        lines.append(f"{label}, part two. The accessories that finish it off.")
    connectors = ["First up,", "Then,", "After that,", "Next,", "Finish with,"]
    for i, ex in enumerate(exercises):
        c = connectors[min(i, len(connectors) - 1)]
        lines.append(f"{c} {ex['name']}, {_spoken_reps(ex['sets'], ex['reps'])}.")
    if part == 1:
        lines.append("Control every rep and leave one in the tank. "
                     "Part two drops tonight, so follow now and don't miss it.")
    else:
        lines.append("Chase the pump and squeeze at the top. "
                     "New body part tomorrow, hit follow and let's build.")
    return " ".join(lines)


def generate(bp, part, exercises):
    label = bp["label"]
    emoji = bp.get("emoji", "\U0001F4AA")
    script = _script(bp, part, exercises)
    hook = f"{label.upper()} - PART {part}"
    chart_lines = [f"{ex['name']} {ex['sets']}x{ex['reps']}" for ex in exercises]
    title = f"{label} {emoji} Part {part} | {chart_lines[0]} #shorts #gym"
    hashtags = [bp["key"], "gym", "fitness", "workout", "gymmotivation",
                "fitfam", "bodybuilding", "shorts", "reels", "fyp"]
    tag_line = " ".join("#" + h for h in hashtags)
    chart_text = "\n".join(f"- {c}" for c in chart_lines)
    description = (
        f"{label} - Part {part}. Today's workout:\n{chart_text}\n\n"
        f"{script}\n\n"
        f"New body part every day. Part 1 (main lifts) in the morning, "
        f"Part 2 (accessories) at night. Follow for your daily workout.\n\n{tag_line}"
    )
    tags = list(dict.fromkeys([bp["key"], label.lower(), "workout", "gym tips",
                               "fitness motivation"] + BASE_TAGS))
    keywords = [ex["kw"] for ex in exercises]        # footage from the actual moves
    print(f"[script] {label} P{part} | chart: {', '.join(chart_lines)}")
    return {"hook": hook, "title": title, "script": script, "description": description,
            "keywords": keywords, "hashtags": hashtags, "tags": tags,
            "exercises": exercises, "label": label, "part": part}


# ======================================================================
# CAPTIONS — the WORKOUT CHART, revealed one exercise at a time.
# ======================================================================
WHITE = "&H00FFFFFF"
ACCENT = "&H0000F5FF"    # warm yellow
OUTLINE = "&H00000000"
BACK = "&H90000000"
FONT = "DejaVu Sans"


def _ts(t):
    h = int(t // 3600); m = int((t % 3600) // 60); s = int(t % 60)
    cs = int(round((t - int(t)) * 100))
    if cs == 100:
        s += 1; cs = 0
    return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"


def build_workout_ass(hook, exercises, duration, ass_path):
    """Title card at top for the whole clip, then each exercise line pops in
    one after another (a building workout list) in the lower half."""
    header = (
        "[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\n"
        "WrapStyle: 2\nScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, "
        "ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
        "MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Title,{FONT},96,{ACCENT},{WHITE},{OUTLINE},{BACK},"
        "1,0,0,0,100,100,0,0,1,8,4,8,60,60,180,1\n"
        f"Style: Row,{FONT},68,{WHITE},{WHITE},{OUTLINE},{BACK},"
        "1,0,0,0,100,100,0,0,1,6,3,7,0,0,0,1\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    events = []
    # Title: whole duration, with a quick pop-in
    title = (r"{\fad(150,200)\fscx70\fscy70\t(0,240,\fscx104\fscy104)"
             r"\t(240,380,\fscx100\fscy100)}" + hook)
    events.append(f"Dialogue: 0,{_ts(0.0)},{_ts(duration)},Title,,0,0,0,,{title}\n")

    n = len(exercises)
    intro, tail = 2.6, 1.4
    span = max(1.0, duration - intro - tail)
    step = span / max(1, n)
    x = 120
    y0 = 980
    row_h = 175
    for i, ex in enumerate(exercises):
        start = intro + i * step
        y = y0 + i * row_h
        line = (r"{\c" + ACCENT + r"}" + f"{i+1}." + r"{\r\c" + WHITE + r"}  "
                + ex["name"] + r"   {\c" + ACCENT + r"}" + f"{ex['sets']}x{ex['reps']}")
        body = (r"{\an7\pos(" + f"{x},{y}" + r")\fad(220,0)\fscx80\fscy80"
                r"\t(0,200,\fscx104\fscy104)\t(200,340,\fscx100\fscy100)}" + line)
        events.append(f"Dialogue: 0,{_ts(start)},{_ts(duration)},Row,,0,0,0,,{body}\n")
    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(header + "".join(events))
    return ass_path


# ======================================================================
# VOICEOVER (edge-tts)
# ======================================================================

async def _synthesize(text, mp3_path):
    communicate = edge_tts.Communicate(text, TTS_VOICE, rate=TTS_RATE, pitch=TTS_PITCH)
    with open(mp3_path, "wb") as audio_file:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_file.write(chunk["data"])


def make_voiceover(text, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    mp3_path = os.path.join(out_dir, "mp3")
    asyncio.run(_synthesize(text, mp3_path))
    print("[voice] voiceover ready.")
    return mp3_path


# ======================================================================
# VISUALS — Pexels, keywords from the exercises, ANY orientation,
# seeded per (date, part) so Part 1 / Part 2 differ.
# ======================================================================
PEXELS_SEARCH = "https://api.pexels.com/videos/search"
GRADIENTS = [((18, 22, 48), (86, 44, 120)), ((10, 30, 40), (14, 92, 110)),
             ((40, 16, 32), (150, 46, 60)), ((12, 28, 20), (30, 100, 70)),
             ((26, 24, 18), (120, 84, 30))]


def _download_pexels(keywords, out_dir, want=4):
    clips = []
    headers = {"Authorization": PEXELS_API_KEY}
    for kw in keywords:
        if len(clips) >= want:
            break
        try:
            resp = requests.get(PEXELS_SEARCH, headers=headers,
                                params={"query": kw, "per_page": 15}, timeout=30)
            if resp.status_code != 200:
                print(f"[visuals] Pexels '{kw}' HTTP {resp.status_code}: {resp.text[:100]}")
                continue
            videos = resp.json().get("videos", [])
            if not videos:
                print(f"[visuals] Pexels '{kw}': 0 results.")
                continue
            random.shuffle(videos)
            for video in videos:
                files = [f for f in video.get("video_files", []) if f.get("link")]
                if not files:
                    continue
                def score(f):
                    h = f.get("height") or 0; w = f.get("width") or 0
                    return (1 if h >= w else 0, -abs(h - 1200))
                chosen = sorted(files, key=score, reverse=True)[0]
                data = requests.get(chosen["link"], timeout=90)
                if not data.ok or len(data.content) < 20000:
                    continue
                path = os.path.join(out_dir, f"clip_{random.randint(100000,999999)}.mp4")
                with open(path, "wb") as f:
                    f.write(data.content)
                clips.append({"type": "video", "path": path})
                print(f"[visuals] Pexels '{kw}' -> {os.path.basename(path)} "
                      f"({chosen.get('width')}x{chosen.get('height')})")
                break
        except Exception as e:  # noqa: BLE001
            print(f"[visuals] Pexels '{kw}' failed ({e}); skipping.")
    return clips


def _make_gradient_backgrounds(out_dir, count=3):
    imgs = []
    for i, (top, bottom) in enumerate(random.sample(GRADIENTS, k=min(count, len(GRADIENTS)))):
        top_arr = np.array(top, dtype=np.float32); bottom_arr = np.array(bottom, dtype=np.float32)
        t = np.linspace(0.0, 1.0, HEIGHT, dtype=np.float32)[:, None]
        col = (top_arr[None, :] + (bottom_arr - top_arr)[None, :] * t)
        row = np.broadcast_to(col[:, None, :], (HEIGHT, WIDTH, 3))
        path = os.path.join(out_dir, f"bg_{i}.png")
        Image.fromarray(row.astype(np.uint8), "RGB").save(path)
        imgs.append({"type": "image", "path": path})
    print(f"[visuals] generated {len(imgs)} gradient backgrounds (Pexels unavailable).")
    return imgs


def get_visuals(keywords, out_dir, part=1):
    os.makedirs(out_dir, exist_ok=True)
    random.seed(f"{datetime.date.today().isoformat()}-{part}")
    if PEXELS_API_KEY:
        clips = _download_pexels(keywords, out_dir)
        if len(clips) < 2:
            print("[visuals] few clips; trying broader gym terms...")
            clips += _download_pexels(["gym workout", "weight training", "fitness exercise"],
                                      out_dir, want=4 - len(clips))
        if clips:
            print(f"[visuals] using {len(clips)} Pexels clip(s).")
            return clips
        print("[visuals] No Pexels clips; check the PEXELS_API_KEY value.")
    return _make_gradient_backgrounds(out_dir)


# ======================================================================
# ASSEMBLE (unchanged pipeline: footage + scrim + chart captions + music)
# ======================================================================

def _run(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def _probe_duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "default=noprint_wrappers=1:nokey=1", path],
                         capture_output=True, text=True)
    try:
        return float(out.stdout.strip())
    except ValueError:
        return 0.0


def generate_ambient_music(duration, out_path, work_dir):
    import wave as wavmod
    sr = 44100; n = int(duration * sr)
    t = np.linspace(0, duration, n, endpoint=False).astype(np.float32)
    freqs = [110.0, 164.81, 220.0, 277.18]
    audio = np.zeros(n, dtype=np.float32)
    for i, f in enumerate(freqs):
        detune = 1.0 + 0.0015 * (i - 1.5)
        vib = 1.0 + 0.002 * np.sin(2 * np.pi * 0.07 * t + i)
        wave = np.sin(2 * np.pi * f * detune * vib * t)
        wave += 0.22 * np.sin(2 * np.pi * 2 * f * detune * t)
        trem = 0.6 + 0.4 * np.sin(2 * np.pi * 0.05 * t + i * 1.3)
        audio += (wave * trem) * (0.9 - 0.12 * i)
    audio /= (np.max(np.abs(audio)) + 1e-9)
    fade = int(sr * 2.0); env = np.ones(n, dtype=np.float32)
    if n > 2 * fade:
        env[:fade] = np.linspace(0, 1, fade); env[-fade:] = np.linspace(1, 0, fade)
    audio = (audio * env * 0.5).astype(np.float32)
    wav_path = os.path.join(work_dir, "ambient.wav")
    with wavmod.open(wav_path, "w") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr)
        wf.writeframes((audio * 32767).astype(np.int16).tobytes())
    _run(["ffmpeg", "-y", "-i", wav_path, "-b:a", "160k", out_path])
    return out_path


def _make_scrim(work_dir):
    W, H = WIDTH, HEIGHT
    alpha = np.zeros(H, dtype=np.float32)
    start = int(H * 0.40)
    alpha[start:] = np.linspace(0, 190, H - start)
    rgba = np.zeros((H, W, 4), dtype=np.uint8)
    rgba[..., 3] = np.broadcast_to(alpha[:, None], (H, W)).astype(np.uint8)
    path = os.path.join(work_dir, "scrim.png")
    Image.fromarray(rgba, "RGBA").save(path)
    return path


def _clip_segment(path, seg_dur, out_path):
    W, H = WIDTH, HEIGHT
    vf = (f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
          f"setsar=1,fps={FPS},format=yuv420p")
    _run(["ffmpeg", "-y", "-stream_loop", "-1", "-t", f"{seg_dur:.3f}",
          "-i", path, "-an", "-vf", vf, "-r", str(FPS),
          "-c:v", "libx264", "-pix_fmt", "yuv420p", out_path])


def _xfade_concat(segments, seg_dur, out_path, work_dir, xfade=0.5):
    if len(segments) == 1:
        _run(["ffmpeg", "-y", "-i", segments[0], "-c", "copy", out_path]); return out_path
    inputs = []
    for s in segments:
        inputs += ["-i", s]
    filt = []; prev = "0:v"; offset = seg_dur - xfade
    for i in range(1, len(segments)):
        label = f"x{i}"
        filt.append(f"[{prev}][{i}:v]xfade=transition=fade:duration={xfade}:"
                    f"offset={offset:.3f}[{label}]")
        prev = label; offset += seg_dur - xfade
    _run(["ffmpeg", "-y", *inputs, "-filter_complex", ";".join(filt),
          "-map", f"[{prev}]", "-c:v", "libx264", "-pix_fmt", "yuv420p", out_path])
    return out_path


def _animated_gradient_bg(duration, out_path, work_dir):
    c = random.choice([("0x030814", "0x0a2540", "0x0e7c8c"),
                       ("0x05010f", "0x1b1050", "0x0e5c8c"),
                       ("0x00110f", "0x073b3a", "0x0aa0a0")])
    src = (f"gradients=s={WIDTH}x{HEIGHT}:c0={c[0]}:c1={c[1]}:c2={c[2]}:"
           f"nb_colors=3:x0=0:y0=0:x1={WIDTH}:y1={HEIGHT}:d={duration:.2f}:speed=0.012:type=linear")
    _run(["ffmpeg", "-y", "-f", "lavfi", "-i", src, "-t", f"{duration:.3f}",
          "-r", str(FPS), "-vf", "format=yuv420p", "-c:v", "libx264",
          "-pix_fmt", "yuv420p", out_path])
    return out_path


def _build_background(visuals, duration, work_dir):
    bg_path = os.path.join(work_dir, "bg.mp4")
    videos = [v for v in visuals if v["type"] == "video"]
    if videos:
        n = len(videos); seg_dur = duration / n + 0.6
        segs = []
        for i, v in enumerate(videos):
            sp = os.path.join(work_dir, f"seg_{i}.mp4")
            _clip_segment(v["path"], seg_dur, sp); segs.append(sp)
        _xfade_concat(segs, seg_dur, bg_path, work_dir)
        return bg_path
    return _animated_gradient_bg(duration, bg_path, work_dir)


def build_video(visuals, mp3_path, ass_path, out_path, work_dir, music_path=None):
    os.makedirs(work_dir, exist_ok=True)
    duration = _probe_duration(mp3_path)
    bg_path = _build_background(visuals, duration, work_dir)
    scrim_path = _make_scrim(work_dir)
    ass_escaped = ass_path.replace(":", "\\:").replace("'", "\\'")
    video_fc = f"[0:v][2:v]overlay=0:0[bgs];[bgs]ass='{ass_escaped}'[v]"
    if music_path and os.path.exists(music_path):
        audio_fc = ("[1:a]volume=1.0[vo];[3:a]volume=0.14,aloop=loop=-1:size=2e9[mu];"
                    "[vo][mu]amix=inputs=2:duration=first:dropout_transition=0[a]")
        cmd = ["ffmpeg", "-y", "-i", bg_path, "-i", mp3_path, "-i", scrim_path, "-i", music_path,
               "-filter_complex", f"{video_fc};{audio_fc}", "-map", "[v]", "-map", "[a]"]
    else:
        cmd = ["ffmpeg", "-y", "-i", bg_path, "-i", mp3_path, "-i", scrim_path,
               "-filter_complex", video_fc, "-map", "[v]", "-map", "1:a"]
    cmd += ["-t", f"{duration:.3f}", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-c:a", "aac", "-b:a", "160k", "-pix_fmt", "yuv420p", "-movflags", "+faststart", out_path]
    _run(cmd)
    print(f"[assemble] Final video: {out_path} ({duration:.1f}s)")
    return out_path


def pick_music(work_dir, duration):
    tracks = glob.glob(os.path.join(BASE_DIR, "music", "*.mp3"))
    if tracks:
        return random.choice(tracks)
    out = os.path.join(work_dir, "ambient.mp3")
    try:
        return generate_ambient_music(duration, out, work_dir)
    except Exception as e:  # noqa: BLE001
        print(f"[music] ambient failed ({e}); voice only.")
        return None


# ======================================================================
# UPLOAD -> YOUTUBE
# ======================================================================

def upload_youtube(video_path, meta):
    cid = os.environ.get("YT_CLIENT_ID", "").strip()
    csec = os.environ.get("YT_CLIENT_SECRET", "").strip()
    rtok = os.environ.get("YT_REFRESH_TOKEN", "").strip()
    if not (cid and csec and rtok):
        print("[youtube] YT secrets not set - skipping upload (video kept as artifact).")
        return None
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    creds = Credentials(token=None, refresh_token=rtok, client_id=cid, client_secret=csec,
                        token_uri="https://oauth2.googleapis.com/token",
                        scopes=["https://www.googleapis.com/auth/youtube.upload"])
    youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)
    title = meta["title"][:100]
    desc = meta["description"][:4900]
    if "#shorts" not in desc.lower():
        desc += "\n\n#Shorts"
    body = {"snippet": {"title": title, "description": desc, "tags": meta.get("tags", [])[:15],
                        "categoryId": "17"},
            "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}}
    media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/mp4")
    print(f"[youtube] uploading '{title[:50]}'...")
    resp = youtube.videos().insert(part="snippet,status", body=body, media_body=media).execute()
    vid = resp.get("id")
    print(f"[youtube] DONE -> https://youtube.com/shorts/{vid}")
    return vid


# ======================================================================
# RUNNER
# ======================================================================

def run():
    stamp = datetime.date.today().isoformat()
    day_dir = os.path.join(OUTPUT_DIR, stamp)
    work_dir = os.path.join(day_dir, "work")
    os.makedirs(work_dir, exist_ok=True)

    bp, part, exercises = pick_topic()
    content = generate(bp, part, exercises)

    mp3_path = make_voiceover(content["script"], work_dir)
    duration = _probe_duration(mp3_path)
    ass_path = os.path.join(work_dir, "ass")
    build_workout_ass(content["hook"], content["exercises"], duration, ass_path)

    assets = get_visuals(content["keywords"], work_dir, part=part)
    music_path = pick_music(work_dir, duration)

    out_path = os.path.join(day_dir, f"video_{stamp}_part{part}.mp4")
    build_video(assets, mp3_path, ass_path, out_path, work_dir, music_path=music_path)

    meta = {"date": stamp, "body_part": bp["label"], "part": part,
            "title": content["title"], "description": content["description"],
            "hashtags": content["hashtags"], "tags": content["tags"], "video_path": out_path}
    with open(os.path.join(day_dir, f"meta_part{part}.json"), "w") as f:
        json.dump(meta, f, indent=2)
    print(f"[main] Done. Video: {out_path}")

    try:
        upload_youtube(out_path, meta)
    except Exception as e:  # noqa: BLE001
        print(f"[youtube] upload failed ({e}); video still saved as an artifact.")
    return meta


if __name__ == "__main__":
    run()
