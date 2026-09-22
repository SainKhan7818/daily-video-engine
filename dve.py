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
TARGET_SECONDS = 42          # aim for a ~40s short/reel (workouts); edu runs longer
FONT_SIZE = 64

# ---------------------------------------------------------------------------
# FITNESS CHANNEL — broad content library (full rotation, both daily slots).
#
# The engine no longer posts only a body-part split. It rotates through the
# whole library below, two items per day (Part 1 morning, Part 2 evening),
# walking the list so consecutive posts are always different and the whole set
# cycles over ~2 weeks. Categories covered:
#   workout   - body-part training (chest, back, legs, ... )   [punchy]
#   warmup    - pre-workout warmups                             [punchy]
#   stretch   - post-workout stretching / flexibility           [punchy]
#   mobility  - joint mobility routines                         [edu]
#   diet      - nutrition / diet                                [edu]
#   anatomy   - muscle anatomy & how a movement works           [edu]
#   cardio    - HIIT / conditioning / zone-2                    [mixed]
#   recovery  - rest, sleep, recovery                           [edu]
#
# Each entry:
#   key, label, emoji, category, style ("punchy" | "edu")
#   sub            - short subtitle used in the title/description
#   stock_keywords - Pexels search terms for background footage
#   hook           - short ALL-CAPS title-card line
#   script         - the full voiceover text
#   hashtags_extra - topic-specific hashtags (base tags added automatically)
# The list is interleaved (a workout, then a non-workout, ...) so each day's
# two posts feel varied.
# ---------------------------------------------------------------------------

CHEST = "\U0001F4AA"; FIRE = "\U0001F525"; LEG = "\U0001F9B5"; LIFT = "\U0001F3CB"
BOLT = "\U000026A1"; BROC = "\U0001F966"; BRAIN = "\U0001F9E0"; STRETCH = "\U0001F938"
RUN = "\U0001F3C3"; SLEEP = "\U0001F634"; MEAT = "\U0001F357"; DROP = "\U0001F4A7"

CONTENT = [
    # ---- 1. Chest (workout) ----
    {
        "key": "chest", "label": "Chest Day", "emoji": CHEST,
        "category": "workout", "style": "punchy",
        "sub": "2 pressing moves for a bigger chest",
        "stock_keywords": ["bench press gym close up", "push up workout",
            "incline dumbbell press", "chest workout gym", "cable chest fly"],
        "hook": "CHEST DAY",
        "script": (
            "It's chest day, and here's what most people get wrong. "
            "Start with a heavy press while you're fresh — flat or incline, barbell or dumbbell. "
            "Lower the weight slow, feel the stretch across your chest, then drive up with power. "
            "Follow it with a fly or a cable crossover to squeeze the muscle at the top. "
            "Leave one or two reps in the tank, and add a little weight each week. "
            "Do this right and you'll feel your chest growing within the first month. "
            "Follow for a new session every single day."
        ),
        "hashtags_extra": ["chest", "chestday", "pushday", "benchpress"],
    },
    # ---- 2. Pre-workout warmup (warmup) ----
    {
        "key": "warmup_full", "label": "Pre-Workout Warmup", "emoji": BOLT,
        "category": "warmup", "style": "punchy",
        "sub": "5-minute warmup before you lift",
        "stock_keywords": ["athlete warm up gym", "dynamic stretching workout",
            "jumping jacks exercise", "arm circles warm up", "treadmill light jog"],
        "hook": "WARM UP FIRST",
        "script": (
            "Never walk in and lift cold — this is the five-minute warmup that protects you. "
            "Start with two minutes of light cardio to raise your heart rate and body temperature. "
            "Then move through dynamic stretches: arm circles, leg swings, hip openers, and bodyweight squats. "
            "Finish with two light warmup sets of your first exercise before you load it up. "
            "This wakes up your muscles, primes your joints, and lets you lift heavier with less risk. "
            "Skip it and you're rolling the dice on an injury. "
            "Save this and warm up right before every session."
        ),
        "hashtags_extra": ["warmup", "mobility", "injuryprevention", "gymtips"],
    },
    # ---- 3. Back (workout) ----
    {
        "key": "back", "label": "Back Day", "emoji": FIRE,
        "category": "workout", "style": "punchy",
        "sub": "The pulls that build a wide, strong back",
        "stock_keywords": ["pull up bar workout", "lat pulldown gym",
            "barbell row close up", "deadlift back muscles", "seated cable row"],
        "hook": "BACK DAY",
        "script": (
            "Back day builds the frame that makes you look strong from every angle. "
            "Start with a vertical pull — pull-ups or a lat pulldown — to widen your back. "
            "Then row: a barbell row or a cable row to build thickness through the middle. "
            "Here's the key most people miss — pull with your elbows, not your hands, and squeeze your shoulder blades together at the end. "
            "Control the weight on the way back so your lats do the work, not your arms. "
            "Two pulls, two rows, and you've hit everything. "
            "Follow for your daily workout."
        ),
        "hashtags_extra": ["back", "backday", "pullday", "lats"],
    },
    # ---- 4. Post-workout stretch (stretch) ----
    {
        "key": "stretch_full", "label": "Post-Workout Stretch", "emoji": STRETCH,
        "category": "stretch", "style": "punchy",
        "sub": "Cool-down stretch after training",
        "stock_keywords": ["person stretching gym", "cool down stretching",
            "yoga stretch floor", "hamstring stretch", "shoulder stretch"],
        "hook": "COOL DOWN",
        "script": (
            "Don't just drop the weights and leave — this cool-down helps you recover faster. "
            "Hold each stretch for thirty seconds and breathe slowly, never bouncing. "
            "Stretch the muscles you just trained: chest in a doorway, lats overhead, hamstrings and hip flexors after legs. "
            "Static stretching after a workout helps your muscles relax and can ease next-day soreness. "
            "It also keeps you flexible, so your joints move through a full range for years to come. "
            "Five minutes now saves you a stiff, sore tomorrow. "
            "Save this and stretch after every session."
        ),
        "hashtags_extra": ["stretching", "flexibility", "cooldown", "recovery"],
    },
    # ---- 5. Legs (workout) ----
    {
        "key": "legs", "label": "Leg Day", "emoji": LEG,
        "category": "workout", "style": "punchy",
        "sub": "Why you can't skip leg day",
        "stock_keywords": ["barbell squat gym", "leg press machine",
            "walking lunges gym", "leg workout quads", "romanian deadlift"],
        "hook": "LEG DAY",
        "script": (
            "Leg day is the one day you can't skip, and here's why. "
            "Your legs are the biggest muscles in your body, so training them releases the hormones that grow your whole physique. "
            "Start with a squat — the king of leg exercises — going as deep as you can control. "
            "Then hit a hinge like a Romanian deadlift for your hamstrings and glutes. "
            "Finish with lunges or a leg press, and never forget your calves. "
            "Push hard here and everything else grows faster. "
            "Follow for a new muscle group every day."
        ),
        "hashtags_extra": ["legday", "squats", "legworkout", "quads"],
    },
    # ---- 6. Protein / diet (diet, edu) ----
    {
        "key": "diet_protein", "label": "Protein Explained", "emoji": MEAT,
        "category": "diet", "style": "edu",
        "sub": "How much protein you actually need",
        "stock_keywords": ["healthy protein food", "chicken breast meal prep",
            "eggs protein breakfast", "protein shake gym", "salmon healthy meal"],
        "hook": "PROTEIN 101",
        "script": (
            "If you train hard but never grow, protein is usually the missing piece. "
            "When you lift, you create tiny tears in your muscle fibers. Protein is the raw material your body uses to repair them bigger and stronger. "
            "A simple target that works for most people is around 1.6 to 2.2 grams of protein per kilogram of bodyweight, every day. "
            "So if you weigh seventy kilos, that's roughly a hundred and twenty to a hundred and fifty grams. "
            "Spread it across your meals — aim for twenty to forty grams each time — instead of cramming it all into one. "
            "Good sources are chicken, eggs, fish, lean beef, Greek yogurt, lentils, tofu, and a scoop of whey if you fall short. "
            "Hit your protein consistently and your training finally starts paying off. "
            "Follow for simple nutrition that actually works."
        ),
        "hashtags_extra": ["protein", "nutrition", "diet", "mealprep"],
        "cta": "Follow for simple nutrition that actually works.",
    },
    # ---- 7. Shoulders (workout) ----
    {
        "key": "shoulders", "label": "Shoulder Day", "emoji": LIFT,
        "category": "workout", "style": "punchy",
        "sub": "Build round, capped shoulders",
        "stock_keywords": ["overhead press barbell", "lateral raise dumbbell",
            "shoulder workout gym", "arnold press dumbbell", "front raise gym"],
        "hook": "SHOULDER DAY",
        "script": (
            "Round, capped shoulders are what make you look wide and athletic in any shirt. "
            "Start with an overhead press — barbell or dumbbell — to build size and strength across the front and middle. "
            "Then hammer lateral raises, because the side delt is what actually gives you width. "
            "Go light, lead with your elbows, and control the weight down slowly — no swinging. "
            "Finish with some rear-delt work like reverse flyes for balanced, healthy shoulders. "
            "Most people press plenty but neglect the sides and rear — don't be one of them. "
            "Follow for your daily session."
        ),
        "hashtags_extra": ["shoulders", "delts", "shoulderworkout", "pushday"],
    },
    # ---- 8. Muscle contraction (anatomy, edu) ----
    {
        "key": "anatomy_contraction", "label": "How Muscles Work", "emoji": BRAIN,
        "category": "anatomy", "style": "edu",
        "sub": "Concentric vs eccentric explained",
        "stock_keywords": ["bicep curl close up muscle", "muscle flexing gym",
            "slow motion weight lifting", "anatomy muscle fitness", "dumbbell curl form"],
        "hook": "HOW MUSCLES MOVE",
        "script": (
            "Understand how a muscle actually works and you'll train smarter for the rest of your life. "
            "Every rep has two halves. When your muscle shortens under load — like curling the weight up — that's the concentric phase, and it's the part everyone focuses on. "
            "But when the muscle lengthens under load — lowering the weight down — that's the eccentric phase, and it's where a huge amount of your growth actually happens. "
            "Most people rush the lowering part and waste it. Instead, take two to three seconds to lower every weight with control. "
            "Your muscles are made of thousands of tiny fibers that slide together to create force, and controlling both halves of the rep recruits more of them. "
            "So slow down the negative, feel the target muscle stretch and contract, and stop swinging the weight around. "
            "Control beats ego every single time. "
            "Follow to actually understand your training."
        ),
        "hashtags_extra": ["anatomy", "musclegrowth", "hypertrophy", "formcheck"],
        "cta": "Follow to actually understand your training.",
    },
    # ---- 9. Arms (workout) ----
    {
        "key": "arms", "label": "Arm Day", "emoji": CHEST,
        "category": "workout", "style": "punchy",
        "sub": "Bigger biceps and triceps",
        "stock_keywords": ["bicep curl dumbbell close up", "tricep pushdown cable",
            "barbell curl gym", "arm workout veins", "hammer curl dumbbell"],
        "hook": "ARM DAY",
        "script": (
            "Want bigger arms? Then stop only training biceps. "
            "Your triceps are two-thirds of your upper arm, so they add the most size. "
            "Hit them with pushdowns and overhead extensions, chasing a deep stretch and a hard squeeze. "
            "Then train biceps with curls — barbell, dumbbell, and hammer curls to hit them from every angle. "
            "The secret is control: no swinging, full range, and a real squeeze at the top of every rep. "
            "Keep the reps a little higher and chase the pump. "
            "Follow for a new workout every day."
        ),
        "hashtags_extra": ["arms", "biceps", "triceps", "armday"],
    },
    # ---- 10. Hip mobility (mobility, edu) ----
    {
        "key": "mobility_hips", "label": "Hip Mobility", "emoji": STRETCH,
        "category": "mobility", "style": "edu",
        "sub": "Fix tight hips for deeper squats",
        "stock_keywords": ["hip mobility stretch", "deep squat mobility",
            "hip flexor stretch floor", "yoga hip opener", "mobility drill gym"],
        "hook": "OPEN YOUR HIPS",
        "script": (
            "If you sit all day, your hips are probably tight — and that's wrecking your squats and your lower back. "
            "Tight hips force your spine to round and your knees to cave, which robs your lifts and invites injury. "
            "Here's a simple routine to fix it. Start with the deep squat hold: sink to the bottom of a squat and gently push your knees out for thirty seconds. "
            "Next, the couch stretch to open your hip flexors — hold each side for about a minute. "
            "Add ninety-ninety hip rotations on the floor to free up how your hips turn. "
            "Then finish with a few slow bodyweight squats to lock in the new range. "
            "Do this a few times a week and your squat depth, posture, and comfort all improve. "
            "Follow for mobility that keeps you training for life."
        ),
        "hashtags_extra": ["mobility", "hipmobility", "flexibility", "squat"],
        "cta": "Follow for mobility that keeps you training for life.",
    },
    # ---- 11. Core / abs (workout) ----
    {
        "key": "core", "label": "Core & Abs", "emoji": FIRE,
        "category": "workout", "style": "punchy",
        "sub": "Train abs the right way",
        "stock_keywords": ["abs workout gym", "plank exercise", "hanging leg raise",
            "core training athlete", "cable crunch"],
        "hook": "CORE DAY",
        "script": (
            "Your abs are a muscle, so train them with real resistance, not a thousand tiny crunches. "
            "Start with hanging leg raises or lying leg raises for the lower abs. "
            "Then add a weighted movement like a cable crunch, controlling the squeeze on every rep. "
            "Finish with planks and anti-rotation holds to build a core that protects your spine under heavy lifts. "
            "But remember — abs are revealed in the kitchen. You need a lean diet for them to show. "
            "Train them two or three times a week, and let a calorie deficit do the rest. "
            "Follow for your daily workout."
        ),
        "hashtags_extra": ["abs", "core", "sixpack", "absworkout"],
    },
    # ---- 12. HIIT (cardio, punchy) ----
    {
        "key": "cardio_hiit", "label": "HIIT Cardio", "emoji": RUN,
        "category": "cardio", "style": "punchy",
        "sub": "Burn fat in 15 minutes",
        "stock_keywords": ["hiit training intense", "sprint running athlete",
            "burpees workout", "battle ropes gym", "jump squats exercise"],
        "hook": "HIIT IT HARD",
        "script": (
            "Short on time but want to torch fat? This is where HIIT wins. "
            "HIIT means high-intensity intervals — you go all-out for a short burst, then rest, and repeat. "
            "Try thirty seconds hard, thirty seconds easy, for ten to fifteen rounds. "
            "Use anything: sprints, a bike, jump rope, burpees, or battle ropes. "
            "The intense bursts spike your heart rate and keep your body burning calories even after you stop. "
            "Just two or three sessions a week is plenty — more isn't better here. "
            "Push hard, recover, repeat. "
            "Follow for training that fits your schedule."
        ),
        "hashtags_extra": ["hiit", "cardio", "fatloss", "conditioning"],
    },
    # ---- 13. Glutes (workout) ----
    {
        "key": "glutes", "label": "Glute Day", "emoji": FIRE,
        "category": "workout", "style": "punchy",
        "sub": "Build stronger glutes",
        "stock_keywords": ["hip thrust gym", "glute bridge exercise",
            "barbell hip thrust", "cable kickback glutes", "bulgarian split squat"],
        "hook": "GLUTE DAY",
        "script": (
            "Strong glutes aren't just about looks — they power every lift and protect your lower back. "
            "The best glute builder is the hip thrust, so start there and drive through your heels, squeezing hard at the top. "
            "Then add Bulgarian split squats to train each side and fix imbalances. "
            "Finish with cable kickbacks or glute bridges for a deep contraction. "
            "The key is squeezing your glutes at the top of every rep — mind-muscle connection matters here more than heavy weight. "
            "Train them twice a week and progress the load. "
            "Follow for your daily session."
        ),
        "hashtags_extra": ["glutes", "hipthrust", "gluteworkout", "legday"],
    },
    # ---- 14. Pre-workout meal (diet, edu) ----
    {
        "key": "diet_preworkout", "label": "Pre-Workout Meal", "emoji": BROC,
        "category": "diet", "style": "edu",
        "sub": "What to eat before you train",
        "stock_keywords": ["healthy meal rice chicken", "banana pre workout",
            "oatmeal breakfast bowl", "meal prep healthy", "smoothie fruit"],
        "hook": "EAT TO PERFORM",
        "script": (
            "What you eat before training decides how much energy and strength you'll have. "
            "Aim to eat a proper meal about one to two hours before you lift. "
            "Focus on two things: carbs for energy and protein to protect your muscle. "
            "Good options are rice with chicken, oats with yogurt, or a banana with a protein shake. "
            "Carbs top up the fuel your muscles burn during hard sets, so you can push more reps and lift heavier. "
            "Keep fats and heavy fiber lower right before training, since they slow digestion and can leave you feeling sluggish. "
            "If you're short on time, even a banana and a shake fifteen minutes before is far better than training on empty. "
            "Fuel the work, and the work pays you back. "
            "Follow for nutrition made simple."
        ),
        "hashtags_extra": ["preworkout", "nutrition", "diet", "energy"],
        "cta": "Follow for nutrition made simple.",
    },
    # ---- 15. Full-body (workout) ----
    {
        "key": "fullbody", "label": "Full-Body Workout", "emoji": BOLT,
        "category": "workout", "style": "punchy",
        "sub": "Train everything in one session",
        "stock_keywords": ["full body workout gym", "functional training",
            "kettlebell workout", "compound lift gym", "athlete training hard"],
        "hook": "FULL BODY",
        "script": (
            "Only training a few days a week? A full-body session is the most efficient way to grow. "
            "Pick one big move per major muscle group. A squat for legs, a bench or push-up for chest, a row or pull-up for back, and an overhead press for shoulders. "
            "Do three to four sets of each, leaving a rep or two in the tank. "
            "Because you hit every muscle in one workout, you can train each one two or three times a week — and that frequency drives growth. "
            "Add a little weight or a rep every session and stay consistent. "
            "This is how busy people still build a great physique. "
            "Follow for smart, simple training."
        ),
        "hashtags_extra": ["fullbody", "workout", "strength", "compound"],
    },
    # ---- 16. Rest & recovery (recovery, edu) ----
    {
        "key": "recovery_rest", "label": "Rest & Recovery", "emoji": SLEEP,
        "category": "recovery", "style": "edu",
        "sub": "Why rest days grow muscle",
        "stock_keywords": ["person resting relaxing", "stretching recovery",
            "sleep bedroom calm", "foam rolling recovery", "walking outdoor nature"],
        "hook": "REST TO GROW",
        "script": (
            "Here's the truth that gym addicts hate to hear — you don't grow in the gym, you grow when you rest. "
            "Training is the stimulus. It breaks your muscle down. The actual repair and growth happen afterward, while you recover. "
            "If you train the same muscle hard every day without rest, you never give it the chance to rebuild, and progress stalls. "
            "Aim for at least one or two full rest days a week, and give each muscle group about forty-eight hours before you hammer it again. "
            "Rest days don't have to mean lying down — a walk, a light stretch, or some easy mobility all help you recover. "
            "And manage your stress, because a stressed body repairs slowly. "
            "Respect recovery and you'll grow faster than the person who never takes a day off. "
            "Follow for training that actually works."
        ),
        "hashtags_extra": ["recovery", "restday", "musclegrowth", "overtraining"],
        "cta": "Follow for training that actually works.",
    },
    # ---- 17. Chest anatomy & bench (anatomy, edu) ----
    {
        "key": "anatomy_chest", "label": "Chest Anatomy", "emoji": BRAIN,
        "category": "anatomy", "style": "edu",
        "sub": "How the bench press really works",
        "stock_keywords": ["bench press form gym", "chest muscle anatomy",
            "incline press close up", "pushup muscle", "cable fly chest"],
        "hook": "INSIDE THE PRESS",
        "script": (
            "Ever wonder why some people press for years and still have a flat chest? It's because they don't understand the muscle. "
            "Your chest — the pectoralis major — has two main regions: an upper part that runs up toward your collarbone, and a larger lower part. "
            "Its job is to bring your arms across and in front of your body, and that's exactly what a press or a fly does. "
            "A flat press hits the mid and lower chest, while an incline press shifts the work to that stubborn upper chest most people are missing. "
            "To actually grow it, think about driving your arms together, not just pushing the weight up. Feel the stretch at the bottom and the squeeze at the top. "
            "Train it from a couple of angles — flat, incline, and a fly for the stretch — and control every rep. "
            "Understand the muscle, and you'll finally build it. "
            "Follow to train with your brain, not just your ego."
        ),
        "hashtags_extra": ["anatomy", "chest", "benchpress", "hypertrophy"],
        "cta": "Follow to train with your brain, not just your ego.",
    },
    # ---- 18. Warmup for legs (warmup) ----
    {
        "key": "warmup_legs", "label": "Leg Day Warmup", "emoji": BOLT,
        "category": "warmup", "style": "punchy",
        "sub": "Prime your legs before squats",
        "stock_keywords": ["leg warm up gym", "bodyweight squat warm up",
            "leg swings stretch", "glute activation exercise", "lunge warm up"],
        "hook": "PRIME YOUR LEGS",
        "script": (
            "Never load a heavy squat with cold legs — do this three-minute prep first. "
            "Start with leg swings, front to back and side to side, to loosen your hips. "
            "Then wake up your glutes with a set of glute bridges or banded walks, so they actually fire under the bar. "
            "Do twenty bodyweight squats, sinking a little deeper each rep to open your range. "
            "Then ramp up with light warmup sets before your working weight — never jump straight to heavy. "
            "This primes your muscles, grooves your form, and lets you squat deeper and safer. "
            "Save this for your next leg day."
        ),
        "hashtags_extra": ["warmup", "legday", "squat", "activation"],
    },
    # ---- 19. Back anatomy (anatomy, edu) ----
    {
        "key": "anatomy_back", "label": "Back Anatomy", "emoji": BRAIN,
        "category": "anatomy", "style": "edu",
        "sub": "Why you can't feel your lats",
        "stock_keywords": ["lat pulldown muscle", "back muscle anatomy",
            "pull up back muscles", "row exercise back", "muscular back flex"],
        "hook": "FEEL YOUR BACK",
        "script": (
            "If you train back but only feel it in your arms, this is for you. "
            "Your lats are the big fan-shaped muscles that give your back its width. They run from your upper arm down to your lower spine. "
            "Their job is to pull your arms down and back toward your body — that's every pulldown, pull-up, and row. "
            "The reason most people can't feel them is simple: they pull with their hands and biceps instead of their elbows. "
            "Here's the fix. Think about driving your elbows down and back, like putting them in your back pockets, and let your hands just be hooks. "
            "Pause for a second at the bottom of each rep and squeeze your shoulder blades together. "
            "Slow the weight down on the way back so the lats stay under tension. "
            "Master that mind-muscle connection and your back finally starts to grow. "
            "Follow to understand every muscle you train."
        ),
        "hashtags_extra": ["anatomy", "back", "lats", "mindmuscle"],
        "cta": "Follow to understand every muscle you train.",
    },
    # ---- 20. Hamstring flexibility (stretch) ----
    {
        "key": "stretch_hamstring", "label": "Hamstring Stretch", "emoji": STRETCH,
        "category": "stretch", "style": "punchy",
        "sub": "Loosen tight hamstrings",
        "stock_keywords": ["hamstring stretch floor", "forward fold stretch",
            "seated stretch legs", "yoga stretch hamstring", "flexibility training"],
        "hook": "LOOSEN UP",
        "script": (
            "Tight hamstrings pull on your lower back and limit almost every lift — here's how to loosen them safely. "
            "Never bounce into a stretch. Ease in slowly and hold each position for thirty seconds while you breathe out. "
            "Try a standing forward fold, letting your head hang and knees soft. "
            "Then a seated single-leg reach, keeping your back long instead of rounding over. "
            "Finish with a lying hamstring stretch using a band or towel around your foot. "
            "Do this after training or on rest days, and your squats, deadlifts, and posture all improve. "
            "Save this and use it a few times a week."
        ),
        "hashtags_extra": ["stretching", "flexibility", "hamstrings", "mobility"],
    },
    # ---- 21. Fat loss basics (diet, edu) ----
    {
        "key": "diet_fatloss", "label": "Fat Loss Basics", "emoji": DROP,
        "category": "diet", "style": "edu",
        "sub": "The one rule of losing fat",
        "stock_keywords": ["healthy food vegetables", "meal prep containers",
            "weighing food scale", "salad healthy bowl", "person cooking healthy"],
        "hook": "FAT LOSS 101",
        "script": (
            "Forget the magic teas and fad diets — fat loss comes down to one rule. "
            "You have to burn more calories than you eat. That's called a calorie deficit, and nothing works without it. "
            "But you don't want to just lose weight — you want to lose fat and keep your muscle. "
            "So keep your protein high, because it protects your muscle while you diet and keeps you full. "
            "Aim for a small, steady deficit — losing around half a kilo a week — instead of starving yourself, which only burns muscle and backfires. "
            "Fill your plate with vegetables, lean protein, and whole foods that keep you satisfied on fewer calories. "
            "And keep training hard, so your body has a reason to hold onto muscle. "
            "Slow and steady wins, every time. "
            "Follow for nutrition without the nonsense."
        ),
        "hashtags_extra": ["fatloss", "diet", "caloriedeficit", "weightloss"],
        "cta": "Follow for nutrition without the nonsense.",
    },
    # ---- 22. Zone-2 / LISS cardio (cardio, edu) ----
    {
        "key": "cardio_zone2", "label": "Zone-2 Cardio", "emoji": RUN,
        "category": "cardio", "style": "edu",
        "sub": "The easy cardio that works",
        "stock_keywords": ["person walking incline", "steady cycling gym",
            "jogging outdoor park", "treadmill walking", "rowing machine cardio"],
        "hook": "GO SLOW TO WIN",
        "script": (
            "Not all cardio has to leave you gasping. The easy kind might be the most underrated tool you have. "
            "It's called zone two — a pace where you're working, but you could still hold a conversation. "
            "Think a brisk incline walk, an easy bike ride, or a steady row for thirty to forty-five minutes. "
            "At this pace your body gets better at burning fat for fuel and builds a stronger, healthier heart. "
            "Because it's low intensity, it doesn't beat up your muscles or wreck your recovery like sprint work can. "
            "That means you can do it several times a week on top of your lifting without burning out. "
            "It's boring, it's simple, and it quietly transforms your fitness. "
            "Follow for training that keeps you healthy for life."
        ),
        "hashtags_extra": ["cardio", "zone2", "fatloss", "endurance"],
        "cta": "Follow for training that keeps you healthy for life.",
    },
    # ---- 23. Shoulder mobility (mobility, edu) ----
    {
        "key": "mobility_shoulders", "label": "Shoulder Mobility", "emoji": STRETCH,
        "category": "mobility", "style": "edu",
        "sub": "Fix stiff, achy shoulders",
        "stock_keywords": ["shoulder mobility stretch", "band shoulder exercise",
            "arm circles mobility", "shoulder stretch wall", "mobility drill athlete"],
        "hook": "HEALTHY SHOULDERS",
        "script": (
            "Achy shoulders that click and pinch when you press? Your mobility is probably the problem. "
            "Your shoulder is the most mobile joint in your body, which also makes it the easiest to mess up when it gets stiff. "
            "Start with band pull-aparts to wake up the muscles that hold your shoulder blades in place. "
            "Then do shoulder dislocates with a band or a broomstick — slow, controlled circles over your head to open the joint. "
            "Add a wall slide, keeping your arms and back flat against the wall as you reach up. "
            "Do these before pressing and a few times a week, and your shoulders move better and hurt less. "
            "Strong shoulders start with mobile shoulders. "
            "Follow for mobility that keeps you lifting pain-free."
        ),
        "hashtags_extra": ["mobility", "shoulders", "shouldermobility", "painfree"],
        "cta": "Follow for mobility that keeps you lifting pain-free.",
    },
    # ---- 24. Post-workout nutrition (diet, edu) ----
    {
        "key": "diet_postworkout", "label": "Post-Workout Food", "emoji": BROC,
        "category": "diet", "style": "edu",
        "sub": "What to eat after training",
        "stock_keywords": ["protein shake after workout", "healthy meal chicken rice",
            "greek yogurt bowl", "post workout meal", "eggs toast breakfast"],
        "hook": "REFUEL RIGHT",
        "script": (
            "You just finished training — what you eat now helps you recover and grow. "
            "After a hard session, your muscles are primed to soak up nutrients and start repairing. "
            "The two things you want are protein to rebuild muscle and carbs to refill your energy stores. "
            "A simple post-workout meal is chicken and rice, a protein shake with a banana, or Greek yogurt with fruit and oats. "
            "You don't need to panic and eat within seconds — the old thirty-minute window is a myth — but getting a solid meal in within a couple of hours is smart. "
            "What matters most is that you hit your total protein and calories for the whole day. "
            "Train hard, then feed the recovery. "
            "Follow for nutrition that actually moves the needle."
        ),
        "hashtags_extra": ["postworkout", "nutrition", "recovery", "protein"],
        "cta": "Follow for nutrition that actually moves the needle.",
    },
    # ---- 25. Mind-muscle connection (anatomy, edu) ----
    {
        "key": "anatomy_mindmuscle", "label": "Mind-Muscle Link", "emoji": BRAIN,
        "category": "anatomy", "style": "edu",
        "sub": "The trick that doubles your gains",
        "stock_keywords": ["focused lifting gym", "slow controlled rep",
            "muscle contraction close up", "bicep squeeze", "concentration curl"],
        "hook": "MIND OVER MUSCLE",
        "script": (
            "Two people can do the exact same exercise and get completely different results. The difference is often the mind-muscle connection. "
            "Your brain controls your muscles through nerve signals. The better you focus on a muscle, the more of its fibers you actually recruit during a rep. "
            "When you just heave a weight from A to B, other muscles take over and the one you're trying to grow barely works. "
            "The fix is to slow down and consciously feel the target muscle stretching and squeezing on every single rep. "
            "Lighten the weight if you have to. A lighter set you truly feel beats a heavy set you just swing. "
            "Squeeze hard at the peak of each rep and hold it for a beat. "
            "Train the muscle, not the movement, and your results change fast. "
            "Follow to get more from every set you do."
        ),
        "hashtags_extra": ["mindmuscle", "hypertrophy", "gymtips", "musclegrowth"],
        "cta": "Follow to get more from every set you do.",
    },
    # ---- 26. Sleep & muscle (recovery, edu) ----
    {
        "key": "recovery_sleep", "label": "Sleep & Gains", "emoji": SLEEP,
        "category": "recovery", "style": "edu",
        "sub": "The most underrated supplement",
        "stock_keywords": ["sleep bedroom calm", "person sleeping rest",
            "relaxing evening calm", "night sky calm", "waking up morning"],
        "hook": "SLEEP = GAINS",
        "script": (
            "The most powerful muscle-building supplement is free, and you do it every night — or you should. "
            "While you sleep, your body releases most of its growth hormone and does the heavy lifting of repairing the muscle you trained. "
            "Skimp on sleep and you blunt recovery, lose strength, feel hungrier, and hold onto more fat. "
            "Aim for seven to nine hours a night, and try to keep a consistent schedule, even on weekends. "
            "Keep your room dark and cool, and get off your phone before bed, because screen light delays the sleep your muscles need. "
            "You can train perfectly and eat perfectly, but if you sleep badly, you leave most of your gains on the table. "
            "Treat sleep like part of your program, not an afterthought. "
            "Follow for the fundamentals that actually build muscle."
        ),
        "hashtags_extra": ["sleep", "recovery", "musclegrowth", "health"],
        "cta": "Follow for the fundamentals that actually build muscle.",
    },
    # ---- 27. Muscle-building diet (diet, edu) ----
    {
        "key": "diet_bulk", "label": "Muscle-Building Diet", "emoji": MEAT,
        "category": "diet", "style": "edu",
        "sub": "How to eat to build muscle",
        "stock_keywords": ["healthy big meal", "meal prep bodybuilding",
            "rice chicken vegetables", "protein foods table", "cooking healthy food"],
        "hook": "EAT TO GROW",
        "script": (
            "You can't build a bigger body on a diet that keeps you the same size. To grow muscle, you have to eat for it. "
            "Muscle is built from a small calorie surplus — eating slightly more than you burn — paired with hard training. "
            "Add roughly two to three hundred calories above your maintenance level, so you gain slowly without piling on fat. "
            "Keep protein high, around two grams per kilo of bodyweight, to give your muscles the building blocks they need. "
            "Fill the rest with quality carbs like rice, oats, and potatoes for training energy, plus healthy fats for your hormones. "
            "Eat consistently across the day and don't skip meals — muscle is built with steady fuel, not one big binge. "
            "Be patient. Real muscle comes slowly, but it stays. "
            "Follow for nutrition that builds a better body."
        ),
        "hashtags_extra": ["bulking", "diet", "musclegain", "nutrition"],
        "cta": "Follow for nutrition that builds a better body.",
    },
    # ---- 28. Leg anatomy (anatomy, edu) ----
    {
        "key": "anatomy_legs", "label": "Leg Anatomy", "emoji": BRAIN,
        "category": "anatomy", "style": "edu",
        "sub": "What a squat actually trains",
        "stock_keywords": ["squat form muscle", "leg muscle anatomy",
            "quad muscle gym", "squat close up legs", "athlete squatting"],
        "hook": "INSIDE THE SQUAT",
        "script": (
            "The squat is called the king of exercises, but do you know what it actually trains? "
            "Your legs have three big players. The quads on the front of your thigh straighten your knee. The hamstrings on the back bend it and help your hips. And your glutes drive your hips forward. "
            "In a squat, you lower by bending your knees and hips together, and all three fire to stand you back up. "
            "How you squat shifts the emphasis. A more upright squat with a deep knee bend hits the quads harder, while sitting your hips back loads the glutes and hamstrings more. "
            "Going deeper — to at least parallel — recruits far more muscle than a shallow quarter squat. "
            "And bracing your core keeps your spine safe under the load. "
            "Understand what's working, and you'll squat with purpose instead of just moving weight. "
            "Follow to understand every rep you do."
        ),
        "hashtags_extra": ["anatomy", "legs", "squat", "quads"],
        "cta": "Follow to understand every rep you do.",
    },
]

# --- Paths ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

# --- Voice (edge-tts neural voice; free, no key) ---
#   en-US-AvaMultilingualNeural   - warm, natural, expressive
#   en-US-AndrewMultilingualNeural- confident male, great for fitness (default)
#   en-US-EmmaMultilingualNeural  - friendly, upbeat
#   en-US-AriaNeural / en-US-GuyNeural - reliable classics
TTS_VOICE = "en-US-ChristopherNeural"   # confident male; emits word timings for captions
TTS_RATE = "+8%"    # punchy pace for motivation
TTS_PITCH = "+0Hz"

# YouTube category IDs per content category (used by the YouTube uploader).
#   17 = Sport, 26 = Howto & Style, 27 = Education
YT_CATEGORY = {
    "workout": "17", "warmup": "17", "stretch": "17", "cardio": "17",
    "mobility": "27", "anatomy": "27", "recovery": "27", "diet": "26",
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
    return 1 if hour < 11 else 2   # <11:00 UTC = morning IST, else evening


def pick_content():
    """Return (entry, part). Rotates through the entire CONTENT library."""
    part = current_part()
    doy = datetime.date.today().timetuple().tm_yday   # 1..366
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
    "workout":  ["workout", "gymmotivation", "bodybuilding"],
    "warmup":   ["warmup", "gymtips", "mobility"],
    "stretch":  ["stretching", "flexibility", "recovery"],
    "mobility": ["mobility", "flexibility", "gymtips"],
    "diet":     ["nutrition", "diet", "healthyeating"],
    "anatomy":  ["fitnesstips", "hypertrophy", "gymscience"],
    "cardio":   ["cardio", "fatloss", "conditioning"],
    "recovery": ["recovery", "restday", "wellness"],
}

DEFAULT_CTA = "Follow for a new fitness video every day."


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
- Optional background music is ducked under the voiceover.
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

Run:  python dve.py
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
        # Some TTS voices don't emit word-boundary events; fall back to
        # evenly-spaced timings so the captions still render.
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

    # 8) auto-post to YouTube (only if the 3 YT secrets are set; skips silently otherwise)
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


def _upload_public(video_path):
    """Put the mp4 at a temporary PUBLIC https URL (Instagram pulls video from a URL).
    Uses catbox.moe (free, no key); falls back to 0x0.st. Returns the URL or None."""
    import requests
    # try catbox.moe
    try:
        with open(video_path, "rb") as f:
            r = requests.post("https://catbox.moe/user/api.php",
                              data={"reqtype": "fileupload"},
                              files={"fileToUpload": f}, timeout=180)
        url = r.text.strip()
        if r.ok and url.startswith("http"):
            print(f"[instagram] public URL (catbox): {url}")
            return url
        print(f"[instagram] catbox failed: {r.status_code} {url[:120]}")
    except Exception as e:  # noqa: BLE001
        print(f"[instagram] catbox error: {e}")
    # fallback 0x0.st
    try:
        with open(video_path, "rb") as f:
            r = requests.post("https://0x0.st", files={"file": f},
                              headers={"User-Agent": "daily-video-engine"}, timeout=180)
        url = r.text.strip()
        if r.ok and url.startswith("http"):
            print(f"[instagram] public URL (0x0): {url}")
            return url
        print(f"[instagram] 0x0 failed: {r.status_code} {url[:120]}")
    except Exception as e:  # noqa: BLE001
        print(f"[instagram] 0x0 error: {e}")
    return None


def upload_instagram(video_path, meta):
    """Publish the finished video as an Instagram Reel.
    Needs GitHub Secrets: IG_USER_ID, IG_ACCESS_TOKEN. Skips quietly if unset."""
    import time
    import requests

    ig_id = os.environ.get("IG_USER_ID", "").strip()
    token = os.environ.get("IG_ACCESS_TOKEN", "").strip()
    if not (ig_id and token):
        print("[instagram] IG secrets not set - skipping upload.")
        return None

    public_url = _upload_public(video_path)
    if not public_url:
        print("[instagram] no public URL available - skipping.")
        return None

    caption = meta["description"]
    if len(caption) > 2100:
        caption = caption[:2100]
    # Instagram Graph API via Facebook login (token from Graph API Explorer)
    base = "https://graph.facebook.com/v21.0"

    # 1) create a REELS container
    r = requests.post(f"{base}/{ig_id}/media", data={
        "media_type": "REELS",
        "video_url": public_url,
        "caption": caption,
        "access_token": token,
    }, timeout=120)
    j = r.json()
    creation_id = j.get("id")
    if not creation_id:
        print(f"[instagram] container error: {j}")
        return None
    print(f"[instagram] container {creation_id} created; waiting for processing...")

    # 2) poll until the container finishes processing (reels take a bit)
    for _ in range(30):
        time.sleep(6)
        s = requests.get(f"{base}/{creation_id}", params={
            "fields": "status_code", "access_token": token}, timeout=60).json()
        code = s.get("status_code")
        if code == "FINISHED":
            break
        if code == "ERROR":
            print(f"[instagram] processing error: {s}")
            return None
    else:
        print("[instagram] processing timed out; not publishing.")
        return None

    # 3) publish
    p = requests.post(f"{base}/{ig_id}/media_publish", data={
        "creation_id": creation_id, "access_token": token}, timeout=120).json()
    media_id = p.get("id")
    if media_id:
        print(f"[instagram] DONE -> published media {media_id}")
    else:
        print(f"[instagram] publish error: {p}")
    return media_id


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
            # Declare the spoken language so YouTube can auto-generate dubs.
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
