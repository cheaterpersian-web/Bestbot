from io import BytesIO
from typing import Optional

import qrcode
from PIL import Image


def generate_qr_with_template(subscription_url: str, template_path: Optional[str] = None) -> bytes:
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(subscription_url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGBA")

    if template_path:
        try:
            base = Image.open(template_path).convert("RGBA")
            # paste qr at bottom-right with margin
            base_width, base_height = base.size
            qr_size = min(base_width // 3, base_height // 3)
            qr_img = qr_img.resize((qr_size, qr_size))
            margin = qr_size // 8
            base.alpha_composite(qr_img, dest=(base_width - qr_size - margin, base_height - qr_size - margin))
            out = base
        except Exception:
            out = qr_img
    else:
        out = qr_img

    buf = BytesIO()
    out.save(buf, format="PNG")
    return buf.getvalue()

