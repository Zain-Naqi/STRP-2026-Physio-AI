"""
Exercise Engine — FSM-Based Pose Comparison
=============================================
Treats an exercise as a finite state machine of clinically meaningful poses.
Each state has entry conditions, hold times, and transition rules.

The engine is renderer-agnostic — it outputs EngineStatus snapshots
that any UI can consume without knowing about angles or landmarks.
"""

import time
import math
from dataclasses import dataclass, field
from typing import Optional

from exercise_utils import ANGLE_JOINTS, compute_angles
from exercise_schema import (
    JOINT_LABELS,
    JOINT_TO_LANDMARK,
    DEFAULT_TOLERANCE,
    DEFAULT_MATCH_THRESHOLD,
)


# ─── Data Classes ──────────────────────────────────────────────────────

@dataclass
class CorrectionInfo:
    """The single most important correction to show the patient."""
    joint_index: int              # Index into ANGLE_JOINTS
    joint_label: str              # Human-readable: "index fingertip"
    landmark_id: int              # MediaPipe landmark ID (vertex of angle)
    angle_error: float            # Signed: positive = extend more, negative = bend more
    correction_direction: str     # "straighten", "bend", "spread", "close"
    correction_message: str       # "Straighten your index finger."
    confidence: float             # 0.0 to 1.0 (based on how clear the correction is)


@dataclass
class EngineStatus:
    """Complete snapshot of engine state for the renderer."""
    phase: str                    # "no_hand", "correcting", "holding", "matched", "complete"
    current_state_id: int         # 0-indexed
    total_states: int
    instruction: str              # "Open your hand fully."
    completion_pct: float         # 0.0 to 1.0
    match_fraction: float         # How well the patient matches (0.0-1.0)
    hold_progress: float          # 0.0 to 1.0 (how much of hold_duration elapsed)
    correction: Optional[CorrectionInfo]  # None when pose is correct
    feedback_message: str         # "✓ Good!" or "Lift your index finger slightly."


# ─── Correction Logic ─────────────────────────────────────────────────

def _classify_direction(joint_index, angle_error):
    """
    Classify whether the angle at a body joint needs to increase or decrease.

    angle_error = target_angle - patient_angle
    """
    if angle_error > 0:
        return "increase"
    return "decrease"


def _build_correction_message(joint_index, direction):
    increase_messages = {
        0: "Raise your left arm further.",
        1: "Raise your right arm further.",
        2: "Straighten your left elbow.",
        3: "Straighten your right elbow.",
        4: "Adjust your left wrist outward.",
        5: "Adjust your right wrist outward.",
        6: "Lift your left leg further.",
        7: "Lift your right leg further.",
        8: "Straighten your left knee.",
        9: "Straighten your right knee.",
        10: "Adjust your left ankle.",
        11: "Adjust your right ankle.",
    }

    decrease_messages = {
        0: "Lower your left arm slightly.",
        1: "Lower your right arm slightly.",
        2: "Bend your left elbow more.",
        3: "Bend your right elbow more.",
        4: "Adjust your left wrist inward.",
        5: "Adjust your right wrist inward.",
        6: "Lower your left leg slightly.",
        7: "Lower your right leg slightly.",
        8: "Bend your left knee more.",
        9: "Bend your right knee more.",
        10: "Adjust your left ankle.",
        11: "Adjust your right ankle.",
    }

    if direction == "increase":
        return increase_messages.get(joint_index, "Increase the joint angle slightly.")

    return decrease_messages.get(joint_index, "Decrease the joint angle slightly.")



def rank_corrections(patient_angles, target_angles, tolerances, priority_joints):
    """
    Rank all incorrect joints, prioritized by clinical importance.

    Returns a list of CorrectionInfo sorted by priority (most important first).
    """
    corrections = []

    for joint_idx in priority_joints:
        if joint_idx >= len(patient_angles) or joint_idx >= len(target_angles):
            continue

        tolerance = tolerances[joint_idx] if joint_idx < len(tolerances) else DEFAULT_TOLERANCE
        error = target_angles[joint_idx] - patient_angles[joint_idx]

        if abs(error) <= tolerance:
            continue  # This joint is within tolerance

        direction = _classify_direction(joint_idx, error)
        label = JOINT_LABELS.get(joint_idx, f"joint {joint_idx}")
        message = _build_correction_message(joint_idx, direction)

        # Confidence: higher when error is clearly outside tolerance
        confidence = min(1.0, abs(error) / (tolerance * 3))

        corrections.append(CorrectionInfo(
            joint_index=joint_idx,
            joint_label=label,
            landmark_id=JOINT_TO_LANDMARK.get(joint_idx, 0),
            angle_error=error,
            correction_direction=direction,
            correction_message=message,
            confidence=confidence,
        ))

    return corrections


# ─── FSM Engine ────────────────────────────────────────────────────────

class ExerciseFSM:
    """
    Finite state machine for guided exercise playback.

    Usage:
        engine = ExerciseFSM(exercise_data)
        while running:
            patient_angles = detect_pose(...)  # or None if no hand
            status = engine.update(patient_angles)
            renderer.draw(frame, status)
    """

    def __init__(self, exercise_data: dict):
        self.exercise = exercise_data
        self.states = exercise_data["states"]
        self.total_states = len(self.states)

        # FSM state
        self.current_idx = 0
        self.phase = "no_pose"  # no_pose, correcting, holding, matched, complete
        self.hold_start_time = None
        self.matched_flash_time = None
        self.match_fraction = 0.0
        self.last_correction = None

    def reset(self):
        """Reset the engine to the beginning."""
        self.current_idx = 0
        self.phase = "no_pose"
        self.hold_start_time = None
        self.matched_flash_time = None
        self.match_fraction = 0.0
        self.last_correction = None

    @property
    def current_state(self):
        """Get the current state definition."""
        if self.current_idx < self.total_states:
            return self.states[self.current_idx]
        return None

    def update(self, patient_angles: Optional[list] = None) -> EngineStatus:
        """
        Process one frame of patient data. Returns a complete EngineStatus.

        Args:
            patient_angles: List of joint angles from compute_angles(), or None if no hand detected.
        """
        now = time.time()
        state = self.current_state

        # ── Already complete ──
        if self.phase == "complete" or state is None:
            self.phase = "complete"
            return self._build_status(
                feedback="Exercise complete! Great work.",
            )

        # ── No pose detected ──
        if patient_angles is None:
            self.phase = "no_pose"
            self.hold_start_time = None
            self.match_fraction = 0.0
            self.last_correction = None
            return self._build_status(
                feedback="Show your body to the camera.",
            )

        # ── Compare angles ──
        target_angles = state["angles"]
        tolerances = state.get("tolerances", [DEFAULT_TOLERANCE] * len(target_angles))
        priority_joints = state.get("priority_joints", list(range(len(target_angles))))
        match_threshold = state.get("entry_match_threshold", DEFAULT_MATCH_THRESHOLD)

        # Compute per-joint match
        matched_count = 0
        total_joints = len(target_angles)
        for i in range(total_joints):
            tol = tolerances[i] if i < len(tolerances) else DEFAULT_TOLERANCE
            if i < len(patient_angles) and abs(patient_angles[i] - target_angles[i]) <= tol:
                matched_count += 1

        self.match_fraction = matched_count / total_joints if total_joints > 0 else 0.0

        # ── Get top correction ──
        corrections = rank_corrections(
            patient_angles, target_angles, tolerances, priority_joints
        )
        self.last_correction = corrections[0] if corrections else None

        # ── State transitions ──
        if self.match_fraction >= match_threshold:
            # Patient is matching well enough
            if self.phase != "holding":
                self.phase = "holding"
                self.hold_start_time = now

            hold_duration = state.get("hold_duration", 2.0)
            elapsed = now - self.hold_start_time

            if elapsed >= hold_duration:
                # Advance to next state!
                self._advance()
                return self._build_status(
                    feedback="Good! Moving to next step...",
                )
            else:
                return self._build_status(
                    feedback="Hold steady...",
                    hold_progress=elapsed / hold_duration,
                )
        else:
            # Not matching — show correction
            self.phase = "correcting"
            self.hold_start_time = None

            feedback = self.last_correction.correction_message if self.last_correction else ""
            return self._build_status(feedback=feedback)

    def _advance(self):
        """Move to the next state in the FSM."""
        state = self.current_state
        next_id = state.get("transition_to")

        if next_id is not None and next_id < self.total_states:
            self.current_idx = next_id
            self.phase = "matched"
            self.matched_flash_time = time.time()
        else:
            self.current_idx = min(self.current_idx + 1, self.total_states)
            self.phase = "complete"

        self.hold_start_time = None

    def _build_status(self, feedback="", hold_progress=0.0) -> EngineStatus:
        """Build an EngineStatus snapshot."""
        state = self.current_state
        instruction = state["instruction"] if state else "Exercise complete!"

        # Handle brief "matched" flash then transition to correcting
        if self.phase == "matched" and self.matched_flash_time:
            if time.time() - self.matched_flash_time > 0.2:
                self.phase = "correcting"
                self.matched_flash_time = None

        return EngineStatus(
            phase=self.phase,
            current_state_id=min(self.current_idx, self.total_states - 1),
            total_states=self.total_states,
            instruction=instruction,
            completion_pct=self.current_idx / self.total_states if self.total_states > 0 else 1.0,
            match_fraction=self.match_fraction,
            hold_progress=hold_progress,
            correction=self.last_correction,
            feedback_message=feedback,
        )
