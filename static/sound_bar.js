// Sound bar (mute, volume slider, level meter) for a media element.
// Usage: const bar = createSoundBar(containerEl, mediaEl); call bar.init() from a user gesture.
// bar.getRecordStream() returns the unattenuated audio, so muting does not silence recordings.
function createSoundBar(container, media) {
    const bar = document.createElement("div");
    bar.style.cssText = "display:flex;align-items:center;justify-content:center;gap:8px;" +
        "width:640px;margin:0 auto;padding:6px 0;background:#333;box-sizing:border-box;";
    bar.innerHTML =
        '<button type="button" class="sb-mute">🔊</button>' +
        '<input type="range" class="sb-vol" min="0" max="1" step="0.01" value="1" style="width:140px;">' +
        '<canvas class="sb-meter" width="200" height="12" style="background:#111;border:1px solid #555;"></canvas>';
    container.appendChild(bar);

    const muteBtn = bar.querySelector(".sb-mute");
    const vol = bar.querySelector(".sb-vol");
    const meter = bar.querySelector(".sb-meter");
    const mctx = meter.getContext("2d");

    let audioCtx = null, gain = null, analyser = null, recDest = null;
    let muted = false;

    function applyVolume() {
        const level = muted ? 0 : parseFloat(vol.value);
        if (gain) gain.gain.value = level;
        else media.volume = level;
        muteBtn.textContent = level === 0 ? "🔇" : "🔊";
    }

    function drawMeter() {
        requestAnimationFrame(drawMeter);
        mctx.clearRect(0, 0, meter.width, meter.height);
        if (!analyser) return;
        const data = new Uint8Array(analyser.fftSize);
        analyser.getByteTimeDomainData(data);
        let peak = 0;
        for (const v of data) peak = Math.max(peak, Math.abs(v - 128) / 128);
        mctx.fillStyle = peak > 0.85 ? "#e55" : peak > 0.6 ? "#ec4" : "#4c4";
        mctx.fillRect(0, 0, Math.min(1, peak) * meter.width, meter.height);
    }

    async function init() {
        if (!audioCtx) {
            audioCtx = new AudioContext();
            const source = audioCtx.createMediaElementSource(media);
            gain = audioCtx.createGain();
            analyser = audioCtx.createAnalyser();
            recDest = audioCtx.createMediaStreamDestination();
            source.connect(analyser);
            source.connect(recDest);
            source.connect(gain);
            gain.connect(audioCtx.destination);
            applyVolume();
        }
        await audioCtx.resume();
    }

    muteBtn.addEventListener("click", () => { muted = !muted; applyVolume(); });
    vol.addEventListener("input", () => { muted = false; applyVolume(); });
    drawMeter();

    return {
        init,
        async getRecordStream() { await init(); return recDest.stream; },
    };
}
