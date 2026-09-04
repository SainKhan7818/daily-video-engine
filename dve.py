"""Daily Video Engine — single-file build. Paste this whole file into GitHub as dve.py."""
import os, sys, math, json, glob, random, datetime, subprocess, asyncio, re
import urllib.parse, xml.etree.ElementTree as ET
import requests, numpy as np
from PIL import Image
import edge_tts

# ===== config =====
"""Central configuration for the daily video engine.

All secrets are read from environment variables so nothing sensitive lives in
the code. On GitHub Actions these come from repository Secrets; for a local
test you can `export` them or drop them in a .env file (which is git-ignored).
"""

# --- API keys (read from environment / GitHub Secrets) ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "")

# --- Video format ---
WIDTH = 1080
HEIGHT = 1920
FPS = 30
TARGET_SECONDS = 42          # aim for a ~40s short/reel
FONT_SIZE = 64

# --- Niche rotation (Tech/AI, Business/productivity, General trending) ---
# The engine rotates through these by day-of-year so the feed stays varied.
# --- FITNESS channel: a 7-day body-part split, two parts per day.
#   Part 1 posts in the morning, Part 2 in the evening (same body part).
#   Indexed by Python weekday(): Mon=0 ... Sun=6.
BODY_PARTS = [
    {
        "key": "chest", "label": "Chest Day", "emoji": "\U0001F4AA",
        "stock_keywords": ["bench press gym close up", "push up workout",
            "incline dumbbell press", "chest workout gym", "cable chest fly",
            "muscular chest training"],
        "p1_topic": "the two pressing moves that build a bigger chest",
        "p2_topic": "the chest finisher and the mistake killing your gains",
    },
    {
        "key": "back", "label": "Back Day", "emoji": "\U0001F53B",
        "stock_keywords": ["pull up bar workout", "lat pulldown gym",
            "barbell row close up", "deadlift back muscles", "back workout gym",
            "seated cable row"],
        "p1_topic": "the pulls that build a wide, strong back",
        "p2_topic": "the back mistake most lifters never fix",
    },
    {
        "key": "legs", "label": "Leg Day", "emoji": "\U0001F9B5",
        "stock_keywords": ["barbell squat gym", "leg press machine",
            "walking lunges gym", "leg workout quads", "calf raise",
            "athlete squatting heavy"],
        "p1_topic": "why leg day is the one day you can't skip",
        "p2_topic": "the leg finisher that builds real size",
    },
    {
        "key": "shoulders", "label": "Shoulder Day", "emoji": "\U0001F3CB",
        "stock_keywords": ["overhead press barbell", "lateral raise dumbbell",
            "shoulder workout gym", "arnold press dumbbell", "front raise gym",
            "muscular shoulders training"],
        "p1_topic": "the press and raise that build boulder shoulders",
        "p2_topic": "the shoulder detail almost everyone gets wrong",
    },
    {
        "key": "arms", "label": "Arm Day", "emoji": "\U0001F4AA",
        "stock_keywords": ["bicep curl dumbbell close up", "tricep pushdown cable",
            "barbell curl gym", "arm workout veins", "hammer curl dumbbell",
            "flexing arm muscle"],
        "p1_topic": "the curl and extension combo for bigger arms",
        "p2_topic": "the arm-pump finisher to end the week strong",
    },
    {
        "key": "core", "label": "Core Day", "emoji": "\U0001F525",
        "stock_keywords": ["abs workout gym", "plank exercise", "hanging leg raise",
            "core training athlete", "cable crunch", "six pack abs close up"],
        "p1_topic": "the core moves that actually reveal your abs",
        "p2_topic": "why abs are built in the kitchen just as much as the gym",
    },
    {
        "key": "fullbody", "label": "Full-Body & Cardio", "emoji": "\U000026A1",
        "stock_keywords": ["full body workout gym", "hiit training intense",
            "athlete running track", "functional training rope", "burpees workout",
            "sweat dripping cardio"],
        "p1_topic": "the full-body reset that starts your week right",
        "p2_topic": "the cardio finish that protects your hard-earned muscle",
    },
]

# --- Paths ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

# --- Voice (edge-tts neural voice; free, no key) ---
# Natural, expressive voices that suit punchy short-form narration.
# Swap TTS_VOICE for any of the alternatives to change the sound.
#   en-US-AvaMultilingualNeural   - warm, natural, expressive (default)
#   en-US-AndrewMultilingualNeural- confident male, great for tech
#   en-US-EmmaMultilingualNeural  - friendly, upbeat
#   en-US-AriaNeural / en-US-GuyNeural - reliable classics
TTS_VOICE = "en-US-AndrewMultilingualNeural"   # confident, energetic — suits fitness
TTS_RATE = "+8%"    # punchy pace for motivation
TTS_PITCH = "+0Hz"
# ===== topics =====
"""Pick today's body part (7-day split) and which part (1 = morning, 2 = evening)."""



def todays_bodypart():
    wd = datetime.date.today().weekday()   # Mon=0 ... Sun=6
    return BODY_PARTS[wd % len(BODY_PARTS)]


def current_part():
    """Part 1 in the morning, Part 2 in the evening.
    Controlled by env VIDEO_PART if set (workflow), else derived from UTC hour."""
    env = os.environ.get("VIDEO_PART", "").strip()
    if env in ("1", "2"):
        return int(env)
    hour = datetime.datetime.utcnow().hour
    return 1 if hour < 11 else 2   # <11:00 UTC = morning IST, else evening


def pick_topic():
    """Return (bodypart, part, topic_string)."""
    bp = todays_bodypart()
    part = current_part()
    topic = bp["p1_topic"] if part == 1 else bp["p2_topic"]
    print(f"[topics] {bp['label']} | Part {part} | Topic: {topic}")
    return bp, part, topic
# ===== script_gen =====
"""Build the fitness script + SEO metadata for a given body part and part number.

Deterministic (no API key needed). Returns a dict with:
  hook, title, script, description, keywords, hashtags, tags
All tuned for reach: strong hook, retention CTA that drives viewers to the
other part, and platform-ready title/description/hashtags.
"""

BASE_TAGS = ["gym", "fitness", "workout", "gymtok", "fitfam", "bodybuilding",
             "gymmotivation", "fitnessmotivation", "training", "shorts", "reels"]


def _script(topic, bp, part):
    label = bp["label"]
    if part == 1:
        return (
            f"It's {label}, and here's what most people get wrong. "
            f"Today, {topic}. "
            "Start with the big compound movement while you're fresh and strong. "
            "Control the weight down, drive it up with power, and leave one or two reps in the tank. "
            "That's how you build muscle without burning out or getting hurt. "
            "Do this right and you'll feel it working in the first week. "
            "Part two drops tonight with the finisher, so follow now and don't miss it."
        )
    return (
        f"Welcome back to {label}, part two. "
        f"If you caught part one, you're ready for this: {topic}. "
        "Finish with higher reps and a real mind-muscle connection. "
        "Slow the tempo, squeeze hard at the top, and chase the pump on your last sets. "
        "This is the part that separates the people who look like they train from the ones who don't. "
        "Missed part one? It's on the profile. New body part tomorrow, so hit follow and let's build."
    )


def generate(topic, bp, part):
    label = bp["label"]
    emoji = bp.get("emoji", "\U0001F4AA")
    script = _script(topic, bp, part)

    hook = f"{label.upper()} — PART {part}"
    title = f"{label} {emoji} Part {part} | {topic[:40].strip().capitalize()} #shorts #gym"
    hashtags = [bp["key"], "gym", "fitness", "workout", "gymmotivation",
                "fitfam", "bodybuilding", "shorts", "reels", "fyp"]
    tag_line = " ".join("#" + h for h in hashtags)
    description = (
        f"{label} — Part {part}. {topic.capitalize()}.\n\n"
        f"{script}\n\n"
        f"New body part every day. Part 1 in the morning, Part 2 at night. "
        f"Follow for your daily workout.\n\n{tag_line}"
    )
    tags = list(dict.fromkeys([bp["key"], label.lower(), "workout", "gym tips",
                               "fitness motivation"] + BASE_TAGS))

    print(f"[script] {label} Part {part} | title: {title[:50]}...")
    return {
        "hook": hook,
        "title": title,
        "script": script,
        "description": description,
        "keywords": bp["stock_keywords"],
        "hashtags": hashtags,
        "tags": tags,
    }
# ===== captions =====
"""Build animated, word-by-word captions in ASS format ("Hormozi" style).

Given per-word timings, render a small rolling phrase (a few words) with the
currently-spoken word popped larger and tinted an accent colour. This is the
look that makes short-form captions feel dynamic instead of static.
"""

# ASS colours are &HAABBGGRR (alpha, blue, green, red).
WHITE = "&H00FFFFFF"
ACCENT = "&H0000F5FF"   # warm yellow
OUTLINE = "&H00000000"
BACK = "&H90000000"

WORDS_PER_PHRASE = 3    # how many words sit on screen at once
FONT = "DejaVu Sans"
FONTSIZE = 90


def _ts(t):
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = int(t % 60)
    cs = int(round((t - int(t)) * 100))
    if cs == 100:
        s += 1
        cs = 0
    return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"


def _header():
    return (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        "PlayResX: 1080\n"
        "PlayResY: 1920\n"
        "WrapStyle: 0\n"
        "ScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, "
        "ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
        "MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Base,{FONT},{FONTSIZE},{WHITE},{ACCENT},{OUTLINE},{BACK},"
        "1,0,0,0,100,100,0,0,1,7,4,2,80,80,620,1\n"
        # Hook title card: big, top-centre, bold
        f"Style: Hook,{FONT},128,{ACCENT},{WHITE},{OUTLINE},{BACK},"
        "1,0,0,0,100,100,0,0,1,9,5,8,60,60,300,1\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, "
        "Effect, Text\n"
    )


def _phrase_groups(words):
    """Split the word list into fixed-size phrase windows."""
    groups = []
    for i in range(0, len(words), WORDS_PER_PHRASE):
        groups.append(words[i:i + WORDS_PER_PHRASE])
    return groups


def build_ass(words, ass_path, hook=None):
    """words: list of dicts {text, start, end} (seconds). Writes an ASS file.
    hook: optional short ALL-CAPS title-card line shown for the first ~2.5s."""
    lines = [_header()]
    if hook:
        # pops in, holds, fades — grabs the eye before the captions start
        hook_text = (r"{\fad(150,250)\fscx60\fscy60\t(0,220,\fscx104\fscy104)"
                     r"\t(220,360,\fscx100\fscy100)}" + hook.upper())
        lines.append(
            f"Dialogue: 0,{_ts(0.0)},{_ts(2.6)},Hook,,0,0,0,,{hook_text}\n"
        )
    for group in _phrase_groups(words):
        for idx, w in enumerate(group):
            start = w["start"]
            end = w["end"]
            # render the whole phrase, active word popped + accent-coloured
            parts = []
            for j, gw in enumerate(group):
                token = gw["text"]
                if j == idx:
                    parts.append(
                        r"{\c" + ACCENT + r"\fscx118\fscy118"
                        r"\t(0,120,\fscx128\fscy128)\t(120,240,\fscx118\fscy118)}"
                        + token + r"{\r}"
                    )
                else:
                    parts.append(token)
            text = " ".join(parts)
            lines.append(
                f"Dialogue: 0,{_ts(start)},{_ts(end)},Base,,0,0,0,,{text}\n"
            )
    with open(ass_path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    return ass_path


def even_word_times(script_text, duration):
    """Fallback word timings (evenly spaced) when real boundaries aren't available."""
    tokens = script_text.split()
    per = duration / max(1, len(tokens))
    return [{"text": t, "start": i * per, "end": (i + 1) * per}
            for i, t in enumerate(tokens)]
# ===== voice =====
"""Voiceover with edge-tts (free Microsoft neural voices, no key), returning the
audio plus real per-word timings so captions can be animated word-by-word.
"""




async def _synthesize(text, mp3_path):
    communicate = edge_tts.Communicate(
        text, TTS_VOICE, rate=TTS_RATE,
        pitch=TTS_PITCH)
    words = []
    with open(mp3_path, "wb") as audio_file:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_file.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                start = chunk["offset"] / 1e7          # 100-ns -> seconds
                dur = chunk["duration"] / 1e7
                words.append({"text": chunk["text"], "start": start,
                              "end": start + dur})
    return words


def make_voiceover(text, out_dir):
    """Return (mp3_path, words) where words is a list of {text,start,end}."""
    os.makedirs(out_dir, exist_ok=True)
    mp3_path = os.path.join(out_dir, "mp3")
    words = asyncio.run(_synthesize(text, mp3_path))
    print(f"[voice] Voiceover ready with {len(words)} word timings.")
    return mp3_path, words
# ===== visuals =====
"""Get background visuals for the video.

Primary path: Pexels stock video (free API key). Downloads a few vertical
clips matching the script's keywords.

Fallback (no key / failure): generate clean animated gradient backgrounds with
Pillow so the engine still produces a polished-looking video.
"""



PEXELS_SEARCH = "https://api.pexels.com/videos/search"

# Pleasant gradient palettes for the no-key fallback (top RGB, bottom RGB).
GRADIENTS = [
    ((18, 22, 48), (86, 44, 120)),      # indigo -> violet
    ((10, 30, 40), (14, 92, 110)),      # deep teal
    ((40, 16, 32), (150, 46, 60)),      # wine -> rose
    ((12, 28, 20), (30, 100, 70)),      # forest
    ((26, 24, 18), (120, 84, 30)),      # amber
]


def _download_pexels(keywords, out_dir, want=4):
    clips = []
    headers = {"Authorization": PEXELS_API_KEY}
    for kw in keywords:
        if len(clips) >= want:
            break
        try:
            resp = requests.get(
                PEXELS_SEARCH,
                headers=headers,
                params={"query": kw, "orientation": "portrait",
                        "size": "medium", "per_page": 5},
                timeout=30,
            )
            resp.raise_for_status()
            videos = resp.json().get("videos", [])
            if not videos:
                continue
            video = random.choice(videos)
            # pick an HD-ish portrait file that isn't huge
            files = sorted(
                video.get("video_files", []),
                key=lambda f: (f.get("height") or 0),
            )
            portrait = [f for f in files if (f.get("height") or 0) >= (f.get("width") or 0)]
            chosen = (portrait or files)
            chosen = chosen[len(chosen) // 2] if chosen else None
            if not chosen:
                continue
            data = requests.get(chosen["link"], timeout=60)
            path = os.path.join(out_dir, f"clip_{len(clips)}.mp4")
            with open(path, "wb") as f:
                f.write(data.content)
            clips.append({"type": "video", "path": path})
            print(f"[visuals] Pexels clip for '{kw}' -> {os.path.basename(path)}")
        except Exception as e:  # noqa: BLE001
            print(f"[visuals] Pexels '{kw}' failed ({e}); skipping.")
    return clips


def _make_gradient_backgrounds(out_dir, count=3):
    imgs = []
    palettes = random.sample(GRADIENTS, k=min(count, len(GRADIENTS)))
    for i, (top, bottom) in enumerate(palettes):
        top_arr = np.array(top, dtype=np.float32)
        bottom_arr = np.array(bottom, dtype=np.float32)
        t = np.linspace(0.0, 1.0, HEIGHT, dtype=np.float32)[:, None]  # (H,1)
        col = (top_arr[None, :] + (bottom_arr - top_arr)[None, :] * t)       # (H,3)
        row = np.broadcast_to(col[:, None, :], (HEIGHT, WIDTH, 3))
        img = Image.fromarray(row.astype(np.uint8), "RGB")
        path = os.path.join(out_dir, f"bg_{i}.png")
        img.save(path)
        imgs.append({"type": "image", "path": path})
    print(f"[visuals] Generated {len(imgs)} gradient backgrounds (no Pexels key).")
    return imgs


def get_visuals(keywords, out_dir):
    """Return a list of {type, path} visual assets."""
    os.makedirs(out_dir, exist_ok=True)
    if PEXELS_API_KEY:
        clips = _download_pexels(keywords, out_dir)
        if clips:
            return clips
        print("[visuals] No Pexels clips returned; falling back to gradients.")
    return _make_gradient_backgrounds(out_dir)
# ===== assemble =====
"""Stitch visuals + voiceover + animated captions + music into a finished
vertical short (faceless-viral style) with ffmpeg.

- Stock clips are scaled/cropped to 1080x1920 and crossfaded together to fill
  the voiceover length; a still-image fallback uses a living animated gradient.
- A smooth bottom scrim keeps captions readable over any footage.
- Captions are animated word-by-word (ASS).
- Optional background music is ducked under the 
"""




def _run(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def _probe_duration(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def generate_ambient_music(duration, out_path, work_dir):
    """Synthesize a soft, calming ambient pad in-code (no external files needed).
    A gentle detuned chord with slow breathing tremolo and long fades — sits
    quietly under narration."""
    import wave as wavmod
    sr = 44100
    n = int(duration * sr)
    t = np.linspace(0, duration, n, endpoint=False).astype(np.float32)
    freqs = [110.0, 164.81, 220.0, 277.18]      # A2, E3, A3, C#4 — warm major
    audio = np.zeros(n, dtype=np.float32)
    for i, f in enumerate(freqs):
        detune = 1.0 + 0.0015 * (i - 1.5)
        vib = 1.0 + 0.002 * np.sin(2 * np.pi * 0.07 * t + i)
        wave = np.sin(2 * np.pi * f * detune * vib * t)
        wave += 0.22 * np.sin(2 * np.pi * 2 * f * detune * t)   # soft harmonic
        trem = 0.6 + 0.4 * np.sin(2 * np.pi * 0.05 * t + i * 1.3)
        audio += (wave * trem) * (0.9 - 0.12 * i)
    audio /= (np.max(np.abs(audio)) + 1e-9)
    fade = int(sr * 2.0)
    env = np.ones(n, dtype=np.float32)
    if n > 2 * fade:
        env[:fade] = np.linspace(0, 1, fade)
        env[-fade:] = np.linspace(1, 0, fade)
    audio = (audio * env * 0.5).astype(np.float32)
    wav_path = os.path.join(work_dir, "ambient.wav")
    pcm = (audio * 32767).astype(np.int16)
    with wavmod.open(wav_path, "w") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())
    _run(["ffmpeg", "-y", "-i", wav_path, "-b:a", "160k", out_path])
    print(f"[music] Generated soft ambient bed ({duration:.0f}s).")
    return out_path


def _make_scrim(work_dir):
    W, H = WIDTH, HEIGHT
    alpha = np.zeros(H, dtype=np.float32)
    start = int(H * 0.42)
    alpha[start:] = np.linspace(0, 180, H - start)
    rgba = np.zeros((H, W, 4), dtype=np.uint8)
    rgba[..., 3] = np.broadcast_to(alpha[:, None], (H, W)).astype(np.uint8)
    path = os.path.join(work_dir, "scrim.png")
    Image.fromarray(rgba, "RGBA").save(path)
    return path


# --- background construction -------------------------------------------------

GRADIENT_COLORS = [
    ("0x030814", "0x0a2540", "0x0e7c8c"),   # deep navy -> cyan (techy)
    ("0x05010f", "0x1b1050", "0x0e5c8c"),   # black-violet -> electric blue
    ("0x00110f", "0x073b3a", "0x0aa0a0"),   # dark teal -> aqua
]


def _animated_gradient_bg(duration, out_path, work_dir):
    """A slowly shifting multi-colour gradient — a 'living' fallback background."""
    c0, c1, c2 = random.choice(GRADIENT_COLORS)
    src = (
        f"gradients=s={WIDTH}x{HEIGHT}:c0={c0}:c1={c1}:c2={c2}:"
        f"nb_colors=3:x0=0:y0=0:x1={WIDTH}:y1={HEIGHT}:"
        f"d={duration:.2f}:speed=0.012:type=linear"
    )
    _run(["ffmpeg", "-y", "-f", "lavfi", "-i", src, "-t", f"{duration:.3f}",
          "-r", str(FPS), "-vf", "format=yuv420p",
          "-c:v", "libx264", "-pix_fmt", "yuv420p", out_path])
    return out_path


def _clip_segment(path, seg_dur, out_path):
    W, H = WIDTH, HEIGHT
    vf = (f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
          f"setsar=1,fps={FPS},format=yuv420p")
    _run(["ffmpeg", "-y", "-stream_loop", "-1", "-t", f"{seg_dur:.3f}",
          "-i", path, "-an", "-vf", vf, "-r", str(FPS),
          "-c:v", "libx264", "-pix_fmt", "yuv420p", out_path])


def _xfade_concat(segments, seg_dur, out_path, work_dir, xfade=0.5):
    """Crossfade a list of equal-length clips into one continuous background."""
    if len(segments) == 1:
        _run(["ffmpeg", "-y", "-i", segments[0], "-c", "copy", out_path])
        return out_path
    inputs = []
    for s in segments:
        inputs += ["-i", s]
    # chain xfades
    filt = []
    prev = "0:v"
    offset = seg_dur - xfade
    for i in range(1, len(segments)):
        label = f"x{i}"
        filt.append(
            f"[{prev}][{i}:v]xfade=transition=fade:duration={xfade}:"
            f"offset={offset:.3f}[{label}]"
        )
        prev = label
        offset += seg_dur - xfade
    filter_complex = ";".join(filt)
    _run(["ffmpeg", "-y", *inputs, "-filter_complex", filter_complex,
          "-map", f"[{prev}]", "-c:v", "libx264", "-pix_fmt", "yuv420p", out_path])
    return out_path


def _build_background(visuals, duration, work_dir):
    bg_path = os.path.join(work_dir, "bg.mp4")
    videos = [v for v in visuals if v["type"] == "video"]
    if videos:
        n = len(videos)
        seg_dur = duration / n + 0.6   # pad for crossfades
        segs = []
        for i, v in enumerate(videos):
            sp = os.path.join(work_dir, f"seg_{i}.mp4")
            _clip_segment(v["path"], seg_dur, sp)
            segs.append(sp)
        _xfade_concat(segs, seg_dur, bg_path, work_dir)
        return bg_path
    # fallback: living animated gradient
    return _animated_gradient_bg(duration, bg_path, work_dir)


# --- final compose -----------------------------------------------------------

def build_video(visuals, mp3_path, ass_path, out_path, work_dir, music_path=None):
    os.makedirs(work_dir, exist_ok=True)
    duration = _probe_duration(mp3_path)

    bg_path = _build_background(visuals, duration, work_dir)
    scrim_path = _make_scrim(work_dir)
    ass_escaped = ass_path.replace(":", "\\:").replace("'", "\\'")

    video_fc = (
        f"[0:v][2:v]overlay=0:0[bgs];"
        f"[bgs]ass='{ass_escaped}'[v]"
    )

    if music_path and os.path.exists(music_path):
        # voice at full, music ducked underneath
        audio_fc = (
            f"[1:a]volume=1.0[vo];"
            f"[3:a]volume=0.14,aloop=loop=-1:size=2e9[mu];"
            f"[vo][mu]amix=inputs=2:duration=first:dropout_transition=0[a]"
        )
        cmd = ["ffmpeg", "-y", "-i", bg_path, "-i", mp3_path, "-i", scrim_path,
               "-i", music_path,
               "-filter_complex", f"{video_fc};{audio_fc}",
               "-map", "[v]", "-map", "[a]"]
    else:
        cmd = ["ffmpeg", "-y", "-i", bg_path, "-i", mp3_path, "-i", scrim_path,
               "-filter_complex", video_fc,
               "-map", "[v]", "-map", "1:a"]

    cmd += ["-t", f"{duration:.3f}",
            "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-c:a", "aac", "-b:a", "160k", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", out_path]
    _run(cmd)
    print(f"[assemble] Final video: {out_path} ({duration:.1f}s)")
    return out_path
# ===== runner =====
"""Daily AI video engine — orchestrates the full pipeline.

Run:  python main.py
Produces a finished vertical video in ./output plus a metadata JSON
(title, description, hashtags) that the uploaders use.
"""



def run():
    stamp = datetime.date.today().isoformat()
    day_dir = os.path.join(OUTPUT_DIR, stamp)
    work_dir = os.path.join(day_dir, "work")
    os.makedirs(work_dir, exist_ok=True)

    # 1) today's body part + which part (1=morning, 2=evening)
    bodypart, part, topic = pick_topic()

    # 2) script + SEO metadata
    content = generate(topic, bodypart, part)

    # 3) voiceover (+ real word timings) and animated captions
    mp3_path, words = voice_step(content["script"], work_dir)
    ass_path = os.path.join(work_dir, "ass")
    build_ass(words, ass_path, hook=content.get("hook"))

    # 4) visuals
    assets = get_visuals(content["keywords"], work_dir)

    # 5) background music — a soft ambient bed sized to the voiceover length
    vdur = _probe_duration(mp3_path)
    music_path = pick_music(work_dir, vdur)

    # 6) assemble (part-tagged filename so morning & evening don't clash)
    out_path = os.path.join(day_dir, f"video_{stamp}_part{part}.mp4")
    build_video(assets, mp3_path, ass_path, out_path, work_dir,
                         music_path=music_path)

    # 7) SEO metadata for the uploaders (title, description, hashtags, tags)
    meta = {
        "date": stamp,
        "body_part": bodypart["label"],
        "part": part,
        "topic": topic,
        "title": content["title"],
        "description": content["description"],
        "hashtags": content["hashtags"],
        "tags": content["tags"],
        "video_path": out_path,
    }
    meta_path = os.path.join(day_dir, f"meta_part{part}.json")
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)

    print(f"\n[main] Done. Video: {out_path}\n[main] Meta: {meta_path}")
    return meta


def voice_step(script_text, work_dir):
    # imported here so a missing edge-tts only fails at this step, not import time
    return make_voiceover(script_text, work_dir)


def pick_music(work_dir, duration):
    """Use a CC0 track from ./music if present, else generate a soft ambient bed."""
    import glob
    import random
    music_dir = os.path.join(BASE_DIR, "music")
    tracks = glob.glob(os.path.join(music_dir, "*.mp3"))
    if tracks:
        return random.choice(tracks)
    out = os.path.join(work_dir, "ambient.mp3")
    try:
        return generate_ambient_music(duration, out, work_dir)
    except Exception as e:  # noqa: BLE001
        print(f"[music] ambient generation failed ({e}); voice only.")
        return None


if __name__ == "__main__":
    run()
