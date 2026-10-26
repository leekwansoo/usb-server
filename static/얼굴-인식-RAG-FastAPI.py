cv2.rectangle(frame, (gx1,gy1), (gx2,gy2), (0,255,255), 2) # yellow
cv2.rectangle(frame, (x1,y1), (x2,y2), (0,0,255), 2) # red
_, jpeg = cv2.imencode('.jpg', frame) # <-- you saved this WITH boxes