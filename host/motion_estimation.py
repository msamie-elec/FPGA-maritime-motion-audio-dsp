"""Estimate 2-D TRANSLATIONAL camera trajectory from a user-provided short video.

This is HOST-SIDE OpenCV processing, not FPGA image tracking. We prefer
stationary-background features and reject moving-object outliers with RANSAC.
The FPGA FIR receives only signed Q16.8 X/Y trajectory samples.
"""
from __future__ import annotations

import csv
from pathlib import Path
from dataclasses import dataclass
import cv2
import numpy as np

MAX_FRAMES = 1500  # host clips up to 50s; FPGA receives overlapping batches of <=512 samples
MIN_FRAMES = 18
MAX_WIDTH, MAX_HEIGHT = 1280, 720
MAX_BYTES = 125 * 1024 * 1024


@dataclass(frozen=True)
class VideoInfo:
    frames: int
    width: int
    height: int
    fps: float


def inspect_video(video_path: Path) -> VideoInfo:
    video_path = Path(video_path)
    if not video_path.is_file():
        raise ValueError(f"Video does not exist: {video_path}")
    if video_path.suffix.lower() not in {'.mp4', '.mov', '.avi', '.m4v'}:
        raise ValueError('Supported extensions: MP4, MOV, AVI, M4V (OpenCV-decoded).')
    if video_path.stat().st_size > MAX_BYTES:
        raise ValueError('Video exceeds 125 MiB. Please trim or export a smaller 30 fps clip.')
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise ValueError('OpenCV cannot decode the selected video. Try an MP4 encoded with H.264 or MPEG-4.')
    try:
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = float(cap.get(cv2.CAP_PROP_FPS))
        frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if not (0 < width <= MAX_WIDTH and 0 < height <= MAX_HEIGHT):
            raise ValueError(f'Video {width}x{height} outside supported resolution <= {MAX_WIDTH}x{MAX_HEIGHT}.')
        if not 29.5 <= fps <= 30.5:
            raise ValueError(f'Video is {fps:.2f} fps. This FIR is calibrated for 30 fps; please convert to 30 fps.')
        if not MIN_FRAMES <= frames <= MAX_FRAMES:
            raise ValueError(f'Video has {frames} frames; supported {MIN_FRAMES}–{MAX_FRAMES} (about 0.6–50 seconds at 30 fps).')
        ok, frame = cap.read()
        if not ok or frame is None:
            raise ValueError('Could not read first video frame.')
        return VideoInfo(frames=frames, width=width, height=height, fps=fps)
    finally:
        cap.release()


def _features(gray: np.ndarray) -> np.ndarray | None:
    h, w = gray.shape
    mask = np.ones_like(gray, dtype=np.uint8) * 255
    # Discourage tracking the target ship / independently moving subject in
    # the central lower region; rely on background/horizon/edge landmarks.
    x0, x1 = int(w * .30), int(w * .70)
    y0, y1 = int(h * .32), int(h * .88)
    mask[y0:y1, x0:x1] = 0
    return cv2.goodFeaturesToTrack(gray, maxCorners=400, qualityLevel=.008,
                                   minDistance=7, blockSize=5, mask=mask)


def estimate_translation(video_path: Path, output_csv: Path) -> dict:
    """Return metrics and write absolute camera X/Y trajectory as Q16.8 CSV.

    Translation model only. Does not compensate rotations, perspective, parallax,
    independent ship motion or severe rolling-shutter distortion.
    """
    info = inspect_video(video_path)
    cap = cv2.VideoCapture(str(video_path))
    x = [0.0]; y = [0.0]
    good_steps, total_features, fallback_steps = 0, 0, 0
    rotation_deg = []
    try:
        ok, frame = cap.read()
        if not ok: raise ValueError('Could not decode first frame')
        previous = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        while True:
            ok, frame = cap.read()
            if not ok: break
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            features = _features(previous)
            if features is None or len(features) < 9:
                raise ValueError('Insufficient stable background features for optical-flow motion estimation. '
                                 'Try a more textured scene, or provide a trajectory CSV.')
            nextpts, st, _ = cv2.calcOpticalFlowPyrLK(previous, gray, features, None,
                winSize=(21, 21), maxLevel=3,
                criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 28, .01))
            if nextpts is None or st is None:
                raise ValueError('Optical flow failed; choose a clearer 30 fps clip.')
            good = st.reshape(-1).astype(bool)
            prev_good, next_good = features.reshape(-1,2)[good], nextpts.reshape(-1,2)[good]
            if len(prev_good) < 9:
                raise ValueError('Too few tracked background points; supply a measured motion trajectory CSV.')
            total_features += len(prev_good)
            matrix, inliers = cv2.estimateAffinePartial2D(prev_good, next_good,
                method=cv2.RANSAC, ransacReprojThreshold=2.4,
                maxIters=1200, confidence=.995, refineIters=10)
            if matrix is not None and inliers is not None and int(inliers.sum()) >= 7:
                dx,dy=float(matrix[0,2]),float(matrix[1,2])
                rotation_deg.append(float(np.degrees(np.arctan2(matrix[1,0],matrix[0,0]))))
                good_steps += 1
            else:
                offsets = next_good-prev_good
                dx,dy=(float(z) for z in np.median(offsets,axis=0))
                fallback_steps += 1
            if abs(dx)>100 or abs(dy)>100:
                raise ValueError('Detected camera jump exceeds 100 px between frames; video is outside this demo scope.')
            x.append(x[-1]+dx)
            y.append(y[-1]+dy)
            previous = gray
    finally:
        cap.release()
    if len(x) != info.frames:
        raise ValueError(f'Video frame-count inconsistent: metadata {info.frames}, decoded {len(x)}')
    out = Path(output_csv)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('w', newline='',encoding='utf-8') as f:
        writer=csv.writer(f)
        writer.writerow(['frame','x_pixels','y_pixels','x_q16_8','y_q16_8'])
        for n,(dx,dy) in enumerate(zip(x,y)):
            qx,qy=int(round(dx*256)),int(round(dy*256))
            if not (-2**23 <= qx < 2**23 and -2**23 <= qy < 2**23):
                raise ValueError('Estimated motion exceeds Q16.8 supported range')
            writer.writerow([n,f'{dx:.8f}',f'{dy:.8f}',qx,qy])
    return {'method':'host_opencv_sparse_optical_flow_ransac_translation',
            'frames':len(x),'fps':info.fps,'ransac_steps':good_steps,
            'fallback_steps':fallback_steps,'average_tracked_features':
            round(total_features/max(1,len(x)-1),1),
            'median_estimated_rotation_deg':float(np.median(np.abs(rotation_deg))) if rotation_deg else None,
            'limitation':'Translation only; camera roll, perspective and independently moving targets remain uncompensated.'}
