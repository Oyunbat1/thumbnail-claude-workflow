# Thumbnail Automation Guide
## 100 Thumbnails in Minutes Instead of Hours

---

## What You Need

- **Python 3** installed on your computer
- **Pillow library** (the script's only dependency)
- **Face photos** of each person (any format: PNG, JPG)
- **A CSV file** listing each person's name, topic, and photo filename

---

## Step 1: Set Up Your Folder

Create a project folder with this structure:

```
thumbnail-project/
├── thumbnail_generator.py    ← the script (attached)
├── thumbnails.csv            ← your data (attached sample)
├── template_bg.png           ← (optional) your background image
├── faces/                    ← folder with all face photos
│   ├── john.png
│   ├── jane.png
│   └── alex.png
└── output/                   ← (auto-created) thumbnails go here
```

---

## Step 2: Install Pillow

Open your terminal/command prompt and run:

```bash
pip install Pillow
```

---

## Step 3: Prepare Your Face Photos

- Collect all 100 face photos into the `faces/` folder
- They don't need to be the same size — the script resizes them
- Name them simply: `john.png`, `jane.jpg`, etc.
- **Tip:** Cropped headshots work best (square-ish photos)

---

## Step 4: Fill In the CSV

Open `thumbnails.csv` in Excel, Google Sheets, or any text editor. Fill in one row per thumbnail:

```
name,topic,photo_filename
John Smith,How to Use ChatGPT for Beginners,john.png
Jane Doe,AI for Data Analysis,jane.png
Alex Kim,Automating Tasks with AI Tools,alex.png
```

**Columns:**
- `name` — person's name (shown on the thumbnail)
- `topic` — the video topic/title
- `photo_filename` — exact filename of their photo in `faces/`

---

## Step 5: Customize the Design (Optional but Recommended)

Open `thumbnail_generator.py` in any text editor. The top section has clearly labeled settings:

### Colors
```python
BG_COLOR = "#1a1a2e"              # Dark blue background
FACE_BORDER_COLOR = "#e94560"     # Red accent border
TOPIC_BG_BAR_COLOR = "#e94560"    # Red bar behind text
TOPIC_COLOR = "#ffffff"           # White text
```

### Layout
```python
FACE_SIZE = (380, 380)            # Make faces bigger/smaller
TOPIC_FONT_SIZE = 58              # Adjust text size
TOPIC_Y_POSITION = 520            # Move text up/down
```

### Font
For professional-looking thumbnails, download a bold font (.ttf file) and set:
```python
FONT_PATH = "path/to/YourFont-Bold.ttf"
```
**Recommended free fonts:** Montserrat Bold, Poppins Bold, or Oswald Bold from Google Fonts.

### Background Image
If you have a template background, save it as `template_bg.png` in the same folder. The script auto-darkens it so text stays readable.

---

## Step 6: Run It

```bash
python thumbnail_generator.py
```

You'll see progress like:
```
🎬 Generating 100 thumbnails...

  [  1/100] John Smith — How to Use ChatGPT for Beginners
  [  2/100] Jane Doe — AI for Data Analysis
  [  3/100] Alex Kim — Automating Tasks with AI Tools
  ...

✅ Done! 100 thumbnails saved to 'output/'
```

All thumbnails land in the `output/` folder, named like `001_john_smith.png`.

---

## Time Comparison

| Method | Per Thumbnail | 100 Thumbnails |
|--------|--------------|----------------|
| Manual (Canva/PS) | ~20 min | ~33 hours |
| This script | ~1 sec | ~2 minutes |

---

## Troubleshooting

**"No .ttf font found"** — The script works without a custom font but looks basic. Download a .ttf font and set `FONT_PATH`.

**Text is cut off** — Reduce `TOPIC_FONT_SIZE` or increase `TOPIC_MAX_WIDTH`.

**Face too big/small** — Adjust `FACE_SIZE = (380, 380)` to your liking.

**Want a different layout?** — Adjust `FACE_Y_OFFSET`, `TOPIC_Y_POSITION`, and `NAME_Y_POSITION` to reposition elements.

---

## Quick Customization Cheat Sheet

| Want to... | Change this setting |
|-----------|-------------------|
| Different background color | `BG_COLOR = "#your_hex"` |
| Use a background image | Save as `template_bg.png` |
| Bigger/smaller face | `FACE_SIZE = (width, height)` |
| Square face (no circle) | `FACE_CIRCLE_CROP = False` |
| No border on face | `FACE_BORDER = False` |
| Change accent color | `FACE_BORDER_COLOR` and `TOPIC_BG_BAR_COLOR` |
| Move text up/down | `TOPIC_Y_POSITION` (lower = further down) |
| Add branding text | `BRAND_TEXT = "AI Series 2026"` |
| No bar behind text | `TOPIC_BG_BAR = False` |
