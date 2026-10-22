// JavaScript controls for NVR functions (start_recording, stop_recording, write_frame)

document.getElementById("startRecording").addEventListener("click", () => {
    fetch("/start_recording", { method: "GET" });
});

document.getElementById("stopRecording").addEventListener("click", () => {
    fetch("/stop_recording", { method: "GET" });
});

document.getElementById("writeFrame").addEventListener("click", () => {
    fetch("/write_frame", { method: "GET" });
});