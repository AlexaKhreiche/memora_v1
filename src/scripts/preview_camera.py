"""Preview a camera, optionally overlaying local facial-expression scores."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import sys
import time

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def load_classifier():
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[2] / '.env', override=True)
    backend = os.getenv('FACE_EMOTION_BACKEND', 'vit').lower()
    if backend == 'vit':
        from agent.toolsimplementations.tools.vit_face_client import ViTFaceClient
        client = ViTFaceClient()
    elif backend == 'deepface':
        from agent.toolsimplementations.tools.deepface_client import DeepFaceClient
        client = DeepFaceClient()
    else:
        raise ValueError('FACE_EMOTION_BACKEND must be vit or deepface')
    from agent.runtime.patient_identity import PatientFaceClient
    return PatientFaceClient(client, 'P001')


def describe_scores(scores, status):
    if not scores:
        return [f'FACE: {status.replace("_", " ")} (no prediction)']
    from agent.toolsimplementations.tools.emotion_safety_detector import EmotionSafetyDetector
    report, _ = EmotionSafetyDetector().build_report(scores)
    top = sorted(scores.items(), key=lambda item: item[1], reverse=True)[:3]
    return [f'Identity: {status.replace(chr(95), chr(32))}', 'FACE: ' + ' | '.join(f'{name} {score:.0%}' for name, score in top),
            f'App label: {report.emotion_label.value} ({report.emotion_confidence:.0%})']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('index', type=int, help='OpenCV camera index to preview')
    parser.add_argument('--emotion', action='store_true', help='Show facial-only model scores and app mapping')
    args = parser.parse_args()
    cap = cv2.VideoCapture(args.index)
    worker = ThreadPoolExecutor(max_workers=1) if args.emotion else None
    pending = worker.submit(load_classifier) if worker else None
    client = None
    lines = ['Loading facial model...'] if worker else []
    last_result = None
    next_analysis = 0.0
    failed = False
    try:
        if not cap.isOpened():
            raise RuntimeError(f'Cannot open camera {args.index}')
        print(f'Previewing OpenCV index {args.index}. Press Q to close.')
        while True:
            ok, frame = cap.read()
            if not ok:
                raise RuntimeError(f'Camera {args.index} returned no frame')
            now = time.monotonic()
            if pending is not None and pending.done():
                try:
                    result = pending.result()
                    if client is None:
                        client = result
                        lines = ['Facial model ready; waiting for analysis...']
                    else:
                        lines = describe_scores(result, client.status)
                        last_result = now
                except Exception as exc:
                    print(f'Facial preview error: {exc}')
                    lines = ['Facial analysis failed - see terminal; restart to retry']
                    failed = True
                pending = None
            if client is not None and pending is None and not failed and now >= next_analysis:
                pending = worker.submit(client.facial_scores_from_bgr_frame, frame.copy())
                next_analysis = now + 0.5
            overlay = list(lines)
            if last_result is not None and not failed:
                overlay.append(f'Last result {now - last_result:.1f}s ago | facial only')
            # Keep all GUI calls on the main thread; model work runs in the worker.
            for i, text in enumerate(overlay):
                y = 28 + i * 28
                cv2.putText(frame, text, (12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 4, cv2.LINE_AA)
                cv2.putText(frame, text, (12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
            cv2.imshow(f'Camera index {args.index} - Q to close', frame)
            if cv2.waitKey(30) & 0xff == ord('q'):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()
        if worker:
            worker.shutdown(wait=True, cancel_futures=True)


if __name__ == '__main__':
    main()
