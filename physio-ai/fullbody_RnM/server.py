"""
PhysioAI Exercise Service
==========================
A small FastAPI service that exposes the existing recording
(exercise_author.py) and guided-playback (follow_exercise.py /
exercise_engine.py / patient_renderer.py) logic to the browser.

The browser owns the webcam. This service:
    - Never opens an OpenCV window (no cv2.imshow / cv2.waitKey).
    - Never touches a camera (no cv2.VideoCapture).
    - Only decodes JPEG frames sent over WebSocket, runs the existing
      MediaPipe + FSM/recording pipeline, and returns an annotated JPEG
      plus JSON status.

Run (from inside fullbody_RnM/, so the relative "Models/" and
"Exercises/" paths resolve the same way they do for the desktop tools):

    uvicorn server:app --reload --port 8000
"""

import json
import logging
import os

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from exercise_schema import list_exercises, load_exercise
from live_session import AuthorSession, PerformSession, SessionError, NAME_RE

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("physioai.server")

EXERCISES_DIR = "Exercises"

app = FastAPI(title="PhysioAI Exercise Service")

# Local dev: the frontend is static HTML served from a different origin
# (Live Server, file://, or the Node backend's static host) than this
# Python service, so allow all origins rather than hardcoding one.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _validate_name(name: str) -> str:
    if not name or not NAME_RE.match(name):
        raise HTTPException(status_code=400, detail="Invalid exercise name.")
    return name


# ─── REST: Exercise Library ────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/exercises")
def get_exercises():
    """List saved exercises with just enough metadata for a library card."""
    names = list_exercises(EXERCISES_DIR)
    exercises = []

    for name in names:
        filepath = os.path.join(EXERCISES_DIR, f"{name}.json")
        try:
            data = load_exercise(filepath)
        except Exception as exc:
            logger.warning("Skipping unreadable exercise '%s': %s", name, exc)
            continue

        exercises.append({
            "name": data.get("name", name),
            "description": data.get("description", ""),
            "num_states": data.get("num_states", len(data.get("states", []))),
            "created_at": data.get("created_at"),
            "created_by": data.get("created_by", "Unknown"),
        })

    return {"exercises": exercises}


@app.get("/api/exercises/{exercise_name}")
def get_exercise(exercise_name: str):
    """Return the full (validated, auto-migrated) exercise definition."""
    name = _validate_name(exercise_name)
    filepath = os.path.join(EXERCISES_DIR, f"{name}.json")

    if not os.path.isfile(filepath):
        raise HTTPException(status_code=404, detail=f"Exercise '{name}' not found.")

    try:
        return load_exercise(filepath)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid exercise file: {exc}")


# ─── WebSocket: Recording (Therapist) ──────────────────────────────────

@app.websocket("/ws/exercise-author")
async def ws_exercise_author(websocket: WebSocket):
    await websocket.accept()
    session = AuthorSession()

    try:
        while True:
            message = await websocket.receive()

            if message["type"] == "websocket.disconnect":
                break

            data = message.get("bytes")
            if data is not None:
                result = session.process_frame(data)
                await websocket.send_json(result)
                continue

            text = message.get("text")
            if text is not None:
                try:
                    payload = json.loads(text)
                except json.JSONDecodeError:
                    await websocket.send_json({"type": "error", "error": "Invalid JSON command."})
                    continue

                action = payload.pop("action", None)
                result = session.handle_command(action, payload)
                await websocket.send_json(result)

    except WebSocketDisconnect:
        pass
    finally:
        session.close()


# ─── WebSocket: Guided Playback (Patient) ──────────────────────────────

@app.websocket("/ws/perform/{exercise_name}")
async def ws_perform(websocket: WebSocket, exercise_name: str):
    await websocket.accept()

    try:
        name = _validate_name(exercise_name)
        session = PerformSession(name, EXERCISES_DIR)
    except (HTTPException, SessionError) as exc:
        detail = exc.detail if isinstance(exc, HTTPException) else str(exc)
        await websocket.send_json({"type": "error", "error": detail})
        await websocket.close()
        return
    except Exception as exc:
        logger.exception("Failed to start perform session for '%s'", exercise_name)
        await websocket.send_json({"type": "error", "error": f"Could not load exercise: {exc}"})
        await websocket.close()
        return

    try:
        while True:
            message = await websocket.receive()

            if message["type"] == "websocket.disconnect":
                break

            data = message.get("bytes")
            if data is not None:
                result = session.process_frame(data)
                await websocket.send_json(result)
                continue

            text = message.get("text")
            if text is not None:
                try:
                    payload = json.loads(text)
                except json.JSONDecodeError:
                    continue

                if payload.get("action") == "restart":
                    session.restart()
                    await websocket.send_json({"type": "restarted"})

    except WebSocketDisconnect:
        pass
    finally:
        session.close()
