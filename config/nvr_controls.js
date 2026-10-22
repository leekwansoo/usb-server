// Pages may define window.getNvrAudioStream = async () => MediaStream to choose the audio source.
// Default is the microphone.
let nvrAudioRecorder = null;
let nvrAudioChunks = [];
let nvrMicStream = null;

function nvrStatus(text) {
    document.getElementById("recStatus").textContent = text;
}

const nvrSourceSelect = document.getElementById("audioSource");

async function nvrLoadSources() {
    if (!nvrSourceSelect || !navigator.mediaDevices) return;
    const previous = nvrSourceSelect.value;
    const devices = (await navigator.mediaDevices.enumerateDevices()).filter((d) => d.kind === "audioinput");
    nvrSourceSelect.innerHTML = "";
    const add = (value, label) => nvrSourceSelect.add(new Option(label, value));
    devices.forEach((d, i) => add(d.deviceId, d.label || "Microphone " + (i + 1)));
    add("music", "Background music (choose a file)");
    add("none", "No audio");
    if ([...nvrSourceSelect.options].some((o) => o.value === previous)) nvrSourceSelect.value = previous;
    nvrToggleMusicPicker();
}

function nvrToggleMusicPicker() {
    const picker = document.getElementById("musicFile");
    if (picker) picker.style.display = nvrSourceSelect.value === "music" ? "inline" : "none";
}

let nvrMusicEl = null;
let nvrMusicCtx = null;
let nvrMusicDest = null;

async function nvrMusicStream() {
    const file = document.getElementById("musicFile").files[0];
    if (!file) throw new Error("no music file chosen");
    if (!nvrMusicEl) {
        nvrMusicEl = new Audio();
        nvrMusicEl.loop = true;
        nvrMusicCtx = new AudioContext();
        const source = nvrMusicCtx.createMediaElementSource(nvrMusicEl);
        nvrMusicDest = nvrMusicCtx.createMediaStreamDestination();
        source.connect(nvrMusicCtx.destination);
        source.connect(nvrMusicDest);
    }
    await nvrMusicCtx.resume();
    nvrMusicEl.src = URL.createObjectURL(file);
    await nvrMusicEl.play();
    return nvrMusicDest.stream;
}

async function nvrGetStream() {
    if (window.getNvrAudioStream) return window.getNvrAudioStream();
    const choice = nvrSourceSelect ? nvrSourceSelect.value : "";
    if (choice === "none") return null;
    if (choice === "music") return nvrMusicStream();
    const audio = choice && choice !== "default" ? { deviceId: { exact: choice } } : true;
    nvrMicStream = await navigator.mediaDevices.getUserMedia({ audio });
    nvrLoadSources();
    return nvrMicStream;
}

async function nvrStart() {
    try {
        const stream = await nvrGetStream();
        if (stream) {
            nvrAudioChunks = [];
            nvrAudioRecorder = new MediaRecorder(stream);
            nvrAudioRecorder.ondataavailable = (e) => { if (e.data.size) nvrAudioChunks.push(e.data); };
            nvrAudioRecorder.start(1000);
        }
    } catch (e) {
        nvrAudioRecorder = null;
        console.warn("Audio capture unavailable, recording video only:", e);
    }
    try {
        const res = await fetch("/start_recording", { method: "GET" });
        nvrStatus((await res.json()).status + (nvrAudioRecorder ? " (with audio)" : " (no audio)"));
    } catch (e) {
        nvrStatus("Error: " + e);
    }
}

function nvrStopAudio() {
    return new Promise((resolve) => {
        const recorder = nvrAudioRecorder;
        nvrAudioRecorder = null;
        if (nvrMicStream) {
            nvrMicStream.getTracks().forEach((t) => t.stop());
            nvrMicStream = null;
        }
        if (nvrMusicEl) nvrMusicEl.pause();
        if (!recorder || recorder.state === "inactive") return resolve(null);
        recorder.onstop = () => resolve(new Blob(nvrAudioChunks, { type: recorder.mimeType }));
        recorder.stop();
    });
}

async function nvrStop() {
    try {
        const audio = await nvrStopAudio();
        const res = await fetch("/stop_recording", { method: "GET" });
        let text = (await res.json()).status;
        if (audio && audio.size) {
            nvrStatus("Saving audio...");
            up = await fetch("/api/recording/audio", { method: "POST", body: audio });
            if (up.ok) {
                text += " (audio added)";
            } else {
                let reason = "";
                try { reason = (await up.json()).error; } catch (e) {}
                text += " (audio failed: " + reason + ")";
            }
        }
        nvrStatus(text);
    } catch (e) {
        nvrStatus("Error: " + e);
    }
}

document.getElementById("startRecording").addEventListener("click", nvrStart);
document.getElementById("stopRecording").addEventListener("click", nvrStop);
nvrLoadSources();
if (nvrSourceSelect) nvrSourceSelect.addEventListener("change", nvrToggleMusicPicker);
