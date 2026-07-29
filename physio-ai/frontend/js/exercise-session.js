(() => {
  // ─────────────────────────────────────────────────────────────
  // Python exercise service (FastAPI) — separate from the Node
  // auth backend on port 5000. Run from fullbody_RnM/ with:
  //   uvicorn server:app --reload --port 8000
  // ─────────────────────────────────────────────────────────────

  const PYTHON_SERVICE_HOST = 'localhost:8000';

  // ─────────────────────────────────────────────────────────────
  // Main page elements
  // ─────────────────────────────────────────────────────────────

  const output = document.getElementById('videoStream');
  const placeholder = document.getElementById('cameraPlaceholder');
  const startButton = document.getElementById('startSession');
  const stopButton = document.getElementById('stopSession');
  const badge = document.getElementById('connectionBadge');
  const error = document.getElementById('sessionError');

  // ─────────────────────────────────────────────────────────────
  // Recording-mode controls
  // ─────────────────────────────────────────────────────────────

  const recordingControls = document.getElementById('recordingControls');
  const toggleRecordingButton = document.getElementById('toggleRecording');
  const captureButton = document.getElementById('captureKeyframe');
  const editModeButton = document.getElementById('enterEditing');

  // ─────────────────────────────────────────────────────────────
  // Editing-mode controls
  // ─────────────────────────────────────────────────────────────

  const editingControls = document.getElementById('editingControls');
  const recordModeButton = document.getElementById('enterRecording');
  const previousButton = document.getElementById('previousKeyframe');
  const nextButton = document.getElementById('nextKeyframe');
  const deleteButton = document.getElementById('deleteKeyframe');
  const applyButton = document.getElementById('applyKeyframe');

  // ─────────────────────────────────────────────────────────────
  // Save controls
  // ─────────────────────────────────────────────────────────────

  const saveButton = document.getElementById('saveExercise');
  const exerciseNameInput = document.getElementById('saveExerciseName');

  // ─────────────────────────────────────────────────────────────
  // Keyframe editing inputs
  // ─────────────────────────────────────────────────────────────

  const instructionInput = document.getElementById('keyframeInstruction');
  const holdInput = document.getElementById('keyframeHold');
  const toleranceInput = document.getElementById('keyframeTolerance');

  // ─────────────────────────────────────────────────────────────
  // Status elements
  // ─────────────────────────────────────────────────────────────

  const keyframeLabel = document.getElementById('keyframeLabel');
  const keyframeCount = document.getElementById('keyframeCount');
  const authorStatus = document.getElementById('authorStatus');

  // ─────────────────────────────────────────────────────────────
  // Hidden video and canvas.
  //
  // The browser camera stream is placed inside the hidden video.
  // Each frame is drawn onto the canvas and sent to Python.
  // ─────────────────────────────────────────────────────────────

  const camera = document.createElement('video');
  const canvas = document.createElement('canvas');
  const context = canvas.getContext('2d');

  camera.autoplay = true;
  camera.muted = true;
  camera.playsInline = true;

  // ─────────────────────────────────────────────────────────────
  // Session state
  // ─────────────────────────────────────────────────────────────

  let socket = null;
  let mediaStream = null;
  let captureTimer = null;

  // Prevents sending several frames while Python is still processing
  // the previous one.
  let awaitingFrame = false;

  // ─────────────────────────────────────────────────────────────
  // Helpers
  // ─────────────────────────────────────────────────────────────

  function setError(message = '') {
    if (error) {
      error.textContent = message;
    }
  }

  function setStatus(message = '') {
    if (authorStatus) {
      authorStatus.textContent = message;
    }
  }

  function sendCommand(action, values = {}) {
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      setError('Start the camera before using the authoring controls.');
      return;
    }

    socket.send(JSON.stringify({ action, ...values }));
  }

  function updateAuthoringUI(result) {
    const isEditing = result.mode === 'editing';
    const count = result.keyframe_count ?? 0;
    const selected = result.selected_keyframe;

    if (recordingControls) {
      recordingControls.hidden = isEditing;
    }

    if (editingControls) {
      editingControls.hidden = !isEditing;
    }

    if (keyframeCount) {
      keyframeCount.textContent = `${count} keyframe${count === 1 ? '' : 's'}`;
    }

    if (authorStatus && result.status) {
      authorStatus.textContent = result.status;
    }

    if (toggleRecordingButton) {
      if (result.countdown_active) {
        toggleRecordingButton.textContent = 'Cancel countdown';
      } else if (result.recording) {
        toggleRecordingButton.textContent = 'Stop recording';
      } else {
        toggleRecordingButton.textContent = 'Start recording';
      }
    }

    if (selected) {
      if (keyframeLabel) {
        keyframeLabel.textContent = `Keyframe ${selected.number} of ${count}`;
      }

      if (instructionInput && document.activeElement !== instructionInput) {
        instructionInput.value = selected.instruction ?? '';
      }

      if (holdInput && document.activeElement !== holdInput) {
        holdInput.value = selected.hold_duration ?? 2;
      }

      if (toleranceInput && document.activeElement !== toleranceInput) {
        toleranceInput.value = selected.tolerance ?? 20;
      }
    } else if (keyframeLabel) {
      keyframeLabel.textContent = 'No keyframe selected';
    }

    if (previousButton) {
      previousButton.disabled = !selected || selected.index <= 0;
    }

    if (nextButton) {
      nextButton.disabled = !selected || selected.index >= count - 1;
    }

    if (deleteButton) {
      deleteButton.disabled = count <= 1;
    }

    if (editModeButton) {
      editModeButton.disabled = count === 0;
    }
  }

  function disableAuthoringControls() {
    [toggleRecordingButton, captureButton, editModeButton, saveButton,
      recordModeButton, previousButton, nextButton, deleteButton, applyButton]
      .forEach(btn => { if (btn) btn.disabled = true; });
  }

  function enableAuthoringControls() {
    [toggleRecordingButton, captureButton, saveButton, recordModeButton, applyButton]
      .forEach(btn => { if (btn) btn.disabled = false; });
  }

  function stopSession(message = 'Session stopped') {
    if (captureTimer) {
      clearInterval(captureTimer);
      captureTimer = null;
    }

    if (socket) {
      // Remove onclose before closing it ourselves, otherwise
      // stopSession could be triggered twice.
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

    if (output) {
      output.classList.remove('active');
    }

    if (placeholder) {
      placeholder.hidden = false;
    }

    if (badge) {
      badge.textContent = message;
      badge.classList.remove('live');
    }

    if (startButton) {
      startButton.disabled = false;
    }

    if (stopButton) {
      stopButton.disabled = true;
    }

    disableAuthoringControls();
  }

  // ─────────────────────────────────────────────────────────────
  // Frame capture
  // ─────────────────────────────────────────────────────────────

  function sendFrame() {
    if (
      !socket ||
      socket.readyState !== WebSocket.OPEN ||
      awaitingFrame ||
      camera.readyState < HTMLMediaElement.HAVE_CURRENT_DATA
    ) {
      return;
    }

    // Mirror the frame so the browser view behaves like a normal mirror:
    // the patient's/therapist's physical right side appears on the right.
    context.save();
    context.translate(canvas.width, 0);
    context.scale(-1, 1);
    context.drawImage(camera, 0, 0, canvas.width, canvas.height);
    context.restore();

    canvas.toBlob(
      blob => {
        if (!blob || !socket || socket.readyState !== WebSocket.OPEN) {
          return;
        }

        awaitingFrame = true;
        socket.send(blob);
      },
      'image/jpeg',
      0.8
    );
  }

  // ─────────────────────────────────────────────────────────────
  // Start camera and connect to Python
  // ─────────────────────────────────────────────────────────────

  startButton?.addEventListener('click', async () => {
    setError();
    setStatus('');

    startButton.disabled = true;

    if (badge) {
      badge.textContent = 'Requesting camera…';
    }

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

      // The browser camera may return a different size from the
      // requested resolution — the outgoing frame is resized to
      // 640px wide to keep WebSocket messages small.
      canvas.width = 640;
      canvas.height = Math.round(640 * camera.videoHeight / camera.videoWidth) || 480;

      socket = new WebSocket(`ws://${PYTHON_SERVICE_HOST}/ws/exercise-author`);

      if (badge) {
        badge.textContent = 'Connecting…';
      }

      socket.onopen = () => {
        if (badge) {
          badge.textContent = 'Authoring live';
          badge.classList.add('live');
        }

        if (stopButton) {
          stopButton.disabled = false;
        }

        enableAuthoringControls();

        // Try sending a frame every 80ms. awaitingFrame ensures another
        // frame is not sent until Python replies.
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
        }

        if (result.type === 'error') {
          console.error('Python error:', result.error);
          setError(result.error || 'The exercise engine returned an error.');
        } else {
          setError('');
        }

        updateAuthoringUI(result);
      };

      socket.onerror = event => {
        console.error('WebSocket error:', event);
        setError('Could not connect to the exercise authoring service. Is the Python server running on port 8000?');
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

  // ─────────────────────────────────────────────────────────────
  // Recording-mode buttons
  // ─────────────────────────────────────────────────────────────

  toggleRecordingButton?.addEventListener('click', event => {
    event.preventDefault();
    sendCommand('toggle_recording');
  });

  captureButton?.addEventListener('click', () => sendCommand('capture_keyframe'));
  editModeButton?.addEventListener('click', () => sendCommand('enter_editing'));

  // ─────────────────────────────────────────────────────────────
  // Editing-mode buttons
  // ─────────────────────────────────────────────────────────────

  recordModeButton?.addEventListener('click', () => sendCommand('enter_recording'));
  previousButton?.addEventListener('click', () => sendCommand('previous_keyframe'));
  nextButton?.addEventListener('click', () => sendCommand('next_keyframe'));
  deleteButton?.addEventListener('click', () => sendCommand('delete_keyframe'));

  applyButton?.addEventListener('click', () => {
    const holdDuration = Number(holdInput?.value);
    const tolerance = Number(toleranceInput?.value);

    if (!Number.isFinite(holdDuration) || holdDuration < 0) {
      setError('Hold duration must be a valid positive number.');
      return;
    }

    if (!Number.isFinite(tolerance) || tolerance <= 0) {
      setError('Tolerance must be greater than zero.');
      return;
    }

    sendCommand('update_keyframe', {
      instruction: instructionInput?.value.trim() || '',
      hold_duration: holdDuration,
      tolerance
    });
  });

  // ─────────────────────────────────────────────────────────────
  // Save button
  // ─────────────────────────────────────────────────────────────

  saveButton?.addEventListener('click', () => {
    const exerciseName = exerciseNameInput?.value.trim() || '';
    sendCommand('save_exercise', { name: exerciseName });
  });

  // ─────────────────────────────────────────────────────────────
  // Stop and page cleanup
  // ─────────────────────────────────────────────────────────────

  stopButton?.addEventListener('click', () => stopSession());
  window.addEventListener('beforeunload', () => stopSession());
  window.addEventListener('pagehide', () => stopSession());

  // Authoring controls should start disabled.
  disableAuthoringControls();
})();
