"""
Shared utilities for the Pose Exercise Recording & Playback system.
Contains common constants, angle calculation, and pose normalization helpers.
"""

import math

# ─── Pose Topology ─────────────────────────────────────────────────────

# A concise upper/lower-body skeleton for drawing guidance overlays.
POSE_CONNECTIONS = [
    (11, 12),               # Shoulders
    (11, 13), (13, 15), (15, 17), (15, 19), (15, 21),
    (12, 14), (14, 16), (16, 18), (16, 20), (16, 22),
    (11, 23), (12, 24), (23, 24),  # Torso
    (23, 25), (25, 27), (27, 29), (27, 31),
    (24, 26), (26, 28), (28, 30), (28, 32),
]

# Joint angles tracked by the recorder/playback engine.
ANGLE_JOINTS = [
    (13, 11, 23),  # Left shoulder
    (14, 12, 24),  # Right shoulder
    (11, 13, 15),  # Left elbow
    (12, 14, 16),  # Right elbow
    (13, 15, 19),  # Left wrist / hand orientation
    (14, 16, 20),  # Right wrist / hand orientation
    (11, 23, 25),  # Left hip
    (12, 24, 26),  # Right hip
    (23, 25, 27),  # Left knee
    (24, 26, 28),  # Right knee
    (25, 27, 31),  # Left ankle
    (26, 28, 32),  # Right ankle
]

POSE_KEY_LANDMARKS = [11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28]


# ─── Math Helpers ──────────────────────────────────────────────────────

def calculate_angle(a, b, c):
    """Calculate the angle (degrees) at point b formed by segments ba and bc."""
    ba = (a[0] - b[0], a[1] - b[1])
    bc = (c[0] - b[0], c[1] - b[1])

    dot = ba[0] * bc[0] + ba[1] * bc[1]
    mag_ba = math.sqrt(ba[0]**2 + ba[1]**2)
    mag_bc = math.sqrt(bc[0]**2 + bc[1]**2)

    if mag_ba == 0 or mag_bc == 0:
        return 0

    cos_angle = max(-1, min(1, dot / (mag_ba * mag_bc)))
    return math.degrees(math.acos(cos_angle))


def compute_angles(points):
    """Compute all tracked joint angles from pose landmark points."""
    return [
        calculate_angle(points[p1], points[p2], points[p3])
        for p1, p2, p3 in ANGLE_JOINTS
    ]


def compute_match_score(patient_angles, target_angles, threshold=20.0):
    """
    Compare patient angles to target angles.
    Returns (match_fraction, per_joint_matched list).
    threshold: max degrees difference for a joint to count as matched.
    """
    per_joint = [abs(p - t) < threshold for p, t in zip(patient_angles, target_angles)]
    fraction = sum(per_joint) / len(per_joint) if per_joint else 0.0
    return fraction, per_joint


def _midpoint(a, b):
    return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)


def _safe_distance(points, i, j):
    if i < len(points) and j < len(points):
        return math.dist(points[i], points[j])
    return 0.0


def get_pose_anchor_and_scale(landmarks_xy):
    """
    Return a stable anchor point and scale for a pose.

    Preference order:
      1. Midpoint of hips with shoulder width scale
      2. Midpoint of shoulders with hip width scale
      3. First landmark with unit scale
    """
    anchor = None
    scale = 0.0

    if len(landmarks_xy) > 24:
        left_hip = landmarks_xy[23]
        right_hip = landmarks_xy[24]
        left_shoulder = landmarks_xy[11]
        right_shoulder = landmarks_xy[12]

        if left_hip and right_hip:
            anchor = _midpoint(left_hip, right_hip)
        elif left_shoulder and right_shoulder:
            anchor = _midpoint(left_shoulder, right_shoulder)

        scale = _safe_distance(landmarks_xy, 11, 12)
        if scale < 1e-6:
            scale = _safe_distance(landmarks_xy, 23, 24)

    if anchor is None:
        anchor = landmarks_xy[0]

    if scale < 1e-6:
        scale = 1.0

    return anchor, scale


def normalize_pose(landmarks_xy):
    """
    Normalize pose landmarks relative to a stable torso anchor and scale.
    Returns (relative_points, pose_scale).
    """
    anchor, pose_scale = get_pose_anchor_and_scale(landmarks_xy)
    relative = [(x - anchor[0], y - anchor[1]) for x, y in landmarks_xy]
    return relative, pose_scale


def normalize_hand_pose(landmarks_xy):
    """Backward-compatible alias for normalize_pose."""
    return normalize_pose(landmarks_xy)


def project_ghost(target_relative, target_scale, patient_anchor, patient_scale):
    """
    Project normalized target landmarks onto the patient's pose frame.
    Anchors the ghost to the patient's torso center and scales it to the
    patient's current pose size.
    Returns list of (x, y) pixel coordinates for the ghost pose.
    """
    scale = patient_scale / target_scale if target_scale > 1e-6 else 1.0
    ax, ay = patient_anchor
    return [
        (int(rx * scale + ax), int(ry * scale + ay))
        for rx, ry in target_relative
    ]


# Backward-compatible aliases for older imports.
HAND_CONNECTIONS = POSE_CONNECTIONS
