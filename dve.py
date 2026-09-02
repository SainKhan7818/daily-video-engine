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
NICHES = [
    {
        "key": "tech_ai",
        "label": "Tech & AI",
        "prompt_topic": "the latest trending development in technology and artificial intelligence",
        # cinematic, techy, visually rich fallback keywords
        "stock_keywords": [
            "futuristic technology", "data center", "neon city night",
            "circuit board macro", "robot", "drone aerial city",
        ],
    },
    {
        "key": "business",
        "label": "Business & Productivity",
        "prompt_topic": "a trending business, career, or productivity idea people are talking about",
        "stock_keywords": [
            "city skyline aerial", "modern office glass", "stock market screen",
            "sunrise skyscraper", "team working", "highway timelapse",
        ],
    },
    {
        "key": "trending",
        "label": "Trending Now",
        "prompt_topic": "a broadly trending topic or interesting fact people are curious about today",
        "stock_keywords": [
            "mountain landscape aerial", "ocean waves drone", "northern lights",
            "desert dunes", "forest fog cinematic", "waterfall slow motion",
        ],
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
TTS_VOICE = "en-US-AvaMultilingualNeural"
TTS_RATE = "+6%"    # a touch faster keeps shorts punchy
TTS_PITCH = "+0Hz"
# ===== topics =====
"""Find what's actually trending *today* across platforms, then hand the
strongest, most curiosity-provoking topic to the scriptwriter.

Sources (all free, no keys), tried in order and pooled:
  1. Google Trends daily trending searches (what people are Googling now)
  2. YouTube trending-style search feed for the niche (via Google News as proxy)
  3. Reddit hot posts for the niche subreddits (what's blowing up socially)
  4. Google News headlines for the niche

Everything is defensive: if a source is unreachable the engine still produces
a video from whatever it did find, or an evergreen seed.
"""



UA = {"User-Agent": "Mozilla/5.0 (compatible; DailyVideoEngine/1.0)"}

NICHE_QUERY = {
    "tech_ai": "artificial intelligence OR AI OR technology",
    "business": "business OR startup OR productivity OR money",
    "trending": "trending OR viral",
}

NICHE_SUBREDDITS = {
    "tech_ai": ["technology", "artificial", "Futurology"],
    "business": ["business", "productivity", "Entrepreneur"],
    "trending": ["todayilearned", "interestingasfuck", "Damnthatsinteresting"],
}

EVERGREEN_FALLBACK = {
    "tech_ai": "The AI feature hiding in your phone that almost nobody uses",
    "business": "The one-sentence habit that quietly makes people rich",
    "trending": "A fact so strange your brain refuses to believe it",
}


def todays_niche():
    doy = datetime.date.today().timetuple().tm_yday
    return NICHES[doy % len(NICHES)]


def _google_trends():
    url = "https://trends.google.com/trends/trendingsearches/daily/rss?geo=US"
    try:
        r = requests.get(url, headers=UA, timeout=15)
        r.raise_for_status()
        root = ET.fromstring(r.content)
        return [i.findtext("title", "").strip() for i in root.iter("item")][:10]
    except Exception as e:  # noqa: BLE001
        print(f"[topics] google trends failed: {e}")
        return []


def _news(query):
    url = ("https://news.google.com/rss/search?q=" + urllib.parse.quote(query)
           + "&hl=en-US&gl=US&ceid=US:en")
    try:
        r = requests.get(url, headers=UA, timeout=15)
        r.raise_for_status()
        root = ET.fromstring(r.content)
        return [i.findtext("title", "").strip() for i in root.iter("item")][:10]
    except Exception as e:  # noqa: BLE001
        print(f"[topics] news failed: {e}")
        return []


def _reddit(subs):
    titles = []
    for sub in subs:
        try:
            r = requests.get(f"https://www.reddit.com/r/{sub}/hot.json?limit=8",
                             headers=UA, timeout=15)
            r.raise_for_status()
            for child in r.json().get("data", {}).get("children", []):
                d = child.get("data", {})
                if not d.get("stickied") and d.get("title"):
                    titles.append(d["title"].strip())
        except Exception as e:  # noqa: BLE001
            print(f"[topics] reddit r/{sub} failed: {e}")
    return titles[:12]


def pick_topic():
    """Return (niche, topic_string) using the freshest trending signal available."""
    niche = todays_niche()
    pool = []
    pool += _news(NICHE_QUERY.get(niche["key"], "trending"))
    pool += _reddit(NICHE_SUBREDDITS.get(niche["key"], []))
    if niche["key"] == "trending":
        pool += _google_trends()

    # clean + de-dupe, prefer punchy, curiosity-friendly headlines
    seen, cleaned = set(), []
    for t in pool:
        t = t.split(" - ")[0].strip()      # strip trailing " - Publisher"
        if 15 <= len(t) <= 120 and t.lower() not in seen:
            seen.add(t.lower())
            cleaned.append(t)

    topic = random.choice(cleaned[:12]) if cleaned else EVERGREEN_FALLBACK[niche["key"]]
    print(f"[topics] Niche: {niche['label']} | Pool: {len(cleaned)} | Topic: {topic}")
    return niche, topic
# ===== script_gen =====
"""Turn the day's topic into a tight ~40-second narration script.

Primary path: Google Gemini (free tier). If no key is set or the call fails,
fall back to a clean template so a video is still produced.

Returns a dict:
  {
    "title":   short video title (for YouTube/Reel caption),
    "script":  the narration text (what the voice reads),
    "keywords": list of visual search keywords for stock footage,
    "hashtags": list of hashtags for the post caption,
  }
"""



GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.0-flash:generateContent"
)

PROMPT_TEMPLATE = """You are a world-class short-form scriptwriter behind viral YouTube Shorts and
Instagram Reels that routinely hit millions of views. You understand retention:
the first second decides everything.

Today's trending topic ({niche_label}): "{topic}"

Write a scroll-stopping ~38 second voiceover script (about 90-105 words).
Non-negotiable rules for maximum retention:
- FIRST LINE is a pattern-interrupt hook: a bold claim, a shocking number, or a
  "you've been doing X wrong" — something that makes scrolling feel like a mistake.
- Then open a curiosity gap and don't fully close it until near the end.
- Short, punchy, spoken-word sentences. Energy and momentum. No fluff, no
  "welcome back", no emojis, no stage directions — only the words to be spoken.
- Land one genuinely surprising insight people will want to share.
- End with a confident one-line CTA to follow for more.

Also give a "hook": a 3-6 word ALL-CAPS on-screen title-card line (the first thing
the viewer reads) that amplifies the hook. Punchy and bold.

For "keywords", give 5-6 CINEMATIC, visually rich stock-footage search terms that
look stunning full-screen — aerial landscapes, futuristic tech, glowing city nights,
drone shots, nature, macro detail. Concrete beautiful shots, never abstract words.

Return ONLY valid JSON (no markdown fences) with these exact keys:
{{
  "hook": "3-6 WORD ON-SCREEN TITLE",
  "title": "a catchy <60 char title",
  "script": "the voiceover text",
  "keywords": ["5-6 cinematic visual search terms for stock footage"],
  "hashtags": ["5-8 relevant hashtags without the # symbol"]
}}"""


def _fallback(topic, niche):
    """Deterministic, no-API script so the pipeline never hard-fails."""
    script = (
        f"Here's something worth knowing. {topic}. "
        "It sounds small, but it changes how you should think about what's coming next. "
        "The people who notice these shifts early are the ones who stay ahead, "
        "while everyone else is still catching up. "
        "So keep your eyes open, stay curious, and don't wait for permission to learn. "
        "Follow for one of these every single day."
    )
    return {
        "hook": "WAIT FOR IT",
        "title": topic[:58],
        "script": script,
        "keywords": niche["stock_keywords"],
        "hashtags": ["shorts", "reels", niche["key"], "trending", "learn"],
    }


def _extract_json(text):
    """Pull the JSON object out of a model response that may have stray text."""
    text = text.strip()
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group(0))
    return json.loads(text)


def generate(topic, niche):
    if not GEMINI_API_KEY:
        print("[script] No GEMINI_API_KEY set; using template fallback.")
        return _fallback(topic, niche)

    prompt = PROMPT_TEMPLATE.format(niche_label=niche["label"], topic=topic)
    try:
        resp = requests.post(
            GEMINI_URL,
            params={"key": GEMINI_API_KEY},
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=45,
        )
        resp.raise_for_status()
        data = resp.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        result = _extract_json(text)
        # sanity-check required keys
        for k in ("title", "script", "keywords", "hashtags"):
            if k not in result:
                raise ValueError(f"missing key {k}")
        result.setdefault("hook", result["title"][:24].upper())
        print(f"[script] Gemini script ready: {result['title']}")
        return result
    except Exception as e:  # noqa: BLE001
        print(f"[script] Gemini failed ({e}); using template fallback.")
        return _fallback(topic, niche)
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

    # 1) topic
    niche, topic = pick_topic()

    # 2) script
    content = generate(topic, niche)

    # 3) voiceover (+ real word timings) and animated captions
    mp3_path, words = voice_step(content["script"], work_dir)
    ass_path = os.path.join(work_dir, "ass")
    build_ass(words, ass_path, hook=content.get("hook"))

    # 4) visuals
    assets = get_visuals(content["keywords"], work_dir)

    # 5) background music (optional; picked from ./music if present)
    music_path = pick_music()

    # 6) assemble
    out_path = os.path.join(day_dir, f"video_{stamp}.mp4")
    build_video(assets, mp3_path, ass_path, out_path, work_dir,
                         music_path=music_path)

    # 6) metadata for the uploaders
    hashtags = " ".join(f"#{h.lstrip('#')}" for h in content["hashtags"])
    meta = {
        "date": stamp,
        "niche": niche["label"],
        "topic": topic,
        "title": content["title"],
        "description": f"{content['script']}\n\n{hashtags}",
        "hashtags": content["hashtags"],
        "video_path": out_path,
    }
    meta_path = os.path.join(day_dir, "meta.json")
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)

    print(f"\n[main] Done. Video: {out_path}\n[main] Meta: {meta_path}")
    return meta


def voice_step(script_text, work_dir):
    # imported here so a missing edge-tts only fails at this step, not import time
    return make_voiceover(script_text, work_dir)


def pick_music():
    """Pick a random track from ./music (CC0 background tracks), if any exist."""
    import glob
    import random
    music_dir = os.path.join(BASE_DIR, "music")
    tracks = glob.glob(os.path.join(music_dir, "*.mp3"))
    if not tracks:
        print("[music] No tracks in ./music; video will use voice only.")
        return None
    return random.choice(tracks)


if __name__ == "__main__":
    run()
