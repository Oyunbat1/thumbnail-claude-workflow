

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance, ImageOps
import csv
import os
import sys
import hashlib
import random

# Load .env file if present (no external dependencies required)
_env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())

sys.path.insert(0, "D:/py_packages")

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# =============================================================
# CONFIGURATION
# =============================================================

WIDTH  = 1280
HEIGHT = 720

# Brand colors — Lambda (shared)
ACCENT_COLOR    = "#4CC9A0"       # Lambda mint teal-green
ACCENT_DARK     = "#FFFFFF"       # Text on teal boxes

# Style alternation: "alternate", "random", "dark", "bright"
STYLE_MODE = "alternate"

# Per-style settings
STYLES = {
    "dark": {
        "bg_color":     "#0A0F1A",   # Very dark navy
        "topic_color":  "#FFFFFF",   # White text
        "overlay":      (5, 20, 12, 165),   # Dark green overlay on illustration
        "text_stroke":  (0, 0, 0, 220),     # Black stroke for white text
        "face_stroke":  (255, 255, 255, 255),
        "logo_color":   (255, 255, 255),
        "prompt_style": "dark cinematic moody dramatic teal glow professional wide 16:9",
    },
    "bright": {
        "bg_color":     "#F0FAF6",   # Very light teal-white
        "topic_color":  "#0D1B2A",   # Dark navy text
        "overlay":      (240, 250, 246, 120),  # Light teal-white wash on illustration
        "text_stroke":  (255, 255, 255, 160),  # White halo for dark text
        "face_stroke":  (76, 201, 160, 200),   # Teal stroke = ACCENT_COLOR
        "logo_color":   (13, 27, 42),
        "prompt_style": "bright airy clean modern professional light studio minimal wide 16:9",
    },
}

# Kept for fallback references
BG_COLOR    = STYLES["dark"]["bg_color"]
TOPIC_COLOR = STYLES["dark"]["topic_color"]

# Face
FACE_HEIGHT_RATIO = 0.85          # Face height as frction of canvas (0.98=huge, 0.75=medium, 0.60=small)
FACE_VERTICAL     = "bottom"      # "bottom" = anchor to bottom, "center" = vertically centered
FACE_X_OFFSET     = 90            # Pixels from left edge (higher = more right)
USE_BG_REMOVAL    = True

# Text sizes
NAME_FONT_SIZE      = 38
TOPIC_FONT_SIZE     = 68          # Big bold main text (6 words or fewer)
HIGHLIGHT_FONT_SIZE = 28          # Keyword in teal box
TOPIC_MAX_WIDTH     = 560         # Right-side text column width

# Background
USE_GRADIENT_BG    = True         # Glow effects layered on illustration
USE_ILLUSTRATIONS  = True         # AI illustration per topic
ILLUSTRATION_AS_BG = True         # Use illustration as full background

# Replicate API
REPLICATE_API_TOKEN   = os.environ.get("REPLICATE_API_TOKEN", "")

# Anthropic API (for smart prompt generation)
ANTHROPIC_API_KEY     = os.environ.get("ANTHROPIC_API_KEY", "")
ILLUSTRATIONS_FOLDER  = "illustrations"
BG_OVERLAY_OPACITY    = 170       # How dark the illustration overlay is (lower = more visible)

# Logo
LOGO_PATH = "brand/Lambda-logo-white.png"
LOGO_SIZE = (280, 280)

# Misc
CSV_FILE     = "thumbnails.csv"
FACES_FOLDER = "faces"
OUTPUT_FOLDER = "output"
FONT_PATH     = "brand/NotoSans-Bold.ttf"

# =============================================================
# HELPERS
# =============================================================

def load_font(size):
    if FONT_PATH and os.path.exists(FONT_PATH):
        return ImageFont.truetype(FONT_PATH, size)
    for name in [
        "/System/Library/Fonts/Supplemental/Verdana Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibrib.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        # Linux
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/ArialHB.ttc",
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/HelveticaNeue.ttc",
    ]:
        if os.path.exists(name):
            return ImageFont.truetype(name, size)
    return ImageFont.load_default()


def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def hex_to_rgba(h, a=255):
    r, g, b = hex_to_rgb(h)
    return (r, g, b, a)


def prepare_logo(path, size, recolor=None):
    """Load logo, resize, and optionally recolor white pixels to a target color."""
    logo = Image.open(path).convert("RGBA")
    logo.thumbnail(size, Image.LANCZOS)
    if recolor:
        r, g, b = recolor
        data = logo.getdata()
        logo.putdata([
            (r, g, b, a) if a > 10 else (0, 0, 0, 0)
            for (_, _, _, a) in data
        ])
    return logo


def add_stroke(img, stroke_width=10, color=(255, 255, 255, 255)):
    """Add a solid stroke outline around a transparent-background image."""
    r, g, b, a = img.split()
    # Dilate the alpha to get the stroke mask
    dilated = a.filter(ImageFilter.MaxFilter(stroke_width * 2 + 1))
    stroke_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    stroke_fill  = Image.new("RGBA", img.size, color)
    stroke_layer.paste(stroke_fill, mask=dilated)
    return Image.alpha_composite(stroke_layer, img)


def draw_rounded_rect(draw, xy, radius, fill):
    x0, y0, x1, y1 = [int(v) for v in xy]
    r = min(radius, (x1-x0)//2, (y1-y0)//2)
    draw.rectangle([x0+r, y0, x1-r, y1], fill=fill)
    draw.rectangle([x0, y0+r, x1, y1-r], fill=fill)
    draw.ellipse([x0, y0, x0+2*r, y0+2*r], fill=fill)
    draw.ellipse([x1-2*r, y0, x1, y0+2*r], fill=fill)
    draw.ellipse([x0, y1-2*r, x0+2*r, y1], fill=fill)
    draw.ellipse([x1-2*r, y1-2*r, x1, y1], fill=fill)


def wrap_text(text, font, max_width, draw):
    words = text.split()
    lines, cur = [], ""
    for word in words:
        test = f"{cur} {word}".strip()
        bb = draw.textbbox((0, 0), test, font=font)
        if bb[2] - bb[0] <= max_width:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def create_gradient_bg(face_x_center=WIDTH//4, style="dark"):
    """Glow background — dark moody or bright airy depending on style."""
    s = STYLES[style]
    bg = Image.new("RGBA", (WIDTH, HEIGHT), (*hex_to_rgb(s["bg_color"]), 255))
    accent = hex_to_rgb(ACCENT_COLOR)
    cx, cy = face_x_center, HEIGHT // 2

    if style == "dark":
        # Dark: deep glow behind face + subtle teal top-right
        glow1 = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
        ImageDraw.Draw(glow1).ellipse([cx-350, cy-350, cx+350, cy+350], fill=(10, 25, 50, 160))
        bg = Image.alpha_composite(bg, glow1.filter(ImageFilter.GaussianBlur(90)))

        glow2 = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
        ImageDraw.Draw(glow2).ellipse([WIDTH-300, -150, WIDTH+100, 250], fill=(*accent, 40))
        bg = Image.alpha_composite(bg, glow2.filter(ImageFilter.GaussianBlur(70)))
    else:
        # Bright: soft teal bloom behind face + corner accent
        glow1 = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
        ImageDraw.Draw(glow1).ellipse([cx-420, cy-380, cx+420, cy+380], fill=(*accent, 45))
        bg = Image.alpha_composite(bg, glow1.filter(ImageFilter.GaussianBlur(110)))

        glow2 = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
        ImageDraw.Draw(glow2).ellipse([WIDTH-280, -120, WIDTH+80, 220], fill=(*accent, 28))
        bg = Image.alpha_composite(bg, glow2.filter(ImageFilter.GaussianBlur(80)))

        glow3 = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
        ImageDraw.Draw(glow3).ellipse([WIDTH//2-300, HEIGHT-200, WIDTH//2+300, HEIGHT+200],
                                      fill=(*accent, 18))
        bg = Image.alpha_composite(bg, glow3.filter(ImageFilter.GaussianBlur(90)))

    return bg


# =============================================================
# REPLICATE API
# =============================================================

def _replicate_headers():
    return {"Authorization": f"Bearer {REPLICATE_API_TOKEN}",
            "Content-Type": "application/json", "Prefer": "wait"}


def _replicate_poll(result, headers, label):
    import urllib.request, json, time
    while result.get("status") not in ("succeeded", "failed", "canceled"):
        time.sleep(3)
        poll = urllib.request.Request(result["urls"]["get"], headers=headers)
        with urllib.request.urlopen(poll, timeout=30) as r:
            result = json.loads(r.read())
    if result.get("status") != "succeeded":
        print(f"    {label} failed: {result.get('error')}")
        return None
    return result


def _replicate_post(endpoint, input_data, label="Replicate"):
    import urllib.request, json, time
    headers = _replicate_headers()
    payload = json.dumps({"input": input_data}).encode()
    for _ in range(6):
        req = urllib.request.Request(endpoint, data=payload, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return _replicate_poll(json.loads(r.read()), headers, label)
        except Exception as e:
            try:
                err = json.loads(e.read().decode())
            except Exception:
                print(f"    {label} error: {e}"); return None
            if err.get("status") == 429:
                wait = err.get("retry_after", 12) + 2
                print(f"    Rate limited — waiting {wait}s..."); time.sleep(wait)
            else:
                print(f"    {label} error: {err.get('detail', err)}"); return None
    return None


def _replicate_post_versioned(version_hash, input_data, label="Replicate"):
    import urllib.request, json, time
    headers = _replicate_headers()
    payload = json.dumps({"version": version_hash, "input": input_data}).encode()
    for _ in range(6):
        req = urllib.request.Request(
            "https://api.replicate.com/v1/predictions",
            data=payload, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return _replicate_poll(json.loads(r.read()), headers, label)
        except Exception as e:
            try:
                err = json.loads(e.read().decode())
            except Exception:
                print(f"    {label} error: {e}"); return None
            if err.get("status") == 429:
                wait = err.get("retry_after", 12) + 2
                print(f"    Rate limited — waiting {wait}s..."); time.sleep(wait)
            else:
                print(f"    {label} error: {err.get('detail', err)}"); return None
    return None


def auto_generate_prompt(topic, style="dark"):
    """Keyword → prompt mapping for Mongolian topics, with dark/bright variants."""
    t = topic.lower()
    dark_map = {
        "ai":       "futuristic AI neural network glowing teal nodes dark space cinematic wide 16:9",
        "хиймэл":   "futuristic AI neural network glowing teal nodes dark space cinematic wide 16:9",
        "gemini":   "Google Gemini AI holographic interface dark space teal glow cinematic wide",
        "chatgpt":  "holographic AI chat interface dark space teal neon glow futuristic cinematic wide",
        "claude":   "futuristic AI assistant glowing teal hologram dark cinematic wide",
        "perplexity":"AI search engine glowing data streams dark space teal cinematic wide",
        "шинжилгээ":"futuristic data visualization glowing charts dark blue teal cinematic wide",
        "мэдээлэл": "futuristic data visualization glowing charts dark blue teal cinematic wide",
        "бичлэг":   "cinematic video production studio camera equipment dramatic dark background wide",
        "видео":    "cinematic video production studio camera equipment dramatic dark background wide",
        "автомат":  "industrial automation glowing robotic arms circuit boards dark teal cinematic wide",
        "чатбот":   "futuristic chatbot hologram dark space speech bubbles teal glow cinematic wide",
        "код":      "dark hacker room glowing code screens teal terminal light cinematic wide",
        "програм":  "dark hacker room glowing code screens teal terminal light cinematic wide",
        "байгуулла":"sleek corporate office dramatic city skyline teal accent cinematic wide",
        "маркетинг":"digital marketing hologram social media icons dark teal neon cinematic wide",
        "мөнгө":    "futuristic finance dashboard glowing gold teal coins dark cinematic wide",
        "санхүү":   "futuristic finance dashboard glowing gold teal coins dark cinematic wide",
        "эрүүл":    "sleek gym dramatic lighting silhouette teal accent motivational cinematic wide",
        "сур":      "futuristic digital classroom glowing holographic books teal cinematic wide",
        "labor":    "modern HR office bright city skyline professional workspace teal cinematic wide",
        "ажилтн":   "professional modern office workspace clean teal accent cinematic wide",
    }
    bright_map = {
        "ai":       "clean modern tech desk white background holographic AI display minimal bright",
        "хиймэл":   "clean modern tech desk white background holographic AI display minimal bright",
        "gemini":   "bright modern workspace Google colors clean minimal professional wide",
        "chatgpt":  "bright clean office laptop chat interface minimal white professional wide",
        "claude":   "bright airy tech workspace minimal holographic interface clean professional wide",
        "perplexity":"bright open office search interface clean minimal professional light wide",
        "шинжилгээ":"bright clean data dashboard light minimal modern office professional wide",
        "мэдээлэл": "bright clean data dashboard light minimal modern office professional wide",
        "бичлэг":   "bright modern studio clean white camera gear minimal professional wide",
        "видео":    "bright modern studio clean white camera gear minimal professional wide",
        "автомат":  "bright clean industrial design minimal automation robot white professional wide",
        "байгуулла":"bright corporate office panoramic window clean minimal professional wide",
        "маркетинг":"bright clean social media dashboard light modern minimal professional wide",
        "мөнгө":    "bright clean finance desk light minimal coins modern professional wide",
        "санхүү":   "bright clean finance desk light minimal modern professional wide",
        "эрүүл":    "bright airy gym natural light clean minimal motivational professional wide",
        "сур":      "bright clean classroom natural light books minimal modern professional wide",
        "labor":    "bright open modern office natural light minimal HR professional wide",
        "ажилтн":   "bright airy modern office workspace natural light clean minimal wide",
    }
    mapping = dark_map if style == "dark" else bright_map
    for kw, scene in mapping.items():
        if kw in t:
            return scene
    if style == "dark":
        return "cinematic dark studio dramatic teal accent glow professional futuristic wide 16:9"
    return "bright airy clean modern studio white background teal accent minimal professional wide 16:9"


def claude_generate_prompt(topic, style="dark"):
    """Use Claude API to generate a topic-relevant image prompt matching the style."""
    if not ANTHROPIC_API_KEY:
        return None
    import urllib.request, json
    style_desc = STYLES[style]["prompt_style"]
    system = (
        "You generate short background image prompts for YouTube thumbnails. "
        "Given a video topic (possibly in Mongolian), output ONLY a single English prompt "
        "describing a vivid scene that visually matches the topic. "
        f"Style: {style_desc}. "
        "Keep it under 20 words. No explanations, no quotes—just the prompt."
    )
    payload = json.dumps({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 100,
        "system": system,
        "messages": [{"role": "user", "content": topic}],
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            result = json.loads(r.read())
        return result["content"][0]["text"].strip()
    except Exception as e:
        print(f"    Claude prompt generation failed: {e}")
        return None


def auto_extract_highlight(topic):
    """Last word(s) as fallback highlight phrase."""
    words = topic.strip().split()
    if not words:
        return ""
    last = words[-1]
    # Include preceding word if last is very short (e.g. "Вэ?")
    if len(last.rstrip("?!.,")) <= 3 and len(words) >= 2:
        return f"{words[-2]} {last}".upper()
    return last.upper()


def generate_illustration(prompt):
    """Generate background via Replicate, cached by prompt hash."""
    import urllib.request
    os.makedirs(ILLUSTRATIONS_FOLDER, exist_ok=True)
    ph = hashlib.md5(prompt.encode()).hexdigest()[:12]
    cache = os.path.join(ILLUSTRATIONS_FOLDER, f"{ph}.png")
    if os.path.exists(cache):
        print(f"    (cached)")
        return Image.open(cache).convert("RGBA")
    if not REPLICATE_API_TOKEN:
        return None
    print(f"    Generating: {prompt[:60]}...")
    result = _replicate_post(
        "https://api.replicate.com/v1/models/black-forest-labs/flux-schnell/predictions",
        {"prompt": prompt, "aspect_ratio": "16:9"}, label="Illustration")
    if not result:
        return None
    url = result["output"][0] if isinstance(result["output"], list) else result["output"]
    urllib.request.urlretrieve(url, cache)
    return Image.open(cache).convert("RGBA")


def remove_face_background(face_path):
    """Remove background locally via rembg, cached per photo."""
    cache_dir = os.path.join(ILLUSTRATIONS_FOLDER, "nobg")
    os.makedirs(cache_dir, exist_ok=True)
    face_name = os.path.splitext(os.path.basename(face_path))[0]
    cache = os.path.join(cache_dir, f"{face_name}.png")
    if os.path.exists(cache):
        # Invalidate cache if source photo is newer
        if os.path.getmtime(face_path) <= os.path.getmtime(cache):
            print(f"    (cached bg removal)")
            return Image.open(cache).convert("RGBA")
        print(f"    Photo updated — re-processing bg removal...")
    print(f"    Removing background: {face_name}...")
    try:
        from rembg import remove as rembg_remove
    except ImportError:
        print("    rembg not installed — skipping bg removal")
        return None
    corrected = ImageOps.exif_transpose(Image.open(face_path))
    result = rembg_remove(corrected)
    result.save(cache)
    return result.convert("RGBA")


# =============================================================
# LAYOUT HELPERS
# =============================================================

def detect_category_tag(topic):
    """Auto-detect a short category tag from the topic text."""
    t = topic.lower()
    if any(k in t for k in ["chatgpt", "claude", "gemini", "perplexity", "ai", "хиймэл"]):
        return "AI"
    if any(k in t for k in ["labor", "ажилтн", "ажил", "гарын авлага", "сургалт", "hr"]):
        return "HR"
    if any(k in t for k in ["маркетинг"]):
        return "МАРКЕТИНГ"
    if any(k in t for k in ["санхүү", "мөнгө"]):
        return "САНХҮҮ"
    if any(k in t for k in ["бичлэг", "видео"]):
        return "ВИДЕО"
    if any(k in t for k in ["код", "програм"]):
        return "КОД"
    return "LAMBDA"


def _draw_line_with_highlight(draw, line, hl_upper, lx, ly, font, main_color, hl_color):
    """Draw a text line, coloring any occurrence of hl_upper in hl_color."""
    idx = line.upper().find(hl_upper)
    if idx == -1 or not hl_upper:
        draw.text((lx, ly), line, font=font, fill=main_color)
        return
    before  = line[:idx]
    keyword = line[idx:idx+len(hl_upper)]
    after   = line[idx+len(hl_upper):]
    cx = lx
    if before:
        bb = draw.textbbox((0, 0), before, font=font)
        draw.text((cx, ly), before, font=font, fill=main_color)
        cx += bb[2] - bb[0]
    bb = draw.textbbox((0, 0), keyword, font=font)
    draw.text((cx, ly), keyword, font=font, fill=hl_color)
    cx += bb[2] - bb[0]
    if after:
        draw.text((cx, ly), after, font=font, fill=main_color)


# =============================================================
# THUMBNAIL GENERATOR
# =============================================================

def generate_thumbnail(name, topic, topic_highlight, face_path, output_path, illustration_prompt="", style="dark"):
    """
    Viral-style layout:
      - Illustration background (topic-relevant) with dark or bright overlay
      - Face: left side, large
      - Right side: name pill → topic text → teal highlight box
      - Lambda logo: top-left
    """
    s = STYLES[style]

    # --- Background ---
    if USE_ILLUSTRATIONS and ILLUSTRATION_AS_BG and illustration_prompt:
        illus_img = generate_illustration(illustration_prompt)
        if illus_img:
            bg = illus_img.resize((WIDTH, HEIGHT), Image.LANCZOS).convert("RGBA")
            overlay = Image.new("RGBA", (WIDTH, HEIGHT), s["overlay"])
            bg = Image.alpha_composite(bg, overlay)
        else:
            bg = Image.new("RGBA", (WIDTH, HEIGHT), (*hex_to_rgb(s["bg_color"]), 255))
    elif USE_GRADIENT_BG:
        bg = create_gradient_bg(face_x_center=WIDTH // 4, style=style)
    else:
        bg = Image.new("RGBA", (WIDTH, HEIGHT), (*hex_to_rgb(s["bg_color"]), 255))

    # Blend style-appropriate glow on top of illustration
    if USE_GRADIENT_BG and USE_ILLUSTRATIONS and ILLUSTRATION_AS_BG:
        glow_overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
        cx, cy = WIDTH // 4, HEIGHT // 2 + 40
        fill = (10, 25, 50, 70) if style == "dark" else (*hex_to_rgb(ACCENT_COLOR), 30)
        ImageDraw.Draw(glow_overlay).ellipse([cx-320, cy-320, cx+320, cy+320], fill=fill)
        bg = Image.alpha_composite(bg, glow_overlay.filter(ImageFilter.GaussianBlur(80)))

    # --- Face photo ---
    face_img = None
    if os.path.exists(face_path):
        if USE_BG_REMOVAL and REPLICATE_API_TOKEN:
            face_img = remove_face_background(face_path)
        if face_img is None:
            face_img = ImageOps.exif_transpose(Image.open(face_path)).convert("RGBA")

        target_h = int(HEIGHT * FACE_HEIGHT_RATIO)
        target_w = int(face_img.width * target_h / face_img.height)
        face_img = face_img.resize((target_w, target_h), Image.LANCZOS)

        if USE_BG_REMOVAL:
            face_img = add_stroke(face_img, stroke_width=8, color=s["face_stroke"])

        # Anchor: position based on config
        face_x = FACE_X_OFFSET
        face_y = HEIGHT - target_h if FACE_VERTICAL == "bottom" else (HEIGHT - target_h) // 2
        bg.paste(face_img, (face_x, face_y), face_img)
    else:
        print(f"  Face photo not found: {face_path}")

    draw = ImageDraw.Draw(bg)

    # --- Text layout — right column ---
    COL_X  = int(WIDTH * 0.46)
    COL_W  = int(WIDTH * 0.97) - COL_X
    COL_CX = COL_X + COL_W // 2

    tag_font   = load_font(21)
    topic_font = load_font(TOPIC_FONT_SIZE)
    name_font  = load_font(26)
    badge_font = load_font(28)

    main_color   = s["topic_color"]
    stroke_color = s["text_stroke"]
    accent_rgba  = hex_to_rgba(ACCENT_COLOR)
    dark_fill    = (*hex_to_rgb("#1a1a2e"), 230)

    # ── Topic font auto-shrink ──────────────────────────────────────────
    topic_line_h = TOPIC_FONT_SIZE + 14
    if len(topic.split()) > 6:
        topic_size = max(40, TOPIC_FONT_SIZE - 18)
        topic_font = load_font(topic_size)
        topic_line_h = topic_size + 12
    topic_lines = wrap_text(topic.upper(), topic_font, COL_W, draw)
    for line in topic_lines:
        lb = draw.textbbox((0, 0), line, font=topic_font)
        if lb[2] - lb[0] > COL_W:
            cur_size = getattr(topic_font, 'size', TOPIC_FONT_SIZE)
            topic_font = load_font(max(36, cur_size - 12))
            topic_lines = wrap_text(topic.upper(), topic_font, COL_W, draw)
            topic_line_h = max(36, cur_size - 12) + 12
            break

    # ── Measure all elements ────────────────────────────────────────────
    cat_tag  = detect_category_tag(topic)
    hl_upper = topic_highlight.upper()
    pad_tx, pad_ty = 14, 7

    def _tag_dims(text, font):
        bb = draw.textbbox((0, 0), text, font=font)
        return bb[2]-bb[0] + pad_tx*2, bb[3]-bb[1] + pad_ty*2, bb[1]

    cat_w, tag_h, _    = _tag_dims(cat_tag, tag_font)
    hl_w,  _,     _    = _tag_dims(hl_upper, tag_font)
    tags_total_w = cat_w + 10 + hl_w

    nb = draw.textbbox((0, 0), name.upper(), font=name_font)
    name_h = nb[3] - nb[1]

    dot_size, dot_gap = 14, 10
    bb2 = draw.textbbox((0, 0), hl_upper, font=badge_font)
    badge_pad_x, badge_pad_y = 20, 12
    badge_w = dot_size + dot_gap + (bb2[2]-bb2[0]) + badge_pad_x*2
    badge_h = max(bb2[3]-bb2[1], dot_size) + badge_pad_y*2

    gap1, gap2, gap3 = 14, 12, 16
    topic_block_h = len(topic_lines) * topic_line_h
    total_h = tag_h + gap1 + topic_block_h + gap2 + name_h + gap3 + badge_h
    block_y = max(20, min((HEIGHT - total_h) // 2, HEIGHT - total_h - 20))

    # 1. Tag row — category (teal) + highlight keyword (dark)
    tags_x = COL_CX - tags_total_w // 2
    # Category tag
    draw_rounded_rect(draw, [tags_x, block_y, tags_x+cat_w, block_y+tag_h],
                      radius=6, fill=accent_rgba)
    cb = draw.textbbox((0, 0), cat_tag, font=tag_font)
    draw.text((tags_x+pad_tx, block_y+pad_ty - cb[1]), cat_tag, font=tag_font,
              fill=(255, 255, 255, 255))
    # Highlight tag (dark)
    hl_tag_x = tags_x + cat_w + 10
    draw_rounded_rect(draw, [hl_tag_x, block_y, hl_tag_x+hl_w, block_y+tag_h],
                      radius=6, fill=dark_fill)
    hb = draw.textbbox((0, 0), hl_upper, font=tag_font)
    draw.text((hl_tag_x+pad_tx, block_y+pad_ty - hb[1]), hl_upper, font=tag_font,
              fill=(255, 255, 255, 255))

    # 2. Topic lines — keyword highlighted in accent color
    ty = block_y + tag_h + gap1
    for i, line in enumerate(topic_lines):
        lb  = draw.textbbox((0, 0), line, font=topic_font)
        lw  = lb[2] - lb[0]
        lx  = COL_CX - lw // 2
        ly  = ty + i * topic_line_h
        # Stroke pass
        for dx, dy in [(-2,0),(2,0),(0,-2),(0,2)]:
            draw.text((lx+dx, ly+dy), line, font=topic_font, fill=stroke_color)
        # Draw with teal highlight on matching word
        _draw_line_with_highlight(draw, line, hl_upper, lx, ly,
                                  topic_font, main_color, accent_rgba)

    # 3. Name — smaller subtitle
    ny  = ty + topic_block_h + gap2
    name_col = (200, 210, 215, 255) if style == "dark" else (*hex_to_rgb(s["topic_color"]), 255)
    nm_bb = draw.textbbox((0, 0), name.upper(), font=name_font)
    nx = COL_CX - (nm_bb[2]-nm_bb[0]) // 2
    draw.text((nx, ny - nm_bb[1]), name.upper(), font=name_font, fill=name_col)

    # 4. Tool badge — dark pill with teal dot + keyword
    by  = ny + name_h + gap3
    bx  = COL_CX - badge_w // 2
    draw_rounded_rect(draw, [bx, by, bx+badge_w, by+badge_h], radius=8, fill=dark_fill)
    dot_x = bx + badge_pad_x
    dot_y = by + (badge_h - dot_size) // 2
    draw.ellipse([dot_x, dot_y, dot_x+dot_size, dot_y+dot_size], fill=accent_rgba)
    btb = draw.textbbox((0, 0), hl_upper, font=badge_font)
    draw.text((dot_x+dot_size+dot_gap, by+badge_pad_y - btb[1]),
              hl_upper, font=badge_font, fill=(255, 255, 255, 255))

    # --- Logo: top-right ---
    if LOGO_PATH and os.path.exists(LOGO_PATH):
        logo = prepare_logo(LOGO_PATH, LOGO_SIZE, recolor=s["logo_color"])
        bg.paste(logo, (20, 14), logo)

    bg.convert("RGB").save(output_path, "PNG", quality=95)


# =============================================================
# MAIN
# =============================================================

def main():
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    if not os.path.exists(CSV_FILE):
        print(f"CSV not found: {CSV_FILE}")
        return

    if not os.path.exists(FACES_FOLDER):
        os.makedirs(FACES_FOLDER)
        print(f"Created '{FACES_FOLDER}/' — add face photos and re-run.")
        return

    with open(CSV_FILE, "r", encoding="utf-8") as f:
        content = (f.read()
                   .replace('\u201c', '"').replace('\u201d', '"')   # " "  → "
                   .replace('\u2018', "'").replace('\u2019', "'"))  # ' '  → '
    import io
    rows = list(csv.DictReader(io.StringIO(content)))

    if not rows:
        print("CSV is empty.")
        return

    print(f"\nGenerating {len(rows)} thumbnails...\n")

    for i, row in enumerate(rows, 1):
        name      = (row.get("name") or "").strip().strip("'")
        topic     = (row.get("topic") or "").strip().strip("'")
        highlight = (row.get("topic_highlight") or "").strip().strip("'")
        photo     = (row.get("photo_filename") or "").strip().strip("'")
        face_path = os.path.join(FACES_FOLDER, photo)

        if not highlight:
            highlight = auto_extract_highlight(topic)

        # Pick style: alternate, random, or fixed
        if STYLE_MODE == "alternate":
            style = "dark" if i % 2 == 1 else "bright"
        elif STYLE_MODE == "random":
            style = random.choice(["dark", "bright"])
        else:
            style = STYLE_MODE  # "dark" or "bright" fixed

        illus_prompt = (row.get("illustration_prompt") or "").strip()
        if not illus_prompt:
            illus_prompt = claude_generate_prompt(topic, style) or auto_generate_prompt(topic, style)

        safe = name.lower().replace(" ", "_").replace("/", "_")
        out  = os.path.join(OUTPUT_FOLDER, f"{i:03d}_{safe}.png")

        label = "[auto highlight]" if not row.get("topic_highlight", "").strip() else ""
        print(f"  [{i:3d}/{len(rows)}] {name} — {topic}  [{style}]  {label}")
        generate_thumbnail(name, topic, highlight, face_path, out, illus_prompt, style=style)

    print(f"\nDone! {len(rows)} thumbnails saved to '{OUTPUT_FOLDER}/'\n")


if __name__ == "__main__":
    main()
