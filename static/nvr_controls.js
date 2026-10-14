// JavaScript controls for NVR functions (start_recording, stop_recording, write_frame)

document.getElementById("startRecording").addEventListener("click", () => {
    fetch("/start_recording", { method: "POST" });
});

document.getElementById("stopRecording").addEventListener("click", () => {
    fetch("/stop_recording", { method: "POST" });
});

document.getElementById("writeFrame").addEventListener("click", () => {
    fetch("/write_frame", { method: "POST" });
});