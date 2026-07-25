# 🎭 Puppet Sprites — one-time setup (this is what makes them TALK)

Generate these **6 images once** in Gemini, drop them in `characters/sprites/`,
and after that every daily video is 100% automatic (lip-sync, blinking, bounce).

**Rules that matter (please follow exactly):**
1. **Plain WHITE background** — the pipeline removes it automatically.
2. **Same pose, same size, same distance** for a character's 3 images —
   ONLY the mouth/eyes change. (This is what makes the animation look clean.)
3. **Full body, facing the camera**, centered.
4. Save as PNG with the **exact filenames** listed below.

> Pro tip for consistency: generate `jon_closed.png` first. Then, for the other
> two, upload that image to Gemini and say: *"Keep this exact character, exact
> same pose, size and style, plain white background — only change the mouth to
> wide open"* (and for blink: *"only change the eyes to closed"*).

---

## 🐶 JON — 3 images

### 1) `jon_closed.png`  (mouth closed — the default)
```
A cute 3D animated Labrador retriever PUPPY named Jon, warm golden butter-yellow
soft fluffy fur, big round glossy dark-brown eyes OPEN, soft floppy ears, tiny
chubby round puppy body, wearing a brown collar with a gold bone-shaped "Jon"
name tag, MOUTH CLOSED with a gentle happy smile, standing upright facing the
camera, full body, centered, PLAIN SOLID WHITE BACKGROUND, no shadow, no text.
Style: cute 3D animated pixar-style, soft rounded shapes, big expressive eyes,
warm soft lighting, ultra adorable, high detail, clean render, family-friendly.
```

### 2) `jon_open.png`  (mouth open — used while he speaks)
```
Same character: cute 3D animated golden Labrador puppy Jon, identical pose, identical
size and identical style as before, brown collar with gold bone "Jon" tag, eyes OPEN,
but MOUTH WIDE OPEN as if talking (tongue slightly visible), standing upright facing
the camera, full body, centered, PLAIN SOLID WHITE BACKGROUND, no shadow, no text.
Style: cute 3D animated pixar-style, soft rounded shapes, warm soft lighting,
ultra adorable, high detail, clean render, family-friendly.
```

### 3) `jon_blink.png`  (eyes closed — optional but makes him feel alive)
```
Same character: cute 3D animated golden Labrador puppy Jon, identical pose, size and
style, brown collar with gold bone "Jon" tag, MOUTH CLOSED smiling, but BOTH EYES
CLOSED (blinking, happy), standing upright facing the camera, full body, centered,
PLAIN SOLID WHITE BACKGROUND, no shadow, no text.
Style: cute 3D animated pixar-style, soft rounded shapes, warm soft lighting,
ultra adorable, high detail, clean render, family-friendly.
```

---

## 🐱 KATIE — 3 images

### 4) `katie_closed.png`  (mouth closed — the default)
```
A cute 3D animated Persian CAT named Katie, fluffy silver-white long luxurious fur,
classic flat Persian face, big round sparkling blue-green eyes OPEN, wearing a pink
bow on her head, a pink heart-shaped "Katie" name tag and a cute pink dress, MOUTH
CLOSED with a calm elegant smile, standing upright facing the camera, full body,
centered, PLAIN SOLID WHITE BACKGROUND, no shadow, no text.
Style: cute 3D animated pixar-style, soft rounded shapes, big expressive eyes,
warm soft lighting, ultra adorable, high detail, clean render, family-friendly.
```

### 5) `katie_open.png`  (mouth open — used while she speaks)
```
Same character: cute 3D animated silver-white Persian cat Katie, identical pose,
identical size and identical style as before, pink bow, pink heart "Katie" tag, pink
dress, eyes OPEN, but MOUTH WIDE OPEN as if talking, standing upright facing the
camera, full body, centered, PLAIN SOLID WHITE BACKGROUND, no shadow, no text.
Style: cute 3D animated pixar-style, soft rounded shapes, warm soft lighting,
ultra adorable, high detail, clean render, family-friendly.
```

### 6) `katie_blink.png`  (eyes closed — optional)
```
Same character: cute 3D animated silver-white Persian cat Katie, identical pose, size
and style, pink bow, pink heart "Katie" tag, pink dress, MOUTH CLOSED smiling, but
BOTH EYES CLOSED (blinking, content), standing upright facing the camera, full body,
centered, PLAIN SOLID WHITE BACKGROUND, no shadow, no text.
Style: cute 3D animated pixar-style, soft rounded shapes, warm soft lighting,
ultra adorable, high detail, clean render, family-friendly.
```

---

## Where to put them
Upload to **`characters/sprites/`** on the `main` branch:

```
characters/sprites/jon_closed.png     (required)
characters/sprites/jon_open.png       (required)
characters/sprites/jon_blink.png      (optional)
characters/sprites/katie_closed.png   (required)
characters/sprites/katie_open.png     (required)
characters/sprites/katie_blink.png    (optional)
```

The scene backgrounds keep coming from `characters/refs/sheet.png` (the 8 activity
panels), so the characters act in front of the cooking / garden / fishing / grocery /
laptop / travel / cleaning / diary scenes.
