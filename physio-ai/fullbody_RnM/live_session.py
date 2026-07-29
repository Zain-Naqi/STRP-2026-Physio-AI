"""
Web Session Adapters
=====================
Bridges the existing desktop tools (exercise_author.py, follow_exercise.py,
exercise_engine.py, patient_renderer.py) to browser WebSocket connections.

The browser owns the webcam. Each connection gets one session object that:
    1. Receives a JPEG frame (bytes) captured by the browser.
    2. Runs the SAME MediaPipe detection + FSM/recording logic the desktop
       tools use.
    3. Draws the SAME cv2 overlays the desktop tools draw (skeleton,
       countdown, instruction panel, ghost pose, ...) onto that frame.
    4. Encodes the annotated frame back to JPEG/base64 for the <img> tag.

No cv2.VideoCapture, cv2.imshow, or cv2.waitKey is used anywhere here —
those are the desktop-only pieces this module replaces.
"""

import base64
import time

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks.python import vision

from exercise_utils import compute_angles
from exercise_schema import (
    DEFAULT_HOLD_DURATION,
    DEFAULT_TOLERANCE,
    SCHEMA_VERSION,
    load_exercise,
    save_exercise,
)
from exercise_engine import ExerciseFSM
from patient_renderer import PatientRenderer
from exercise_author import (
    AuthorState,
    CAPTURE_INTERVAL,
    COUNTDOWN_DURATION,
    TRIM_END_SECONDS,
    create_state_from_capture,
    draw_angle_values,
    draw_countdown,
    draw_editing_ui,
    draw_pose_skeleton,
    draw_recording_ui,
    extract_points,
    finish_recording,
    pose_changed_enough,
    set_status,
)
from follow_exercise import project_ghost_default, project_ghost_to_patient

MODEL_PATH = "Models/pose_landmarker_lite.task"
SAVE_DIR = "Exercises"

BaseOptions = mp.tasks.BaseOptions
PoseLandmarker = vision.PoseLandmarker
PoseLandmarkerOptions = vision.PoseLandmarkerOptions
VisionRunningMode = vision.RunningMode


class SessionError(Exception):
    """Raised for client-facing errors (invalid names, bad frames, ...)."""


def _create_image_landmarker():
    """
    Build a PoseLandmarker in synchronous IMAGE mode.

    The desktop tools use LIVE_STREAM mode with an async callback because
    they pull frames continuously from cv2.VideoCapture. Over a WebSocket,
    frames arrive one at a time as discrete messages, so IMAGE mode's
    synchronous detect() is the natural (and simpler/race-free) fit.
    """
    options = PoseLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=MODEL_PATH),
        running_mode=VisionRunningMode.IMAGE,
        num_poses=1,
    )
    return PoseLandmarker.create_from_options(options)


def _decode_jpeg(data: bytes):
    array = np.frombuffer(data, dtype=np.uint8)
    if array.size == 0:
        return None
    return cv2.imdecode(array, cv2.IMREAD_COLOR)


def _encode_jpeg(frame) -> str:
    ok, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
    if not ok:
        raise SessionError("Failed to encode output frame.")
    return base64.b64encode(buffer).decode("ascii")


def _detect_pose(landmarker, frame):
    """Run one synchronous detection pass. Returns a landmark list or None."""
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    result = landmarker.detect(mp_image)
    if result and result.pose_landmarks:
        return result.pose_landmarks[0]
    return None


# ─── Recording (Therapist) Session ─────────────────────────────────────

class AuthorSession:
    """
    One browser recording session. Mirrors exercise_author.py's main loop
    and keyboard handlers, minus the OpenCV window and camera capture.
    """

    def __init__(self):
        self.state = AuthorState()
        self.state.recording_start_index = 0
        self.landmarker = _create_image_landmarker()
        self._last_capture_points = None  # (pixel_pts, norm_pts) for manual capture

    def close(self):
        self.landmarker.close()

    # ── Frame handling ──

    def process_frame(self, jpeg_bytes: bytes) -> dict:
        frame = _decode_jpeg(jpeg_bytes)
        if frame is None:
            return self._response(type_="error", error="Could not decode incoming frame.")

        state = self.state
        now = time.time()
        self._advance_countdown(now)

        elapsed = now - state.record_start_time if state.recording else 0
        h, w = frame.shape[:2]

        if state.mode == "recording":
            pose_landmarks = _detect_pose(self.landmarker, frame)

            if pose_landmarks is not None:
                pixel_pts, norm_pts = extract_points(pose_landmarks, w, h)
                self._last_capture_points = (pixel_pts, norm_pts)

                draw_pose_skeleton(frame, pixel_pts)
                draw_angle_values(frame, pixel_pts)

                if state.recording and (now - state.last_capture_time) >= CAPTURE_INTERVAL:
                    angles = compute_angles(pixel_pts)
                    if pose_changed_enough(angles, state.last_angles):
                        new_kf = create_state_from_capture(
                            pixel_pts, norm_pts, elapsed,
                            len(state.keyframes), len(state.keyframes) + 1,
                        )
                        state.keyframes.append(new_kf)
                        state.last_angles = angles
                        state.last_capture_time = now
            else:
                self._last_capture_points = None

            draw_recording_ui(frame, state, elapsed, web_mode=True)
            draw_countdown(frame, state, now)
        else:
            draw_editing_ui(frame, state, web_mode=True)

        return self._response(type_="frame", frame=_encode_jpeg(frame))

    def _advance_countdown(self, now):
        state = self.state
        if state.mode == "recording" and state.countdown_active:
            if now - state.countdown_start_time >= COUNTDOWN_DURATION:
                state.countdown_active = False
                state.recording = True
                state.record_start_time = now
                state.last_capture_time = 0
                state.last_angles = None
                state.recording_start_index = len(state.keyframes)
                set_status(state, "Recording started!")

    # ── Commands (replace keyboard shortcuts) ──

    def handle_command(self, action: str, payload: dict) -> dict:
        state = self.state
        payload = payload or {}

        handlers = {
            "toggle_recording": self._toggle_recording,
            "capture_keyframe": self._capture_keyframe,
            "enter_editing": self._enter_editing,
            "enter_recording": self._enter_recording,
            "previous_keyframe": self._previous_keyframe,
            "next_keyframe": self._next_keyframe,
            "delete_keyframe": self._delete_keyframe,
            "update_keyframe": self._update_keyframe,
            "save_exercise": self._save_exercise,
        }

        handler = handlers.get(action)
        if handler is None:
            return self._response(type_="error", error=f"Unknown action: {action!r}")

        try:
            handler(payload, state)
        except SessionError as exc:
            return self._response(type_="error", error=str(exc))

        return self._response(type_="command")

    def _toggle_recording(self, payload, state):
        if state.mode != "recording":
            raise SessionError("Switch to recording mode before starting/stopping.")

        if state.countdown_active:
            state.countdown_active = False
            set_status(state, "Countdown cancelled.")
        elif state.recording:
            removed = finish_recording(state)
            set_status(
                state,
                f"Stopped — removed {removed} keyframes from the final "
                f"{TRIM_END_SECONDS:.0f} seconds. {len(state.keyframes)} remain.",
            )
        else:
            state.countdown_active = True
            state.countdown_start_time = time.time()
            set_status(state, "Get ready!")

    def _capture_keyframe(self, payload, state):
        if state.mode != "recording":
            raise SessionError("Switch to recording mode to capture a keyframe.")

        if not self._last_capture_points:
            set_status(state, "No pose detected!")
            return

        pixel_pts, norm_pts = self._last_capture_points
        elapsed = time.time() - state.record_start_time if state.recording else 0
        new_kf = create_state_from_capture(
            pixel_pts, norm_pts, elapsed,
            len(state.keyframes), len(state.keyframes) + 1,
        )
        state.keyframes.append(new_kf)
        set_status(state, f"Keyframe {len(state.keyframes)} captured!")

    def _enter_editing(self, payload, state):
        if not state.keyframes:
            raise SessionError("Record keyframes before entering editing mode.")
        state.mode = "editing"
        state.recording = False
        state.countdown_active = False
        state.selected_kf = 0
        set_status(state, "Switched to editing mode.")

    def _enter_recording(self, payload, state):
        state.mode = "recording"
        set_status(state, "Switched to recording mode.")

    def _previous_keyframe(self, payload, state):
        if not state.keyframes:
            return
        state.selected_kf = max(0, state.selected_kf - 1)
        set_status(state, f"Keyframe {state.selected_kf + 1}/{len(state.keyframes)}")

    def _next_keyframe(self, payload, state):
        if not state.keyframes:
            return
        state.selected_kf = min(len(state.keyframes) - 1, state.selected_kf + 1)
        set_status(state, f"Keyframe {state.selected_kf + 1}/{len(state.keyframes)}")

    def _delete_keyframe(self, payload, state):
        if state.mode != "editing" or not state.keyframes:
            raise SessionError("No keyframe to delete.")
        if len(state.keyframes) <= 1:
            set_status(state, "Cannot delete last keyframe.")
            return
        del state.keyframes[state.selected_kf]
        state.selected_kf = min(state.selected_kf, len(state.keyframes) - 1)
        set_status(state, "Keyframe deleted.")

    def _update_keyframe(self, payload, state):
        if state.mode != "editing" or not state.keyframes:
            raise SessionError("No keyframe selected to update.")

        kf = state.keyframes[state.selected_kf]

        instruction = payload.get("instruction")
        if instruction:
            kf["instruction"] = str(instruction)[:200]

        if "hold_duration" in payload:
            try:
                hold_duration = float(payload["hold_duration"])
            except (TypeError, ValueError):
                raise SessionError("Hold duration must be a number.")
            if hold_duration < 0:
                raise SessionError("Hold duration must be zero or positive.")
            kf["hold_duration"] = hold_duration

        if "tolerance" in payload:
            try:
                tolerance = float(payload["tolerance"])
            except (TypeError, ValueError):
                raise SessionError("Tolerance must be a number.")
            if tolerance <= 0:
                raise SessionError("Tolerance must be greater than zero.")
            n = len(kf.get("tolerances", [])) or len(kf.get("angles", [])) or 1
            kf["tolerances"] = [tolerance] * n

        set_status(state, "Keyframe updated.")

    def _save_exercise(self, payload, state):
        if not state.keyframes:
            raise SessionError("Record at least one keyframe before saving.")

        name = _sanitize_exercise_name(payload.get("name"))

        for i, kf in enumerate(state.keyframes):
            kf["id"] = i
            kf["transition_to"] = i + 1 if i < len(state.keyframes) - 1 else None

        from datetime import datetime
        import os

        data = {
            "name": name,
            "version": SCHEMA_VERSION,
            "created_by": "Therapist",
            "created_at": datetime.now().isoformat(),
            "description": f"Exercise recorded on {datetime.now().strftime('%Y-%m-%d')}",
            "num_states": len(state.keyframes),
            "states": state.keyframes,
        }

        os.makedirs(SAVE_DIR, exist_ok=True)
        filepath = os.path.join(SAVE_DIR, f"{name}.json")
        save_exercise(data, filepath)
        set_status(state, f"Saved: {name}")

    # ── Response shape ──

    def _response(self, type_: str, **extra) -> dict:
        state = self.state
        selected = None

        if state.mode == "editing" and state.keyframes:
            kf = state.keyframes[state.selected_kf]
            tolerances = kf.get("tolerances") or [DEFAULT_TOLERANCE]
            selected = {
                "index": state.selected_kf,
                "number": state.selected_kf + 1,
                "instruction": kf.get("instruction", ""),
                "hold_duration": kf.get("hold_duration", DEFAULT_HOLD_DURATION),
                "tolerance": tolerances[0],
            }

        status = ""
        if state.status_message and (time.time() - state.status_time) < 2.5:
            status = state.status_message

        result = {
            "type": type_,
            "mode": state.mode,
            "recording": state.recording,
            "countdown_active": state.countdown_active,
            "keyframe_count": len(state.keyframes),
            "selected_keyframe": selected,
            "status": status,
        }
        result.update(extra)
        return result


# ─── Playback (Patient) Session ────────────────────────────────────────

class PerformSession:
    """
    One browser playback session. Mirrors follow_exercise.py's main loop,
    minus the OpenCV window and camera capture.
    """

    def __init__(self, exercise_name: str, exercises_dir: str = "Exercises"):
        filepath = _safe_exercise_path(exercise_name, exercises_dir)
        self.exercise_data = load_exercise(filepath)
        self.engine = ExerciseFSM(self.exercise_data)
        self.renderer = PatientRenderer(web_mode=True)
        self.landmarker = _create_image_landmarker()

    def close(self):
        self.landmarker.close()

    def restart(self):
        self.engine.reset()

    def process_frame(self, jpeg_bytes: bytes) -> dict:
        frame = _decode_jpeg(jpeg_bytes)
        if frame is None:
            return {"type": "error", "error": "Could not decode incoming frame."}

        h, w = frame.shape[:2]
        frame = cv2.convertScaleAbs(frame, alpha=0.75, beta=10)

        pose_landmarks = _detect_pose(self.landmarker, frame)

        patient_points = None
        patient_angles = None
        if pose_landmarks is not None:
            patient_points = [(int(lm.x * w), int(lm.y * h)) for lm in pose_landmarks]
            patient_angles = compute_angles(patient_points)

        status = self.engine.update(patient_angles)

        ghost_points = None
        current_state = self.engine.current_state
        if current_state and status.phase != "complete":
            if patient_points:
                ghost_points = project_ghost_to_patient(current_state, patient_points, w, h)
            else:
                ghost_points = project_ghost_default(current_state, w, h)

        self.renderer.draw(frame, status, patient_points, ghost_points)

        return {
            "type": "frame",
            "frame": _encode_jpeg(frame),
            "phase": status.phase,
            "current_state_id": status.current_state_id,
            "total_states": status.total_states,
            "instruction": status.instruction,
            "completion_pct": status.completion_pct,
            "match_fraction": status.match_fraction,
            "hold_progress": status.hold_progress,
            "feedback_message": status.feedback_message,
            "correction_message": (
                status.correction.correction_message if status.correction else None
            ),
        }


# ─── Shared Validation Helpers ─────────────────────────────────────────

import re

NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,80}$")


def _sanitize_exercise_name(raw_name) -> str:
    """
    Turn a user-supplied exercise name into a filesystem-safe name.
    Falls back to a timestamped default when blank, matching the
    desktop tool's behaviour.
    """
    from datetime import datetime

    name = (raw_name or "").strip()
    if not name:
        return f"exercise_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    name = re.sub(r"\s+", "_", name)
    name = re.sub(r"[^A-Za-z0-9_-]", "", name)
    name = name[:80]

    if not name:
        raise SessionError("Exercise name must contain letters, numbers, - or _.")

    return name


def _safe_exercise_path(exercise_name: str, exercises_dir: str) -> str:
    """
    Validate an exercise name and resolve it to a path inside
    exercises_dir. Raises SessionError on anything unsafe or missing.
    """
    import os

    if not exercise_name or not NAME_RE.match(exercise_name):
        raise SessionError(f"Invalid exercise name: {exercise_name!r}")

    base_dir = os.path.abspath(exercises_dir)
    filepath = os.path.abspath(os.path.join(base_dir, f"{exercise_name}.json"))

    if os.path.commonpath([base_dir, filepath]) != base_dir:
        raise SessionError("Invalid exercise name.")

    if not os.path.isfile(filepath):
        raise SessionError(f"Exercise '{exercise_name}' not found.")

    return filepath
