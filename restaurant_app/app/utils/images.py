import os, uuid
import secrets
from PIL import Image, ImageOps
from werkzeug.utils import secure_filename

ALLOWED_EXT = {"png", "jpg", "jpeg", "gif", "webp"}

def save_image(file_storage, out_dir_abs, max_size=(100, 100)):
    filename = file_storage.filename or ""
    ext = os.path.splitext(filename)[1].lower().lstrip(".")  # ⭐关键：去掉点

    if ext not in ALLOWED_EXT:
        raise ValueError("图片格式不支持（仅 png/jpg/jpeg/gif/webp）")

    os.makedirs(out_dir_abs, exist_ok=True)

    # 用 uuid 防止中文名/重复名/路径问题
    out_name = f"{uuid.uuid4().hex}.{ext}"
    out_path = os.path.join(out_dir_abs, out_name)

    # 读取并缩略
    file_storage.stream.seek(0)
    img = Image.open(file_storage.stream)

    # jpg 不能保存 RGBA
    if ext in ("jpg", "jpeg") and img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    img.thumbnail(max_size)

    save_format = "JPEG" if ext in ("jpg", "jpeg") else ext.upper()
    img.save(out_path, format=save_format, quality=85, optimize=True)

    return out_name
