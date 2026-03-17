"""
YouTube Thumbnail Generator
============================
Viral-style: face-left, text-right, clean dark gradient bg, bold highlight box.

CSV columns: name, topic, topic_highlight, photo_filename, illustration_prompt
  - topic_highlight: the big keyword in the teal accent box (e.g. "ВЭ?", "БҮТЭЭХ")
  - illustration_prompt: optional, leave blank to auto-generate
  - topic_highlight: optional, leave blank to auto-extract last word

Requirements:
    pip install Pillow

Usage:
    1. Put face photos in "faces/"
    2. Fill in "thumbnails.csv"
    3. Run: python thumbnail_generator.py
    4. Find thumbnails in "output/"
"""

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import csv
import os
import sys
import hashlib

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

# Brand colors
BG_COLOR        = "#080c14"       # Very dark base
ACCENT_COLOR    = "#5DC9B4"       # Lambda teal
ACCENT_DARK     = "#0d1520"       # Dark text on teal box
TOPIC_COLOR     = "#ffffff"       # Main topic text

# Face
FACE_HEIGHT_RATIO = 0.75          # Face height as fraction of canvas (0.98=huge, 0.75=medium, 0.60=small)
FACE_VERTICAL     = "bottom"      # "bottom" = anchor to bottom, "center" = vertically centered
FACE_X_OFFSET     = 90            # Pixels from left edge (higher = more right)
USE_BG_REMOVAL    = True

# Text sizes
NAME_FONT_SIZE      = 38
TOPIC_FONT_SIZE     = 58          # Big bold main text (6 words or fewer)
HIGHLIGHT_FONT_SIZE = 28          # Keyword in teal box
TOPIC_MAX_WIDTH     = 560         # Right-side text column width

# Background
USE_GRADIENT_BG    = True         # Overlay glow effects on top of illustration
USE_ILLUSTRATIONS  = True         # Generate AI background illustrations
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
FONT_PATH     = None

# =============================================================
# HELPERS
# =============================================================

def load_font(size):
    if FONT_PATH and os.path.exists(FONT_PATH):
        return ImageFont.truetype(FONT_PATH, size)
    for name in [
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibrib.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
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


def prepare_logo(path, size):
    logo = Image.open(path).convert("RGBA")
    logo.thumbnail(size, Image.LANCZOS)
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


def create_gradient_bg(face_x_center=WIDTH//4):
    """Dark gradient with subtle radial glow behind face + faint teal top-right."""
    # Base: very dark navy
    bg = Image.new("RGBA", (WIDTH, HEIGHT), (*hex_to_rgb(BG_COLOR), 255))

    # Left glow behind face — soft dark-blue radial
    glow1 = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    gd1 = ImageDraw.Draw(glow1)
    cx, cy = face_x_center, HEIGHT // 2 + 40
    gd1.ellipse([cx-350, cy-350, cx+350, cy+350], fill=(20, 35, 65, 160))
    glow1 = glow1.filter(ImageFilter.GaussianBlur(90))
    bg = Image.alpha_composite(bg, glow1)

    # Top-right teal accent glow (very subtle)
    glow2 = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    gd2 = ImageDraw.Draw(glow2)
    gd2.ellipse([WIDTH-300, -150, WIDTH+100, 250], fill=(*hex_to_rgb(ACCENT_COLOR), 35))
    glow2 = glow2.filter(ImageFilter.GaussianBlur(70))
    bg = Image.alpha_composite(bg, glow2)

    # Bottom-right dark vignette to separate face from text side
    vig = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    vd = ImageDraw.Draw(vig)
    for x in range(WIDTH//2, WIDTH):
        alpha = int(30 * ((x - WIDTH//2) / (WIDTH//2)))
        vd.line([(x, 0), (x, HEIGHT)], fill=(4, 6, 12, alpha))
    bg = Image.alpha_composite(bg, vig)

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


def auto_generate_prompt(topic):
    """Keyword → cinematic prompt mapping for Mongolian topics."""
    t = topic.lower()
    mapping = {
        "ai":       "futuristic AI neural network glowing teal nodes dark space cinematic wide 16:9",
        "хиймэл":   "futuristic AI neural network glowing teal nodes dark space cinematic wide 16:9",
        "chatgpt":  "holographic AI chat interface dark space teal neon glow futuristic cinematic wide",
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
    }
    for kw, scene in mapping.items():
        if kw in t:
            return scene
    return "cinematic dark studio dramatic teal accent glow professional futuristic wide 16:9"


def claude_generate_prompt(topic):
    """Use Claude API to generate a topic-relevant cinematic image prompt."""
    if not ANTHROPIC_API_KEY:
        return None
    import urllib.request, json
    system = (
        "You generate short cinematic background image prompts for YouTube thumbnails. "
        "Given a video topic (possibly in Mongolian), output ONLY a single English prompt "
        "describing a vivid, atmospheric scene that visually matches the topic. "
        "Style: dark background, teal accent glow, cinematic, wide 16:9, professional. "
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
    """Remove background via Replicate rembg, cached per photo."""
    import urllib.request, base64
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
    ext = os.path.splitext(face_path)[1].lower()
    mime = "image/jpeg" if ext in (".jpg", ".jpeg") else "image/png"
    with open(face_path, "rb") as f:
        data_uri = f"data:{mime};base64,{base64.b64encode(f.read()).decode()}"
    REMBG_VERSION = "fb8af171cfa1616ddcf1242c093f9c46bcada5ad4cf6f2fbe8b81b330ec5c003"
    result = _replicate_post_versioned(REMBG_VERSION, {"image": data_uri}, label="BG removal")
    if not result:
        return None
    out = result["output"]
    url = out[0] if isinstance(out, list) else out
    urllib.request.urlretrieve(url, cache)
    return Image.open(cache).convert("RGBA")


# =============================================================
# THUMBNAIL GENERATOR
# =============================================================

def generate_thumbnail(name, topic, topic_highlight, face_path, output_path, illustration_prompt=""):
    """
    Viral-style layout:
      - Clean dark gradient background
      - Face: left side, large (almost full height)
      - Right side: name pill → big topic text → bold teal highlight box
      - Lambda logo: top-right
    """

    # --- Background ---
    if USE_ILLUSTRATIONS and ILLUSTRATION_AS_BG and illustration_prompt:
        illus_img = generate_illustration(illustration_prompt)
        if illus_img:
            bg = illus_img.resize((WIDTH, HEIGHT), Image.LANCZOS).convert("RGBA")
            # Dark overlay so face and text pop
            dark_over = Image.new("RGBA", (WIDTH, HEIGHT), (5, 10, 20, BG_OVERLAY_OPACITY))
            bg = Image.alpha_composite(bg, dark_over)
        else:
            bg = Image.new("RGBA", (WIDTH, HEIGHT), hex_to_rgba(BG_COLOR))
    elif USE_GRADIENT_BG:
        bg = create_gradient_bg(face_x_center=WIDTH // 4)
    else:
        bg = Image.new("RGBA", (WIDTH, HEIGHT), hex_to_rgba(BG_COLOR))

    # Add gradient glow effects on top of illustration
    if USE_GRADIENT_BG and USE_ILLUSTRATIONS and ILLUSTRATION_AS_BG:
        glow = create_gradient_bg(face_x_center=WIDTH // 4)
        # Blend glow lightly on top — extract only the glow layers, not the opaque base
        glow_overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
        # Left face glow
        gd = ImageDraw.Draw(glow_overlay)
        cx, cy = WIDTH // 4, HEIGHT // 2 + 40
        gd.ellipse([cx-320, cy-320, cx+320, cy+320], fill=(15, 25, 50, 80))
        glow_overlay = glow_overlay.filter(ImageFilter.GaussianBlur(80))
        bg = Image.alpha_composite(bg, glow_overlay)

    # --- Face photo ---
    face_img = None
    if os.path.exists(face_path):
        if USE_BG_REMOVAL and REPLICATE_API_TOKEN:
            face_img = remove_face_background(face_path)
        if face_img is None:
            face_img = Image.open(face_path).convert("RGBA")

        target_h = int(HEIGHT * FACE_HEIGHT_RATIO)
        target_w = int(face_img.width * target_h / face_img.height)
        face_img = face_img.resize((target_w, target_h), Image.LANCZOS)

        # White stroke outline around the cutout
        if USE_BG_REMOVAL:
            face_img = add_stroke(face_img, stroke_width=10, color=(255, 255, 255, 255))

        # Anchor: position based on config
        face_x = FACE_X_OFFSET
        face_y = HEIGHT - target_h if FACE_VERTICAL == "bottom" else (HEIGHT - target_h) // 2
        bg.paste(face_img, (face_x, face_y), face_img)
    else:
        print(f"  Face photo not found: {face_path}")

    draw = ImageDraw.Draw(bg)

    # --- Text layout — right column ---
    # Right column: from 48% to 97% of width
    COL_X  = int(WIDTH * 0.48)
    COL_W  = int(WIDTH * 0.97) - COL_X
    COL_CX = COL_X + COL_W // 2

    name_font      = load_font(NAME_FONT_SIZE)
    topic_font     = load_font(TOPIC_FONT_SIZE)
    highlight_font = load_font(HIGHLIGHT_FONT_SIZE)

    # Wrap main topic text
    topic_lines = wrap_text(topic.upper(), topic_font, COL_W, draw)
    topic_line_h = TOPIC_FONT_SIZE + 14

    # Measure name pill — subtract font's internal top offset for true centering
    nm = name.upper()
    nb = draw.textbbox((0, 0), nm, font=name_font)
    nm_w  = nb[2] - nb[0]
    nm_h  = nb[3] - nb[1]
    nm_dy = nb[1]           # hidden ascender offset PIL adds above visible text
    pill_px, pill_py = 24, 11
    pill_w = nm_w + pill_px * 2
    pill_h = nm_h + pill_py * 2

    hl = topic_highlight.upper()
    box_px, box_py = 30, 16

    # ── Topic font size logic ───────────────────────────────────────────
    # >6 words → shrink 20px; further shrink if any line still overflows
    word_count = len(topic.split())
    if word_count > 6:
        topic_size = max(44, TOPIC_FONT_SIZE - 20)
        topic_font = load_font(topic_size)
        topic_lines = wrap_text(topic.upper(), topic_font, COL_W, draw)
        topic_line_h = topic_size + 12
    for line in topic_lines:
        lb = draw.textbbox((0, 0), line, font=topic_font)
        if lb[2] - lb[0] > COL_W:
            cur_size = getattr(topic_font, 'size', TOPIC_FONT_SIZE)
            shrunk = load_font(max(40, cur_size - 14))
            topic_lines = wrap_text(topic.upper(), shrunk, COL_W, draw)
            topic_font = shrunk
            topic_line_h = max(40, cur_size - 14) + 12
            break

    # ── Highlight box logic ─────────────────────────────────────────────
    # Wrap highlight text into multiple lines if >5 words or too wide;
    # shrink font until every line fits within the column.
    hl_size = HIGHLIGHT_FONT_SIZE
    hl_max_w = COL_W - box_px * 2
    hl_lines = wrap_text(hl, highlight_font, hl_max_w, draw)
    # Shrink until all lines fit
    while True:
        too_wide = any(
            draw.textbbox((0,0), ln, font=highlight_font)[2]
            - draw.textbbox((0,0), ln, font=highlight_font)[0] > hl_max_w
            for ln in hl_lines
        )
        if not too_wide or hl_size <= 36:
            break
        hl_size -= 6
        highlight_font = load_font(hl_size)
        hl_lines = wrap_text(hl, highlight_font, hl_max_w, draw)

    # Measure the highlight box dimensions (tallest line × number of lines)
    sample_h = draw.textbbox((0,0), hl_lines[0], font=highlight_font)
    hl_line_h = (sample_h[3] - sample_h[1]) + 10
    widest = max(
        draw.textbbox((0,0), ln, font=highlight_font)[2]
        - draw.textbbox((0,0), ln, font=highlight_font)[0]
        for ln in hl_lines
    )
    box_w = widest + box_px * 2
    box_h = hl_line_h * len(hl_lines) + box_py * 2

    # Total block height and vertical centering
    gap1, gap2 = 20, 22
    total_h = pill_h + gap1 + len(topic_lines)*topic_line_h + gap2 + box_h
    block_y = max(20, min((HEIGHT - total_h) // 2, HEIGHT - total_h - 20))

    # 1. Name pill
    pill_x = COL_CX - pill_w // 2
    draw_rounded_rect(draw, [pill_x, block_y, pill_x+pill_w, block_y+pill_h],
                      radius=pill_h//2, fill=hex_to_rgba(ACCENT_COLOR))
    draw.text((pill_x+pill_px, block_y+pill_py - nm_dy), nm, font=name_font,
              fill=hex_to_rgba(ACCENT_DARK))

    # 2. Topic lines (white, bold outline)
    ty = block_y + pill_h + gap1
    for i, line in enumerate(topic_lines):
        lb = draw.textbbox((0, 0), line, font=topic_font)
        lw = lb[2]-lb[0]
        lx = COL_CX - lw // 2
        ly = ty + i * topic_line_h
        for dx, dy in [(-3,0),(3,0),(0,-3),(0,3),(-3,-3),(3,-3),(-3,3),(3,3)]:
            draw.text((lx+dx, ly+dy), line, font=topic_font, fill=(0,0,0,230))
        draw.text((lx, ly), line, font=topic_font, fill=TOPIC_COLOR)

    # 3. Teal highlight box — wraps if text is long
    hy = ty + len(topic_lines) * topic_line_h + gap2
    box_x = COL_CX - box_w // 2
    draw_rounded_rect(draw, [box_x, hy, box_x+box_w, hy+box_h],
                      radius=14, fill=hex_to_rgba(ACCENT_COLOR))
    for i, ln in enumerate(hl_lines):
        lb = draw.textbbox((0,0), ln, font=highlight_font)
        lw = lb[2]-lb[0]
        lx = box_x + (box_w - lw) // 2
        ly = hy + box_py + i * hl_line_h
        draw.text((lx, ly), ln, font=highlight_font, fill=hex_to_rgba(ACCENT_DARK))

    # --- Logo: top-left ---
    if LOGO_PATH and os.path.exists(LOGO_PATH):
        logo = prepare_logo(LOGO_PATH, LOGO_SIZE)
        bg.paste(logo, (24, 14), logo)

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
        rows = list(csv.DictReader(f))

    if not rows:
        print("CSV is empty.")
        return

    print(f"\nGenerating {len(rows)} thumbnails...\n")

    for i, row in enumerate(rows, 1):
        name      = (row.get("name") or "").strip()
        topic     = (row.get("topic") or "").strip()
        highlight = (row.get("topic_highlight") or "").strip()
        photo     = (row.get("photo_filename") or "").strip()
        face_path = os.path.join(FACES_FOLDER, photo)

        if not highlight:
            highlight = auto_extract_highlight(topic)

        illus_prompt = (row.get("illustration_prompt") or "").strip()
        if not illus_prompt:
            illus_prompt = claude_generate_prompt(topic) or auto_generate_prompt(topic)

        safe = name.lower().replace(" ", "_").replace("/", "_")
        out  = os.path.join(OUTPUT_FOLDER, f"{i:03d}_{safe}.png")

        label = "[auto highlight]" if not row.get("topic_highlight", "").strip() else ""
        print(f"  [{i:3d}/{len(rows)}] {name} — {topic}  {label}")
        generate_thumbnail(name, topic, highlight, face_path, out, illus_prompt)

    print(f"\nDone! {len(rows)} thumbnails saved to '{OUTPUT_FOLDER}/'\n")


if __name__ == "__main__":
    main()
