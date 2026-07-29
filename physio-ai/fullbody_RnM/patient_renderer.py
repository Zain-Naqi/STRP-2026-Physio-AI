"""
Patient Renderer
=================
All patient-facing visual logic for the rehabilitation interface.

Design Principles:
    - NEVER shows full pose skeleton or all landmarks
    - NEVER displays angle values or technical metrics
    - Shows only ONE correction at a time (the most important)
    - Uses soft pulsing, glowing highlights — no harsh indicators
    - Large text, high contrast, accessibility-first
    - Communicates through animation, not numbers

Consumes EngineStatus from exercise_engine — zero knowledge of MediaPipe.
"""

import cv2
import math
import time
import numpy as np
from exercise_engine import EngineStatus
from exercise_utils import ANGLE_JOINTS, POSE_CONNECTIONS


# ─── Color Palette (BGR) ──────────────────────────────────────────────

# Primary colors — warm, calming, clinical
COLOR_BG_DARK      = (26, 26, 26)         # #1A1A1A — dark overlay
COLOR_BG_PANEL     = (30, 30, 35)         # Slightly warm dark
COLOR_TEXT_PRIMARY  = (255, 255, 255)      # White
COLOR_TEXT_SECONDARY= (180, 180, 180)     # Light gray
COLOR_TEXT_MUTED    = (120, 120, 120)      # Muted gray

COLOR_ACCENT       = (225, 170, 65)       # Warm amber #41AADE (BGR)
COLOR_ACCENT_GLOW  = (200, 150, 50)       # Softer amber for glow
COLOR_SUCCESS      = (120, 220, 80)       # Soft green
COLOR_SUCCESS_GLOW = (80, 200, 50)        # Green glow
COLOR_HOLD         = (80, 200, 255)       # Warm orange for hold ring
COLOR_PROGRESS_BG  = (50, 50, 55)         # Progress track
COLOR_PROGRESS_FILL= (225, 170, 65)       # Amber progress
COLOR_DOT_INACTIVE = (70, 70, 75)         # Inactive step dot
COLOR_DOT_ACTIVE   = (225, 170, 65)       # Active step dot
COLOR_DOT_DONE     = (120, 220, 80)       # Completed step dot


# ─── Renderer Configuration ───────────────────────────────────────────

# Fonts
FONT_PRIMARY   = cv2.FONT_HERSHEY_SIMPLEX
FONT_SECONDARY = cv2.FONT_HERSHEY_SIMPLEX

# Animation timing
PULSE_FREQ     = 1.5       # Hz — highlight pulse frequency
ARROW_FREQ     = 1.0       # Hz — arrow animation cycle
FEEDBACK_DURATION = 0.8    # seconds — how long feedback flashes stay


class PatientRenderer:
    """
    Draws the patient-facing rehabilitation interface.

    Only knows about EngineStatus and pixel positions — no angle math.
    """

    def __init__(self, web_mode=False):
        """
        web_mode=True suppresses the on-frame instruction panel (step
        counter, instruction text, correction hint, keyboard-shortcut
        controls line) and the completion screen's text, because the
        browser-based perform page already shows all of that in its own
        sidebar. The desktop tool (follow_exercise.py) keeps instantiating
        this with web_mode=False and is unaffected.
        """
        self.web_mode = web_mode
        self.feedback_text = ""
        self.feedback_time = 0.0
        self.feedback_type = "neutral"  # "success", "correction", "neutral"
        self.last_phase = "no_hand"
        self.phase_change_time = time.time()

    # ─── Main Draw Entry Point ─────────────────────────────────────

    def draw(self, frame, status: EngineStatus, patient_points=None, ghost_points=None):
        """
        Render the complete patient interface onto the frame.

        Args:
            frame: BGR image to draw on (modified in-place)
            status: EngineStatus from the FSM engine
            patient_points: List of 33 (x, y) pose landmark coordinates, or None
            ghost_points: List of 33 (x, y) target pose coordinates, or None
    """
        h, w = frame.shape[:2]

        # Track phase changes for animations
        if status.phase != self.last_phase:
            self.phase_change_time = time.time()
            if self.last_phase == "holding" and status.phase == "matched":
                self._trigger_feedback("Good!", "success")
            self.last_phase = status.phase

        # Update feedback from status
        if status.feedback_message and status.phase == "correcting":
            self._trigger_feedback(status.feedback_message, "correction")

        # ── Layer 1: Ghost Pose (subtle, background) ──
        if ghost_points and status.phase not in ("complete",):
            self._draw_ghost_hint(frame, ghost_points, status)

        # ── Layer 2: Single Joint Highlight ──
        # (Removed to prevent flickering as requested)

        # ── Layer 3: Hold Progress Ring ──
        if patient_points and status.phase == "holding" and status.correction:
            lm_id = status.correction.landmark_id
            if lm_id < len(patient_points):
                self._draw_hold_ring(frame, (w // 2, h // 2), status.hold_progress)
        elif patient_points and status.phase == "holding":
            # No specific correction — show ring at wrist
            self._draw_hold_ring(frame, (w // 2, h - 120), status.hold_progress)

        # ── Layer 4: UI Panels ──
        # The instruction panel duplicates text the browser page already
        # shows (step counter, instruction, correction hint, and the
        # keyboard-shortcut controls line), so it's desktop-only.
        if not self.web_mode:
            self._draw_instruction_panel(frame, status)
        self._draw_progress_dots(frame, status)
        self._draw_feedback_flash(frame, status)

        # ── Layer 5: Completion Screen ──
        if status.phase == "complete":
            self._draw_completion_overlay(frame)

    # ─── Ghost pose (Subtle Target Hint) ───────────────────────────

    def _draw_ghost_hint(self, frame, ghost_points, status):
        """
        Draw the target ghost pose to guide the patient.
        Shows body connections and joint landmarks with clear visibility.
    """
        
        overlay = frame.copy()

        # Draw connections as thicker, highly visible lines
        for start, end in POSE_CONNECTIONS:
            if (start < len(ghost_points) and end < len(ghost_points)
                    and ghost_points[start] is not None and ghost_points[end] is not None):
                cv2.line(overlay, ghost_points[start], ghost_points[end],
                         COLOR_ACCENT, 3, cv2.LINE_AA)

        # Draw joint circles for better visibility
        for pt in ghost_points:
            if pt is not None:
                cv2.circle(overlay, pt, 5, COLOR_ACCENT_GLOW, -1, cv2.LINE_AA)

        # Blend with a much higher opacity (0.50) so it's clearly visible
        alpha = 0.50
        cv2.addWeighted(overlay, alpha, frame, 1.0 - alpha, 0, frame)

    # ─── Single Joint Highlight ────────────────────────────────────

    def _draw_joint_highlight(self, frame, patient_points, status):
        """
        Highlight ONLY the single most important incorrect joint.
        Uses a soft pulsing glow — never the entire hand.
        """
        if not status.correction:
            return

        lm_id = status.correction.landmark_id
        if lm_id >= len(patient_points):
            return

        pt = patient_points[lm_id]
        now = time.time()

        # Pulsing radius: sine wave between 16-24px
        pulse = math.sin(now * PULSE_FREQ * 2 * math.pi)
        radius_outer = int(20 + 4 * pulse)
        radius_inner = 8

        # Outer glow (multiple layers for soft effect)
        overlay = frame.copy()
        for r_offset in range(3):
            r = radius_outer + r_offset * 6
            alpha = 0.08 - r_offset * 0.02
            cv2.circle(overlay, pt, r, COLOR_ACCENT_GLOW, -1, cv2.LINE_AA)
        cv2.addWeighted(overlay, 0.3, frame, 0.7, 0, frame)

        # Core highlight ring
        cv2.circle(frame, pt, radius_outer, COLOR_ACCENT, 2, cv2.LINE_AA)

        # Inner filled dot
        cv2.circle(frame, pt, radius_inner, COLOR_ACCENT, -1, cv2.LINE_AA)

    # ─── Direction Arrow ───────────────────────────────────────────

    def _draw_direction_arrow(self, frame, patient_points, status):
        """
        Draw an animated arrow showing the direction the patient should move.
        Arrow originates at the highlighted joint and points in the correction direction.
        """
        if not status.correction:
            return

        lm_id = status.correction.landmark_id
        joint_idx = status.correction.joint_index

        if lm_id >= len(patient_points):
            return

        pt = patient_points[lm_id]

        # Get the angle triplet for this joint
        if joint_idx < len(ANGLE_JOINTS):
            p1_id, p2_id, p3_id = ANGLE_JOINTS[joint_idx]
        else:
            return

        # Determine arrow direction based on correction
        direction = status.correction.correction_direction

        # Calculate the finger direction vector (from joint toward fingertip)
        if p3_id < len(patient_points) and p2_id < len(patient_points):
            limb_vec = (
                patient_points[p3_id][0] - patient_points[p2_id][0],
                patient_points[p3_id][1] - patient_points[p2_id][1],
            )
        else:
            limb_vec = (0, -1)  # default up

        # Normalize
        mag = math.sqrt(limb_vec[0]**2 + limb_vec[1]**2)
        if mag < 1e-6:
            limb_vec = (0, -1)
        else:
            limb_vec = (limb_vec[0] / mag, limb_vec[1] / mag)

        # Arrow animation: oscillating offset
        now = time.time()
        anim_t = (math.sin(now * ARROW_FREQ * 2 * math.pi) + 1) / 2  # 0 to 1

        if direction == "increase":
            arrow_vec = limb_vec
        elif direction == "decrease":
            arrow_vec = (-limb_vec[0], -limb_vec[1])
        else:
            arrow_vec = limb_vec

            
        # Animated arrow length
        arrow_len = 30 + int(15 * anim_t)
        arrow_start = (
            int(pt[0] + arrow_vec[0] * 25),
            int(pt[1] + arrow_vec[1] * 25),
        )
        arrow_end = (
            int(pt[0] + arrow_vec[0] * (25 + arrow_len)),
            int(pt[1] + arrow_vec[1] * (25 + arrow_len)),
        )

        # Draw arrow with transparency
        overlay = frame.copy()
        cv2.arrowedLine(overlay, arrow_start, arrow_end,
                        COLOR_ACCENT, 3, cv2.LINE_AA, tipLength=0.35)
        alpha = 0.5 + 0.3 * anim_t  # Fade in/out
        cv2.addWeighted(overlay, alpha, frame, 1.0 - alpha, 0, frame)

    # ─── Hold Progress Ring ────────────────────────────────────────

    def _draw_hold_ring(self, frame, center, progress):
        """
        Draw a thin ring that fills up as the patient holds the pose.
        Provides visual feedback on hold duration without numbers.
        """
        radius = 30
        thickness = 3

        # Background ring
        cv2.circle(frame, center, radius, COLOR_PROGRESS_BG, thickness, cv2.LINE_AA)

        # Progress arc
        angle = int(360 * min(progress, 1.0))
        if angle > 0:
            cv2.ellipse(frame, center, (radius, radius), -90, 0, angle,
                        COLOR_HOLD, thickness + 1, cv2.LINE_AA)

        # Glow when nearly complete
        if progress > 0.8:
            overlay = frame.copy()
            cv2.circle(overlay, center, radius + 5, COLOR_SUCCESS_GLOW, -1)
            alpha = 0.1 * (progress - 0.8) / 0.2
            cv2.addWeighted(overlay, alpha, frame, 1.0 - alpha, 0, frame)

    # ─── Instruction Panel ─────────────────────────────────────────

    def _draw_instruction_panel(self, frame, status):
        """
        Bottom-center panel with step info and current instruction.
        Large, high-contrast text suitable for elderly users.
        """
        h, w = frame.shape[:2]
        panel_h = 90
        panel_y = h - panel_h

        # Semi-transparent dark panel
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, panel_y), (w, h), COLOR_BG_DARK, -1)
        cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)

        # Top accent line
        cv2.line(frame, (0, panel_y), (w, panel_y), COLOR_ACCENT, 1, cv2.LINE_AA)

        # Step indicator
        step_text = f"Step {status.current_state_id + 1} of {status.total_states}"
        cv2.putText(frame, step_text, (20, panel_y + 28),
                    FONT_PRIMARY, 0.55, COLOR_TEXT_MUTED, 1, cv2.LINE_AA)

        # Main instruction (large text)
        instruction = status.instruction
        cv2.putText(frame, instruction, (20, panel_y + 58),
                    FONT_PRIMARY, 0.75, COLOR_TEXT_PRIMARY, 2, cv2.LINE_AA)

        # Correction hint (if correcting)
        if status.phase == "correcting" and status.correction:
            hint = status.correction.correction_message
            cv2.putText(frame, hint, (20, panel_y + 80),
                        FONT_SECONDARY, 0.50, COLOR_ACCENT, 1, cv2.LINE_AA)

        # Controls hint (very subtle)
        controls = "[F] Fullscreen    [R] Restart    [Q] Quit"
        (tw, _), _ = cv2.getTextSize(controls, FONT_SECONDARY, 0.35, 1)
        cv2.putText(frame, controls, (w - tw - 15, panel_y + 80),
                    FONT_SECONDARY, 0.35, COLOR_TEXT_MUTED, 1, cv2.LINE_AA)

    # ─── Progress Dots ─────────────────────────────────────────────

    def _draw_progress_dots(self, frame, status):
        """
        Top-right corner: minimal step dots (●●○○○).
        Current step is larger, completed steps are green.
        """
        h, w = frame.shape[:2]

        total = status.total_states
        current = status.current_state_id

        # Dot layout
        dot_spacing = 22
        dot_radius = 5
        active_radius = 8
        total_width = (total - 1) * dot_spacing
        start_x = w - total_width - 30
        y = 30

        for i in range(total):
            x = start_x + i * dot_spacing

            if i < current:
                # Completed
                cv2.circle(frame, (x, y), dot_radius, COLOR_DOT_DONE, -1, cv2.LINE_AA)
            elif i == current:
                # Active — larger with glow
                overlay = frame.copy()
                cv2.circle(overlay, (x, y), active_radius + 4, COLOR_ACCENT_GLOW, -1)
                cv2.addWeighted(overlay, 0.15, frame, 0.85, 0, frame)
                cv2.circle(frame, (x, y), active_radius, COLOR_DOT_ACTIVE, -1, cv2.LINE_AA)

                # Completion arc around active dot
                if status.hold_progress > 0:
                    angle = int(360 * status.hold_progress)
                    cv2.ellipse(frame, (x, y), (active_radius + 3, active_radius + 3),
                                -90, 0, angle, COLOR_HOLD, 2, cv2.LINE_AA)
            else:
                # Future
                cv2.circle(frame, (x, y), dot_radius, COLOR_DOT_INACTIVE, -1, cv2.LINE_AA)

    # ─── Feedback Flash ────────────────────────────────────────────

    def _trigger_feedback(self, text, feedback_type="neutral"):
        """Trigger a feedback message to flash on screen."""
        self.feedback_text = text
        self.feedback_time = time.time()
        self.feedback_type = feedback_type

    def _draw_feedback_flash(self, frame, status):
        """
        Brief feedback message that fades in and out.
        "✓ Good!" in green, or correction in amber.
        """
        if not self.feedback_text:
            return

        elapsed = time.time() - self.feedback_time
        if elapsed > FEEDBACK_DURATION:
            self.feedback_text = ""
            return

        # Fade animation: fade in (0-0.3s), hold, fade out (last 0.5s)
        if elapsed < 0.3:
            alpha = elapsed / 0.3
        elif elapsed > FEEDBACK_DURATION - 0.5:
            alpha = (FEEDBACK_DURATION - elapsed) / 0.5
        else:
            alpha = 1.0

        alpha = max(0.0, min(1.0, alpha))

        if self.feedback_type == "success":
            color = COLOR_SUCCESS
        elif self.feedback_type == "correction":
            return  # Corrections show in the panel, not as flash
        else:
            color = COLOR_TEXT_PRIMARY

        h, w = frame.shape[:2]
        text = self.feedback_text

        # Only flash "success" type messages
        (tw, th), _ = cv2.getTextSize(text, FONT_PRIMARY, 1.0, 2)
        tx = (w - tw) // 2
        ty = h // 2

        # Background pill
        overlay = frame.copy()
        padding = 20
        cv2.rectangle(overlay,
                      (tx - padding, ty - th - padding),
                      (tx + tw + padding, ty + padding),
                      COLOR_BG_DARK, -1)
        cv2.addWeighted(overlay, 0.7 * alpha, frame, 1.0 - 0.7 * alpha, 0, frame)

        # Text
        text_color = tuple(int(c * alpha) for c in color)
        cv2.putText(frame, text, (tx, ty),
                    FONT_PRIMARY, 1.0, text_color, 2, cv2.LINE_AA)

    # ─── Completion Screen ─────────────────────────────────────────

    def _draw_completion_overlay(self, frame):
        """Draw a calming completion screen."""
        h, w = frame.shape[:2]

        # Dark overlay
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, h), COLOR_BG_DARK, -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

        # Checkmark circle
        cx, cy = w // 2, h // 2 - 40
        radius = 50

        # Animated glow
        now = time.time()
        glow_alpha = 0.1 + 0.05 * math.sin(now * 2)
        glow_overlay = frame.copy()
        cv2.circle(glow_overlay, (cx, cy), radius + 15, COLOR_SUCCESS_GLOW, -1)
        cv2.addWeighted(glow_overlay, glow_alpha, frame, 1.0 - glow_alpha, 0, frame)

        # Circle
        cv2.circle(frame, (cx, cy), radius, COLOR_SUCCESS, 3, cv2.LINE_AA)

        # Checkmark
        check_pts = [
            (cx - 20, cy),
            (cx - 5, cy + 18),
            (cx + 22, cy - 15),
        ]
        cv2.polylines(frame, [np.array(check_pts)], False, COLOR_SUCCESS, 3, cv2.LINE_AA)

        # Title/subtitle text (including the keyboard-shortcut hint) is
        # desktop-only — the browser page already shows a completion
        # message and a Restart button, so only the checkmark animation
        # renders in web_mode.
        if self.web_mode:
            return

        # Title
        title = "Exercise Complete!"
        (tw, _), _ = cv2.getTextSize(title, FONT_PRIMARY, 1.0, 2)
        cv2.putText(frame, title, ((w - tw) // 2, cy + radius + 45),
                    FONT_PRIMARY, 1.0, COLOR_SUCCESS, 2, cv2.LINE_AA)

        # Subtitle
        sub = "Great work! Press [R] to restart or [Q] to quit."
        (sw, _), _ = cv2.getTextSize(sub, FONT_SECONDARY, 0.5, 1)
        cv2.putText(frame, sub, ((w - sw) // 2, cy + radius + 75),
                    FONT_SECONDARY, 0.5, COLOR_TEXT_SECONDARY, 1, cv2.LINE_AA)
