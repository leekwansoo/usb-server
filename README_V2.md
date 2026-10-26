
# V1 -> V2 Passport Fix

## V1 Problems
1. Duplicate route /api/webcam/capture/{name} - FastAPI conflict, second overwrites first
2. Fixed +40px padding fails for small image 244x309 and for passport spec
3. No frame-size guide - user doesn't know how close to stand
4. No 35x45mm final resize
5. Cascade !empty crash if file missing (previous bug)

## V2 Passport Solution

### Frame-Size
- Preview: 1280x720 (good for YOLOv8)
- Passport Guide: 38% width (~486px) * aspect 0.777 = 35x45 ratio
- Guide centered slightly up (eyes at 60% height per ICAO)

### Face Capture Size
- Final: 413x531px @300DPI = 35x45mm
- Face height = 70-80% of final image (32-36mm)
- Implementation: expand_for_passport() with top 40%, bottom 60%, side 50% padding
- If YOLO box <60px (eye bug) -> expand 3x

### New Endpoints
- GET /api/webcam/stream/passport - MJPEG with yellow guide overlay + green OK box
- POST /api/webcam/capture/passport - Returns passport 413x531 ready image

### How to get passport size
1. User stands so face fills 70-80% of yellow guide
2. Press Capture
3. Server crops guide area, resizes to 413x531, saves to passport_photos/
