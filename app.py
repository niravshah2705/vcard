#!/usr/bin/env python3
"""Flask front-end for vcard_qr.py — form in, verified QR images out."""

from __future__ import annotations

import base64
import io

import qrcode
from flask import Flask, jsonify, request, send_from_directory
from PIL import Image

import vcard_qr as V

app = Flask(__name__, static_folder="static")

CONTACT_FIELDS = [f for f in V.Contact.__dataclass_fields__ if f != "social"]


@app.get("/")
def index():
    return send_from_directory("templates", "index.html")


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/api/meta")
def meta():
    platforms = ["twitter", "instagram", "linkedin", "facebook", "github",
                 "youtube", "tiktok", "threads", "mastodon", "pinterest",
                 "snapchat", "custom"]
    themes = {name: {"fg": list(t["fg"]), "badge": list(t["badge"])}
              for name, t in V.THEMES.items()}
    return jsonify(platforms=platforms, themes=themes,
                   contact_fields=CONTACT_FIELDS)


def _to_data_url(png: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(png).decode()


def _decode_logo(value):
    if not value:
        return None
    raw = base64.b64decode(value.split(",", 1)[-1])
    return Image.open(io.BytesIO(raw))


@app.post("/api/generate")
def generate():
    data = request.get_json(force=True, silent=True) or {}
    social = {k: v for k, v in (data.get("social") or {}).items() if str(v).strip()}
    kwargs = {f: str(data.get(f) or "") for f in CONTACT_FIELDS}
    contact = V.Contact(**kwargs, social=social)
    if not (contact.first or contact.last):
        return jsonify(error="Please provide at least a first or last name."), 400

    payload = V.build_vcard(contact)
    try:
        qr = V.make_qr(payload)
    except Exception as exc:
        return jsonify(error=f"Payload too large for a QR code ({len(payload)} bytes): {exc}"), 400

    theme = V.THEMES.get(data.get("theme"), V.THEMES["indigo"])
    try:
        logo_source = _decode_logo(data.get("logo"))
    except Exception:
        logo_source = None
    logo = V.prepare_logo(logo_source, contact,
                          int((qr.modules_count + 8) * 12 * 0.20), theme)

    rendered = {
        "styled": V.render(qr, theme=theme, logo=logo),
        "dots": V.render(qr, theme=theme, logo=logo, style="dots"),
        "classic": V.render_classic(qr, theme),
    }
    rendered["card"] = V.caption_card(rendered["styled"], contact, theme)

    images, verified = {}, {}
    qr_w = rendered["styled"].width
    for name, img in rendered.items():
        buf = io.BytesIO()
        img.save(buf, "PNG")
        png = buf.getvalue()
        images[name] = _to_data_url(png)
        probe = png
        if name == "card":
            pad = int(qr_w * 0.07)
            crop = img.crop((pad, pad, pad + qr_w, pad + qr_w))
            cbuf = io.BytesIO()
            crop.save(cbuf, "PNG")
            probe = cbuf.getvalue()
        decoded = V.verify_bytes(probe) or ""
        verified[name] = decoded.startswith("BEGIN:VCARD") and "END:VCARD" in decoded

    return jsonify(images=images, verified=verified, payload=payload,
                   version=qr.version, modules=qr.modules_count,
                   bytes=len(payload.encode()))


@app.errorhandler(404)
def not_found(_):
    return jsonify(error="not found"), 404


if __name__ == "__main__":
    port = int(__import__("os").environ.get("PORT", 5057))
    app.run(host="127.0.0.1", port=port, debug=False)
