
V3 - Clean Passport without boxes + White Background

Problem you had:
Saved photo had yellow/red boxes because you did cv2.rectangle on frame then saved same frame

Fix:
- Keep clean_frame = frame.copy() BEFORE drawing boxes
- Save clean_frame cropped to yellow guide, not drawn frame
- Endpoints:
  - /api/webcam/stream/passport -> shows boxes (for display)
  - /api/webcam/capture/passport -> saves CLEAN without boxes + white bg

New params:
- white_bg=True/False
- bg_method: mediapipe (fast, no extra model) or rembg (best quality, pip install rembg)

White background:
- mediapipe selfie segmentation -> background white
- rembg (U2Net) -> better edge, install: pip install rembg

To clean your existing boxed image:
POST /api/clean/boxed-image with your boxed jpg -> returns cleaned white bg version
