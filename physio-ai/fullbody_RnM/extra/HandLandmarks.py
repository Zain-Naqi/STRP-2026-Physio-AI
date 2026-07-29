import cv2
import mediapipe as mp
import time
from mediapipe.tasks.python import vision
from exercise_utils import POSE_CONNECTIONS, ANGLE_JOINTS, calculate_angle


model_path = "Models/pose_landmarker_lite.task"

BaseOptions = mp.tasks.BaseOptions
PoseLandmarker = vision.PoseLandmarker
PoseLandmarkerOptions = vision.PoseLandmarkerOptions
VisionRunningMode = vision.RunningMode

latest_result = None

def print_result(result, output_image, timestamp_ms):
    global latest_result
    latest_result = result

options = PoseLandmarkerOptions(
    base_options = BaseOptions(model_asset_path = model_path),
    running_mode = VisionRunningMode.LIVE_STREAM,
    num_poses = 1,
    result_callback = print_result
)

cap = cv2.VideoCapture(0)

with PoseLandmarker.create_from_options(options) as landmarker:

    while cap.isOpened():

        success, frame = cap.read()
        if not success:
            break

        frame = cv2.flip(frame, 1)

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        mp_image = mp.Image(
            image_format = mp.ImageFormat.SRGB,
            data = rgb
        )

        timestamp = int(time.time() * 1000)
        landmarker.detect_async(mp_image, timestamp)

        if latest_result is not None:

            h, w, _ = frame.shape

            for pose in latest_result.pose_landmarks:

                points = []

                # Draw landmarks
                for landmark in pose:
                    x = int(landmark.x * w)
                    y = int(landmark.y * h)

                    points.append((x, y))

                    cv2.circle(frame, (x, y), 4, (0, 255, 0), -1)

                # Draw connections
                for start, end in POSE_CONNECTIONS:
                    cv2.line(
                        frame,
                        points[start],
                        points[end],
                        (255, 0, 0),
                        2
                    )
                
                for p1, p2, p3 in ANGLE_JOINTS:
                    angle = calculate_angle(
                        points[p1],
                        points[p2],
                        points[p3]
                    )

                    x, y = points[p2]

                    cv2.putText(
                        frame,
                        f"{int(angle)}",
                        (x + 5, y - 5),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.45,
                        (0, 255, 255),
                        1,
                        cv2.LINE_AA
                    )


        cv2.imshow("Pose Tracking", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

cap.release()
cv2.destroyAllWindows()