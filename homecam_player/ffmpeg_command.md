## FFMPEG Config
ffmpeg -i rtsp://timebridge49:james1030@192.168.0.50:554/stream1 -c:v copy -c:a aac -f hls -hls_time 2 -hls_list_size 3 stream.m3u8

python -m http.server 8000

# Powershell Command
powershell -ExecutionPolicy Bypass -File nvr_record.ps1
