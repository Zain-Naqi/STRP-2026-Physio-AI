"""
Guided Exercise Playback — FSM-Based Patient Interface
=======================================================
Clean, minimal rehabilitation interface. The patient follows along
with an exercise using real-time pose comparison.

Architecture:
    Camera → MediaPipe → ExerciseFSM (engine) → PatientRenderer (UI)

The patient NEVER sees: skeletons, angle values, or multiple indicators.
They see: one gentle highlight, one animated arrow, one instruction.

Usage:
    python follow_exercise.py                     # lists available exercises
    python follow_exercise.py <exercise_name>     # loads directly

Controls:
    R  —  Restart the exercise
    Q  —  Quit
"""

import cv2
import mediapipe as mp
import time
import math
import sys
import os
from mediapipe.tasks.python import vision

from exercise_utils import (
    compute_angles, normalize_pose, get_pose_anchor_and_scale, project_ghost
)
from exercise_schema import load_exercise, list_exercises
from exercise_engine import ExerciseFSM
from patient_renderer import PatientRenderer


# ─── Config ────────────────────────────────────────────────────────────

MODEL_PATH = "Models/pose_landmarker_lite.task"
EXERCISES_DIR = "Exercises"


# ─── MediaPipe Setup ───────────────────────────────────────────────────

BaseOptions = mp.tasks.BaseOptions
PoseLandmarker = vision.PoseLandmarker
PoseLandmarkerOptions = vision.PoseLandmarkerOptions
VisionRunningMode = vision.RunningMode

latest_result = None

def on_result(result, output_image, timestamp_ms):
    global latest_result
    latest_result = result

options = PoseLandmarkerOptions(
    base_options=BaseOptions(model_asset_path=MODEL_PATH),
    running_mode=VisionRunningMode.LIVE_STREAM,
    num_poses=1,
    result_callback=on_result
)


# ─── Exercise Selection ───────────────────────────────────────────────

def select_exercise():
    """Interactive exercise selection."""
    exercises = list_exercises(EXERCISES_DIR)
    if not exercises:
        print("[ERROR] No exercises found. Record one first with exercise_author.py")
        sys.exit(1)

    print("\n  Available exercises:")
    for i, name in enumerate(exercises):
        print(f"    {i + 1}. {name}")
    print()

    choice = input("  Enter exercise number or name: ").strip()

    try:
        idx = int(choice) - 1
        if 0 <= idx < len(exercises):
            return exercises[idx]
    except ValueError:
        pass

    if choice in exercises:
        return choice

    print(f"[ERROR] Invalid selection: {choice}")
    sys.exit(1)


# ─── Ghost Projection Helpers ─────────────────────────────────────────

def project_ghost_to_patient(state, patient_points, frame_w, frame_h):
    """
    Project the target ghost pose onto the patient's pose position and scale.
    """
    target_relative_norm = state.get("landmarks_relative", [])
    target_scale = state.get(
        "pose_scale",
        state.get("hand_scale", 1.0)
    )

    # Convert relative from normalized to pixel space
    target_relative_px = [
        (r[0] * frame_w, r[1] * frame_h)
        for r in target_relative_norm
    ]
    target_scale_px = target_scale * frame_w

    # Patient anchor and scale in pixels
    patient_anchor, patient_scale_px = get_pose_anchor_and_scale(patient_points)
    if patient_scale_px < 1e-6:
        patient_scale_px = frame_h * 0.15

    return project_ghost(target_relative_px, target_scale_px, patient_anchor, patient_scale_px)


def project_ghost_default(state, frame_w, frame_h):
    """
    Show the ghost pose at center-screen when no patient pose is detected.
    """
    target_relative_norm = state.get("landmarks_relative", [])
    target_scale = state.get(
        "pose_scale",
        state.get("hand_scale", 1.0)
    )

    default_anchor = (frame_w // 2, frame_h // 2)
    default_scale = frame_h * 0.15

    target_relative_px = [
        (r[0] * frame_w, r[1] * frame_h)
        for r in target_relative_norm
    ]

    return project_ghost(
        target_relative_px,
        target_scale * frame_w,
        default_anchor,
        default_scale
    )


# ─── Main ──────────────────────────────────────────────────────────────

def main():
    # ── Select & Load Exercise ──
    if len(sys.argv) > 1:
        exercise_name = sys.argv[1]
    else:
        exercise_name = select_exercise()

    filepath = os.path.join(EXERCISES_DIR, f"{exercise_name}.json")
    exercise_data = load_exercise(filepath)

    print(f"[LOADED] '{exercise_data['name']}' — {exercise_data['num_states']} states")

    # ── Initialize Engine & Renderer ──
    engine = ExerciseFSM(exercise_data)
    renderer = PatientRenderer()

    cap = cv2.VideoCapture(0)
    
    cv2.namedWindow("Exercise Guide", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Exercise Guide", 1024, 768)

    with PoseLandmarker.create_from_options(options) as landmarker:
        while cap.isOpened():
            success, frame = cap.read()
            if not success:
                break

            frame = cv2.flip(frame, 1)
            h, w, _ = frame.shape

            # Subtle background darkening for contrast
            frame = cv2.convertScaleAbs(frame, alpha=0.75, beta=10)

            # ── Detect Pose ──
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            timestamp = int(time.time() * 1000)
            landmarker.detect_async(mp_image, timestamp)

            patient_angles = None
            patient_points = None
            ghost_points = None

            if latest_result is not None and latest_result.pose_landmarks:
                for pose_lm in latest_result.pose_landmarks:
                    patient_points = [
                        (int(lm.x * w), int(lm.y * h))
                        for lm in pose_lm
                    ]
                    patient_angles = compute_angles(patient_points)
                    break  # First pose only

            # ── Update Engine ──
            status = engine.update(patient_angles)

            # ── Project Ghost pose ──
            current_state = engine.current_state
            if current_state and status.phase != "complete":
                if patient_points:
                    ghost_points = project_ghost_to_patient(
                        current_state, patient_points, w, h
                    )
                else:
                    ghost_points = project_ghost_default(current_state, w, h)

            # ── Render ──
            renderer.draw(frame, status, patient_points, ghost_points)

            cv2.imshow("Exercise Guide", frame)

            # ── Handle Keys ──
            key = cv2.waitKey(1) & 0xFF

            if key == ord("r"):
                engine.reset()
                print("[INFO] Exercise restarted.")

            elif key == ord("f"):
                # Toggle fullscreen
                try:
                    val = cv2.getWindowProperty("Exercise Guide", cv2.WND_PROP_FULLSCREEN)
                    if val == cv2.WINDOW_FULLSCREEN:
                        cv2.setWindowProperty("Exercise Guide", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_NORMAL)
                    else:
                        cv2.setWindowProperty("Exercise Guide", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
                except cv2.error:
                    pass

            elif key == ord("q"):
                break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
