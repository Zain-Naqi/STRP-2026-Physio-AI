"""
Exercise Authoring Tool
========================
Therapist-facing tool for creating and editing exercises as FSM state sequences.

Two modes:
    RECORDING   — Capture pose landmarks from camera (auto or manual keyframes)
    EDITING     — Review, annotate, and configure each keyframe

Output: v2 exercise JSON with clinical metadata (tolerances, hold times,
        priority joints, instructions, transition rules).

Usage:
    python exercise_author.py

Controls (Recording Mode):
    R         — Start / stop recording
    SPACE     — Manually capture a keyframe
    E         — Switch to editing mode
    Q         — Quit

Controls (Editing Mode):
    LEFT/RIGHT — Navigate between keyframes
    I          — Set instruction text for current keyframe
    H          — Set hold duration (seconds)
    D          — Delete current keyframe
    T          — Set tolerance (global for this keyframe)
    S          — Save exercise
    R          — Switch back to recording mode
    Q          — Quit
"""

import cv2
import mediapipe as mp
import time
import math
import json
import os
import sys
from datetime import datetime
from mediapipe.tasks.python import vision

from exercise_utils import (
    HAND_CONNECTIONS, ANGLE_JOINTS,
    calculate_angle, compute_angles, normalize_pose
)
from exercise_schema import (
    SCHEMA_VERSION, JOINT_LABELS, JOINT_TO_LANDMARK,
    DEFAULT_TOLERANCE, DEFAULT_HOLD_DURATION, DEFAULT_MATCH_THRESHOLD,
    save_exercise,
)


# ─── Config ────────────────────────────────────────────────────────────

MODEL_PATH = "Models/pose_landmarker_lite.task"
SAVE_DIR = "Exercises"
CAPTURE_INTERVAL = 0.33        # seconds between auto-keyframes (~3 FPS)
MIN_ANGLE_CHANGE = 5.0         # min degrees change for auto-capture
COUNTDOWN_DURATION = 5  # seconds for countdown before recording
TRIM_END_SECONDS = 2  # seconds to trim from start/end of exercise

# Colors (BGR)
COLOR_SKELETON    = (255, 200, 0)
COLOR_LANDMARK    = (0, 255, 0)
COLOR_HIGHLIGHT   = (0, 200, 255)
COLOR_BG_DARK     = (20, 20, 20)
COLOR_BG_PANEL    = (30, 30, 35)
COLOR_TEXT         = (255, 255, 255)
COLOR_TEXT_DIM     = (150, 150, 150)
COLOR_ACCENT      = (0, 215, 255)  # Amber
COLOR_REC         = (0, 0, 255)    # Red
COLOR_SUCCESS     = (0, 220, 100)
COLOR_SELECTED    = (255, 180, 50)


# ─── MediaPipe Setup ───────────────────────────────────────────────────

BaseOptions = mp.tasks.BaseOptions
PoseLandmarker = vision.PoseLandmarker
PoseLandmarkerOptions = vision.PoseLandmarkerOptions
VisionRunningMode = vision.RunningMode

latest_result = None

def on_result(result, output_image, timestamp_ms):
    global latest_result
    latest_result = result

mp_options = PoseLandmarkerOptions(
    base_options=BaseOptions(model_asset_path=MODEL_PATH),
    running_mode=VisionRunningMode.LIVE_STREAM,
    num_poses=1,
    result_callback=on_result
)


# ─── State ─────────────────────────────────────────────────────────────

class AuthorState:
    """Mutable authoring state."""
    def __init__(self):
        self.mode = "recording"   # "recording" or "editing"
        self.recording = False
        self.keyframes = []       # List of v2 state dicts
        self.last_capture_time = 0
        self.last_angles = None
        self.record_start_time = 0
        self.selected_kf = 0      # Currently selected keyframe in edit mode
        self.status_message = ""
        self.status_time = 0
        self.countdown_active = False
        self.countdown_start_time = 0
        self.record_start_time = 0


# ─── Helpers ───────────────────────────────────────────────────────────

def pose_changed_enough(new_angles, old_angles):
    """Check if pose changed significantly from last keyframe."""
    if old_angles is None:
        return True
    max_diff = max(abs(n - o) for n, o in zip(new_angles, old_angles))
    return max_diff > MIN_ANGLE_CHANGE


def extract_points(pose_landmarks, w, h):
    """Convert MediaPipe landmarks to pixel and normalized lists."""
    pixel_pts = []
    norm_pts = []
    for lm in pose_landmarks:
        pixel_pts.append((int(lm.x * w), int(lm.y * h)))
        norm_pts.append((lm.x, lm.y))
    return pixel_pts, norm_pts


def create_state_from_capture(pixel_pts, norm_pts, elapsed, state_id, total):
    """Create a v2 state dict from captured pose data."""
    angles = compute_angles(pixel_pts)
    relative, scale = normalize_pose(norm_pts)
    num_angles = len(angles)

    return {
        "id": state_id,
        "instruction": f"Move to position {state_id + 1}.",
        "hold_duration": DEFAULT_HOLD_DURATION,
        "landmarks": norm_pts,
        "landmarks_relative": relative,
        "pose_scale": scale,
        "angles": angles,
        "tolerances": [DEFAULT_TOLERANCE] * num_angles,
        "priority_joints": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],  # All joints by default
        "priority_labels": {
            str(j): JOINT_LABELS.get(j, f"joint {j}")
            for j in range(num_angles)
        },
        "transition_to": state_id + 1,
        "entry_match_threshold": DEFAULT_MATCH_THRESHOLD,
        "capture_time": round(elapsed, 3),
    }


def set_status(state, msg):
    """Set a temporary status message."""
    state.status_message = msg
    state.status_time = time.time()


def finish_recording(state):
    """
    Stop recording and remove keyframes captured during the final
    TRIM_END_SECONDS seconds of the current recording.
    """
    if not state.recording:
        return 0

    recording_duration = time.time() - state.record_start_time
    cutoff_time = max(
        0.0,
        recording_duration - TRIM_END_SECONDS
    )

    # Only inspect keyframes from the current recording
    previous_keyframes = state.keyframes[
        :state.recording_start_index
    ]

    current_recording = state.keyframes[
        state.recording_start_index:
    ]

    kept_keyframes = [
        keyframe
        for keyframe in current_recording
        if keyframe.get("capture_time", 0) <= cutoff_time
    ]

    removed_count = (
        len(current_recording) - len(kept_keyframes)
    )

    state.keyframes = previous_keyframes + kept_keyframes
    state.recording = False
    state.last_angles = None
    state.last_capture_time = 0

    return removed_count

# ─── Drawing (Recording Mode) ─────────────────────────────────────────

def draw_pose_skeleton(frame, points):
    """Draw full pose skeleton — therapist sees all landmarks."""
    for start, end in HAND_CONNECTIONS:
        cv2.line(frame, points[start], points[end], COLOR_SKELETON, 2, cv2.LINE_AA)
    for i, pt in enumerate(points):
        cv2.circle(frame, pt, 5, COLOR_LANDMARK, -1, cv2.LINE_AA)
        cv2.circle(frame, pt, 5, (255, 255, 255), 1, cv2.LINE_AA)


def draw_angle_values(frame, points):
    """Draw angle values at each joint — useful for therapist."""
    for p1, p2, p3 in ANGLE_JOINTS:
        angle = calculate_angle(points[p1], points[p2], points[p3])
        x, y = points[p2]
        cv2.putText(frame, f"{int(angle)}", (x + 5, y - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 255, 255), 1, cv2.LINE_AA)

def draw_countdown(frame, state, now):
    """Display the get-ready countdown before recording starts."""
    if not state.countdown_active:
        return

    elapsed = now - state.countdown_start_time
    remaining = max(
        1,
        math.ceil(COUNTDOWN_DURATION - elapsed)
    )

    h, w = frame.shape[:2]

    # Dark transparent background
    overlay = frame.copy()
    cv2.rectangle(
        overlay,
        (0, 0),
        (w, h),
        (0, 0, 0),
        -1
    )
    cv2.addWeighted(
        overlay,
        0.45,
        frame,
        0.55,
        0,
        frame
    )

    message = "GET IN POSITION"
    number = str(remaining)

    (message_w, _), _ = cv2.getTextSize(
        message,
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        2
    )

    (number_w, _), _ = cv2.getTextSize(
        number,
        cv2.FONT_HERSHEY_SIMPLEX,
        4.0,
        8
    )

    cv2.putText(
        frame,
        message,
        ((w - message_w) // 2, h // 2 - 70),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        COLOR_TEXT,
        2,
        cv2.LINE_AA
    )

    cv2.putText(
        frame,
        number,
        ((w - number_w) // 2, h // 2 + 70),
        cv2.FONT_HERSHEY_SIMPLEX,
        4.0,
        COLOR_ACCENT,
        8,
        cv2.LINE_AA
    )


def draw_recording_ui(frame, state, elapsed, web_mode=False):
    """
    Draw recording mode UI.

    web_mode=True suppresses chrome that only makes sense for the desktop
    OpenCV window — the title bar, keyboard-shortcut hints, and the status
    message flash — because the browser page already shows the mode,
    keyframe count, and status text in its own UI. The desktop tool keeps
    calling this with web_mode=False (the default) and is unaffected.
    """
    h, w = frame.shape[:2]

    if not web_mode:
        # ── Title Bar ──
        cv2.rectangle(frame, (0, 0), (w, 50), COLOR_BG_DARK, -1)
        cv2.putText(frame, "EXERCISE AUTHOR", (15, 22),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, COLOR_ACCENT, 2, cv2.LINE_AA)
        cv2.putText(frame, "Recording Mode", (15, 42),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, COLOR_TEXT_DIM, 1, cv2.LINE_AA)

    # ── Recording Status ──
    if state.recording:
        if int(time.time() * 3) % 2 == 0:
            cv2.circle(frame, (w - 25, 25), 8, COLOR_REC, -1)
        label = (f"REC  {elapsed:.1f}s" if web_mode
                 else f"REC  {elapsed:.1f}s  [{len(state.keyframes)} keyframes]")
        cv2.putText(frame, label, (w - (190 if web_mode else 280), 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, COLOR_REC, 1, cv2.LINE_AA)
    elif not web_mode:
        status = (f"{len(state.keyframes)} keyframes" if state.keyframes
                  else "Ready — press [R] to record")
        cv2.putText(frame, status, (w - 320, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, COLOR_TEXT_DIM, 1, cv2.LINE_AA)

    # ── Keyframe Timeline ──
    # Kept in both modes: it shows *when* each keyframe was captured, which
    # isn't represented anywhere in the browser page's simple count.
    if state.keyframes:
        timeline_y = h - 60
        cv2.rectangle(frame, (0, timeline_y - 5), (w, timeline_y + 30), COLOR_BG_DARK, -1)
        cv2.putText(frame, "KEYFRAMES:", (10, timeline_y + 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, COLOR_TEXT_DIM, 1)

        for i, kf in enumerate(state.keyframes):
            x = 120 + i * 25
            if x > w - 30:
                break
            cv2.rectangle(frame, (x, timeline_y), (x + 18, timeline_y + 18),
                          COLOR_SUCCESS, -1)
            cv2.putText(frame, str(i + 1), (x + 3, timeline_y + 14),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.35, COLOR_BG_DARK, 1)

    if not web_mode:
        # ── Controls Bar ──
        cv2.rectangle(frame, (0, h - 30), (w, h), COLOR_BG_DARK, -1)
        controls = "[R] Record   [SPACE] Manual Capture   [E] Edit Mode   [Q] Quit"
        cv2.putText(frame, controls, (10, h - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, COLOR_TEXT_DIM, 1, cv2.LINE_AA)

        # ── Status Message ──
        if state.status_message and (time.time() - state.status_time) < 2.0:
            msg = state.status_message
            (tw, _), _ = cv2.getTextSize(msg, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            cv2.putText(frame, msg, ((w - tw) // 2, h // 2),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, COLOR_SUCCESS, 2, cv2.LINE_AA)


# ─── Drawing (Editing Mode) ───────────────────────────────────────────

def draw_editing_ui(frame, state, web_mode=False):
    """
    Draw editing mode UI with keyframe properties.

    web_mode=True suppresses the title bar, the properties panel (already
    shown as editable fields in the browser sidebar), and the keyboard
    hints/status flash, keeping only the ghost pose preview and keyframe
    thumbnail strip — the parts that are genuinely visual overlays rather
    than duplicated text. The desktop tool is unaffected (web_mode=False).
    """
    h, w = frame.shape[:2]

    if not state.keyframes:
        cv2.putText(frame, "No keyframes to edit. Switch to recording mode.",
                    (40, h // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.6, COLOR_TEXT, 1)
        return

    kf = state.keyframes[state.selected_kf]

    if not web_mode:
        # ── Title Bar ──
        cv2.rectangle(frame, (0, 0), (w, 50), COLOR_BG_DARK, -1)
        cv2.putText(frame, "EXERCISE AUTHOR", (15, 22),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, COLOR_ACCENT, 2, cv2.LINE_AA)
        cv2.putText(frame, f"Editing Mode — Keyframe {state.selected_kf + 1} / {len(state.keyframes)}",
                    (15, 42), cv2.FONT_HERSHEY_SIMPLEX, 0.4, COLOR_TEXT_DIM, 1, cv2.LINE_AA)

    # ── Ghost Preview of Selected Keyframe ──
    landmarks = kf.get("landmarks", [])
    if landmarks:
        preview_pts = []
        for lm in landmarks:
            px = int(lm[0] * w)
            py = int(lm[1] * h)
            preview_pts.append((px, py))

        # Draw ghost
        overlay = frame.copy()
        for start, end in HAND_CONNECTIONS:
            if start < len(preview_pts) and end < len(preview_pts):
                cv2.line(overlay, preview_pts[start], preview_pts[end],
                         COLOR_SELECTED, 2, cv2.LINE_AA)
        cv2.addWeighted(overlay, 0.5, frame, 0.5, 0, frame)

        for pt in preview_pts:
            cv2.circle(frame, pt, 4, COLOR_SELECTED, -1, cv2.LINE_AA)

    # ── Properties Panel (Right Side) ──
    # Desktop-only: the browser sidebar already has editable instruction/
    # hold/tolerance fields for the selected keyframe, so this duplicate
    # read-only panel is skipped in web_mode.
    panel_w = 0 if web_mode else 290
    panel_x = w - (300 if not web_mode else 0)

    if not web_mode:
        cv2.rectangle(frame, (panel_x, 55), (panel_x + panel_w, h - 35),
                      COLOR_BG_PANEL, -1)
        cv2.rectangle(frame, (panel_x, 55), (panel_x + panel_w, h - 35),
                      COLOR_ACCENT, 1)

        y = 80
        props = [
            ("Instruction:", kf.get("instruction", "—")),
            ("Hold Duration:", f"{kf.get('hold_duration', 2.0):.1f}s"),
            ("Tolerance:", f"{kf.get('tolerances', [20])[0]:.0f}°"),
            ("Priority Joints:", f"{len(kf.get('priority_joints', []))} joints"),
            ("Match Threshold:", f"{kf.get('entry_match_threshold', 0.75)*100:.0f}%"),
            ("Transition To:", str(kf.get('transition_to', 'End'))),
        ]

        for label, value in props:
            cv2.putText(frame, label, (panel_x + 10, y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, COLOR_ACCENT, 1, cv2.LINE_AA)
            y += 18
            # Wrap long text
            display_val = value[:35] + "..." if len(value) > 35 else value
            cv2.putText(frame, display_val, (panel_x + 15, y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, COLOR_TEXT, 1, cv2.LINE_AA)
            y += 25

    # ── Keyframe Thumbnails (Bottom) ──
    # Kept in both modes: a compact visual index of every keyframe with the
    # current selection highlighted isn't something the browser sidebar
    # (which only shows "Keyframe X of Y" as text) represents on its own.
    thumb_y = h - 80
    cv2.rectangle(frame, (0, thumb_y - 5), (w, h - 30), COLOR_BG_DARK, -1)

    thumb_limit = (w - 40) if web_mode else (panel_x - 40)
    for i in range(len(state.keyframes)):
        x = 15 + i * 35
        if x > thumb_limit:
            break

        is_selected = (i == state.selected_kf)
        color = COLOR_SELECTED if is_selected else COLOR_TEXT_DIM
        thickness = 2 if is_selected else 1

        cv2.rectangle(frame, (x, thumb_y), (x + 28, thumb_y + 25), color, thickness)
        cv2.putText(frame, str(i + 1), (x + 6, thumb_y + 18),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)

    if not web_mode:
        # ── Controls ──
        cv2.rectangle(frame, (0, h - 30), (w, h), COLOR_BG_DARK, -1)
        controls = "[←→] Navigate  [I] Instruction  [H] Hold  [T] Tolerance  [D] Delete  [S] Save  [R] Record  [Q] Quit"
        cv2.putText(frame, controls, (10, h - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.32, COLOR_TEXT_DIM, 1, cv2.LINE_AA)

        # ── Status ──
        if state.status_message and (time.time() - state.status_time) < 2.0:
            msg = state.status_message
            (tw, _), _ = cv2.getTextSize(msg, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            cv2.putText(frame, msg, ((w - tw) // 2, h // 2 + 80),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, COLOR_SUCCESS, 2, cv2.LINE_AA)


# ─── Save ──────────────────────────────────────────────────────────────

def save_authored_exercise(state):
    """Save keyframes as a v2 exercise."""
    if not state.keyframes:
        print("[WARN] No keyframes to save.")
        return

    name = input("  Enter exercise name (or press Enter for default): ").strip()
    if not name:
        name = f"exercise_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # Fix transition_to pointers
    for i, kf in enumerate(state.keyframes):
        kf["id"] = i
        kf["transition_to"] = i + 1 if i < len(state.keyframes) - 1 else None

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


# ─── Main Loop ─────────────────────────────────────────────────────────

def main():
    state = AuthorState()
    cap = cv2.VideoCapture(0)

    with PoseLandmarker.create_from_options(mp_options) as landmarker:

        while cap.isOpened():
            success, frame = cap.read()
            if not success:
                break

            frame = cv2.flip(frame, 1)
            h, w, _ = frame.shape
            now = time.time()
            # Complete the countdown and begin recording
            if state.mode == "recording" and state.countdown_active:
                countdown_elapsed = now - state.countdown_start_time

                if countdown_elapsed >= COUNTDOWN_DURATION:
                    state.countdown_active = False
                    state.recording = True
                    state.record_start_time = now
                    state.last_capture_time = 0
                    state.last_angles = None
                    state.recording_start_index = len(state.keyframes)

                    set_status(state, "Recording started!")

            # ── MediaPipe Detection ──
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            timestamp = int(time.time() * 1000)
            landmarker.detect_async(mp_image, timestamp)

            elapsed = now - state.record_start_time if state.recording else 0

            # ── Recording Mode ──
            if state.mode == "recording":
                if latest_result is not None and latest_result.pose_landmarks:
                    for pose in latest_result.pose_landmarks:
                        pixel_pts, norm_pts = extract_points(pose, w, h)

                        # Draw full skeleton for therapist
                        draw_pose_skeleton(frame, pixel_pts)
                        draw_angle_values(frame, pixel_pts)

                        # Auto-capture during recording
                        if state.recording and (now - state.last_capture_time) >= CAPTURE_INTERVAL:
                            angles = compute_angles(pixel_pts)
                            if pose_changed_enough(angles, state.last_angles):
                                new_state = create_state_from_capture(
                                    pixel_pts, norm_pts, elapsed,
                                    len(state.keyframes), len(state.keyframes) + 1
                                )
                                state.keyframes.append(new_state)
                                state.last_angles = angles
                                state.last_capture_time = now
                        break

                draw_recording_ui(frame, state, elapsed)
                draw_countdown(frame, state, now)

            # ── Editing Mode ──
            elif state.mode == "editing":
                draw_editing_ui(frame, state)

            cv2.imshow("Exercise Author", frame)

            # ── Handle Keys ──
            key = cv2.waitKeyEx(1)

            if state.mode == "recording":
                if key == ord("r"):
                    if state.countdown_active:
                        # Press R during the countdown to cancel it
                        state.countdown_active = False
                        set_status(state, "Countdown cancelled.")

                    elif state.recording:
                        removed_count = finish_recording(state)

                        set_status(
                            state,
                            f"Stopped — removed {removed_count} keyframes "
                            f"from the final {TRIM_END_SECONDS:.0f} seconds. "
                            f"{len(state.keyframes)} remain."
                        )
                    else:
                        # Start the five-second countdown
                        state.countdown_active = True
                        state.countdown_start_time = time.time()
                        set_status(state, "Get ready!")

                elif key == ord(" "):
                    # Manual keyframe capture
                    if latest_result is not None and latest_result.pose_landmarks:
                        for pose in latest_result.pose_landmarks:
                            pixel_pts, norm_pts = extract_points(pose, w, h)
                            new_kf = create_state_from_capture(
                                pixel_pts, norm_pts,
                                now - state.record_start_time if state.recording else 0,
                                len(state.keyframes), len(state.keyframes) + 1
                            )
                            state.keyframes.append(new_kf)
                            set_status(state, f"Keyframe {len(state.keyframes)} captured!")
                            break
                    else:
                        set_status(state, "No pose detected!")

                elif key == ord("e"):
                    if state.keyframes:
                        state.mode = "editing"
                        state.recording = False
                        state.selected_kf = 0
                        set_status(state, "Switched to editing mode.")
                    else:
                        set_status(state, "Record keyframes first!")

                elif key == ord("q"):
                    break

            elif state.mode == "editing":
                # Arrow-key codes for Windows and Linux
                LEFT_ARROW_KEYS = (2424832, 65361, 81, 2)
                RIGHT_ARROW_KEYS = (2555904, 65363, 83, 3)

                if key in LEFT_ARROW_KEYS:
                    state.selected_kf = max(
                        0,
                        state.selected_kf - 1
                    )
                    set_status(
                        state,
                        f"Keyframe {state.selected_kf + 1}/{len(state.keyframes)}"
                    )

                elif key in RIGHT_ARROW_KEYS:
                    state.selected_kf = min(
                        len(state.keyframes) - 1,
                        state.selected_kf + 1
                    )
                    set_status(
                        state,
                        f"Keyframe {state.selected_kf + 1}/{len(state.keyframes)}"
                    )

                elif key == ord("i"):
                    # Set instruction
                    cv2.destroyAllWindows()
                    instruction = input(
                        f"  Instruction for keyframe {state.selected_kf + 1}: "
                    ).strip()
                    if instruction:
                        state.keyframes[state.selected_kf]["instruction"] = instruction
                        set_status(state, "Instruction updated.")

                elif key == ord("h"):
                    cv2.destroyAllWindows()
                    try:
                        duration = float(input(
                            f"  Hold duration (seconds, current: "
                            f"{state.keyframes[state.selected_kf]['hold_duration']}): "
                        ).strip())
                        state.keyframes[state.selected_kf]["hold_duration"] = duration
                        set_status(state, f"Hold: {duration}s")
                    except ValueError:
                        set_status(state, "Invalid input.")

                elif key == ord("t"):
                    cv2.destroyAllWindows()
                    try:
                        tol = float(input(
                            f"  Global tolerance (degrees, current: "
                            f"{state.keyframes[state.selected_kf]['tolerances'][0]}): "
                        ).strip())
                        n = len(state.keyframes[state.selected_kf]["tolerances"])
                        state.keyframes[state.selected_kf]["tolerances"] = [tol] * n
                        set_status(state, f"Tolerance: {tol}°")
                    except ValueError:
                        set_status(state, "Invalid input.")

                elif key == ord("d"):
                    if len(state.keyframes) > 1:
                        del state.keyframes[state.selected_kf]
                        state.selected_kf = min(state.selected_kf, len(state.keyframes) - 1)
                        set_status(state, "Keyframe deleted.")
                    else:
                        set_status(state, "Cannot delete last keyframe.")

                elif key == ord("s"):
                    save_authored_exercise(state)

                elif key == ord("r"):
                    state.mode = "recording"
                    set_status(state, "Switched to recording mode.")

                elif key == ord("q"):
                    break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
