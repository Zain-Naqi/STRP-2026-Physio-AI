(() => {
  // ─────────────────────────────────────────────────────────────
  // Python exercise service (FastAPI) — separate from the Node
  // auth backend on port 5000. Run from fullbody_RnM/ with:
  //   uvicorn server:app --reload --port 8000
  // ─────────────────────────────────────────────────────────────

  const PYTHON_SERVICE_HOST = 'localhost:8000';

  const params = new URLSearchParams(window.location.search);
  const exerciseName = params.get('exercise');

  // ─────────────────────────────────────────────────────────────
  // Elements
  // ─────────────────────────────────────────────────────────────

  const output = document.getElementById('videoStream');
  const placeholder = document.getElementById('cameraPlaceholder');
  const startButton = document.getElementById('startSession');
  const stopButton = document.getElementById('stopSession');
  const restartButton = document.getElementById('restartExercise');
  const badge = document.getElementById('connectionBadge');
  const error = document.getElementById('sessionError');

  const nameHeading = document.getElementById('exerciseName');
  const descriptionEl = document.getElementById('exerciseDescription');
  const stepLabel = document.getElementById('stepLabel');
  const instructionText = document.getElementById('instructionText');
  const correctionText = document.getElementById('correctionText');
  const progressPct = document.getElementById('progressPct');
  const progressFill = document.getElementById('progressFill');
  const holdPct = document.getElementById('holdPct');
  const holdFill = document.getElementById('holdFill');

  const camera = document.createElement('video');
  const canvas = document.createElement('canvas');
  const context = canvas.getContext('2d');

  camera.autoplay = true;
  camera.muted = true;
  camera.playsInline = true;

  let socket = null;
  let mediaStream = null;
  let captureTimer = null;
  let awaitingFrame = false;

  function setError(message = '') {
    if (error) error.textContent = message;
  }

  if (!exerciseName) {
    setError('No exercise was selected. Go back to the exercise library and choose one.');
    if (startButton) startButton.disabled = true;
  }

  // ─────────────────────────────────────────────────────────────
  // Load exercise metadata for the header (name/description)
  // ─────────────────────────────────────────────────────────────

  async function loadExerciseMeta() {
    if (!exerciseName) return;

    try {
      const response = await fetch(`http://${PYTHON_SERVICE_HOST}/api/exercises/${encodeURIComponent(exerciseName)}`);
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Could not load exercise.');
      }

      if (nameHeading) nameHeading.textContent = data.name;
      if (descriptionEl) descriptionEl.textContent = data.description || 'Follow the on-screen guide and hold each position.';
      if (stepLabel) stepLabel.textContent = `Step 0 of ${data.num_states ?? 0}`;
    } catch (reason) {
      console.error('Failed to load exercise metadata:', reason);
      setError(`Could not load exercise "${exerciseName}": ${reason.message}`);
      if (startButton) startButton.disabled = true;
    }
  }

  loadExerciseMeta();

  // ─────────────────────────────────────────────────────────────
  // Rendering live status
  // ─────────────────────────────────────────────────────────────

  function updatePerformanceUI(result) {
    if (stepLabel) {
      stepLabel.textContent = `Step ${(result.current_state_id ?? 0) + 1} of ${result.total_states ?? 0}`;
    }

    if (instructionText) {
      instructionText.textContent = result.feedback_message || result.instruction || '';
    }

    if (correctionText) {
      correctionText.textContent = result.phase === 'correcting' ? (result.correction_message || '') : '';
    }

    const pct = Math.round((result.completion_pct ?? 0) * 100);
    if (progressPct) progressPct.textContent = `${pct}%`;
    if (progressFill) progressFill.style.width = `${pct}%`;

    const holdProgress = Math.round((result.hold_progress ?? 0) * 100);
    if (holdPct) holdPct.textContent = `${holdProgress}%`;
    if (holdFill) holdFill.style.width = `${holdProgress}%`;

    if (result.phase === 'complete') {
      if (instructionText) instructionText.textContent = 'Exercise complete! Great work.';
      if (restartButton) restartButton.hidden = false;
    } else if (restartButton) {
      restartButton.hidden = true;
    }
  }

  // ─────────────────────────────────────────────────────────────
  // Session lifecycle
  // ─────────────────────────────────────────────────────────────

  function stopSession(message = 'Session stopped') {
    if (captureTimer) {
      clearInterval(captureTimer);
      captureTimer = null;
    }

    if (socket) {
      socket.onclose = null;
      if (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING) {
        socket.close();
      }
      socket = null;
    }

    if (mediaStream) {
      mediaStream.getTracks().forEach(track => track.stop());
      mediaStream = null;
    }

    camera.pause();
    camera.srcObject = null;
    awaitingFrame = false;

    if (output) output.classList.remove('active');
    if (placeholder) placeholder.hidden = false;

    if (badge) {
      badge.textContent = message;
      badge.classList.remove('live');
    }

    if (startButton) startButton.disabled = !exerciseName;
    if (stopButton) stopButton.disabled = true;
  }

  function sendFrame() {
    if (
      !socket ||
      socket.readyState !== WebSocket.OPEN ||
      awaitingFrame ||
      camera.readyState < HTMLMediaElement.HAVE_CURRENT_DATA
    ) {
      return;
    }

    // Mirror the frame so the patient sees a normal mirror image.
    context.save();
    context.translate(canvas.width, 0);
    context.scale(-1, 1);
    context.drawImage(camera, 0, 0, canvas.width, canvas.height);
    context.restore();

    canvas.toBlob(
      blob => {
        if (!blob || !socket || socket.readyState !== WebSocket.OPEN) return;
        awaitingFrame = true;
        socket.send(blob);
      },
      'image/jpeg',
      0.8
    );
  }

  startButton?.addEventListener('click', async () => {
    if (!exerciseName) return;

    setError();
    startButton.disabled = true;

    if (badge) badge.textContent = 'Requesting camera…';

    if (!navigator.mediaDevices?.getUserMedia) {
      setError('Camera access requires localhost or HTTPS.');
      stopSession('Camera unavailable');
      return;
    }

    try {
      mediaStream = await navigator.mediaDevices.getUserMedia({
        video: {
          width: { ideal: 960 },
          height: { ideal: 720 },
          facingMode: 'user'
        },
        audio: false
      });

      camera.srcObject = mediaStream;
      await camera.play();

      canvas.width = 640;
      canvas.height = Math.round(640 * camera.videoHeight / camera.videoWidth) || 480;

      socket = new WebSocket(`ws://${PYTHON_SERVICE_HOST}/ws/perform/${encodeURIComponent(exerciseName)}`);

      if (badge) badge.textContent = 'Connecting…';

      socket.onopen = () => {
        if (badge) {
          badge.textContent = 'Session live';
          badge.classList.add('live');
        }

        if (stopButton) stopButton.disabled = false;

        captureTimer = setInterval(sendFrame, 80);
      };

      socket.onmessage = event => {
        let result;

        try {
          result = JSON.parse(event.data);
        } catch (parseError) {
          console.error('Invalid server response:', event.data);
          setError('The server returned invalid JSON.');
          awaitingFrame = false;
          return;
        }

        if (result.type === 'frame') {
          awaitingFrame = false;

          if (result.frame) {
            output.src = `data:image/jpeg;base64,${result.frame}`;
            output.classList.add('active');
            if (placeholder) placeholder.hidden = true;
          }

          updatePerformanceUI(result);
        }

        if (result.type === 'error') {
          console.error('Python error:', result.error);
          setError(result.error || 'The exercise engine returned an error.');
          stopSession('Error');
        } else {
          setError('');
        }
      };

      socket.onerror = event => {
        console.error('WebSocket error:', event);
        setError('Could not connect to the exercise service. Is the Python server running on port 8000?');
      };

      socket.onclose = event => {
        console.log('WebSocket closed:', event.code, event.reason);
        stopSession('Disconnected');
      };
    } catch (reason) {
      console.error('Camera start error:', reason);

      const denied = reason?.name === 'NotAllowedError';

      setError(
        denied
          ? 'Camera permission was denied. Allow camera access and try again.'
          : `Could not start the camera: ${reason?.message || 'unknown error'}`
      );

      stopSession('Camera unavailable');
    }
  });

  restartButton?.addEventListener('click', () => {
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ action: 'restart' }));
      restartButton.hidden = true;
    }
  });

  stopButton?.addEventListener('click', () => stopSession());
  window.addEventListener('beforeunload', () => stopSession());
  window.addEventListener('pagehide', () => stopSession());
})();
