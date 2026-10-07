/**
 * Blind Helper — Frontend Application
 * Camera capture, WebSocket streaming, TTS, haptic feedback, detection overlay
 */

(() => {
    'use strict';

    // ── State ───────────────────────────────────────────
    const state = {
        isRunning: false,
        isMuted: false,
        wsConnected: false,
        describingScene: false, // true while scene description is in progress
        resumeAfter: 0, // Date.now() timestamp to ignore stale frames after resuming
        searchedObject: null, // target object string, e.g. "laptop"
        lastSearchSpoken: 0,
        searchTimeout: null,
        searchFoundCount: 0,
        searchMaxAnnounce: 3, // auto-stop after this many found announcements
        searchLastFoundInfo: null, // {label, distance, position} for stop notification
        searchLastPosition: null, // track position zone changes
        stream: null,
        ws: null,
        sendInterval: null,
        vlmInterval: null,
        facingMode: 'environment', // rear camera default
        settings: {
            serverUrl: '',
            fps: 2,
            speechRate: 1.0,
            showOverlay: true,
            hapticEnabled: true,
            vlmIntervalSec: 10
        }
    };

    // ── DOM Elements ────────────────────────────────────
    const $ = (id) => document.getElementById(id);

    const els = {
        splash: $('splash-screen'),
        loadFill: $('loading-fill'),
        loadText: $('loading-text'),
        app: $('app'),
        video: $('camera-feed'),
        canvas: $('overlay-canvas'),
        statusIndicator: $('status-indicator'),
        statusText: $('status-text'),
        statusFps: $('status-fps'),
        alertBanner: $('alert-banner'),
        alertText: $('alert-text'),
        messageFeed: $('message-feed'),
        btnToggle: $('btn-toggle'),
        iconPlay: $('icon-play'),
        iconStop: $('icon-stop'),
        btnDescribe: $('btn-describe'),
        btnReadSigns: $('btn-read-signs'),
        btnFindObject: $('btn-find-object'),
        btnMute: $('btn-mute'),
        btnSettings: $('btn-settings'),
        settingsModal: $('settings-modal'),
        btnCloseSettings: $('btn-close-settings'),
        serverUrl: $('server-url'),
        fpsSlider: $('fps-slider'),
        fpsValue: $('fps-value'),
        speechRate: $('speech-rate'),
        speechRateValue: $('speech-rate-value'),
        showOverlay: $('show-overlay'),
        hapticEnabled: $('haptic-enabled'),
        vlmInterval: $('vlm-interval'),
        vlmIntervalValue: $('vlm-interval-value'),
        srAnnouncements: $('sr-announcements')
    };

    const ctx = els.canvas.getContext('2d');

    // ── Initialization ──────────────────────────────────
    function init() {
        loadSettings();
        setupEventListeners();
        autoDetectServerUrl();
        simulateSplash();
    }

    function simulateSplash() {
        const steps = [
            { pct: 20, text: 'Loading camera module...' },
            { pct: 50, text: 'Preparing detection engine...' },
            { pct: 80, text: 'Setting up audio...' },
            { pct: 100, text: 'Ready!' }
        ];
        let i = 0;
        const interval = setInterval(() => {
            if (i >= steps.length) {
                clearInterval(interval);
                setTimeout(() => {
                    els.splash.classList.add('fade-out');
                    els.app.classList.remove('hidden');
                }, 400);
                return;
            }
            els.loadFill.style.width = steps[i].pct + '%';
            els.loadText.textContent = steps[i].text;
            i++;
        }, 500);
    }

    function autoDetectServerUrl() {
        if (!state.settings.serverUrl) {
            const loc = window.location;
            const wsProtocol = loc.protocol === 'https:' ? 'wss:' : 'ws:';
            state.settings.serverUrl = `${wsProtocol}//${loc.host}`;
            els.serverUrl.value = state.settings.serverUrl;
        }
    }

    // ── Settings ────────────────────────────────────────
    function loadSettings() {
        try {
            const saved = localStorage.getItem('blindhelper_settings');
            if (saved) {
                Object.assign(state.settings, JSON.parse(saved));
            }
        } catch (e) { /* ignore */ }
        applySettingsToUI();
    }

    function saveSettings() {
        localStorage.setItem('blindhelper_settings', JSON.stringify(state.settings));
    }

    function applySettingsToUI() {
        els.serverUrl.value = state.settings.serverUrl || '';
        els.fpsSlider.value = state.settings.fps;
        els.fpsValue.textContent = state.settings.fps;
        els.speechRate.value = state.settings.speechRate;
        els.speechRateValue.textContent = state.settings.speechRate.toFixed(1);
        els.showOverlay.checked = state.settings.showOverlay;
        els.hapticEnabled.checked = state.settings.hapticEnabled;
        els.vlmInterval.value = state.settings.vlmIntervalSec;
        els.vlmIntervalValue.textContent = state.settings.vlmIntervalSec;
    }

    // ── Event Listeners ─────────────────────────────────
    function setupEventListeners() {
        els.btnToggle.addEventListener('click', toggleStream);
        els.btnDescribe.addEventListener('click', () => requestSceneDescription(true));
        els.btnReadSigns.addEventListener('click', requestSignReading);
        els.btnFindObject.addEventListener('click', toggleVoiceSearch);
        els.btnMute.addEventListener('click', toggleMute);
        els.btnSettings.addEventListener('click', () => {
            els.settingsModal.classList.remove('hidden');
        });
        els.btnCloseSettings.addEventListener('click', () => {
            els.settingsModal.classList.add('hidden');
        });
        els.settingsModal.addEventListener('click', (e) => {
            if (e.target === els.settingsModal) {
                els.settingsModal.classList.add('hidden');
            }
        });

        // Settings inputs
        els.serverUrl.addEventListener('change', () => {
            state.settings.serverUrl = els.serverUrl.value;
            saveSettings();
        });
        els.fpsSlider.addEventListener('input', () => {
            state.settings.fps = parseInt(els.fpsSlider.value);
            els.fpsValue.textContent = state.settings.fps;
            saveSettings();
            if (state.isRunning) restartSendInterval();
        });
        els.speechRate.addEventListener('input', () => {
            state.settings.speechRate = parseFloat(els.speechRate.value);
            els.speechRateValue.textContent = state.settings.speechRate.toFixed(1);
            saveSettings();
        });
        els.showOverlay.addEventListener('change', () => {
            state.settings.showOverlay = els.showOverlay.checked;
            saveSettings();
            if (!state.settings.showOverlay) clearCanvas();
        });
        els.hapticEnabled.addEventListener('change', () => {
            state.settings.hapticEnabled = els.hapticEnabled.checked;
            saveSettings();
        });
        els.vlmInterval.addEventListener('input', () => {
            state.settings.vlmIntervalSec = parseInt(els.vlmInterval.value);
            els.vlmIntervalValue.textContent = state.settings.vlmIntervalSec;
            saveSettings();
            if (state.isRunning) restartVLMInterval();
        });
    }

    // ── Camera ──────────────────────────────────────────
    async function startCamera() {
        try {
            const constraints = {
                video: {
                    facingMode: state.facingMode,
                    width: { ideal: 640 },
                    height: { ideal: 480 }
                },
                audio: false
            };
            state.stream = await navigator.mediaDevices.getUserMedia(constraints);
            els.video.srcObject = state.stream;
            await els.video.play();
            resizeCanvas();
            window.addEventListener('resize', resizeCanvas);
            return true;
        } catch (err) {
            console.error('Camera error:', err);
            showAlert(`Camera error: ${err.message}`);
            return false;
        }
    }

    function stopCamera() {
        if (state.stream) {
            state.stream.getTracks().forEach(t => t.stop());
            state.stream = null;
        }
        els.video.srcObject = null;
        window.removeEventListener('resize', resizeCanvas);
    }

    function resizeCanvas() {
        els.canvas.width = els.video.videoWidth || els.video.clientWidth;
        els.canvas.height = els.video.videoHeight || els.video.clientHeight;
    }

    // ── WebSocket ───────────────────────────────────────
    function connectWebSocket() {
        const url = state.settings.serverUrl + '/ws/stream';
        setStatus('connecting', 'Connecting...');

        try {
            state.ws = new WebSocket(url);
        } catch (err) {
            setStatus('error', 'Connection error');
            showAlert('Cannot connect to server. Check the server URL in Settings.');
            return;
        }

        state.ws.onopen = () => {
            state.wsConnected = true;
            setStatus('active', 'Connected');
            hideAlert();
            els.btnDescribe.disabled = false;
            els.btnReadSigns.disabled = false;
            els.btnFindObject.disabled = false;
        };

        state.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                handleDetectionResult(data);
            } catch (e) {
                console.error('Parse error:', e);
            }
        };

        state.ws.onerror = (err) => {
            console.error('WebSocket error:', err);
            setStatus('error', 'Connection error');
        };

        state.ws.onclose = () => {
            state.wsConnected = false;
            setStatus('error', 'Disconnected');
            els.btnDescribe.disabled = true;
            els.btnReadSigns.disabled = true;
            els.btnFindObject.disabled = true;

            // Auto-reconnect if still running
            if (state.isRunning) {
                setTimeout(() => {
                    if (state.isRunning) connectWebSocket();
                }, 3000);
            }
        };
    }

    function disconnectWebSocket() {
        if (state.ws) {
            state.ws.close();
            state.ws = null;
        }
        state.wsConnected = false;
    }

    // ── Frame Streaming ─────────────────────────────────
    function startSendingFrames() {
        restartSendInterval();
        restartVLMInterval();
    }

    function stopSendingFrames() {
        if (state.sendInterval) {
            clearInterval(state.sendInterval);
            state.sendInterval = null;
        }
        if (state.vlmInterval) {
            clearInterval(state.vlmInterval);
            state.vlmInterval = null;
        }
    }

    function restartSendInterval() {
        if (state.sendInterval) clearInterval(state.sendInterval);
        const intervalMs = Math.round(1000 / state.settings.fps);
        state.sendInterval = setInterval(sendFrame, intervalMs);
    }

    function restartVLMInterval() {
        if (state.vlmInterval) clearInterval(state.vlmInterval);
        state.vlmInterval = setInterval(requestSceneDescription, state.settings.vlmIntervalSec * 1000);
    }

    function sendFrame() {
        if (!state.ws || state.ws.readyState !== WebSocket.OPEN) return;
        if (!els.video.videoWidth) return;

        const tempCanvas = document.createElement('canvas');
        tempCanvas.width = els.video.videoWidth;
        tempCanvas.height = els.video.videoHeight;
        const tCtx = tempCanvas.getContext('2d');
        tCtx.drawImage(els.video, 0, 0, tempCanvas.width, tempCanvas.height);

        const dataUrl = tempCanvas.toDataURL('image/jpeg', 0.7);
        state.ws.send(dataUrl);
    }

    // ── Detection Result Handling ───────────────────────
    function handleDetectionResult(data) {
        if (data.error) {
            console.warn('Server error:', data.error);
            return;
        }

        // While describing scene, suppress all pipeline speech/haptic
        if (state.describingScene) return;

        // Suppress stale frames that arrive right after resume
        if (state.resumeAfter && Date.now() < state.resumeAfter) return;

        // -- SEARCH MODE --
        if (state.searchedObject) {
            if (data.process_time_ms) els.statusFps.textContent = `${data.process_time_ms} ms`;
            if (state.settings.showOverlay && data.overlay) {
                drawOverlay(data.overlay, data.frame_width, data.frame_height);
            }

            // Fuzzy match against all detections in overlay
            const matches = (data.overlay || []).filter(o => matchesSearchTarget(o.label, state.searchedObject));

            if (matches.length > 0) {
                if (state.searchTimeout) {
                    clearTimeout(state.searchTimeout);
                    state.searchTimeout = null;
                }

                const closest = matches.reduce((prev, curr) => (prev.distance < curr.distance) ? prev : curr);
                const currentPosition = closest.position;
                const positionChanged = state.searchLastPosition && state.searchLastPosition !== currentPosition;
                const cooldownPassed = Date.now() - state.lastSearchSpoken > 1500;

                if (cooldownPassed || positionChanged) {
                    // Play beep + strong vibration on FIRST detection
                    if (state.searchFoundCount === 0) {
                        playBeep(880, 250);
                        if (state.settings.hapticEnabled) navigator.vibrate && navigator.vibrate([200, 100, 200, 100, 200]);
                    }

                    state.searchFoundCount++;
                    const distStr = closest.distance <= 1 ? "1 meter" : `${closest.distance} meters`;
                    const msg = `Found ${closest.label}, ${distStr} ${closest.position}`;
                    showMessage(msg, 'warning');
                    speak(msg);
                    if (state.settings.hapticEnabled) vibrate();
                    state.lastSearchSpoken = Date.now();
                    state.searchLastPosition = currentPosition;

                    // Save for stop notification
                    state.searchLastFoundInfo = {
                        label: closest.label,
                        distance: distStr,
                        position: closest.position
                    };

                    // Auto-stop after N announcements
                    if (state.searchFoundCount >= state.searchMaxAnnounce) {
                        stopVoiceSearch(`${closest.label} located! ${distStr} ${closest.position}. Search complete.`);
                    }
                }
            }
            return;
        }

        // Update FPS display
        if (data.process_time_ms) {
            els.statusFps.textContent = `${data.process_time_ms} ms`;
        }

        // Draw overlay
        if (state.settings.showOverlay && data.overlay) {
            drawOverlay(data.overlay, data.frame_width, data.frame_height);
        }

        // Draw OCR overlay (text bounding boxes)
        if (state.settings.showOverlay && data.ocr_overlay && data.ocr_overlay.length > 0) {
            drawOCROverlay(data.ocr_overlay, data.frame_width, data.frame_height);
        }

        // Speak messages
        if (data.messages && data.messages.length > 0) {
            data.messages.forEach(msg => {
                showMessage(msg, isCloseObject(msg) ? 'warning' : '');
                speak(msg);
                if (isCloseObject(msg) && state.settings.hapticEnabled) {
                    vibrate();
                }
            });
        }

        // Speak OCR sign text
        if (data.ocr_texts && data.ocr_texts.length > 0) {
            data.ocr_texts.forEach(msg => {
                showMessage(msg, 'ocr');
                speak(msg);
                if (state.settings.hapticEnabled) {
                    vibrate();
                }
            });
        }
    }

    function isCloseObject(msg) {
        // Check if the distance mentioned is <= 1 meter
        const match = msg.match(/([\d.]+)\s*meters?/);
        return match && parseFloat(match[1]) <= 1;
    }

    // ── Overlay Drawing ─────────────────────────────────
    function drawOverlay(objects, frameW, frameH) {
        clearCanvas();
        if (!objects || objects.length === 0) return;

        const scaleX = els.canvas.width / frameW;
        const scaleY = els.canvas.height / frameH;

        objects.forEach(obj => {
            const [cx, cy] = obj.center;
            const x = cx * scaleX;
            const y = cy * scaleY;

            // Color based on distance
            let color;
            if (obj.distance < 1.5) {
                color = '#ff4757'; // danger - very close
            } else if (obj.distance < 2.5) {
                color = '#ffa502'; // warning - near
            } else {
                color = '#2ed573'; // safe - far
            }

            // Draw bounding box if available
            if (obj.bbox) {
                const [bx1, by1, bx2, by2] = obj.bbox;
                const rx = bx1 * scaleX;
                const ry = by1 * scaleY;
                const rw = (bx2 - bx1) * scaleX;
                const rh = (by2 - by1) * scaleY;

                ctx.strokeStyle = color;
                ctx.lineWidth = 2;
                ctx.setLineDash([6, 4]);
                ctx.strokeRect(rx, ry, rw, rh);
                ctx.setLineDash([]);

                // Label background
                const labelText = `${obj.label} ${obj.distance}m`;
                ctx.font = '600 13px Inter, sans-serif';
                const textW = ctx.measureText(labelText).width;
                const labelH = 22;
                ctx.fillStyle = color;
                ctx.globalAlpha = 0.85;
                ctx.beginPath();
                ctx.roundRect(rx, ry - labelH - 4, textW + 14, labelH, 4);
                ctx.fill();
                ctx.globalAlpha = 1;

                // Label text
                ctx.fillStyle = '#fff';
                ctx.fillText(labelText, rx + 7, ry - 10);
            } else {
                // Just draw a dot at center
                ctx.beginPath();
                ctx.arc(x, y, 8, 0, Math.PI * 2);
                ctx.fillStyle = color;
                ctx.globalAlpha = 0.7;
                ctx.fill();
                ctx.globalAlpha = 1;
            }
        });
    }

    function clearCanvas() {
        ctx.clearRect(0, 0, els.canvas.width, els.canvas.height);
    }

    // ── OCR Overlay Drawing ─────────────────────────────
    function drawOCROverlay(ocrItems, frameW, frameH) {
        if (!ocrItems || ocrItems.length === 0) return;

        const scaleX = els.canvas.width / frameW;
        const scaleY = els.canvas.height / frameH;

        ocrItems.forEach(item => {
            const [bx1, by1, bx2, by2] = item.bbox;
            const rx = bx1 * scaleX;
            const ry = by1 * scaleY;
            const rw = (bx2 - bx1) * scaleX;
            const rh = (by2 - by1) * scaleY;

            // Cyan color for OCR text boxes
            const color = '#00d2ff';

            ctx.strokeStyle = color;
            ctx.lineWidth = 2;
            ctx.setLineDash([4, 3]);
            ctx.strokeRect(rx, ry, rw, rh);
            ctx.setLineDash([]);

            // Label background
            const labelText = `📋 ${item.text}`;
            ctx.font = '600 12px Inter, sans-serif';
            const textW = ctx.measureText(labelText).width;
            const labelH = 20;
            ctx.fillStyle = color;
            ctx.globalAlpha = 0.85;
            ctx.beginPath();
            ctx.roundRect(rx, ry - labelH - 3, textW + 12, labelH, 4);
            ctx.fill();
            ctx.globalAlpha = 1;

            // Label text
            ctx.fillStyle = '#000';
            ctx.fillText(labelText, rx + 6, ry - 9);
        });
    }

    // ── On-Demand Sign Reading ──────────────────────────
    async function requestSignReading() {
        if (!state.isRunning || !els.video.videoWidth) return;

        try {
            showMessage('Reading signs...', 'ocr');

            const tempCanvas = document.createElement('canvas');
            tempCanvas.width = els.video.videoWidth;
            tempCanvas.height = els.video.videoHeight;
            const tCtx = tempCanvas.getContext('2d');
            tCtx.drawImage(els.video, 0, 0, tempCanvas.width, tempCanvas.height);

            const blob = await new Promise(resolve => {
                tempCanvas.toBlob(resolve, 'image/jpeg', 0.85);
            });

            const baseUrl = state.settings.serverUrl.replace(/^ws/, 'http');
            const formData = new FormData();
            formData.append('file', blob, 'frame.jpg');

            const response = await fetch(`${baseUrl}/api/read-signs`, {
                method: 'POST',
                body: formData
            });

            const result = await response.json();

            if (result.messages && result.messages.length > 0) {
                result.messages.forEach(msg => {
                    showMessage(msg, 'ocr');
                    speak(msg);
                });
            } else if (result.texts && result.texts.length > 0) {
                // If no new messages (cooldown), still show the detected text
                result.texts.forEach(t => {
                    const msg = `Sign: ${t.text}`;
                    showMessage(msg, 'ocr');
                    speak(msg);
                });
            } else {
                showMessage('No signs detected nearby', 'ocr');
                speak('No signs detected nearby');
            }
        } catch (err) {
            console.error('Sign reading error:', err);
            showMessage('Could not read signs', 'ocr');
        }
    }

    // ── VLM Scene Description ───────────────────────────
    async function requestSceneDescription(isManual = false) {
        if (!state.isRunning || !els.video.videoWidth) return;

        // If manually triggered, clear the entire pipeline first
        if (isManual) {
            state.describingScene = true;

            // 1. Stop sending frames (pauses YOLO/depth/OCR pipeline)
            stopSendingFrames();

            // 2. Cancel all queued TTS immediately
            if (window.speechSynthesis) {
                speechSynthesis.cancel();
            }

            showMessage('Describing scene...', 'vlm');
        }

        try {
            const tempCanvas = document.createElement('canvas');
            tempCanvas.width = 384;
            tempCanvas.height = 384;
            const tCtx = tempCanvas.getContext('2d');
            tCtx.drawImage(els.video, 0, 0, 384, 384);

            const blob = await new Promise(resolve => {
                tempCanvas.toBlob(resolve, 'image/jpeg', 0.7);
            });

            const baseUrl = state.settings.serverUrl.replace(/^ws/, 'http');
            const formData = new FormData();
            formData.append('file', blob, 'frame.jpg');

            const response = await fetch(`${baseUrl}/api/describe-scene`, {
                method: 'POST',
                body: formData
            });

            const result = await response.json();
            const desc = (result.description || '').trim();

            // Only speak valid scene descriptions (not errors or empty)
            if (desc && desc.length > 3 && !desc.toLowerCase().includes('error') && !desc.toLowerCase().includes('unavailable')) {
                showMessage(desc, 'vlm');

                if (isManual) {
                    // Speak with priority — wait for it to finish, then resume pipeline
                    await speakAndWait(desc);
                } else {
                    speak(desc);
                }
            }
        } catch (err) {
            console.error('VLM error:', err);
            if (isManual) {
                showMessage('Could not describe scene', 'vlm');
            }
        } finally {
            // Resume the pipeline if this was a manual request
            if (isManual && state.isRunning) {
                // Cancel any lingering TTS from stale pipeline responses
                if (window.speechSynthesis) speechSynthesis.cancel();

                // Set a cooldown: ignore detection results for 1s so
                // in-flight stale frames are discarded before fresh ones arrive
                state.resumeAfter = Date.now() + 1000;
                state.describingScene = false;
                startSendingFrames();
            }
        }
    }

    /**
     * Speak text and return a promise that resolves when speech finishes.
     * Cancels any existing speech first for clean priority playback.
     */
    function speakAndWait(text) {
        return new Promise(resolve => {
            if (state.isMuted || !window.speechSynthesis) {
                resolve();
                return;
            }

            speechSynthesis.cancel(); // ensure nothing else is speaking

            const utterance = new SpeechSynthesisUtterance(text);
            utterance.rate = state.settings.speechRate;
            utterance.pitch = 1;
            utterance.volume = 1;

            const voices = speechSynthesis.getVoices();
            const enVoice = voices.find(v => v.lang.startsWith('en'));
            if (enVoice) utterance.voice = enVoice;

            utterance.onend = resolve;
            utterance.onerror = resolve; // resolve even on error to not block forever

            speechSynthesis.speak(utterance);

            // Also update screen reader
            els.srAnnouncements.textContent = text;
        });
    }

    // ── Search Helpers ──────────────────────────────────
    const cocoClasses = [
        "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train",
        "truck", "boat", "traffic light", "fire hydrant", "stop sign",
        "parking meter", "bench", "bird", "cat", "dog", "horse", "sheep",
        "cow", "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella",
        "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard",
        "sports ball", "kite", "baseball bat", "baseball glove", "skateboard",
        "surfboard", "tennis racket", "bottle", "wine glass", "cup", "fork",
        "knife", "spoon", "bowl", "banana", "apple", "sandwich", "orange",
        "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair",
        "couch", "potted plant", "bed", "dining table", "toilet", "tv",
        "laptop", "mouse", "remote", "keyboard", "cell phone", "microwave",
        "oven", "toaster", "sink", "refrigerator", "book", "clock", "vase",
        "scissors", "teddy bear", "hair drier", "toothbrush"
    ];

    const objectAliases = {
        "phone": "cell phone", "mobile": "cell phone", "cellphone": "cell phone",
        "mobile phone": "cell phone", "smartphone": "cell phone", "cell": "cell phone",
        "table": "dining table", "desk": "dining table",
        "sofa": "couch", "settee": "couch",
        "television": "tv", "telly": "tv", "monitor": "tv", "screen": "tv",
        "motorbike": "motorcycle", "bike": "bicycle", "cycle": "bicycle",
        "bag": "backpack", "rucksack": "backpack",
        "plant": "potted plant", "flower": "potted plant", "flowerpot": "potted plant",
        "glass": "cup", "mug": "cup",
        "computer": "laptop", "notebook": "laptop",
        "fridge": "refrigerator", "icebox": "refrigerator",
        "aeroplane": "airplane", "plane": "airplane",
        "remote control": "remote", "microwave oven": "microwave",
        "teddy": "teddy bear", "hair dryer": "hair drier",
        "water bottle": "bottle", "wine": "wine glass"
    };

    function levenshteinDistance(a, b) {
        if (a.length === 0) return b.length;
        if (b.length === 0) return a.length;
        const matrix = [];
        for (let i = 0; i <= b.length; i++) matrix[i] = [i];
        for (let j = 0; j <= a.length; j++) matrix[0][j] = j;
        for (let i = 1; i <= b.length; i++) {
            for (let j = 1; j <= a.length; j++) {
                if (b.charAt(i - 1) === a.charAt(j - 1)) {
                    matrix[i][j] = matrix[i - 1][j - 1];
                } else {
                    matrix[i][j] = Math.min(
                        matrix[i - 1][j - 1] + 1,
                        matrix[i][j - 1] + 1,
                        matrix[i - 1][j] + 1
                    );
                }
            }
        }
        return matrix[b.length][a.length];
    }

    function matchesSearchTarget(detectionLabel, searchTarget) {
        const label = detectionLabel.toLowerCase().trim();
        const target = searchTarget.toLowerCase().trim();
        if (label === target) return true;
        if (label.includes(target) || target.includes(label)) return true;
        const maxDist = target.length <= 4 ? 1 : 2;
        if (levenshteinDistance(label, target) <= maxDist) return true;
        // Word-level matching
        const targetWords = target.split(/\s+/);
        const labelWords = label.split(/\s+/);
        for (const tw of targetWords) {
            if (tw.length < 2) continue;
            for (const lw of labelWords) {
                if (lw.length < 2) continue;
                if (tw === lw) return true;
                const wMax = Math.min(tw.length, lw.length) <= 4 ? 1 : 2;
                if (levenshteinDistance(tw, lw) <= wMax) return true;
            }
        }
        return false;
    }

    function resolveObjectName(transcript) {
        let cleaned = transcript.toLowerCase().trim();
        const prefixes = [
            "search for a ", "search for ", "search ", "find a ", "find my ",
            "find the ", "find ", "where is the ", "where is a ", "where is my ",
            "where is ", "where's the ", "where's a ", "where's my ", "where's ",
            "look for a ", "look for the ", "look for ", "locate a ", "locate the ",
            "locate ", "i need a ", "i need my ", "i need the ", "i need ",
            "show me the ", "show me a ", "show me "
        ];
        for (const p of prefixes) {
            if (cleaned.startsWith(p)) { cleaned = cleaned.slice(p.length).trim(); break; }
        }
        cleaned = cleaned.replace(/\s*(please|now|quickly|fast|nearby)\s*$/i, '').trim();
        if (objectAliases[cleaned]) return objectAliases[cleaned];
        for (const cls of cocoClasses) { if (cleaned === cls) return cls; }
        for (const cls of cocoClasses) {
            if (cleaned.includes(cls) || cls.includes(cleaned)) return cls;
        }
        let bestMatch = null, bestDist = Infinity;
        for (const cls of cocoClasses) {
            const dist = levenshteinDistance(cleaned, cls);
            const maxAllowed = Math.max(cleaned.length, cls.length) <= 4 ? 1 : 2;
            if (dist <= maxAllowed && dist < bestDist) { bestDist = dist; bestMatch = cls; }
        }
        for (const [alias, target] of Object.entries(objectAliases)) {
            const dist = levenshteinDistance(cleaned, alias);
            const maxAllowed = Math.max(cleaned.length, alias.length) <= 4 ? 1 : 2;
            if (dist <= maxAllowed && dist < bestDist) { bestDist = dist; bestMatch = target; }
        }
        return bestMatch || cleaned;
    }

    function playBeep(frequency = 880, duration = 200) {
        try {
            const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            const oscillator = audioCtx.createOscillator();
            const gainNode = audioCtx.createGain();
            oscillator.connect(gainNode);
            gainNode.connect(audioCtx.destination);
            oscillator.frequency.value = frequency;
            oscillator.type = 'sine';
            gainNode.gain.setValueAtTime(0.3, audioCtx.currentTime);
            gainNode.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + duration / 1000);
            oscillator.start(audioCtx.currentTime);
            oscillator.stop(audioCtx.currentTime + duration / 1000);
        } catch (e) { /* ignore beep errors */ }
    }

    // ── Voice Search (Object Finder) ────────────────────
    let backgroundStopListener = null;

    async function toggleVoiceSearch() {
        if (!state.isRunning) return;

        // If already searching, this acts as a manual STOP
        if (state.searchedObject || els.btnFindObject.classList.contains('active')) {
            const stopMsg = state.searchLastFoundInfo
                ? `Stopped. Last seen: ${state.searchLastFoundInfo.label}, ${state.searchLastFoundInfo.distance} ${state.searchLastFoundInfo.position}`
                : "Stopped searching";
            stopVoiceSearch(stopMsg);
            return;
        }

        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SpeechRecognition) {
            const obj = prompt("Voice input not supported. Type what object to find:");
            if (obj && obj.trim()) {
                const resolved = resolveObjectName(obj.trim());
                startObjectSearchLogic(resolved, obj.trim());
            }
            return;
        }

        // 1. Pause pipeline
        stopSendingFrames();
        if (window.speechSynthesis) speechSynthesis.cancel();

        els.btnFindObject.classList.add('active');

        // 2. Prompt user
        showMessage('Listening... Say the object name', 'warning');
        speak("What are you looking for?");

        // 3. Start mic with multiple alternatives for better accuracy
        try {
            const recognition = new SpeechRecognition();
            recognition.lang = 'en-US';
            recognition.interimResults = false;
            recognition.maxAlternatives = 3;

            recognition.onresult = (event) => {
                let bestName = null;
                let rawTranscript = '';

                for (let i = 0; i < event.results[0].length; i++) {
                    const alt = event.results[0][i].transcript.toLowerCase().trim();
                    if (i === 0) rawTranscript = alt;
                    console.log(`[FindObject] Alt ${i}: "${alt}" (conf: ${event.results[0][i].confidence.toFixed(2)})`);

                    if (alt.includes("stop") || alt.includes("cancel")) {
                        stopVoiceSearch("Search cancelled");
                        return;
                    }

                    const resolved = resolveObjectName(alt);
                    if (cocoClasses.includes(resolved) && !bestName) {
                        bestName = resolved;
                    }
                }

                const objectName = bestName || resolveObjectName(rawTranscript);
                console.log(`[FindObject] Resolved: "${rawTranscript}" → "${objectName}"`);
                startObjectSearchLogic(objectName, rawTranscript);
            };

            recognition.onerror = (event) => {
                console.error('Speech error:', event.error);
                if (event.error !== 'aborted') {
                    stopVoiceSearch("Could not hear you. Try again.");
                }
            };

            recognition.onend = () => {
                if (!state.searchedObject && els.btnFindObject.classList.contains('active')) {
                    els.btnFindObject.classList.remove('active');
                    if (state.isRunning) {
                        state.resumeAfter = Date.now() + 1000;
                        startSendingFrames();
                    }
                }
            };

            recognition.start();
        } catch (e) {
            console.error("Speech recognition error:", e);
            stopVoiceSearch("Microphone error");
        }
    }

    function startObjectSearchLogic(objectName, rawTranscript) {
        state.searchedObject = objectName;
        state.lastSearchSpoken = 0;
        state.searchFoundCount = 0;
        state.searchLastFoundInfo = null;
        state.searchLastPosition = null;
        els.btnFindObject.classList.remove('active');
        els.btnFindObject.classList.add('recording');

        // Confirm what was heard so user knows it's correct
        const confirmMsg = (rawTranscript && rawTranscript !== objectName)
            ? `Heard "${rawTranscript}". Searching for ${objectName}`
            : `Searching for ${objectName}`;
        showMessage(confirmMsg, 'warning');
        speakAndWait(confirmMsg).then(() => {
            // 2-minute auto timeout
            state.searchTimeout = setTimeout(() => {
                if (state.searchedObject) {
                    const timeoutMsg = state.searchLastFoundInfo
                        ? `Search timed out. Last seen: ${state.searchLastFoundInfo.label}, ${state.searchLastFoundInfo.distance} ${state.searchLastFoundInfo.position}`
                        : `${objectName} not found. Search timed out.`;
                    stopVoiceSearch(timeoutMsg);
                }
            }, 120000);

            // Background listener for "stop" with interimResults for faster detection
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            if (SpeechRecognition) {
                backgroundStopListener = new SpeechRecognition();
                backgroundStopListener.lang = 'en-US';
                backgroundStopListener.continuous = true;
                backgroundStopListener.interimResults = true; // detect "stop" before utterance ends

                backgroundStopListener.onresult = (e) => {
                    for (let i = e.resultIndex; i < e.results.length; i++) {
                        const transcript = e.results[i][0].transcript.toLowerCase();
                        if (transcript.includes("stop") || transcript.includes("cancel") || transcript.includes("enough")) {
                            const stopMsg = state.searchLastFoundInfo
                                ? `Stopped. ${state.searchLastFoundInfo.label}, ${state.searchLastFoundInfo.distance} ${state.searchLastFoundInfo.position}`
                                : "Stopped searching";
                            stopVoiceSearch(stopMsg);
                            return;
                        }
                    }
                };

                backgroundStopListener.onend = () => {
                    if (state.searchedObject && backgroundStopListener) {
                        try { backgroundStopListener.start(); } catch (err) { }
                    }
                };

                try { backgroundStopListener.start(); } catch (err) { }
            }

            // Resume pipeline in search mode
            if (state.isRunning) {
                state.resumeAfter = Date.now() + 1000;
                startSendingFrames();
            }
        });
    }

    function stopVoiceSearch(reasonMsg) {
        // Immediately clear search state
        state.searchedObject = null;
        state.searchFoundCount = 0;
        state.searchLastPosition = null;

        if (state.searchTimeout) {
            clearTimeout(state.searchTimeout);
            state.searchTimeout = null;
        }

        // Cleanup background listener
        if (backgroundStopListener) {
            backgroundStopListener.onend = null;
            try { backgroundStopListener.stop(); } catch (err) { }
            backgroundStopListener = null;
        }

        els.btnFindObject.classList.remove('active');
        els.btnFindObject.classList.remove('recording');

        // Cancel ALL pending speech immediately
        if (window.speechSynthesis) speechSynthesis.cancel();

        // Play a distinctive low tone to signal search ended
        playBeep(440, 150);

        showMessage(reasonMsg);

        speakAndWait(reasonMsg).then(() => {
            state.searchLastFoundInfo = null;
            if (state.isRunning && !state.sendInterval) {
                state.resumeAfter = Date.now() + 1000;
                startSendingFrames();
            }
        });
    }

    // ── TTS (Text-to-Speech) ────────────────────────────
    function speak(text) {
        if (state.isMuted || !window.speechSynthesis) return;

        const utterance = new SpeechSynthesisUtterance(text);
        utterance.rate = state.settings.speechRate;
        utterance.pitch = 1;
        utterance.volume = 1;

        // Use the first English voice if available
        const voices = speechSynthesis.getVoices();
        const enVoice = voices.find(v => v.lang.startsWith('en'));
        if (enVoice) utterance.voice = enVoice;

        speechSynthesis.speak(utterance);

        // Also update screen reader
        els.srAnnouncements.textContent = text;
    }

    // ── Haptic ──────────────────────────────────────────
    function vibrate() {
        if (navigator.vibrate) {
            navigator.vibrate([100, 50, 100]);
        }
    }

    // ── UI Helpers ──────────────────────────────────────
    function setStatus(type, text) {
        els.statusIndicator.className = 'status-indicator ' + type;
        els.statusText.textContent = text;
    }

    function showAlert(text) {
        els.alertText.textContent = text;
        els.alertBanner.classList.remove('hidden');
    }

    function hideAlert() {
        els.alertBanner.classList.add('hidden');
    }

    function showMessage(text, type = '') {
        const div = document.createElement('div');
        div.className = 'message-item ' + type;
        div.textContent = text;
        els.messageFeed.appendChild(div);

        // Keep max 4 messages
        while (els.messageFeed.children.length > 4) {
            els.messageFeed.removeChild(els.messageFeed.firstChild);
        }

        // Auto-remove after 6s
        setTimeout(() => {
            if (div.parentNode) {
                div.style.transition = 'opacity 0.4s';
                div.style.opacity = '0';
                setTimeout(() => div.remove(), 400);
            }
        }, 6000);
    }

    // ── Toggle Stream ───────────────────────────────────
    async function toggleStream() {
        if (state.isRunning) {
            stopStream();
        } else {
            await startStream();
        }
    }

    async function startStream() {
        const cameraOk = await startCamera();
        if (!cameraOk) return;

        connectWebSocket();
        startSendingFrames();

        state.isRunning = true;
        els.btnToggle.classList.add('recording');
        els.iconPlay.classList.add('hidden');
        els.iconStop.classList.remove('hidden');
    }

    function stopStream() {
        state.isRunning = false;
        stopSendingFrames();
        disconnectWebSocket();
        stopCamera();
        clearCanvas();

        els.btnToggle.classList.remove('recording');
        els.iconPlay.classList.remove('hidden');
        els.iconStop.classList.add('hidden');
        els.btnDescribe.disabled = true;
        els.btnReadSigns.disabled = true;
        els.btnFindObject.disabled = true;
        setStatus('', 'Stopped');
        els.statusFps.textContent = '-- ms';
    }

    function toggleMute() {
        state.isMuted = !state.isMuted;
        const unmutedIcon = els.btnMute.querySelector('.icon-unmuted');
        const mutedIcon = els.btnMute.querySelector('.icon-muted');

        if (state.isMuted) {
            unmutedIcon.classList.add('hidden');
            mutedIcon.classList.remove('hidden');
            els.btnMute.classList.add('active');
            speechSynthesis.cancel();
        } else {
            unmutedIcon.classList.remove('hidden');
            mutedIcon.classList.add('hidden');
            els.btnMute.classList.remove('active');
        }
    }

    // ── Boot ────────────────────────────────────────────
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
