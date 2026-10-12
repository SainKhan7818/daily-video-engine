"""Daily Video Engine — single-file build. Paste this whole file into GitHub as dve.py."""
import os, sys, math, json, glob, random, time, datetime, subprocess, asyncio, re
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
TARGET_SECONDS = 42  # aim for a ~40s short/reel (workouts); edu runs longer
FONT_SIZE = 64

# ---------------------------------------------------------------------------
# FITNESS CHANNEL — broad content library (full rotation, both daily slots).
#
# The engine rotates through the whole library below, two items per day
# (Part 1 morning, Part 2 evening), walking the list so consecutive posts are
# always different and the whole set cycles over ~2 weeks.
#
# Each entry:
#   key, label, emoji, category, style ("punchy" | "edu")
#   sub            - short subtitle used in the title/description
#   stock_keywords - Pexels search terms for background footage
#   hook           - short ALL-CAPS title-card line
#   script         - the full voiceover text
#   hashtags_extra - topic-specific hashtags (base tags added automatically)
# ---------------------------------------------------------------------------

CHEST = "\U0001F4AA"; FIRE = "\U0001F525"; LEG = "\U0001F9B5"; LIFT = "\U0001F3CB"
BOLT = "\U000026A1"; BROC = "\U0001F966"; BRAIN = "\U0001F9E0"; STRETCH = "\U0001F938"
RUN = "\U0001F3C3"; SLEEP = "\U0001F634"; MEAT = "\U0001F357"; DROP = "\U0001F4A7"
TROPHY = "\U0001F3C6"; HOME = "\U0001F3E0"; CLOCK = "\U000023F0"; CHART = "\U0001F4C8"
TARGET = "\U0001F3AF"; CHECK = "\U00002705"; CROSS = "\U0000274C"; FILM = "\U0001F3AC"

CONTENT = [
# ---- 1. Ranked: best chest exercises (ranked) ----
{
    "key": "ranked_chest", "label": "Chest Exercises Ranked", "emoji": TROPHY,
    "category": "ranked", "style": "punchy",
    "sub": "Top 3 moves for a bigger chest",
    "stock_keywords": ["bench press gym close up", "incline dumbbell press",
                       "cable chest fly", "push up workout", "chest workout gym"],
    "hook": "CHEST, RANKED",
    "script": (
        "Here are the three best chest exercises, ranked. "
        "Number three: the cable fly. Constant tension and a deep stretch make it perfect for finishing your chest off. "
        "Number two: the incline dumbbell press. It builds that upper chest shelf most people are missing, with a huge range of motion. "
        "And number one: the flat barbell or dumbbell press. Nothing beats it for raw size and strength when you press heavy and control the weight down. "
        "Start heavy, finish with the stretch, and your chest grows. "
        "Follow for a new ranking every day."
    ),
    "hashtags_extra": ["chest", "chestday", "benchpress", "ranked"],
},
# ---- 2. Science: progressive overload (science) ----
{
    "key": "science_overload", "label": "Why You're Not Growing", "emoji": BRAIN,
    "category": "science", "style": "edu",
    "sub": "The science of progressive overload",
    "stock_keywords": ["adding weight plates barbell", "lifting heavy gym",
                       "workout notebook tracking", "dumbbell rack gym", "focused training"],
    "hook": "THE GROWTH RULE",
    "script": (
        "If you've trained for months and look the same, here's the science you're missing. "
        "Muscle only grows when you force it to adapt to more than it's used to. That's called progressive overload. "
        "Doing the same weight, for the same reps, every week, gives your body no reason to change. "
        "So each week, do a little more: add a rep, add a small amount of weight, or control the movement a little slower. "
        "Track your main lifts in your notes, and beat last week's number even by a tiny bit. "
        "Stay consistent and that slow progress compounds into a new physique. "
        "Follow to train with the science, not guesswork."
    ),
    "hashtags_extra": ["progressiveoverload", "musclegrowth", "gymscience", "hypertrophy"],
    "cta": "Follow to train with the science, not guesswork.",
},
# ---- 3. Home workout: no equipment chest/arms (home) ----
{
    "key": "home_upper", "label": "Home Upper Body", "emoji": HOME,
    "category": "home", "style": "punchy",
    "sub": "No equipment, no excuses",
    "stock_keywords": ["push ups home workout", "home workout living room",
                       "bodyweight exercise floor", "diamond push up", "pike push up home"],
    "hook": "NO GYM NEEDED",
    "script": (
        "No gym? No problem. Here's a full upper-body workout you can do at home with zero equipment. "
        "Start with standard push-ups for your chest. Can't do many? Drop to your knees and keep the form strict. "
        "Then diamond push-ups, hands together, to hammer your triceps. "
        "Next, pike push-ups with your hips high to hit your shoulders. "
        "Finish with a set of slow negatives, lowering as slowly as you can to build real strength. "
        "Three rounds, short rest, and your upper body is done. "
        "Follow for home workouts that actually work."
    ),
    "hashtags_extra": ["homeworkout", "nogym", "calisthenics", "pushups"],
},
# ---- 4. Comeback: getting back after a short break (comeback) ----
{
    "key": "comeback_short", "label": "Back After a Break", "emoji": BOLT,
    "category": "comeback", "style": "edu",
    "sub": "Returning after 1-2 weeks off",
    "stock_keywords": ["returning to gym workout", "light warm up gym",
                       "person entering gym", "dumbbell light workout", "motivated gym training"],
    "hook": "BACK IN THE GYM",
    "script": (
        "Took a week or two off? Here's exactly how to come back without wrecking yourself. "
        "First, don't try to lift what you did before. Your strength is still there, it just needs waking up. "
        "Start your first few sessions at around eighty percent of your old weights. "
        "Keep the reps a little higher and leave two or three reps in the tank on every set. "
        "Expect some soreness — that's normal, not a setback. "
        "Within a week or two you'll be right back to where you were, often stronger. "
        "The key is just to start. Follow for smart training."
    ),
    "hashtags_extra": ["gymmotivation", "comeback", "fitnesstips", "consistency"],
    "cta": "The key is just to start. Follow for smart training.",
},
# ---- 5. Legs ranked (ranked) ----
{
    "key": "ranked_legs", "label": "Leg Exercises Ranked", "emoji": TROPHY,
    "category": "ranked", "style": "punchy",
    "sub": "Top 3 moves for bigger legs",
    "stock_keywords": ["barbell squat gym", "romanian deadlift gym",
                       "leg press machine", "walking lunges gym", "leg workout quads"],
    "hook": "LEGS, RANKED",
    "script": (
        "The three best leg exercises, ranked. "
        "Number three: the walking lunge. It builds your quads and glutes while fixing left-to-right imbalances. "
        "Number two: the Romanian deadlift. The best move for strong, full hamstrings and glutes — feel the stretch and drive your hips. "
        "And number one: the squat. The king of leg exercises. Go as deep as you can control and nothing builds your whole lower body faster. "
        "Squat, hinge, lunge — that's a complete leg day. "
        "Follow for a new ranking every day."
    ),
    "hashtags_extra": ["legday", "squats", "legworkout", "ranked"],
},
# ---- 6. 60-day plan (plan) ----
{
    "key": "plan_60day", "label": "60-Day Transformation", "emoji": CLOCK,
    "category": "plan", "style": "edu",
    "sub": "How to change your body in 60 days",
    "stock_keywords": ["fitness transformation training", "meal prep healthy",
                       "calendar planning", "consistent gym workout", "healthy lifestyle"],
    "hook": "60 DAYS TO CHANGE",
    "script": (
        "Want a real change in sixty days? Here's the honest plan that works. "
        "First, train four days a week, hitting every muscle group twice. Push each set close to failure and add a little each week. "
        "Second, fix your food. Hit your protein — around two grams per kilo of bodyweight — and set your calories for your goal: a small deficit to lean down, a small surplus to build. "
        "Third, walk eight to ten thousand steps a day and sleep seven to eight hours, because that's when you recover. "
        "Do this consistently for sixty days and you won't just look different, you'll feel different. "
        "No shortcuts, just the basics done daily. "
        "Follow and start your sixty days today."
    ),
    "hashtags_extra": ["transformation", "60daychallenge", "fitnessplan", "fatloss"],
    "cta": "Follow and start your sixty days today.",
},
# ---- 7. Back ranked (ranked) ----
{
    "key": "ranked_back", "label": "Back Exercises Ranked", "emoji": TROPHY,
    "category": "ranked", "style": "punchy",
    "sub": "Top 3 moves for a wide back",
    "stock_keywords": ["pull up bar workout", "barbell row close up",
                       "lat pulldown gym", "seated cable row", "deadlift back muscles"],
    "hook": "BACK, RANKED",
    "script": (
        "The three best back exercises, ranked. "
        "Number three: the seated cable row. Perfect for mid-back thickness with a strong squeeze on every rep. "
        "Number two: the barbell row. A mass builder that trains your whole back when you row with your elbows, not your hands. "
        "And number one: the pull-up. Nothing builds that wide, V-taper back like pulling your own bodyweight. Can't do them yet? Use a band or the lat pulldown. "
        "Pull wide, row heavy, squeeze hard. "
        "Follow for a new ranking every day."
    ),
    "hashtags_extra": ["back", "pullups", "backday", "ranked"],
},
# ---- 8. How to grow your arms (howto) ----
{
    "key": "howto_arms", "label": "How to Grow Your Arms", "emoji": CHEST,
    "category": "howto", "style": "edu",
    "sub": "The right way to train arms",
    "stock_keywords": ["bicep curl dumbbell close up", "tricep pushdown cable",
                       "barbell curl gym", "hammer curl dumbbell", "arm workout veins"],
    "hook": "HOW TO: BIG ARMS",
    "script": (
        "Here's how to actually grow your arms, step by step. "
        "Step one: train your triceps first, because they're two-thirds of your arm. Use pushdowns and overhead extensions for a deep stretch. "
        "Step two: hit biceps from two angles — regular curls for the peak, and hammer curls for thickness and the forearm. "
        "Step three: slow every rep down and squeeze hard at the top. No swinging, full range. "
        "Step four: train arms twice a week and chase a few more reps or a little more weight each time. "
        "Control plus progression equals bigger arms. "
        "Follow for a how-to every single day."
    ),
    "hashtags_extra": ["arms", "biceps", "triceps", "howto"],
    "cta": "Follow for a how-to every single day.",
},
# ---- 9. Myth: lifting makes you bulky (myth) ----
{
    "key": "myth_bulky", "label": "Lifting Myths", "emoji": CROSS,
    "category": "myth", "style": "edu",
    "sub": "Lifting won't make you bulky",
    "stock_keywords": ["woman lifting weights gym", "toned workout gym",
                       "dumbbell training", "strength training female", "gym workout fit"],
    "hook": "MYTH BUSTED",
    "script": (
        "Myth: lifting weights makes you big and bulky. Let's bust it. "
        "Building large, bulky muscle takes years of heavy training and eating in a big calorie surplus on purpose. It does not happen by accident. "
        "What lifting actually does is build a lean, toned, strong-looking body, while burning fat and shaping your curves. "
        "That toned look everyone wants? That is literally muscle. You can't tone without building a little of it. "
        "So don't fear the weights. Lift, eat for your goal, and you'll look fit and athletic, not bulky. "
        "Follow to train on facts, not fear."
    ),
    "hashtags_extra": ["fitnessmyths", "mythbusting", "womensfitness", "strengthtraining"],
    "cta": "Follow to train on facts, not fear.",
},
# ---- 10. Before/after motivation (transformation) ----
{
    "key": "transform_discipline", "label": "Discipline Over Motivation", "emoji": CHART,
    "category": "transformation", "style": "punchy",
    "sub": "The real secret to results",
    "stock_keywords": ["sunrise running motivation", "hard gym training sweat",
                       "discipline workout", "early morning workout", "focused athlete gym"],
    "hook": "DISCIPLINE WINS",
    "script": (
        "Here's the truth behind every great transformation: it isn't motivation, it's discipline. "
        "Motivation shows up on the good days. Discipline is what drags you to the gym on the days you feel like doing nothing. "
        "The person who gets results isn't the most motivated — they're the one who shows up anyway, again and again. "
        "You won't feel ready every day. You won't always want it. Go anyway. "
        "Small, boring, consistent effort beats one perfect week every single time. "
        "Fall in love with the process, and the results take care of themselves. "
        "Follow for your daily push."
    ),
    "hashtags_extra": ["discipline", "gymmotivation", "mindset", "transformation"],
},
# ---- 11. Shoulders ranked (ranked) ----
{
    "key": "ranked_shoulders", "label": "Shoulder Exercises Ranked", "emoji": TROPHY,
    "category": "ranked", "style": "punchy",
    "sub": "Top 3 moves for round delts",
    "stock_keywords": ["overhead press barbell", "lateral raise dumbbell",
                       "shoulder workout gym", "arnold press dumbbell", "rear delt fly"],
    "hook": "SHOULDERS, RANKED",
    "script": (
        "The three best shoulder exercises, ranked. "
        "Number three: the rear-delt fly. The muscle everyone forgets, and the one that makes your shoulders look complete from the side. "
        "Number two: the overhead press. Your main strength and size builder for the front and middle of your delts. "
        "And number one: the lateral raise. The side delt is what gives you that wide, capped look — go light, lead with your elbows, and control it down. "
        "Press heavy, raise light, and never skip the rear. "
        "Follow for a new ranking every day."
    ),
    "hashtags_extra": ["shoulders", "delts", "lateralraise", "ranked"],
},
# ---- 12. Science: muscle recovery (science) ----
{
    "key": "science_recovery", "label": "How Muscles Recover", "emoji": BRAIN,
    "category": "science", "style": "edu",
    "sub": "Why rest builds muscle",
    "stock_keywords": ["person resting relaxing", "sleep bedroom calm",
                       "foam rolling recovery", "stretching recovery", "protein meal healthy"],
    "hook": "GROW WHILE YOU REST",
    "script": (
        "Here's the science most people ignore: you don't build muscle in the gym, you build it while you recover. "
        "When you train, you create tiny tears in your muscle fibers. The workout is just the signal. "
        "The actual repair and growth happen in the hours and days afterward, powered by protein, sleep, and rest. "
        "This is why hammering the same muscle every single day backfires — you never give it time to rebuild stronger. "
        "Give each muscle around forty-eight hours before you train it hard again. Sleep seven to nine hours. Hit your protein. "
        "Respect recovery and you'll grow faster than someone who never rests. "
        "Follow for training backed by science."
    ),
    "hashtags_extra": ["recovery", "musclegrowth", "gymscience", "restday"],
    "cta": "Follow for training backed by science.",
},
# ---- 13. Home lower body (home) ----
{
    "key": "home_legs", "label": "Home Leg Workout", "emoji": HOME,
    "category": "home", "style": "punchy",
    "sub": "Build legs with no weights",
    "stock_keywords": ["bodyweight squat home", "lunges home workout",
                       "home leg workout", "wall sit exercise", "jump squat home"],
    "hook": "LEGS AT HOME",
    "script": (
        "You can build serious legs at home with zero equipment. Here's how. "
        "Start with bodyweight squats, going slow and deep for high reps. "
        "Then reverse lunges, one leg at a time, to build each side evenly. "
        "Next, Bulgarian split squats with your back foot on a chair — brutal and effective. "
        "Finish with a wall sit, holding until your legs are on fire. "
        "The secret is reps and control: slow everything down and chase the burn. "
        "Three rounds and you won't miss the gym. "
        "Follow for home workouts that deliver."
    ),
    "hashtags_extra": ["homeworkout", "legday", "nogym", "bodyweight"],
},
# ---- 14. Comeback: long break (comeback) ----
{
    "key": "comeback_long", "label": "Back After Months Off", "emoji": BOLT,
    "category": "comeback", "style": "edu",
    "sub": "Returning after a long layoff",
    "stock_keywords": ["person starting gym", "beginner gym workout",
                       "light dumbbell training", "gym motivation return", "warm up stretching gym"],
    "hook": "RESTART STRONG",
    "script": (
        "Been away from the gym for months, or longer? Here's how to restart without hurting yourself or burning out. "
        "Forget where you used to be — your ego will want to chase it, and that's how people get injured. "
        "For the first two weeks, train light, keep reps moderate, and stop well before failure. Let your joints and tendons catch up to your muscles. "
        "Focus on simple full-body sessions, two or three times a week, hitting the big basics. "
        "Here's the good news: thanks to muscle memory, you'll regain your old strength and size far faster than it took to build the first time. "
        "Be patient for a few weeks and momentum takes over. "
        "Follow and let's rebuild together."
    ),
    "hashtags_extra": ["gymmotivation", "musclememory", "comeback", "beginner"],
    "cta": "Follow and let's rebuild together.",
},
# ---- 15. 90-day plan (plan) ----
{
    "key": "plan_90day", "label": "90-Day Dream Physique", "emoji": CLOCK,
    "category": "plan", "style": "edu",
    "sub": "Build your dream body in 90 days",
    "stock_keywords": ["fitness transformation gym", "healthy meal prep containers",
                       "consistent training workout", "progress tracking fitness", "athlete physique"],
    "hook": "90 DAYS, NEW YOU",
    "script": (
        "Ninety days is enough time to completely change how you look, if you do these four things right. "
        "One: lift weights four to five days a week on a simple push, pull, legs split, and get stronger over time. "
        "Two: eat for your goal. High protein always, with calories set for fat loss or muscle gain — pick one and commit. "
        "Three: do a little cardio and stay active daily. Ten thousand steps keeps fat loss moving without killing your gains. "
        "Four: sleep and recover, because your body changes while you rest, not while you scroll. "
        "Take a photo today, repeat this for ninety days, and the before-and-after will shock you. "
        "Follow and start day one now."
    ),
    "hashtags_extra": ["90daychallenge", "transformation", "fitnessplan", "dreamphysique"],
    "cta": "Follow and start day one now.",
},
# ---- 16. Myth: spot reduction (myth) ----
{
    "key": "myth_spotreduction", "label": "Belly Fat Myth", "emoji": CROSS,
    "category": "myth", "style": "edu",
    "sub": "You can't target fat loss",
    "stock_keywords": ["abs workout gym", "healthy food vegetables",
                       "person running cardio", "core training", "meal prep healthy"],
    "hook": "MYTH BUSTED",
    "script": (
        "Myth: doing endless crunches burns belly fat. Let's bust it. "
        "You cannot spot-reduce fat. Training a muscle does not burn the fat sitting on top of it. "
        "A thousand crunches will build your abs, but if they're hidden under fat, no one will ever see them. "
        "Fat comes off your whole body at once, in the order your genetics decide — and you lose it by being in a calorie deficit. "
        "So to see your abs: eat in a slight deficit, keep your protein high, lift weights, and stay active. "
        "Train abs like any muscle, but reveal them in the kitchen. "
        "Follow to train on facts, not myths."
    ),
    "hashtags_extra": ["fitnessmyths", "absworkout", "fatloss", "mythbusting"],
    "cta": "Follow to train on facts, not myths.",
},
# ---- 17. Compilation / remix-style best tips (compilation) ----
{
    "key": "compilation_tips", "label": "5 Gym Tips in 40 Seconds", "emoji": FILM,
    "category": "compilation", "style": "punchy",
    "sub": "Rapid-fire tips that actually work",
    "stock_keywords": ["fast gym workout montage", "intense training gym",
                       "dumbbell workout close up", "barbell lifting gym", "athlete training hard"],
    "hook": "5 TIPS, FAST",
    "script": (
        "Five gym tips in forty seconds. Go. "
        "One: control the lowering half of every rep. Slow negatives build more muscle than heavy swinging. "
        "Two: train close to failure. Leaving one or two reps in the tank, not ten. "
        "Three: progressive overload. Beat last week by a rep or a little weight, every single session. "
        "Four: hit your protein, around two grams per kilo of bodyweight, every day. "
        "Five: sleep seven to nine hours, because that's when muscle is actually built. "
        "Master these five and you're ahead of ninety percent of the gym. "
        "Follow for rapid tips every day."
    ),
    "hashtags_extra": ["gymtips", "fitnesstips", "workout", "gymhacks"],
},
# ---- 18. How to lose belly fat (howto) ----
{
    "key": "howto_fatloss", "label": "How to Lose Fat", "emoji": DROP,
    "category": "howto", "style": "edu",
    "sub": "Step-by-step fat loss",
    "stock_keywords": ["healthy food vegetables", "person walking outdoor",
                       "meal prep containers", "weighing food scale", "cooking healthy meal"],
    "hook": "HOW TO: LOSE FAT",
    "script": (
        "Here's how to lose fat, step by step, no gimmicks. "
        "Step one: eat in a small calorie deficit. Burn a little more than you eat — that's the only thing that actually loses fat. "
        "Step two: keep protein high to protect your muscle and stay full, so you lose fat, not muscle. "
        "Step three: lift weights three or four times a week, giving your body a reason to keep its muscle. "
        "Step four: walk every day. Steps burn more fat over time than punishing cardio. "
        "Step five: aim to lose around half a kilo a week — slow and steady stays off. "
        "Do these five and the fat comes off for good. "
        "Follow for a how-to every day."
    ),
    "hashtags_extra": ["fatloss", "howto", "weightloss", "caloriedeficit"],
    "cta": "Follow for a how-to every day.",
},
]

# --- Paths ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

# --- Voice (edge-tts neural voice; free, no key) ---
TTS_VOICE = "en-US-ChristopherNeural"   # confident male; emits word timings for captions
TTS_RATE = "+8%"                        # punchy pace for motivation
TTS_PITCH = "+0Hz"
# Backup English voices tried (in order) if the primary 403s / fails.
TTS_FALLBACK_VOICES = ["en-US-GuyNeural", "en-US-AndrewMultilingualNeural",
                       "en-US-EricNeural", "en-GB-RyanNeural"]

# YouTube category IDs per content category (used by the YouTube uploader).
# 17 = Sport, 26 = Howto & Style, 27 = Education
YT_CATEGORY = {
    "workout": "17", "warmup": "17", "stretch": "17", "cardio": "17",
    "mobility": "27", "anatomy": "27", "recovery": "27", "diet": "26",
    "ranked": "17", "home": "17", "comeback": "17", "plan": "17",
    "transformation": "17", "compilation": "17",
    "science": "27", "myth": "27", "howto": "26",
}

# ===== topics =====
"""Full rotation: walk the whole CONTENT library, two items per day.

Part 1 (morning) and Part 2 (evening) take consecutive entries, so the two
daily posts are always different, and the whole library cycles over time.
"""

def current_part():
    """Part 1 in the morning, Part 2 in the evening.
    Controlled by env VIDEO_PART if set (workflow), else derived from UTC hour."""
    env = os.environ.get("VIDEO_PART", "").strip()
    if env in ("1", "2"):
        return int(env)
    hour = datetime.datetime.utcnow().hour
    return 1 if hour < 11 else 2  # <11:00 UTC = morning IST, else evening

def pick_content():
    """Return (entry, part). Rotates through the entire CONTENT library."""
    part = current_part()
    doy = datetime.date.today().timetuple().tm_yday  # 1..366
    idx = (doy * 2 + (part - 1)) % len(CONTENT)
    entry = CONTENT[idx]
    print(f"[topics] {entry['label']} | {entry['category']} | Part {part} "
          f"| idx {idx}/{len(CONTENT)}")
    return entry, part

# ===== script_gen =====
"""Assemble SEO metadata (title, description, hashtags, tags) around each
content entry's ready-made script. Deterministic, no API key needed.
"""

BASE_TAGS = ["gym", "fitness", "workout", "gymtok", "fitfam", "bodybuilding",
             "gymmotivation", "fitnessmotivation", "training", "shorts", "reels"]

# Category-level hashtags mixed into every post of that category.
CATEGORY_HASHTAGS = {
    "workout": ["workout", "gymmotivation", "bodybuilding"],
    "warmup": ["warmup", "gymtips", "mobility"],
    "stretch": ["stretching", "flexibility", "recovery"],
    "mobility": ["mobility", "flexibility", "gymtips"],
    "diet": ["nutrition", "diet", "healthyeating"],
    "anatomy": ["fitnesstips", "hypertrophy", "gymscience"],
    "cardio": ["cardio", "fatloss", "conditioning"],
    "recovery": ["recovery", "restday", "wellness"],
    "ranked": ["gymtips", "workout", "bestexercises"],
    "science": ["gymscience", "hypertrophy", "fitnesstips"],
    "home": ["homeworkout", "calisthenics", "nogym"],
    "comeback": ["gymmotivation", "consistency", "fitnessjourney"],
    "plan": ["fitnessplan", "transformation", "workoutplan"],
    "transformation": ["motivation", "discipline", "transformation"],
    "myth": ["fitnessmyths", "mythbusting", "gymfacts"],
    "howto": ["howto", "gymtips", "fitnesstips"],
    "compilation": ["gymtips", "gymhacks", "fitnesstips"],
}

DEFAULT_CTA = "If this helped, like, share, and subscribe for your daily dose."

def generate(entry, part):
    label = entry["label"]
    emoji = entry.get("emoji", CHEST)
    sub = entry.get("sub", "")
    script = entry["script"]
    hook = entry.get("hook", label.upper())
    cta = entry.get("cta", DEFAULT_CTA)

    # Title: label + short subtitle, platform tags appended.
    title = f"{label} {emoji} | {sub} #shorts #fitness"
    if len(title) > 100:
        title = title[:100]

    # Hashtags: topic-specific + category + a few base, de-duplicated.
    hashtags = list(dict.fromkeys(
        entry.get("hashtags_extra", [])
        + CATEGORY_HASHTAGS.get(entry["category"], [])
        + ["gym", "fitness", "shorts", "reels", "fyp"]
    ))[:15]
    tag_line = " ".join("#" + h for h in hashtags)

    description = (
        f"{label} — {sub}.\n\n"
        f"{script}\n\n"
        f"{cta} Part 1 in the morning, Part 2 at night.\n\n{tag_line}"
    )

    # YouTube search tags (plain keywords, not #hashtags).
    tags = list(dict.fromkeys(
        [entry["key"].replace("_", " "), label.lower(), entry["category"],
         "fitness", "workout", "gym tips"] + BASE_TAGS
    ))[:15]

    print(f"[script] {label} Part {part} | {title[:50]}...")
    return {
        "hook": hook,
        "title": title,
        "script": script,
        "description": description,
        "keywords": entry["stock_keywords"],
        "hashtags": hashtags,
        "tags": tags,
        "category_id": YT_CATEGORY.get(entry["category"], "17"),
    }

# ===== captions =====
"""Build animated, word-by-word captions in ASS format ("Hormozi" style)."""

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
        hook_text = (r"{\fad(150,250)\fscx60\fscy60\t(0,220,\fscx104\fscy104)"
                     r"\t(220,360,\fscx100\fscy100)}" + hook.upper())
        lines.append(
            f"Dialogue: 0,{_ts(0.0)},{_ts(2.6)},Hook,,0,0,0,,{hook_text}\n"
        )
    for group in _phrase_groups(words):
        for idx, w in enumerate(group):
            start = w["start"]
            end = w["end"]
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
"""Voiceover with edge-tts (free Microsoft neural voices), returning the audio
plus real per-word timings so captions can be animated word-by-word.

Robust against Microsoft's intermittent 403 blocks: the primary voice is
retried, then a list of backup voices is tried, and finally gTTS is used as a
last resort so a single outage can never kill the whole run.
"""

async def _synthesize(text, mp3_path, voice):
    communicate = edge_tts.Communicate(text, voice, rate=TTS_RATE, pitch=TTS_PITCH)
    words = []
    with open(mp3_path, "wb") as audio_file:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_file.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                start = chunk["offset"] / 1e7   # 100-ns -> seconds
                dur = chunk["duration"] / 1e7
                words.append({"text": chunk["text"], "start": start,
                              "end": start + dur})
    return words

def _gtts_fallback(text, mp3_path):
    """Last-resort voiceover via gTTS (Google). Returns [] (no word timings),
    so captions fall back to even spacing."""
    from gtts import gTTS
    gTTS(text=text, lang="en", slow=False).save(mp3_path)
    return []

def make_voiceover(text, out_dir):
    """Return (mp3_path, words) where words is a list of {text,start,end}.
    Tries the primary edge-tts voice, then backups, then gTTS."""
    os.makedirs(out_dir, exist_ok=True)
    mp3_path = os.path.join(out_dir, "mp3")
    voices = [TTS_VOICE] + TTS_FALLBACK_VOICES
    for voice in voices:
        for attempt in range(1, 4):   # up to 3 tries per voice
            try:
                words = asyncio.run(_synthesize(text, mp3_path, voice))
                if os.path.exists(mp3_path) and os.path.getsize(mp3_path) > 2000:
                    print(f"[voice] Voiceover ready ({voice}) with {len(words)} word timings.")
                    return mp3_path, words
                print(f"[voice] {voice} produced empty audio (try {attempt}); retrying.")
            except Exception as e:  # noqa: BLE001
                print(f"[voice] {voice} failed try {attempt} ({e}).")
                time.sleep(2 * attempt)
    # Every edge-tts voice failed (e.g. a Microsoft 403). Fall back to gTTS.
    try:
        print("[voice] edge-tts unavailable; falling back to gTTS.")
        words = _gtts_fallback(text, mp3_path)
        print("[voice] gTTS voiceover ready (even-spaced captions).")
        return mp3_path, words
    except Exception as e:  # noqa: BLE001
        print(f"[voice] gTTS fallback also failed ({e}).")
        raise

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
    ((18, 22, 48), (86, 44, 120)),    # indigo -> violet
    ((10, 30, 40), (14, 92, 110)),    # deep teal
    ((40, 16, 32), (150, 46, 60)),    # wine -> rose
    ((12, 28, 20), (30, 100, 70)),    # forest
    ((26, 24, 18), (120, 84, 30)),    # amber
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
        col = (top_arr[None, :] + (bottom_arr - top_arr)[None, :] * t)  # (H,3)
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
vertical short with ffmpeg."""

def _run(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

def _probe_duration(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True, check=True)
    return float(out.stdout.strip())

def generate_ambient_music(duration, out_path, work_dir):
    """Synthesize a soft, calming ambient pad in-code (no external files needed)."""
    import wave as wavmod
    sr = 44100
    n = int(duration * sr)
    t = np.linspace(0, duration, n, endpoint=False).astype(np.float32)
    freqs = [110.0, 164.81, 220.0, 277.18]  # A2, E3, A3, C#4 — warm major
    audio = np.zeros(n, dtype=np.float32)
    for i, f in enumerate(freqs):
        detune = 1.0 + 0.0015 * (i - 1.5)
        vib = 1.0 + 0.002 * np.sin(2 * np.pi * 0.07 * t + i)
        wave = np.sin(2 * np.pi * f * detune * vib * t)
        wave += 0.22 * np.sin(2 * np.pi * 2 * f * detune * t)  # soft harmonic
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
    ("0x030814", "0x0a2540", "0x0e7c8c"),  # deep navy -> cyan (techy)
    ("0x05010f", "0x1b1050", "0x0e5c8c"),  # black-violet -> electric blue
    ("0x00110f", "0x073b3a", "0x0aa0a0"),  # dark teal -> aqua
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
        seg_dur = duration / n + 0.6  # pad for crossfades
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

Run: python dve.py
Produces a finished vertical video in ./output plus a metadata JSON
(title, description, hashtags) and auto-posts to YouTube / Instagram.
"""

def run():
    stamp = datetime.date.today().isoformat()
    day_dir = os.path.join(OUTPUT_DIR, stamp)
    work_dir = os.path.join(day_dir, "work")
    os.makedirs(work_dir, exist_ok=True)

    # 1) today's content item (full library rotation) + part (1=morning, 2=evening)
    entry, part = pick_content()

    # 2) script + SEO metadata
    content = generate(entry, part)

    # 3) voiceover (+ real word timings) and animated captions
    mp3_path, words = voice_step(content["script"], work_dir)
    if not words:
        cap_dur = _probe_duration(mp3_path)
        words = even_word_times(content["script"], cap_dur)
        print(f"[captions] no TTS word timings; using {len(words)} evenly-spaced.")
    ass_path = os.path.join(work_dir, "ass")
    build_ass(words, ass_path, hook=content.get("hook"))

    # 4) visuals
    assets = get_visuals(content["keywords"], work_dir)

    # 5) background music — a soft ambient bed sized to the voiceover length
    vdur = _probe_duration(mp3_path)
    music_path = pick_music(work_dir, vdur)

    # 6) assemble (part- and key-tagged filename so posts don't clash)
    out_path = os.path.join(day_dir, f"video_{stamp}_part{part}_{entry['key']}.mp4")
    build_video(assets, mp3_path, ass_path, out_path, work_dir,
                music_path=music_path)

    # 7) SEO metadata for the uploaders
    meta = {
        "date": stamp,
        "content_key": entry["key"],
        "category": entry["category"],
        "label": entry["label"],
        "part": part,
        "title": content["title"],
        "description": content["description"],
        "hashtags": content["hashtags"],
        "tags": content["tags"],
        "category_id": content["category_id"],
        "video_path": out_path,
    }
    meta_path = os.path.join(day_dir, f"meta_part{part}.json")
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)

    print(f"\n[main] Done. Video: {out_path}\n[main] Meta: {meta_path}")

    # 8) auto-post to YouTube (only if the 3 YT secrets are set; skips otherwise)
    try:
        upload_youtube(out_path, meta)
    except Exception as e:  # noqa: BLE001
        print(f"[youtube] upload failed ({e}); video still saved as an artifact.")

    # 9) auto-post to Instagram Reels (only if the 2 IG secrets are set)
    try:
        upload_instagram(out_path, meta)
    except Exception as e:  # noqa: BLE001
        print(f"[instagram] upload failed ({e}); video still saved as an artifact.")

    return meta

IG_API = "https://graph.instagram.com/v21.0"

def _upload_public(video_path):
    ua = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"}
    fname = os.path.basename(video_path)

    def litterbox():
        with open(video_path, "rb") as f:
            r = requests.post("https://litterbox.catbox.moe/resources/internals/api.php",
                              data={"reqtype": "fileupload", "time": "24h"},
                              files={"fileToUpload": (fname, f, "video/mp4")},
                              headers=ua, timeout=180)
        return r.text.strip() if r.ok and r.text.strip().startswith("http") else None

    def catbox():
        with open(video_path, "rb") as f:
            r = requests.post("https://catbox.moe/user/api.php",
                              data={"reqtype": "fileupload"},
                              files={"fileToUpload": (fname, f, "video/mp4")},
                              headers=ua, timeout=180)
        return r.text.strip() if r.ok and r.text.strip().startswith("http") else None

    def tmpfiles():
        with open(video_path, "rb") as f:
            r = requests.post("https://tmpfiles.org/api/v1/upload",
                              files={"file": (fname, f, "video/mp4")},
                              headers=ua, timeout=180)
        if r.ok:
            u = (r.json().get("data") or {}).get("url", "")
            if u.startswith("http"):
                return u.replace("tmpfiles.org/", "tmpfiles.org/dl/", 1)
        return None

    def zerox():
        with open(video_path, "rb") as f:
            r = requests.post("https://0x0.st",
                              files={"file": (fname, f, "video/mp4")},
                              headers=ua, timeout=180)
        return r.text.strip() if r.ok and r.text.strip().startswith("http") else None

    for name, fn in [("litterbox", litterbox), ("catbox", catbox),
                     ("tmpfiles", tmpfiles), ("0x0", zerox)]:
        for attempt in (1, 2):
            try:
                link = fn()
                if link and link.startswith("http"):
                    print(f"[ig] public url ({name}): {link}")
                    return link
                print(f"[ig] {name} no url (try {attempt})")
            except Exception as e:  # noqa: BLE001
                print(f"[ig] {name} failed try {attempt} ({e})")
    return None

def upload_instagram(video_path, meta):
    ig_user = os.environ.get("IG_USER_ID", "").strip()
    ig_token = os.environ.get("IG_ACCESS_TOKEN", "").strip()
    if not (ig_user and ig_token):
        print("[ig] IG secrets not set - skipping Instagram (video kept as artifact).")
        return None
    public_url = _upload_public(video_path)
    if not public_url:
        print("[ig] no public URL for the mp4 - skipping Instagram.")
        return None
    caption = meta["description"][:2100]
    try:
        j = requests.post(f"{IG_API}/{ig_user}/media",
                          data={"media_type": "REELS", "video_url": public_url,
                                "caption": caption, "access_token": ig_token},
                          timeout=60).json()
        cid = j.get("id")
        if not cid:
            print(f"[ig] container create failed: {j}")
            return None
        print(f"[ig] container {cid}; waiting for processing...")
    except Exception as e:  # noqa: BLE001
        print(f"[ig] container error ({e})")
        return None
    ready = False
    for attempt in range(20):
        time.sleep(15)
        try:
            s = requests.get(f"{IG_API}/{cid}",
                             params={"fields": "status_code", "access_token": ig_token},
                             timeout=30).json()
            status = s.get("status_code")
            print(f"[ig] status[{attempt}]: {status}")
            if status == "FINISHED":
                ready = True; break
            if status == "ERROR":
                print(f"[ig] container errored: {s}"); return None
        except Exception as e:  # noqa: BLE001
            print(f"[ig] status poll error ({e})")
    if not ready:
        print("[ig] container not ready in time - skipping publish.")
        return None
    try:
        j = requests.post(f"{IG_API}/{ig_user}/media_publish",
                          data={"creation_id": cid, "access_token": ig_token},
                          timeout=60).json()
        mid = j.get("id")
        print(f"[ig] DONE -> published Reel {mid}" if mid else f"[ig] publish failed: {j}")
        return mid
    except Exception as e:  # noqa: BLE001
        print(f"[ig] publish error ({e})")
        return None

def upload_youtube(video_path, meta):
    """Upload the finished video to YouTube as a public Short.
    Needs GitHub Secrets: YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN.
    If any is missing, it skips quietly so the run still succeeds."""
    cid = os.environ.get("YT_CLIENT_ID", "").strip()
    csec = os.environ.get("YT_CLIENT_SECRET", "").strip()
    rtok = os.environ.get("YT_REFRESH_TOKEN", "").strip()
    if not (cid and csec and rtok):
        print("[youtube] YT secrets not set - skipping upload (video kept as artifact).")
        return None

    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    creds = Credentials(
        token=None,
        refresh_token=rtok,
        client_id=cid,
        client_secret=csec,
        token_uri="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/youtube.upload"],
    )
    youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)

    title = meta["title"][:100]
    desc = meta["description"][:4900]
    if "#shorts" not in desc.lower():
        desc = desc + "\n\n#Shorts"
    tags = meta.get("tags", [])[:15]
    category_id = meta.get("category_id", "17")

    body = {
        "snippet": {
            "title": title,
            "description": desc,
            "tags": tags,
            "categoryId": category_id,
            "defaultLanguage": "en",
            "defaultAudioLanguage": "en",
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        },
    }
    media = MediaFileUpload(video_path, chunksize=-1, resumable=True,
                            mimetype="video/mp4")
    print(f"[youtube] uploading '{title[:50]}'...")
    req = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    resp = req.execute()
    vid = resp.get("id")
    print(f"[youtube] DONE -> https://youtube.com/shorts/{vid}")
    return vid

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
