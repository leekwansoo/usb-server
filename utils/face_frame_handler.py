import os, uuid, datetime
from pathlib import Path
from PIL import Image, ImageOps
import cv2
import numpy as np
try:
    import mediapipe as mp
    HAS_MEDIAPIPE =True
except ImportError:
    HAS_MEDIAPIPE = False
    
PASSPORT_W, PASSPORT_H = 413, 531
PASSPORT_TARGET_W, PASSPORT_TARGET_H = 413, 531

def get_frame_guide(frame_w, frame_h):
    """
    Frame-Size: How big should live preview guide be?
    - For 1280x720 preview, guide = 50% width, 70% height, centered slightly up
    - This guide = final passport area
    """
    guide_w = int(frame_w * 0.38) # 1280*0.38 ≈ 486px ~ passport ratio
     # Force passport aspect 35:45 = 0.777
    guide_h = int(guide_w / 0.777)
    if guide_h > frame_h*0.7:
        guide_h = int(frame_h*0.7)
        guide_w = int(guide_h * 0.777)
    x1 = (frame_w - guide_w)//2
    y1 = (frame_h - guide_h)//2 - int(frame_h*0.05)
    return (x1, y1, x1+guide_w, y1+guide_h, guide_w, guide_h)

def expand_for_passport(x1, y1, x2, y2, img_w, img_h):
    """
    Expand YOLO box to passport composition:
    - Passport: face = 70-80% of height, centered, top padding 15%, bottom 20%
    - Your V1 had fixed +40px, which fails for small images like 244x309
    """
    bw = x2 - x1
    bh = y2 - y1
    if bw < 60 or bh < 60:
        cx, cy = x1 + bw/2, y1 + bh/2
        bw, bh = bw*3, bh*3
        x1, y1 = int(cx - bw/2), int(cy - bh/2)
        x2, y2 = int(x1 + bw), int(y1 + bh)
    # Calculate padding based on face box size
    top_pad = int(bh * 0.4) # 40% of face height for top padding
    bottom_pad = int(bh * 0.6) # 60% of face height for bottom padding
    side_pad = int(bw * 0.5)
    x1_e = max(0, x1 - side_pad)
    y1_e = max(0, y1 - top_pad)
    x2_e = min(img_w, x2 + side_pad)
    y2_e = min(img_h, y2 + bottom_pad)
    
    return x1_e, y1_e, x2_e, y2_e

def resize_for_recognition(x1, y1, x2, y2, img_w, img_h):
    """
    resize YOLO box to fit face recognition:
    - Face recognition: face = +10% of face_height and width for context
    """
    bw = x2 - x1
    bh = y2 - y1
    if bw < 60 or bh < 60:
        cx, cy = x1 + bw/2, y1 + bh/2
        bw, bh = bw*3, bh*3
        x1, y1 = int(cx - bw/2), int(cy - bh/2)
        x2, y2 = int(x1 + bw), int(y1 + bh)
    # Calculate padding based on face box size
    top_pad = int(bh * 0.1) # 10% of face height for top padding
    bottom_pad = int(bh * 0.1) # 10% of face height for bottom padding
    side_pad = int(bw * 0.1)
    x1_e = max(0, x1 - side_pad)
    y1_e = max(0, y1 - top_pad)
    x2_e = min(img_w, x2 + side_pad)
    y2_e = min(img_h, y2 + bottom_pad)
    
    return x1_e, y1_e, x2_e, y2_e

def make_passport_image(cropped_path, output_path):
    """Resize cropped face to exact 413x531 and add white background if needed"""
    with Image.open(cropped_path) as im:
        # Convert to RGB
        im = im.convert("RGB")
        # Resize to passport with aspect ratio preserved, then pad white
        # Use ImageOps.fit to crop to exact ratio
        passport = ImageOps.fit(im, (PASSPORT_TARGET_W, PASSPORT_TARGET_H), method=Image.LANCZOS, centering=(0.5, 0.4))
        # remove the rectangle guide if any for final passport image)
        
        passport.save(output_path, "JPEG", quality=95, dpi=(300,300))
    return output_path

def remove_background_white(image_bgr, method="mediapipe"):
    """
    Make background white - 3 methods:
    - rembg (best quality, needs pip install rembg)
    - mediapipe selfie segmentation (good, no extra install if you have mediapipe)
    - simple threshold (fallback)
    """
    try:
        if method == "rembg":
            print("Using rembg for background removal")
            from rembg import remove
            from PIL import Image as PILImage
            pil = PILImage.fromarray(cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB))
            no_bg = remove(pil)  # RGBA
            white_bg = PILImage.new("RGB", no_bg.size, (255,255,255))
            white_bg.paste(no_bg, mask=no_bg.split()[3])
            return cv2.cvtColor(np.array(white_bg), cv2.COLOR_RGB2BGR)
    except Exception as e:
        print(f"rembg failed: {e}, trying mediapipe")
    
    try:
        if method in ["mediapipe","auto"]:
            import mediapipe as mp
            mp_selfie = mp.solutions.selfie_segmentation
            with mp_selfie.SelfieSegmentation(model_selection=1) as seg:
                rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
                res = seg.process(rgb)
                mask = res.segmentation_mask
                # mask: 0=background, 1=person
                condition = np.stack((mask,) * 3, axis=-1) > 0.6
                white_bg = np.ones_like(image_bgr, dtype=np.uint8) * 255
                output = np.where(condition, image_bgr, white_bg)
                return output
    except Exception as e:
        print(f"mediapipe seg failed: {e}")
    
    # Fallback: just return original (no bg removal)
    return image_bgr

def make_passport_final(cropped_bgr, output_path, white_bg=True, bg_method="mediapipe"):
    """Crop -> white bg -> resize to 413x531"""
    if white_bg:
        cropped_bgr = remove_background_white(cropped_bgr, method=bg_method)
    # Resize to passport
    passport = cv2.resize(cropped_bgr, (PASSPORT_W, PASSPORT_H), interpolation=cv2.INTER_LANCZOS4)
    cv2.imwrite(str(output_path), passport)
    # Also save with PIL for DPI metadata
    try:
        pil = Image.fromarray(cv2.cvtColor(passport, cv2.COLOR_BGR2RGB))
        pil.save(output_path, "JPEG", quality=95, dpi=(300,300))
    except:
        pass
    return output_path
