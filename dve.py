"""Daily Video Engine — single-file build. Paste this whole file into GitHub as dve.py."""
import os, sys, math, json, glob, random, time, datetime, subprocess, asyncio, re
import urllib.parse, xml.etree.ElementTree as ET
import requests, numpy as np
from PIL import Image
import edge_tts

# ===== config =====
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "")

WIDTH = 1080
HEIGHT = 1920
FPS = 30
TARGET_SECONDS = 42
FONT_SIZE = 64

# ---------------------------------------------------------------------------
# FITNESS CHANNEL — bilingual content library (English + Hindi).
# Each entry carries English fields plus *_hi Hindi fields. The engine picks the
# language per slot (morning = English, evening = Hindi) and renders captions
# with a language-appropriate font.
# ---------------------------------------------------------------------------

CHEST = "\U0001F4AA"; FIRE = "\U0001F525"; LEG = "\U0001F9B5"; LIFT = "\U0001F3CB"
BOLT = "\U000026A1"; BROC = "\U0001F966"; BRAIN = "\U0001F9E0"; STRETCH = "\U0001F938"
RUN = "\U0001F3C3"; SLEEP = "\U0001F634"; MEAT = "\U0001F357"; DROP = "\U0001F4A7"
TROPHY = "\U0001F3C6"; HOME = "\U0001F3E0"; CLOCK = "\U000023F0"; CHART = "\U0001F4C8"
TARGET = "\U0001F3AF"; CHECK = "\U00002705"; CROSS = "\U0000274C"; FILM = "\U0001F3AC"

CONTENT = [
# ---- 1. Ranked: chest ----
{
    "key": "ranked_chest", "label": "Chest Exercises Ranked", "emoji": TROPHY,
    "label_hi": "बेस्ट चेस्ट एक्सरसाइज", "sub_hi": "बड़ी चेस्ट के लिए टॉप 3",
    "hook_hi": "चेस्ट रैंकिंग",
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
    "script_hi": (
        "बड़ी और मजबूत चेस्ट के लिए ये हैं टॉप तीन एक्सरसाइज। "
        "नंबर तीन, केबल फ्लाई। लगातार टेंशन और गहरी स्ट्रेच इसे चेस्ट फिनिश करने के लिए बेहतरीन बनाती है। "
        "नंबर दो, इनक्लाइन डम्बल प्रेस। यह अपर चेस्ट बनाता है, जो ज्यादातर लोगों की कमजोर रहती है। "
        "और नंबर एक, फ्लैट बारबेल या डम्बल प्रेस। साइज और ताकत के लिए इससे बेहतर कुछ नहीं, बस वजन को कंट्रोल के साथ नीचे लाएं। "
        "भारी से शुरू करें, स्ट्रेच पर खत्म करें, और चेस्ट बढ़ेगी। "
        "रोज नई जानकारी के लिए फॉलो करें।"
    ),
    "hashtags_extra": ["chest", "chestday", "benchpress", "ranked"],
},
# ---- 2. Science: progressive overload ----
{
    "key": "science_overload", "label": "Why You're Not Growing", "emoji": BRAIN,
    "label_hi": "मसल क्यों नहीं बढ़ रही", "sub_hi": "प्रोग्रेसिव ओवरलोड का विज्ञान",
    "hook_hi": "ग्रोथ का नियम",
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
    "script_hi": (
        "महीनों से जिम जा रहे हैं पर शरीर वैसा ही है? तो यह विज्ञान आपको पता होना चाहिए। "
        "मसल तभी बढ़ती है जब आप उसे पहले से ज्यादा करने पर मजबूर करें। इसे प्रोग्रेसिव ओवरलोड कहते हैं। "
        "हर हफ्ते वही वजन, वही रेप्स करने से शरीर को बदलने की कोई वजह नहीं मिलती। "
        "इसलिए हर हफ्ते थोड़ा ज्यादा करें, एक रेप बढ़ाएं, थोड़ा वजन बढ़ाएं, या मूवमेंट को धीरे कंट्रोल करें। "
        "अपनी मेन लिफ्ट्स को नोट करें और पिछले हफ्ते से थोड़ा बेहतर करें। "
        "लगातार करते रहें और यही छोटी प्रोग्रेस नया शरीर बनाती है। "
        "विज्ञान के साथ ट्रेनिंग के लिए फॉलो करें।"
    ),
    "hashtags_extra": ["progressiveoverload", "musclegrowth", "gymscience", "hypertrophy"],
    "cta": "Follow to train with the science, not guesswork.",
},
# ---- 3. Home upper body ----
{
    "key": "home_upper", "label": "Home Upper Body", "emoji": HOME,
    "label_hi": "घर पर अपर बॉडी", "sub_hi": "बिना इक्विपमेंट, बिना बहाने",
    "hook_hi": "जिम की जरूरत नहीं",
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
    "script_hi": (
        "जिम नहीं? कोई बात नहीं। यह रही पूरी अपर बॉडी वर्कआउट, घर पर, बिना किसी इक्विपमेंट के। "
        "शुरू करें नॉर्मल पुश-अप्स से, चेस्ट के लिए। ज्यादा नहीं कर पाते? घुटनों पर आ जाएं पर फॉर्म सही रखें। "
        "फिर डायमंड पुश-अप्स, दोनों हाथ पास-पास, ट्राइसेप्स के लिए। "
        "इसके बाद पाइक पुश-अप्स, कमर ऊपर उठाकर, कंधों के लिए। "
        "आखिर में धीरे-धीरे नीचे आते हुए स्लो नेगेटिव्स करें, इससे असली ताकत बनती है। "
        "तीन राउंड, थोड़ा आराम, और अपर बॉडी हो गई। "
        "घर की असरदार वर्कआउट के लिए फॉलो करें।"
    ),
    "hashtags_extra": ["homeworkout", "nogym", "calisthenics", "pushups"],
},
# ---- 4. Comeback: short break ----
{
    "key": "comeback_short", "label": "Back After a Break", "emoji": BOLT,
    "label_hi": "ब्रेक के बाद वापसी", "sub_hi": "1-2 हफ्ते बाद लौटना",
    "hook_hi": "वापस जिम में",
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
    "script_hi": (
        "एक या दो हफ्ते का ब्रेक लिया? तो ऐसे करें वापसी, बिना चोट लगाए। "
        "सबसे पहले, पहले जैसा वजन उठाने की कोशिश मत करें। ताकत अभी भी है, बस उसे जगाना है। "
        "शुरुआती कुछ सेशन अपने पुराने वजन के करीब अस्सी प्रतिशत पर करें। "
        "रेप्स थोड़े ज्यादा रखें और हर सेट में दो-तीन रेप्स बाकी छोड़ दें। "
        "थोड़ी अकड़न होगी, यह सामान्य है, कोई नुकसान नहीं। "
        "एक-दो हफ्ते में आप फिर वहीं पहुंच जाएंगे, अक्सर पहले से मजबूत। "
        "बस शुरू करना जरूरी है। स्मार्ट ट्रेनिंग के लिए फॉलो करें।"
    ),
    "hashtags_extra": ["gymmotivation", "comeback", "fitnesstips", "consistency"],
    "cta": "The key is just to start. Follow for smart training.",
},
# ---- 5. Ranked: legs ----
{
    "key": "ranked_legs", "label": "Leg Exercises Ranked", "emoji": TROPHY,
    "label_hi": "बेस्ट लेग एक्सरसाइज", "sub_hi": "बड़ी लेग्स के लिए टॉप 3",
    "hook_hi": "लेग्स रैंकिंग",
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
    "script_hi": (
        "बड़ी और मजबूत लेग्स के लिए ये हैं टॉप तीन एक्सरसाइज। "
        "नंबर तीन, वॉकिंग लंज। यह क्वाड्स और ग्लूट्स बनाता है और दोनों पैरों का फर्क भी ठीक करता है। "
        "नंबर दो, रोमानियन डेडलिफ्ट। मजबूत हैमस्ट्रिंग और ग्लूट्स के लिए सबसे अच्छा, स्ट्रेच महसूस करें और कूल्हे आगे धकेलें। "
        "और नंबर एक, स्क्वाट। लेग एक्सरसाइज का राजा। जितना कंट्रोल के साथ नीचे जा सकें जाएं, पूरी लोअर बॉडी इससे तेजी से बनती है। "
        "स्क्वाट, हिंज और लंज, यही है पूरा लेग डे। "
        "रोज नई जानकारी के लिए फॉलो करें।"
    ),
    "hashtags_extra": ["legday", "squats", "legworkout", "ranked"],
},
# ---- 6. 60-day plan ----
{
    "key": "plan_60day", "label": "60-Day Transformation", "emoji": CLOCK,
    "label_hi": "60 दिन का ट्रांसफॉर्मेशन", "sub_hi": "60 दिन में बदलें अपनी बॉडी",
    "hook_hi": "60 दिन में बदलाव",
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
    "script_hi": (
        "साठ दिन में असली बदलाव चाहिए? तो यह रहा सच्चा प्लान जो काम करता है। "
        "पहला, हफ्ते में चार दिन ट्रेनिंग करें, हर मसल ग्रुप को दो बार। हर सेट फेलियर के पास ले जाएं और हर हफ्ते थोड़ा बढ़ाएं। "
        "दूसरा, खाना सही करें। प्रोटीन पूरा लें, शरीर के हर किलो वजन पर करीब दो ग्राम, और कैलोरी अपने लक्ष्य के हिसाब से रखें। "
        "तीसरा, रोज आठ से दस हजार कदम चलें और सात-आठ घंटे सोएं, क्योंकि रिकवरी तभी होती है। "
        "साठ दिन लगातार यह करें और आप सिर्फ दिखेंगे नहीं, महसूस भी अलग करेंगे। "
        "कोई शॉर्टकट नहीं, बस रोज बेसिक्स। "
        "फॉलो करें और आज से अपने साठ दिन शुरू करें।"
    ),
    "hashtags_extra": ["transformation", "60daychallenge", "fitnessplan", "fatloss"],
    "cta": "Follow and start your sixty days today.",
},
# ---- 7. Ranked: back ----
{
    "key": "ranked_back", "label": "Back Exercises Ranked", "emoji": TROPHY,
    "label_hi": "बेस्ट बैक एक्सरसाइज", "sub_hi": "चौड़ी बैक के लिए टॉप 3",
    "hook_hi": "बैक रैंकिंग",
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
    "script_hi": (
        "चौड़ी और मजबूत बैक के लिए ये हैं टॉप तीन एक्सरसाइज। "
        "नंबर तीन, सीटेड केबल रो। मिड-बैक की मोटाई के लिए बढ़िया, हर रेप पर अच्छे से स्क्वीज करें। "
        "नंबर दो, बारबेल रो। पूरी बैक बनाता है, बस कोहनियों से खींचें, हाथों से नहीं। "
        "और नंबर एक, पुल-अप। चौड़ी वी-शेप बैक इससे बेहतर कुछ नहीं बनाता। अभी नहीं कर पाते? बैंड या लैट पुलडाउन इस्तेमाल करें। "
        "चौड़ा खींचें, भारी रो करें, अच्छे से स्क्वीज करें। "
        "रोज नई जानकारी के लिए फॉलो करें।"
    ),
    "hashtags_extra": ["back", "pullups", "backday", "ranked"],
},
# ---- 8. How to grow arms ----
{
    "key": "howto_arms", "label": "How to Grow Your Arms", "emoji": CHEST,
    "label_hi": "बड़े आर्म्स कैसे बनाएं", "sub_hi": "आर्म्स ट्रेन करने का सही तरीका",
    "hook_hi": "बड़े आर्म्स का तरीका",
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
    "script_hi": (
        "बड़े आर्म्स कैसे बनाएं, स्टेप बाय स्टेप। "
        "स्टेप एक, पहले ट्राइसेप्स ट्रेन करें, क्योंकि यह आपके आर्म का दो-तिहाई हिस्सा है। पुशडाउन और ओवरहेड एक्सटेंशन से गहरी स्ट्रेच लें। "
        "स्टेप दो, बाइसेप्स को दो एंगल से लगाएं, नॉर्मल कर्ल पीक के लिए और हैमर कर्ल मोटाई और फोरआर्म के लिए। "
        "स्टेप तीन, हर रेप धीरे करें और ऊपर अच्छे से स्क्वीज करें। झटका नहीं, पूरा रेंज। "
        "स्टेप चार, हफ्ते में दो बार आर्म्स ट्रेन करें और हर बार थोड़े ज्यादा रेप्स या वजन लगाएं। "
        "कंट्रोल और प्रोग्रेशन मिलकर बड़े आर्म्स बनाते हैं। "
        "रोज एक नई टिप के लिए फॉलो करें।"
    ),
    "hashtags_extra": ["arms", "biceps", "triceps", "howto"],
    "cta": "Follow for a how-to every single day.",
},
# ---- 9. Myth: bulky ----
{
    "key": "myth_bulky", "label": "Lifting Myths", "emoji": CROSS,
    "label_hi": "जिम का मिथक", "sub_hi": "वजन उठाने से बॉडी भारी नहीं होती",
    "hook_hi": "मिथक गलत",
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
    "script_hi": (
        "मिथक, वजन उठाने से शरीर भारी और भद्दा हो जाता है। चलिए इसे तोड़ते हैं। "
        "बड़ी, भारी मसल बनाने में सालों की भारी ट्रेनिंग और जानबूझकर ज्यादा कैलोरी खाना लगता है। यह गलती से नहीं होता। "
        "वजन उठाने से असल में एक लीन, टोन्ड और मजबूत दिखने वाला शरीर बनता है, फैट घटता है और शेप बनती है। "
        "वह टोन्ड लुक जो सबको चाहिए? वह असल में मसल ही है। थोड़ी मसल बनाए बिना टोन नहीं होता। "
        "तो वजन से मत डरें। उठाएं, अपने लक्ष्य के हिसाब से खाएं, और आप फिट और एथलेटिक दिखेंगे, भारी नहीं। "
        "फैक्ट्स पर ट्रेनिंग के लिए फॉलो करें, डर पर नहीं।"
    ),
    "hashtags_extra": ["fitnessmyths", "mythbusting", "womensfitness", "strengthtraining"],
    "cta": "Follow to train on facts, not fear.",
},
# ---- 10. Transformation: discipline ----
{
    "key": "transform_discipline", "label": "Discipline Over Motivation", "emoji": CHART,
    "label_hi": "मोटिवेशन से ऊपर डिसिप्लिन", "sub_hi": "रिजल्ट का असली राज",
    "hook_hi": "डिसिप्लिन जीतता है",
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
    "script_hi": (
        "हर बड़े ट्रांसफॉर्मेशन के पीछे का सच, यह मोटिवेशन नहीं, डिसिप्लिन है। "
        "मोटिवेशन अच्छे दिनों में आता है। डिसिप्लिन वह है जो आपको उन दिनों भी जिम खींच लाता है जब कुछ करने का मन नहीं होता। "
        "रिजल्ट उसे मिलता है जो सबसे ज्यादा मोटिवेटेड नहीं, बल्कि जो बार-बार फिर भी आता है। "
        "हर दिन तैयार महसूस नहीं होगा। हर दिन मन नहीं करेगा। फिर भी जाएं। "
        "छोटी, बोरिंग, लगातार मेहनत एक परफेक्ट हफ्ते से हमेशा जीतती है। "
        "प्रोसेस से प्यार करें, रिजल्ट अपने आप आएंगे। "
        "रोज के पुश के लिए फॉलो करें।"
    ),
    "hashtags_extra": ["discipline", "gymmotivation", "mindset", "transformation"],
},
# ---- 11. Ranked: shoulders ----
{
    "key": "ranked_shoulders", "label": "Shoulder Exercises Ranked", "emoji": TROPHY,
    "label_hi": "बेस्ट शोल्डर एक्सरसाइज", "sub_hi": "गोल कंधों के लिए टॉप 3",
    "hook_hi": "शोल्डर रैंकिंग",
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
    "script_hi": (
        "गोल और चौड़े कंधों के लिए ये हैं टॉप तीन एक्सरसाइज। "
        "नंबर तीन, रियर-डेल्ट फ्लाई। वह मसल जिसे सब भूल जाते हैं, और जो कंधों को साइड से पूरा दिखाती है। "
        "नंबर दो, ओवरहेड प्रेस। कंधों के आगे और बीच के हिस्से के लिए मुख्य ताकत और साइज बनाने वाली एक्सरसाइज। "
        "और नंबर एक, लेटरल रेज। साइड डेल्ट ही चौड़ा लुक देता है, हल्का वजन लें, कोहनियों से उठाएं और कंट्रोल से नीचे लाएं। "
        "भारी प्रेस करें, हल्का रेज करें, और रियर कभी न छोड़ें। "
        "रोज नई जानकारी के लिए फॉलो करें।"
    ),
    "hashtags_extra": ["shoulders", "delts", "lateralraise", "ranked"],
},
# ---- 12. Science: recovery ----
{
    "key": "science_recovery", "label": "How Muscles Recover", "emoji": BRAIN,
    "label_hi": "मसल कैसे रिकवर होती है", "sub_hi": "आराम से मसल क्यों बढ़ती है",
    "hook_hi": "आराम में ग्रोथ",
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
    "script_hi": (
        "यह विज्ञान ज्यादातर लोग अनदेखा करते हैं, मसल जिम में नहीं, आराम में बनती है। "
        "ट्रेनिंग के दौरान मसल फाइबर में छोटे-छोटे टियर बनते हैं। वर्कआउट सिर्फ एक सिग्नल है। "
        "असली रिपेयर और ग्रोथ बाद के घंटों और दिनों में होती है, प्रोटीन, नींद और आराम से। "
        "इसीलिए एक ही मसल रोज पीटना उल्टा पड़ता है, उसे मजबूत होने का समय ही नहीं मिलता। "
        "हर मसल को दोबारा भारी ट्रेन करने से पहले करीब अड़तालीस घंटे दें। सात से नौ घंटे सोएं। प्रोटीन पूरा लें। "
        "रिकवरी को महत्व दें और आप उससे तेज बढ़ेंगे जो कभी आराम नहीं करता। "
        "विज्ञान वाली ट्रेनिंग के लिए फॉलो करें।"
    ),
    "hashtags_extra": ["recovery", "musclegrowth", "gymscience", "restday"],
    "cta": "Follow for training backed by science.",
},
# ---- 13. Home legs ----
{
    "key": "home_legs", "label": "Home Leg Workout", "emoji": HOME,
    "label_hi": "घर पर लेग वर्कआउट", "sub_hi": "बिना वजन के बनाएं लेग्स",
    "hook_hi": "घर पर लेग्स",
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
    "script_hi": (
        "घर पर बिना इक्विपमेंट के भी मजबूत लेग्स बना सकते हैं। यह रहा तरीका। "
        "शुरू करें बॉडीवेट स्क्वाट से, धीरे और गहरे, ज्यादा रेप्स में। "
        "फिर रिवर्स लंज, एक-एक पैर, ताकि दोनों तरफ बराबर बने। "
        "इसके बाद बल्गेरियन स्प्लिट स्क्वाट, पिछला पैर कुर्सी पर, मुश्किल पर असरदार। "
        "आखिर में वॉल सिट, तब तक रुकें जब तक पैर जलने न लगें। "
        "राज है रेप्स और कंट्रोल, सब कुछ धीरे करें और बर्न महसूस करें। "
        "तीन राउंड और जिम याद नहीं आएगा। "
        "असरदार होम वर्कआउट के लिए फॉलो करें।"
    ),
    "hashtags_extra": ["homeworkout", "legday", "nogym", "bodyweight"],
},
# ---- 14. Comeback: long break ----
{
    "key": "comeback_long", "label": "Back After Months Off", "emoji": BOLT,
    "label_hi": "महीनों बाद वापसी", "sub_hi": "लंबे ब्रेक के बाद शुरुआत",
    "hook_hi": "मजबूत रीस्टार्ट",
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
    "script_hi": (
        "महीनों या उससे ज्यादा जिम से दूर रहे? तो ऐसे करें रीस्टार्ट, बिना चोट और बिना थके। "
        "भूल जाएं कि पहले कहां थे, ईगो वहीं पहुंचना चाहेगा, और इसी से लोग चोटिल होते हैं। "
        "पहले दो हफ्ते हल्का ट्रेन करें, रेप्स मीडियम रखें और फेलियर से काफी पहले रुकें। जोड़ों और टेंडन को मसल के साथ आने दें। "
        "सिंपल फुल-बॉडी सेशन पर ध्यान दें, हफ्ते में दो-तीन बार, बड़े बेसिक्स। "
        "अच्छी खबर, मसल मेमोरी की वजह से आप अपनी पुरानी ताकत और साइज पहली बार से कहीं तेजी से वापस पाएंगे। "
        "कुछ हफ्ते धैर्य रखें, फिर रफ्तार खुद आ जाएगी। "
        "फॉलो करें, साथ मिलकर दोबारा बनाते हैं।"
    ),
    "hashtags_extra": ["gymmotivation", "musclememory", "comeback", "beginner"],
    "cta": "Follow and let's rebuild together.",
},
# ---- 15. 90-day plan ----
{
    "key": "plan_90day", "label": "90-Day Dream Physique", "emoji": CLOCK,
    "label_hi": "90 दिन में ड्रीम फिजीक", "sub_hi": "90 दिन में बनाएं ड्रीम बॉडी",
    "hook_hi": "90 दिन, नया आप",
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
    "script_hi": (
        "नब्बे दिन काफी हैं अपना पूरा लुक बदलने के लिए, अगर ये चार चीजें सही करें। "
        "एक, हफ्ते में चार-पांच दिन वजन उठाएं, सिंपल पुश, पुल, लेग्स स्प्लिट पर, और समय के साथ मजबूत बनें। "
        "दो, अपने लक्ष्य के हिसाब से खाएं। प्रोटीन हमेशा ज्यादा, और कैलोरी फैट लॉस या मसल गेन के लिए सेट करें, एक चुनें और टिके रहें। "
        "तीन, थोड़ा कार्डियो करें और रोज एक्टिव रहें। दस हजार कदम फैट लॉस चालू रखते हैं बिना गेन नुकसान किए। "
        "चार, सोएं और रिकवर करें, क्योंकि शरीर आराम में बदलता है, स्क्रॉल करते हुए नहीं। "
        "आज एक फोटो लें, नब्बे दिन यही दोहराएं, और बिफोर-आफ्टर चौंका देगा। "
        "फॉलो करें और आज से दिन एक शुरू करें।"
    ),
    "hashtags_extra": ["90daychallenge", "transformation", "fitnessplan", "dreamphysique"],
    "cta": "Follow and start day one now.",
},
# ---- 16. Myth: spot reduction ----
{
    "key": "myth_spotreduction", "label": "Belly Fat Myth", "emoji": CROSS,
    "label_hi": "पेट की चर्बी का मिथक", "sub_hi": "एक जगह की चर्बी टारगेट नहीं होती",
    "hook_hi": "मिथक गलत",
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
    "script_hi": (
        "मिथक, लगातार क्रंचेस करने से पेट की चर्बी घटती है। चलिए इसे तोड़ते हैं। "
        "आप किसी एक जगह की चर्बी टारगेट करके नहीं घटा सकते। किसी मसल को ट्रेन करने से उसके ऊपर की चर्बी नहीं जलती। "
        "हजार क्रंचेस आपके एब्स बना देंगे, पर अगर वे चर्बी के नीचे छुपे हैं, तो कोई नहीं देख पाएगा। "
        "चर्बी पूरे शरीर से एक साथ घटती है, उसी क्रम में जो आपके जीन तय करते हैं, और घटती है कैलोरी डेफिसिट से। "
        "तो एब्स दिखाने के लिए, हल्के डेफिसिट में खाएं, प्रोटीन ज्यादा रखें, वजन उठाएं और एक्टिव रहें। "
        "एब्स को किसी मसल की तरह ट्रेन करें, पर दिखाएं किचन से। "
        "फैक्ट्स पर ट्रेनिंग के लिए फॉलो करें, मिथकों पर नहीं।"
    ),
    "hashtags_extra": ["fitnessmyths", "absworkout", "fatloss", "mythbusting"],
    "cta": "Follow to train on facts, not myths.",
},
# ---- 17. Compilation: 5 tips ----
{
    "key": "compilation_tips", "label": "5 Gym Tips in 40 Seconds", "emoji": FILM,
    "label_hi": "40 सेकंड में 5 जिम टिप्स", "sub_hi": "तेज टिप्स जो काम करती हैं",
    "hook_hi": "5 टिप्स, तेज",
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
    "script_hi": (
        "चालीस सेकंड में पांच जिम टिप्स। शुरू। "
        "एक, हर रेप का नीचे वाला हिस्सा कंट्रोल करें। स्लो नेगेटिव्स भारी झटके से ज्यादा मसल बनाते हैं। "
        "दो, फेलियर के पास ट्रेन करें, एक-दो रेप्स बाकी छोड़ें, दस नहीं। "
        "तीन, प्रोग्रेसिव ओवरलोड। हर सेशन पिछले हफ्ते से एक रेप या थोड़ा वजन ज्यादा करें। "
        "चार, प्रोटीन पूरा लें, शरीर के हर किलो वजन पर करीब दो ग्राम, रोज। "
        "पांच, सात से नौ घंटे सोएं, क्योंकि मसल असल में तभी बनती है। "
        "ये पांच अपना लें और आप नब्बे प्रतिशत लोगों से आगे हैं। "
        "रोज तेज टिप्स के लिए फॉलो करें।"
    ),
    "hashtags_extra": ["gymtips", "fitnesstips", "workout", "gymhacks"],
},
# ---- 18. How to lose fat ----
{
    "key": "howto_fatloss", "label": "How to Lose Fat", "emoji": DROP,
    "label_hi": "फैट कैसे घटाएं", "sub_hi": "स्टेप बाय स्टेप फैट लॉस",
    "hook_hi": "फैट घटाने का तरीका",
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
    "script_hi": (
        "फैट कैसे घटाएं, स्टेप बाय स्टेप, बिना किसी नौटंकी के। "
        "स्टेप एक, हल्के कैलोरी डेफिसिट में खाएं। खाने से थोड़ा ज्यादा जलाएं, असल में फैट सिर्फ इसी से घटता है। "
        "स्टेप दो, प्रोटीन ज्यादा रखें ताकि मसल बची रहे और पेट भरा लगे, जिससे फैट घटे, मसल नहीं। "
        "स्टेप तीन, हफ्ते में तीन-चार बार वजन उठाएं, ताकि शरीर को मसल बनाए रखने की वजह मिले। "
        "स्टेप चार, रोज चलें। कदम लंबे समय में कठिन कार्डियो से ज्यादा फैट जलाते हैं। "
        "स्टेप पांच, हफ्ते में करीब आधा किलो घटाने का लक्ष्य रखें, धीरे और टिकाऊ। "
        "ये पांच करें और फैट हमेशा के लिए जाएगा। "
        "रोज एक नई टिप के लिए फॉलो करें।"
    ),
    "hashtags_extra": ["fatloss", "howto", "weightloss", "caloriedeficit"],
    "cta": "Follow for a how-to every day.",
},
# ---- 19. Science: reps & sets ----
{
    "key": "science_reps", "label": "How Many Reps to Grow", "emoji": BRAIN,
    "label_hi": "कितने रेप्स से ग्रोथ", "sub_hi": "रेप्स और सेट्स का विज्ञान",
    "hook_hi": "कितने रेप्स?",
    "category": "science", "style": "edu",
    "sub": "Reps and sets, settled",
    "stock_keywords": ["dumbbell reps gym", "counting reps workout",
                       "barbell training sets", "focused lifting gym", "gym training intense"],
    "hook": "REPS, SETTLED",
    "script": (
        "How many reps should you actually do to build muscle? Here's what the science says. "
        "The sweet spot for growth is roughly six to fifteen reps per set, taken close to failure. "
        "What matters most isn't the exact number — it's that the last few reps are genuinely hard. "
        "Heavier sets of six to eight build more strength; lighter sets of twelve to fifteen give a great pump. Use both. "
        "Aim for around ten to twenty hard sets per muscle group per week, spread over two sessions. "
        "And push each set close to failure, leaving one or two reps in the tank. "
        "Effort plus the right rep range equals growth. "
        "Follow for training backed by science."
    ),
    "script_hi": (
        "मसल बनाने के लिए असल में कितने रेप्स करने चाहिए? यह रहा विज्ञान। "
        "ग्रोथ के लिए सबसे अच्छी रेंज है हर सेट में करीब छह से पंद्रह रेप्स, फेलियर के पास तक। "
        "सबसे जरूरी सही संख्या नहीं, बल्कि यह है कि आखिरी कुछ रेप्स सच में मुश्किल हों। "
        "छह से आठ के भारी सेट ताकत ज्यादा बढ़ाते हैं, बारह से पंद्रह के हल्के सेट अच्छा पंप देते हैं। दोनों इस्तेमाल करें। "
        "हर मसल ग्रुप के लिए हफ्ते में करीब दस से बीस हार्ड सेट रखें, दो सेशन में बांटकर। "
        "और हर सेट फेलियर के पास ले जाएं, एक-दो रेप्स बाकी छोड़कर। "
        "मेहनत और सही रेप रेंज मिलकर ग्रोथ देते हैं। "
        "विज्ञान वाली ट्रेनिंग के लिए फॉलो करें।"
    ),
    "hashtags_extra": ["repsandsets", "hypertrophy", "gymscience", "musclegrowth"],
    "cta": "Follow for training backed by science.",
},
# ---- 20. How to: first pull-up ----
{
    "key": "howto_firstpullup", "label": "Get Your First Pull-Up", "emoji": LIFT,
    "label_hi": "पहला पुल-अप कैसे करें", "sub_hi": "जीरो से पहला पुल-अप",
    "hook_hi": "पहला पुल-अप",
    "category": "howto", "style": "edu",
    "sub": "From zero to your first rep",
    "stock_keywords": ["pull up bar workout", "assisted pull up band",
                       "hanging bar grip", "lat pulldown gym", "negative pull up"],
    "hook": "YOUR FIRST PULL-UP",
    "script": (
        "Can't do a single pull-up yet? Here's how to get your first one, step by step. "
        "Step one: just hang from the bar for thirty seconds at a time to build grip and shoulder strength. "
        "Step two: do negatives. Jump to the top, then lower yourself as slowly as you can — aim for three to five seconds down. "
        "Step three: use a resistance band looped on the bar for assisted reps, and use a thinner band as you get stronger. "
        "Step four: train lat pulldowns and rows so your back gets stronger every week. "
        "Do this two or three times a week and that first clean pull-up is closer than you think. "
        "Follow for a how-to every day."
    ),
    "script_hi": (
        "अभी एक भी पुल-अप नहीं कर पाते? यह रहा पहला पुल-अप पाने का तरीका, स्टेप बाय स्टेप। "
        "स्टेप एक, बार पर बस तीस-तीस सेकंड लटकें, इससे ग्रिप और कंधे की ताकत बनेगी। "
        "स्टेप दो, नेगेटिव्स करें। कूदकर ऊपर जाएं, फिर खुद को जितना धीरे हो सके नीचे लाएं, तीन से पांच सेकंड में। "
        "स्टेप तीन, बार पर रेजिस्टेंस बैंड लगाकर असिस्टेड रेप्स करें, और मजबूत होते जाएं तो पतला बैंड लें। "
        "स्टेप चार, लैट पुलडाउन और रो करें ताकि बैक हर हफ्ते मजबूत हो। "
        "हफ्ते में दो-तीन बार यह करें और पहला साफ पुल-अप जितना सोचते हैं उससे पास है। "
        "रोज एक नई टिप के लिए फॉलो करें।"
    ),
    "hashtags_extra": ["pullups", "howto", "calisthenics", "backday"],
    "cta": "Follow for a how-to every day.",
},
# ---- 21. Myth: soreness ----
{
    "key": "myth_soreness", "label": "Soreness Myth", "emoji": CROSS,
    "label_hi": "दर्द का मिथक", "sub_hi": "दर्द का मतलब ग्रोथ नहीं",
    "hook_hi": "मिथक गलत",
    "category": "myth", "style": "edu",
    "sub": "Sore doesn't mean growth",
    "stock_keywords": ["muscle soreness stretch", "gym recovery rest",
                       "athlete tired workout", "foam rolling recovery", "gym training hard"],
    "hook": "MYTH BUSTED",
    "script": (
        "Myth: if you're not sore, your workout didn't work. Let's bust it. "
        "Soreness just means you did something your body isn't used to yet. It is not a scoreboard for muscle growth. "
        "Beginners and people trying new exercises get very sore. Trained lifters often grow fast while barely feeling sore at all. "
        "What actually builds muscle is progressive overload — doing a little more over time — not how wrecked you feel the next day. "
        "Chasing soreness on purpose just hurts your recovery and your next session. "
        "So track your reps and weights, not your soreness. "
        "Follow to train on facts, not myths."
    ),
    "script_hi": (
        "मिथक, अगर दर्द नहीं हुआ तो वर्कआउट काम नहीं आया। चलिए इसे तोड़ते हैं। "
        "दर्द का बस इतना मतलब है कि आपने कुछ ऐसा किया जिसका शरीर को अभी आदत नहीं। यह मसल ग्रोथ का स्कोरबोर्ड नहीं। "
        "शुरुआती लोगों और नई एक्सरसाइज करने वालों को बहुत दर्द होता है। अनुभवी लोग अक्सर बिना ज्यादा दर्द के तेजी से बढ़ते हैं। "
        "मसल असल में प्रोग्रेसिव ओवरलोड से बनती है, समय के साथ थोड़ा ज्यादा करने से, न कि अगले दिन कितना दर्द हुआ उससे। "
        "जानबूझकर दर्द के पीछे भागना बस आपकी रिकवरी और अगला सेशन खराब करता है। "
        "तो दर्द नहीं, अपने रेप्स और वजन ट्रैक करें। "
        "फैक्ट्स पर ट्रेनिंग के लिए फॉलो करें, मिथकों पर नहीं।"
    ),
    "hashtags_extra": ["fitnessmyths", "doms", "recovery", "mythbusting"],
    "cta": "Follow to train on facts, not myths.",
},
]

# --- Paths ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

# --- Voice (edge-tts neural voices; free, no key) ---
# English + Hindi primaries, each with backups, then gTTS as last resort.
VOICE_CONFIG = {
    "en": {
        "primary": "en-US-ChristopherNeural",
        "backups": ["en-US-GuyNeural", "en-US-AndrewMultilingualNeural",
                    "en-US-EricNeural", "en-GB-RyanNeural"],
        "rate": "+8%", "pitch": "+0Hz", "gtts_lang": "en",
    },
    "hi": {
        "primary": "hi-IN-MadhurNeural",
        "backups": ["hi-IN-SwaraNeural", "en-US-AndrewMultilingualNeural"],
        "rate": "+0%", "pitch": "+0Hz", "gtts_lang": "hi",
    },
}

# Caption fonts per language (installed on the runner via the workflow).
FONT_EN = "DejaVu Sans"
FONT_HI = "Lohit Devanagari"   # Devanagari-capable; from fonts-lohit-deva

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
"""Rotation — the repeat fix.

Two posts per day. 'part' (1 = morning, 2 = evening) is passed in from the
workflow based on WHICH cron fired, so GitHub's scheduler drift can no longer
make both daily runs pick the same slot (that was the cause of same-day
duplicate uploads).

A monotonic post counter (days since an epoch * 2 + part) walks the whole
CONTENT library one entry at a time, so the two daily posts are always
different, consecutive topics. Language alternates by slot: morning = English,
evening = Hindi. With an odd-length library, every topic cycles through both
languages over time.
"""

EPOCH = datetime.date(2026, 1, 1)

def current_part():
    """1 = morning, 2 = evening. Comes from VIDEO_PART (set by the workflow from
    the cron that fired, or the manual input). Falls back to UTC hour only if
    that is somehow unset."""
    env = os.environ.get("VIDEO_PART", "").strip()
    if env in ("1", "2"):
        return int(env)
    hour = datetime.datetime.utcnow().hour
    return 1 if hour < 11 else 2

def pick_content():
    """Return (entry, part, lang). Walks the whole library one topic per post."""
    part = current_part()
    days = (datetime.date.today() - EPOCH).days
    slot = days * 2 + (part - 1)        # monotonic post number (…,N,N+1,…)
    topic_idx = slot % len(CONTENT)
    lang = "en" if part == 1 else "hi"
    entry = CONTENT[topic_idx]
    print(f"[topics] {entry['label']} | {entry['category']} | Part {part} "
          f"| lang {lang} | idx {topic_idx}/{len(CONTENT)}")
    return entry, part, lang

# ===== script_gen =====
"""Assemble SEO metadata around each content entry's ready-made script, in the
chosen language. Deterministic, no API key needed.
"""

BASE_TAGS = ["gym", "fitness", "workout", "gymtok", "fitfam", "bodybuilding",
             "gymmotivation", "fitnessmotivation", "training", "shorts", "reels"]

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

DEFAULT_CTA_EN = "If this helped, like, share, and subscribe for your daily dose."
DEFAULT_CTA_HI = "पसंद आया तो लाइक, शेयर और सब्सक्राइब करना न भूलें।"
HINDI_EXTRA_TAGS = ["hindi", "fitnesshindi", "gymhindi", "workouthindi"]

def generate(entry, part, lang="en"):
    hi = (lang == "hi")
    label = entry.get("label_hi", entry["label"]) if hi else entry["label"]
    emoji = entry.get("emoji", CHEST)
    sub = entry.get("sub_hi", entry.get("sub", "")) if hi else entry.get("sub", "")
    script = entry.get("script_hi", entry["script"]) if hi else entry["script"]
    hook = (entry.get("hook_hi") or entry.get("hook") or label) if hi else entry.get("hook", label.upper())
    cta = (entry.get("cta_hi", DEFAULT_CTA_HI) if hi else entry.get("cta", DEFAULT_CTA_EN))

    # Title
    if hi:
        title = f"{label} {emoji} | {sub} #shorts #fitness #hindi"
    else:
        title = f"{label} {emoji} | {sub} #shorts #fitness"
    if len(title) > 100:
        title = title[:100]

    hashtags = list(dict.fromkeys(
        entry.get("hashtags_extra", [])
        + CATEGORY_HASHTAGS.get(entry["category"], [])
        + (HINDI_EXTRA_TAGS if hi else [])
        + ["gym", "fitness", "shorts", "reels", "fyp"]
    ))[:15]
    tag_line = " ".join("#" + h for h in hashtags)

    description = (
        f"{label} — {sub}.\n\n"
        f"{script}\n\n"
        f"{cta}\n\n{tag_line}"
    )

    tags = list(dict.fromkeys(
        [entry["key"].replace("_", " "), entry["label"].lower(), entry["category"],
         "fitness", "workout", "gym tips"] + BASE_TAGS + (["hindi fitness"] if hi else [])
    ))[:15]

    print(f"[script] {label} Part {part} ({lang}) | {title[:50]}...")
    return {
        "hook": hook,
        "title": title,
        "script": script,
        "description": description,
        "keywords": entry["stock_keywords"],
        "hashtags": hashtags,
        "tags": tags,
        "category_id": YT_CATEGORY.get(entry["category"], "17"),
        "lang": lang,
        "font": FONT_HI if hi else FONT_EN,
        "audio_lang": "hi" if hi else "en",
    }

# ===== captions =====
"""Animated, word-by-word captions in ASS ("Hormozi" style). Font is chosen by
language so Hindi (Devanagari) renders correctly."""

WHITE = "&H00FFFFFF"
ACCENT = "&H0000F5FF"   # warm yellow
OUTLINE = "&H00000000"
BACK = "&H90000000"

WORDS_PER_PHRASE = 3
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

def _header(font):
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
        f"Style: Base,{font},{FONTSIZE},{WHITE},{ACCENT},{OUTLINE},{BACK},"
        "1,0,0,0,100,100,0,0,1,7,4,2,80,80,620,1\n"
        f"Style: Hook,{font},128,{ACCENT},{WHITE},{OUTLINE},{BACK},"
        "1,0,0,0,100,100,0,0,1,9,5,8,60,60,300,1\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, "
        "Effect, Text\n"
    )

def _phrase_groups(words):
    groups = []
    for i in range(0, len(words), WORDS_PER_PHRASE):
        groups.append(words[i:i + WORDS_PER_PHRASE])
    return groups

def build_ass(words, ass_path, hook=None, font=FONT_EN, upper_hook=True):
    lines = [_header(font)]
    if hook:
        hook_disp = hook.upper() if upper_hook else hook
        hook_text = (r"{\fad(150,250)\fscx60\fscy60\t(0,220,\fscx104\fscy104)"
                     r"\t(220,360,\fscx100\fscy100)}" + hook_disp)
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
    tokens = script_text.split()
    per = duration / max(1, len(tokens))
    return [{"text": t, "start": i * per, "end": (i + 1) * per}
            for i, t in enumerate(tokens)]

# ===== voice =====
"""Language-aware voiceover with edge-tts, retried across backup voices, then
gTTS as a last resort so Microsoft's intermittent 403s can't kill a run."""

async def _synthesize(text, mp3_path, voice, rate, pitch):
    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    words = []
    with open(mp3_path, "wb") as audio_file:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_file.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                start = chunk["offset"] / 1e7
                dur = chunk["duration"] / 1e7
                words.append({"text": chunk["text"], "start": start,
                              "end": start + dur})
    return words

def _gtts_fallback(text, mp3_path, gtts_lang):
    from gtts import gTTS
    gTTS(text=text, lang=gtts_lang, slow=False).save(mp3_path)
    return []

def make_voiceover(text, out_dir, lang="en"):
    """Return (mp3_path, words). Tries the language's primary edge voice, then
    its backups, then gTTS in that language."""
    os.makedirs(out_dir, exist_ok=True)
    mp3_path = os.path.join(out_dir, "mp3")
    cfg = VOICE_CONFIG.get(lang, VOICE_CONFIG["en"])
    voices = [cfg["primary"]] + cfg["backups"]
    for voice in voices:
        for attempt in range(1, 3):
            try:
                words = asyncio.run(_synthesize(text, mp3_path, voice,
                                                cfg["rate"], cfg["pitch"]))
                if os.path.exists(mp3_path) and os.path.getsize(mp3_path) > 2000:
                    print(f"[voice] Voiceover ready ({voice}) with {len(words)} word timings.")
                    return mp3_path, words
                print(f"[voice] {voice} produced empty audio (try {attempt}); retrying.")
            except Exception as e:  # noqa: BLE001
                print(f"[voice] {voice} failed try {attempt} ({e}).")
                time.sleep(2 * attempt)
    try:
        print(f"[voice] edge-tts unavailable; falling back to gTTS ({cfg['gtts_lang']}).")
        words = _gtts_fallback(text, mp3_path, cfg["gtts_lang"])
        print("[voice] gTTS voiceover ready (even-spaced captions).")
        return mp3_path, words
    except Exception as e:  # noqa: BLE001
        print(f"[voice] gTTS fallback also failed ({e}).")
        raise

# ===== visuals =====
"""Pexels stock video (free key) with an animated-gradient fallback."""

PEXELS_SEARCH = "https://api.pexels.com/videos/search"

GRADIENTS = [
    ((18, 22, 48), (86, 44, 120)),
    ((10, 30, 40), (14, 92, 110)),
    ((40, 16, 32), (150, 46, 60)),
    ((12, 28, 20), (30, 100, 70)),
    ((26, 24, 18), (120, 84, 30)),
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
        t = np.linspace(0.0, 1.0, HEIGHT, dtype=np.float32)[:, None]
        col = (top_arr[None, :] + (bottom_arr - top_arr)[None, :] * t)
        row = np.broadcast_to(col[:, None, :], (HEIGHT, WIDTH, 3))
        img = Image.fromarray(row.astype(np.uint8), "RGB")
        path = os.path.join(out_dir, f"bg_{i}.png")
        img.save(path)
        imgs.append({"type": "image", "path": path})
    print(f"[visuals] Generated {len(imgs)} gradient backgrounds (no Pexels key).")
    return imgs

def get_visuals(keywords, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    if PEXELS_API_KEY:
        clips = _download_pexels(keywords, out_dir)
        if clips:
            return clips
        print("[visuals] No Pexels clips returned; falling back to gradients.")
    return _make_gradient_backgrounds(out_dir)

# ===== assemble =====
def _run(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

def _probe_duration(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True, check=True)
    return float(out.stdout.strip())

def generate_ambient_music(duration, out_path, work_dir):
    import wave as wavmod
    sr = 44100
    n = int(duration * sr)
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

GRADIENT_COLORS = [
    ("0x030814", "0x0a2540", "0x0e7c8c"),
    ("0x05010f", "0x1b1050", "0x0e5c8c"),
    ("0x00110f", "0x073b3a", "0x0aa0a0"),
]

def _animated_gradient_bg(duration, out_path, work_dir):
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
        seg_dur = duration / n + 0.6
        segs = []
        for i, v in enumerate(videos):
            sp = os.path.join(work_dir, f"seg_{i}.mp4")
            _clip_segment(v["path"], seg_dur, sp)
            segs.append(sp)
        _xfade_concat(segs, seg_dur, bg_path, work_dir)
        return bg_path
    return _animated_gradient_bg(duration, bg_path, work_dir)

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
def run():
    stamp = datetime.date.today().isoformat()
    day_dir = os.path.join(OUTPUT_DIR, stamp)
    work_dir = os.path.join(day_dir, "work")
    os.makedirs(work_dir, exist_ok=True)

    # 1) today's content item + part (1=morning/EN, 2=evening/HI) + language
    entry, part, lang = pick_content()

    # 2) script + SEO metadata in the chosen language
    content = generate(entry, part, lang)

    # 3) voiceover (+ real word timings) and animated captions
    mp3_path, words = voice_step(content["script"], work_dir, lang)
    if not words:
        cap_dur = _probe_duration(mp3_path)
        words = even_word_times(content["script"], cap_dur)
        print(f"[captions] no TTS word timings; using {len(words)} evenly-spaced.")
    ass_path = os.path.join(work_dir, "ass")
    build_ass(words, ass_path, hook=content.get("hook"),
              font=content.get("font", FONT_EN),
              upper_hook=(lang == "en"))

    # 4) visuals
    assets = get_visuals(content["keywords"], work_dir)

    # 5) background music
    vdur = _probe_duration(mp3_path)
    music_path = pick_music(work_dir, vdur)

    # 6) assemble
    out_path = os.path.join(
        day_dir, f"video_{stamp}_part{part}_{lang}_{entry['key']}.mp4")
    build_video(assets, mp3_path, ass_path, out_path, work_dir,
                music_path=music_path)

    # 7) SEO metadata for the uploaders
    meta = {
        "date": stamp,
        "content_key": entry["key"],
        "category": entry["category"],
        "label": content.get("title", entry["label"]),
        "part": part,
        "lang": lang,
        "audio_lang": content.get("audio_lang", "en"),
        "title": content["title"],
        "description": content["description"],
        "hashtags": content["hashtags"],
        "tags": content["tags"],
        "category_id": content["category_id"],
        "video_path": out_path,
    }
    meta_path = os.path.join(day_dir, f"meta_part{part}.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    print(f"\n[main] Done. Video: {out_path}\n[main] Meta: {meta_path}")

    try:
        upload_youtube(out_path, meta)
    except Exception as e:  # noqa: BLE001
        print(f"[youtube] upload failed ({e}); video still saved as an artifact.")

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
    """Upload the finished video to YouTube as a public Short."""
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
    audio_lang = meta.get("audio_lang", "en")

    body = {
        "snippet": {
            "title": title,
            "description": desc,
            "tags": tags,
            "categoryId": category_id,
            "defaultLanguage": audio_lang,
            "defaultAudioLanguage": audio_lang,
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

def voice_step(script_text, work_dir, lang="en"):
    return make_voiceover(script_text, work_dir, lang)

def pick_music(work_dir, duration):
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
