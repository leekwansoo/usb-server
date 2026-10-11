# ================================
# NVR Recording Script
# - record_duration: length of each file (seconds)
# - record_interval: time between recordings (seconds)
# - max_files: maximum number of files to keep
# ================================

# 설정
$record_duration = 60          # 1-minute file
$record_interval = 300         # 5 minutes interval
$max_files = 30                # keep only newest 30 files

$folder = "C:\NVR_Recordings\$(Get-Date -Format 'yyyy-MM-dd')"

# 폴더 생성
New-Item -ItemType Directory -Force -Path $folder | Out-Null
Set-Location $folder

while ($true) {

    # 파일 이름 생성
    $timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
    $filename = "record_$timestamp.mp4"

    # 녹화 (record_duration 만큼)
    ffmpeg -i rtsp://821095305200:<password>@192.168.0.16:554/stream1 `
           -c:v copy -c:a aac `
           -t $record_duration `
           $filename

    # 파일 목록 가져오기 (오래된 순)
    $files = Get-ChildItem -File | Sort-Object LastWriteTime

    # 파일 개수 초과 시 오래된 파일 삭제
    if ($files.Count -gt $max_files) {
        $remove_count = $files.Count - $max_files
        $files[0..($remove_count - 1)] | Remove-Item
    }

    # 다음 녹화까지 대기 (record_interval)
    Start-Sleep -Seconds $record_interval
}
