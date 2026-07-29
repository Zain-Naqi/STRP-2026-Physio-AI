"""
Exercise Schema v2
===================
Defines the FSM-based exercise format and provides migration from v1.

Each exercise is a sequence of clinically meaningful states (poses),
each with explicit entry conditions, hold times, priority joints,
and human-readable instructions.
"""

import json
import os
from datetime import datetime

# ─── Joint Labels ──────────────────────────────────────────────────────

# Human-readable labels for ANGLE_JOINTS indices.
JOINT_LABELS = {
    0:  "left shoulder",
    1:  "right shoulder",
    2:  "left elbow",
    3:  "right elbow",
    4:  "left wrist",
    5:  "right wrist",
    6:  "left hip",
    7:  "right hip",
    8:  "left knee",
    9:  "right knee",
    10: "left ankle",
    11: "right ankle",
}

# Mapping from ANGLE_JOINTS index to the MediaPipe landmark at the vertex
# (the middle point of the triplet, where the angle is measured)
from exercise_utils import ANGLE_JOINTS

JOINT_TO_LANDMARK = {i: triplet[1] for i, triplet in enumerate(ANGLE_JOINTS)}

# Limb groupings for correction messages
LIMB_GROUPS = {
    "left_arm": [0, 2, 4],
    "right_arm": [1, 3, 5],
    "left_leg": [6, 8, 10],
    "right_leg": [7, 9, 11],
}


# Default values
DEFAULT_TOLERANCE = 15       # degrees
DEFAULT_HOLD_DURATION = 0.8    # seconds
DEFAULT_MATCH_THRESHOLD = 0.9 # fraction of joints

SCHEMA_VERSION = 2


# ─── Schema Validation ────────────────────────────────────────────────

def validate_exercise(data):
    """Validate an exercise dict against the v2 schema. Returns (valid, errors)."""
    errors = []

    if "version" not in data:
        errors.append("Missing 'version' field")
    elif data["version"] != SCHEMA_VERSION:
        errors.append(f"Expected version {SCHEMA_VERSION}, got {data['version']}")

    if "states" not in data:
        errors.append("Missing 'states' field")
        return False, errors

    for i, state in enumerate(data["states"]):
        prefix = f"State {i}"
        if "angles" not in state:
            errors.append(f"{prefix}: missing 'angles'")
        if "landmarks" not in state:
            errors.append(f"{prefix}: missing 'landmarks'")
        if "instruction" not in state:
            errors.append(f"{prefix}: missing 'instruction'")
        if "hold_duration" not in state:
            errors.append(f"{prefix}: missing 'hold_duration'")

        # Validate lengths
        if "angles" in state and len(state["angles"]) != len(ANGLE_JOINTS):
            errors.append(
                f"{prefix}: 'angles' has {len(state['angles'])} entries, "
                f"expected {len(ANGLE_JOINTS)}"
            )
        if "tolerances" in state and len(state["tolerances"]) != len(ANGLE_JOINTS):
            errors.append(
                f"{prefix}: 'tolerances' has {len(state['tolerances'])} entries, "
                f"expected {len(ANGLE_JOINTS)}"
            )

    return len(errors) == 0, errors


# ─── Migration from v1 ────────────────────────────────────────────────

def _generate_instruction(state_index, total_states):
    """Generate a default instruction for a migrated state."""
    if state_index == 0:
        return "Move into the starting position."
    elif state_index == total_states - 1:
        return "Hold this final position."
    else:
        return f"Move to position {state_index + 1}."


def migrate_v1_to_v2(v1_data):
    """
    Convert a v1 exercise (from record_exercise.py) to v2 FSM format.

    v1 has: name, recorded_at, num_keyframes, keyframes[]
    v2 has: name, version, states[] with clinical metadata
    """
    total = len(v1_data.get("keyframes", []))

    states = []
    for i, kf in enumerate(v1_data.get("keyframes", [])):
        num_angles = len(kf.get("angles", []))

        state = {
            "id": i,
            "instruction": _generate_instruction(i, total),
            "hold_duration": DEFAULT_HOLD_DURATION,
            "landmarks": kf.get("landmarks", []),
            "landmarks_relative": kf.get("landmarks_relative", []),
            "pose_scale": kf.get(
                "pose_scale",
                kf.get("hand_scale", 1.0)
            ),            "angles": kf.get("angles", []),
            "tolerances": [DEFAULT_TOLERANCE] * num_angles,
            "priority_joints": list(range(num_angles)),  # all joints equal
            "priority_labels": {
                str(j): JOINT_LABELS.get(j, f"joint {j}")
                for j in range(num_angles)
            },
            "transition_to": i + 1 if i < total - 1 else None,
            "entry_match_threshold": DEFAULT_MATCH_THRESHOLD,
        }
        states.append(state)

    return {
        "name": v1_data.get("name", "Unnamed Exercise"),
        "version": SCHEMA_VERSION,
        "created_by": "Unknown",
        "created_at": v1_data.get("recorded_at", datetime.now().isoformat()),
        "description": f"Migrated from v1 exercise '{v1_data.get('name', '')}'",
        "num_states": total,
        "states": states,
    }


# ─── Load / Save ──────────────────────────────────────────────────────

def load_exercise(filepath):
    """
    Load an exercise file. Auto-migrates v1 format to v2.
    Returns validated v2 exercise dict.
    """
    with open(filepath, "r") as f:
        data = json.load(f)

    # Detect version
    version = data.get("version", 1)

    if version == 1 or "keyframes" in data:
        print(f"[MIGRATE] Converting v1 exercise to v2 format...")
        data = migrate_v1_to_v2(data)

    valid, errors = validate_exercise(data)
    if not valid:
        raise ValueError(f"Invalid exercise schema:\n" + "\n".join(errors))

    return data


def save_exercise(data, filepath):
    """Save a v2 exercise to JSON."""
    data["version"] = SCHEMA_VERSION
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)
    print(f"[SAVED] {filepath} ({data.get('num_states', 0)} states)")


def list_exercises(directory="Exercises"):
    """List all available exercise files."""
    if not os.path.isdir(directory):
        return []
    return [
        f.replace(".json", "")
        for f in sorted(os.listdir(directory))
        if f.endswith(".json")
    ]
