#!/usr/bin/env python3
"""Stylish vCard QR generator — payloads follow vCard 3.0 so Google Contact
(Android) and the iOS Camera/Contacts app can both parse name, phone, email,
website and social profiles (X-SOCIALPROFILE) out of one scan."""

from __future__ import annotations

import argparse
import datetime
import json
from dataclasses import dataclass, field
from pathlib import Path

import qrcode
from qrcode.constants import ERROR_CORRECT_H
from PIL import Image, ImageDraw, ImageFont

SOCIAL_PLATFORMS = {
    "twitter":   ("twitter",   "https://x.com/"),
    "x":         ("twitter",   "https://x.com/"),
    "instagram": ("instagram", "https://instagram.com/"),
    "linkedin":  ("linkedin",  "https://linkedin.com/in/"),
    "facebook":  ("facebook",  "https://facebook.com/"),
    "github":    ("github",    "https://github.com/"),
    "youtube":   ("youtube",   "https://youtube.com/@"),
    "tiktok":    ("tiktok",    "https://tiktok.com/@"),
    "threads":   ("threads",   "https://threads.net/@"),
    "mastodon":  ("mastodon",  "https://mastodon.social/@"),
    "pinterest": ("pinterest", "https://pinterest.com/"),
    "snapchat":  ("snapchat",  "https://snapchat.com/add/"),
}

THEMES = {
    "indigo":   {"fg": ("#4338ca", "#0d9488"), "badge": ("#6366f1", "#14b8a6"),
                 "text": "#111827", "sub": "#6b7280", "ring": "#e5e7eb"},
    "sunset":   {"fg": ("#c2410c", "#be123c"), "badge": ("#f97316", "#e11d48"),
                 "text": "#1f2937", "sub": "#78716c", "ring": "#fde8d7"},
    "midnight": {"fg": ("#0f172a", "#475569"), "badge": ("#1e293b", "#64748b"),
                 "text": "#0f172a", "sub": "#64748b", "ring": "#e2e8f0"},
    "forest":   {"fg": ("#166534", "#0e7490"), "badge": ("#15803d", "#0891b2"),
                 "text": "#14532d", "sub": "#6b7280", "ring": "#d7f0e2"},
}

FONT_CANDIDATES = [
    "/System/Library/Fonts/SFNSDisplay.ttf",
    "/System/Library/Fonts/HelveticaNeue.ttc",
    "/System/Library/Fonts/Helvetica.ttc",
    "/Library/Fonts/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]

NUM_ALIGNMENT_PATTERNS = [0, 0, 0, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 3, 3, 3, 3, 3,
                          4, 4, 4, 4, 4, 5, 5, 5, 5, 5, 6, 6, 6, 6, 6, 7, 7, 7,
                          7, 7, 7, 7, 7]


@dataclass
class Contact:
    first: str
    last: str
    title: str = ""
    org: str = ""
    phone: str = ""
    phone_home: str = ""
    email: str = ""
    website: str = ""
    note: str = ""
    street: str = ""
    city: str = ""
    region: str = ""
    postal: str = ""
    country: str = ""
    photo: str = ""
    social: dict = field(default_factory=dict)

    @property
    def full_name(self) -> str:
        return f"{self.first} {self.last}".strip()

    @property
    def initials(self) -> str:
        return (self.first[:1] + self.last[:1]).upper() or "?"


def hex_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def lerp(a: tuple[int, int, int], b: tuple[int, int, int], t: float):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def fold_line(line: str, limit: int = 74) -> str:
    raw = line.encode("utf-8")
    chunks = []
    start, first = 0, True
    while start < len(raw):
        cut = min(limit if first else limit - 1, len(raw) - start)
        while cut > 0 and start + cut < len(raw) and (raw[start + cut] & 0xC0) == 0x80:
            cut -= 1
        chunks.append(raw[start:start + cut].decode("utf-8"))
        start += cut
        first = False
    return "\r\n".join([chunks[0]] + [" " + c for c in chunks[1:]])


def social_value(platform: str, handle: str) -> tuple[str, str]:
    key = platform.lower().strip()
    vtype, prefix = SOCIAL_PLATFORMS.get(key, (key or "custom", ""))
    handle = handle.strip()
    url = handle if handle.startswith(("http://", "https://")) else prefix + handle
    return vtype, url


def build_vcard(contact: Contact) -> str:
    lines = ["BEGIN:VCARD", "VERSION:3.0"]
    lines.append(f"N:{contact.last};{contact.first};;;")
    lines.append(f"FN:{contact.full_name}")
    if contact.title:
        lines.append(f"TITLE:{contact.title}")
    if contact.org:
        lines.append(f"ORG:{contact.org}")
    if contact.phone:
        lines.append(f"TEL;TYPE=CELL:{contact.phone}")
    if contact.phone_home:
        lines.append(f"TEL;TYPE=HOME:{contact.phone_home}")
    if contact.email:
        lines.append(f"EMAIL;TYPE=INTERNET:{contact.email}")
    if contact.website:
        lines.append(f"URL;TYPE=WORK:{contact.website}")
    if any([contact.street, contact.city, contact.region, contact.postal, contact.country]):
        lines.append(f"ADR;TYPE=WORK:;;{contact.street};{contact.city};{contact.region};{contact.postal};{contact.country}")
    for platform, handle in contact.social.items():
        if not handle:
            continue
        vtype, url = social_value(platform, handle)
        lines.append(f"X-SOCIALPROFILE;TYPE={vtype}:{url}")
    if contact.note:
        lines.append(f"NOTE:{contact.note}")
    lines.append("REV:" + datetime.date.today().isoformat())
    lines.append("END:VCARD")
    return "\r\n".join(fold_line(l) for l in lines) + "\r\n"


def make_qr(payload: str, min_version: int = 1) -> qrcode.QRCode:
    qr = qrcode.QRCode(error_correction=ERROR_CORRECT_H)
    qr.add_data(payload)
    qr.make(fit=True)
    if qr.version < min_version:
        qr = qrcode.QRCode(error_correction=ERROR_CORRECT_H, version=min_version)
        qr.add_data(payload)
        qr.make(fit=True)
    return qr


def alignment_centers(version: int) -> list[int]:
    if version == 1:
        return []
    num = NUM_ALIGNMENT_PATTERNS[version - 1]
    if num == 0:
        return []
    step = 26 if version == 32 else ((version * 4 + 4) // (num * 2 - 2)) * 2
    centers = [6]
    for i in range(num - 1):
        centers.append(4 * version + 10 - i * step)
    return sorted(set(centers))


def load_font(size: int):
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def make_badge(text: str, size: int, colors: tuple[str, str]) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    ss = 4
    work = Image.new("RGBA", (size * ss, size * ss), (0, 0, 0, 0))
    wd = ImageDraw.Draw(work)
    c1, c2 = hex_rgb(colors[0]), hex_rgb(colors[1])
    for y in range(size * ss):
        wd.line([(0, y), (size * ss, y)], fill=lerp(c1, c2, y / (size * ss)) + (255,))
    mask = Image.new("L", (size * ss, size * ss), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size * ss - 1, size * ss - 1), fill=255)
    work.putalpha(mask)
    img = work.resize((size, size), Image.LANCZOS)
    d = ImageDraw.Draw(img)
    font = load_font(int(size * 0.42))
    box = d.textbbox((0, 0), text, font=font)
    d.text(((size - box[2] + box[0]) / 2 - box[0], (size - box[3] + box[1]) / 2 - box[1]),
           text, font=font, fill="white")
    return img


def prepare_logo(logo, contact: Contact, size: int, theme: dict) -> Image.Image:
    source = None
    if isinstance(logo, Image.Image):
        source = logo
    elif logo and Path(logo).exists():
        source = Image.open(logo)
    if source is not None:
        img = source.convert("RGBA")
        img.thumbnail((size, size), Image.LANCZOS)
        pad = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        off = ((size - img.width) // 2, (size - img.height) // 2)
        pad.paste(img, off, img)
        img = pad
    else:
        img = make_badge(contact.initials if contact else "", size, theme["badge"])
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size - 1, size - 1), radius=size // 6, fill=255)
    out = Image.new("RGBA", (size, size), (255, 255, 255, 255))
    out.paste(img, (0, 0), mask)
    return out


def render(qr: qrcode.QRCode, *, theme: dict, box: int = 12, border: int = 4,
           style: str = "rounded", logo: Image.Image | None = None) -> Image.Image:
    matrix = qr.modules
    n = len(matrix)
    side = n + border * 2
    px = side * box
    ss = 3
    scale = px * ss
    canvas = Image.new("RGB", (scale, scale), "white")
    draw = ImageDraw.Draw(canvas)

    c1, c2 = hex_rgb(theme["fg"][0]), hex_rgb(theme["fg"][1])
    B, bs = border * ss, box * ss

    finder_zones = {
        (0, 0, 7, 7), (0, n - 7, 7, n), (n - 7, 0, n, 7),
    }

    def in_finder(r: int, c: int) -> bool:
        return any(r0 <= r <= r1 and c0 <= c <= c1
                   for (r0, c0, r1, c1) in finder_zones)

    centers = alignment_centers(qr.version)
    align_zones = set()
    if centers:
        last = centers[-1]
        for r in centers:
            for c in centers:
                if (r, c) in {(6, 6), (6, last), (last, 6)}:
                    continue
                align_zones.add((r - 2, c - 2))

    logo_clear = None
    if logo is not None:
        half = logo.width * ss // 2
        cx = cy = scale // 2
        clear_half = half + int(bs * 0.9)
        logo_clear = (cx - clear_half, cy - clear_half, cx + clear_half, cy + clear_half)

    ratio = 0.82 if style == "dots" else 0.96
    half = bs * ratio / 2
    corner = half if style == "dots" else half * 0.62
    for r in range(n):
        for c in range(n):
            if not matrix[r][c] or in_finder(r, c) or (r, c) in align_zones:
                continue
            x, y = (c + border) * bs + bs / 2, (r + border) * bs + bs / 2
            if logo_clear and logo_clear[0] - half <= x <= logo_clear[2] and \
               logo_clear[1] - half <= y <= logo_clear[3]:
                continue
            t = (x + y) / (2 * scale)
            color = lerp(c1, c2, t)
            if style == "dots":
                draw.ellipse((x - half, y - half, x + half, y + half), fill=color)
            else:
                draw.rounded_rectangle((x - half, y - half, x + half, y + half),
                                       radius=corner, fill=color)

    def rounded_zone(r0: int, c0: int, span: int, ring: int):
        x0, y0 = (c0 + border) * bs, (r0 + border) * bs
        size = span * bs
        t = ((x0 + size / 2) + (y0 + size / 2)) / (2 * scale)
        color = lerp(c1, c2, t)
        draw.rounded_rectangle((x0, y0, x0 + size, y0 + size),
                               radius=size * 0.28, fill=color)
        inner = ring * bs
        draw.rounded_rectangle((x0 + inner, y0 + inner,
                                x0 + size - inner, y0 + size - inner),
                               radius=size * 0.18, fill="white")
        core = ring * 2 * bs
        draw.rounded_rectangle((x0 + core, y0 + core, x0 + size - core, y0 + size - core),
                               radius=size * 0.12, fill=color)

    for (r0, c0, _, _) in finder_zones:
        rounded_zone(r0, c0, 7, 1)
    for (r0, c0) in align_zones:
        rounded_zone(r0, c0, 5, 1)

    img = canvas.resize((px, px), Image.LANCZOS)

    if logo is not None:
        lw, lh = logo.size
        lx, ly = (px - lw) // 2, (px - lh) // 2
        pad = max(3, lw // 14)
        d2 = ImageDraw.Draw(img)
        d2.rounded_rectangle((lx - pad, ly - pad, lx + lw + pad, ly + lh + pad),
                             radius=lw // 5, fill="white")
        img.paste(logo, (lx, ly), logo)
    return img


def render_classic(qr: qrcode.QRCode, theme: dict) -> Image.Image:
    return qr.make_image(fill_color=hex_rgb(theme["fg"][0]),
                         back_color="white").convert("RGB")


def caption_card(qr_img: Image.Image, contact: Contact, theme: dict) -> Image.Image:
    w = qr_img.width
    pad = int(w * 0.07)
    head_h = int(w * 0.30)
    W = w + pad * 2
    H = pad + w + head_h + pad
    card = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(card)
    d.rounded_rectangle((0, 0, W - 1, H - 1), radius=int(W * 0.04),
                        outline=theme["ring"], width=max(2, W // 200))
    card.paste(qr_img, (pad, pad))
    y = pad + w + int(head_h * 0.18)
    name_font = load_font(int(w * 0.075))
    sub_font = load_font(int(w * 0.045))
    d.text((W / 2, y), contact.full_name, font=name_font,
           fill=theme["text"], anchor="ma")
    sub = "  ·  ".join(x for x in (contact.title, contact.org) if x)
    if sub:
        y += int(w * 0.085)
        d.text((W / 2, y), sub, font=sub_font, fill=theme["sub"], anchor="ma")
    handles = []
    for platform, handle in contact.social.items():
        if handle:
            _, url = social_value(platform, handle)
            handles.append(url.replace("https://", "").replace("http://", "").rstrip("/"))
    max_w = W - pad * 2
    for size in (0.038, 0.032, 0.026, 0.021):
        font = load_font(int(w * size))
        rows = _wrap_handles(handles, font, d, max_w)
        if rows:
            y += int(w * 0.06)
            for row in rows:
                d.text((W / 2, y), row, font=font, fill=theme["sub"], anchor="ma")
                y += int(w * size * 1.6)
            break
    return card


def _wrap_handles(handles: list[str], font, draw: ImageDraw.ImageDraw, max_w: int):
    rows, current = [], ""
    for h in handles:
        candidate = f"{current}  ·  {h}" if current else h
        if draw.textlength(candidate, font=font) <= max_w:
            current = candidate
        elif current:
            rows.append(current)
            current = h
        else:
            return None
    if current:
        rows.append(current)
    return rows or None


_WECHAT_DETECTOR = None


def _wechat_once(png: bytes) -> str | None:
    global _WECHAT_DETECTOR
    try:
        import cv2
        import numpy as np
    except ImportError:
        return None
    models = Path(__file__).resolve().parent / "models"
    if not (models / "detect.caffemodel").exists():
        return None
    try:
        if _WECHAT_DETECTOR is None:
            _WECHAT_DETECTOR = cv2.wechat_qrcode_WeChatQRCode(
                str(models / "detect.prototxt"), str(models / "detect.caffemodel"),
                str(models / "sr.prototxt"), str(models / "sr.caffemodel"))
        image = cv2.imdecode(np.frombuffer(png, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            return ""
        texts, _, _, _ = _WECHAT_DETECTOR.detectAndDecode(image)
        return texts[0] if texts else ""
    except Exception:
        return ""


def _zbar_once(png: bytes) -> str | None:
    import shutil
    import subprocess
    if not shutil.which("zbarimg"):
        return None
    try:
        done = subprocess.run(["zbarimg", "-q", "--raw", "-"],
                              input=png, capture_output=True, timeout=20)
        return done.stdout.decode("utf-8", "replace")
    except (OSError, subprocess.TimeoutExpired):
        return ""


def _scale_candidates(png: bytes) -> list[bytes]:
    import io
    candidates = [png]
    try:
        im = Image.open(io.BytesIO(png))
    except Exception:
        return candidates
    for w in (500, 700, 1000, 1200, 1500):
        if im.width == w:
            continue
        h = round(w * im.height / im.width)
        buf = io.BytesIO()
        im.resize((w, h), Image.LANCZOS).save(buf, "PNG")
        candidates.append(buf.getvalue())
    return candidates


def verify_bytes(png: bytes) -> str | None:
    for cand in _scale_candidates(png):
        out = _wechat_once(cand)
        if out and out.strip():
            return out
        if out is None:
            break
    for cand in _scale_candidates(png):
        out = _zbar_once(cand)
        if out and out.strip():
            return out
        if out is None:
            break
    try:
        import cv2
        import numpy as np
    except ImportError:
        return None
    detector = cv2.QRCodeDetector()
    for cand in _scale_candidates(png):
        image = cv2.imdecode(np.frombuffer(cand, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            continue
        data, _, _ = detector.detectAndDecode(image)
        if data:
            return data
    return None


def verify_decodable(path: Path) -> str | None:
    return verify_bytes(Path(path).read_bytes())


SAMPLE = Contact(
    first="Alex",
    last="Morgan",
    title="Product Designer",
    org="Northwind Studio",
    phone="+14155550123",
    email="alex@northwind.studio",
    website="https://northwind.studio",
    city="San Francisco",
    region="CA",
    country="USA",
    note="Building calm, useful interfaces.",
    social={
        "twitter": "alexmorgan",
        "instagram": "alex.builds",
        "linkedin":  "alexmorgan",
        "github": "alexmorgan",
        "dribbble": "https://dribbble.com/alexmorgan",
        "youtube": "alexmorgan",
    },
)


def contact_from_dict(data: dict) -> Contact:
    known = {f for f in Contact.__dataclass_fields__}
    extra = set(data) - known
    if extra:
        raise SystemExit(f"unknown contact keys: {', '.join(sorted(extra))}")
    return Contact(**data)


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate a styled vCard QR code")
    ap.add_argument("--json", help="path to a JSON file describing the contact")
    ap.add_argument("--theme", default="indigo", choices=sorted(THEMES))
    ap.add_argument("--logo", help="PNG/SVG-as-PNG placed in the QR center")
    ap.add_argument("--out", default="out", help="output directory")
    ap.add_argument("--no-card", action="store_true", help="skip the captioned card")
    args = ap.parse_args()

    contact = contact_from_dict(json.loads(Path(args.json).read_text())) if args.json else SAMPLE
    theme = THEMES[args.theme]
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    payload = build_vcard(contact)
    (out / "vcard.txt").write_text(payload)

    qr = make_qr(payload)
    logo_px = int((qr.modules_count + 8) * 12 * 0.20)
    logo = prepare_logo(args.logo, contact, logo_px, theme)

    styled = render(qr, theme=theme, logo=logo)
    dots = render(qr, theme=theme, logo=logo, style="dots")
    classic = render_classic(qr, theme)
    styled.save(out / "vcard_qr_styled.png")
    dots.save(out / "vcard_qr_dots.png")
    classic.save(out / "vcard_qr_classic.png")
    outputs = [out / "vcard_qr_styled.png", out / "vcard_qr_dots.png",
               out / "vcard_qr_classic.png"]
    if not args.no_card:
        card = caption_card(styled, contact, theme)
        card.save(out / "vcard_qr_card.png")
        outputs.append(out / "vcard_qr_card.png")

    print(f"vCard payload: {len(payload.encode())} bytes, QR version {qr.version}, "
          f"modules {qr.modules_count}x{qr.modules_count}, theme '{args.theme}'")
    for path in outputs:
        data = verify_decodable(path)
        if data is None:
            print(f"  {path.name}: cv2 decoder unavailable, open on a phone to confirm")
        else:
            ok = "FN:" in data and "END:VCARD" in data
            print(f"  {path.name}: {'OK — decodes to a vCard' if ok else 'WARNING — decode failed'}")


if __name__ == "__main__":
    main()
