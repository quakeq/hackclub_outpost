"""Volumetric slice rasterizer for a hinged 16×16 LED panel."""

import math

try:
    from config import (
        JOINT_COLOR,
        PANEL_H,
        PANEL_W,
        SKELETON_COLOR,
        SLICE_THICKNESS,
        VOLUME_SCALE,
    )
except ImportError:
    PANEL_W = 16
    PANEL_H = 16
    SLICE_THICKNESS = 0.04
    VOLUME_SCALE = 0.80
    SKELETON_COLOR = (0, 255, 80)
    JOINT_COLOR = (255, 255, 255)

# MediaPipe PoseLandmarksConnections.POSE_LANDMARKS
POSE_CONNECTIONS = (
    (0, 1),
    (1, 2),
    (2, 3),
    (3, 7),
    (0, 4),
    (4, 5),
    (5, 6),
    (6, 8),
    (9, 10),
    (11, 12),
    (11, 13),
    (13, 15),
    (15, 17),
    (15, 19),
    (15, 21),
    (17, 19),
    (12, 14),
    (14, 16),
    (16, 18),
    (16, 20),
    (16, 22),
    (18, 20),
    (11, 23),
    (12, 24),
    (23, 24),
    (23, 25),
    (25, 27),
    (27, 29),
    (27, 31),
    (29, 31),
    (24, 26),
    (26, 28),
    (28, 30),
    (28, 32),
    (30, 32),
)

HIP_L = 23
HIP_R = 24
NUM_LANDMARKS = 33


def make_framebuffer(color=(0, 0, 0)):
    """Return a PANEL_H × PANEL_W list of (r, g, b) tuples."""
    row = [color] * PANEL_W
    return [list(row) for _ in range(PANEL_H)]


def clear_framebuffer(fb, color=(0, 0, 0)):
    for y in range(PANEL_H):
        for x in range(PANEL_W):
            fb[y][x] = color


def set_pixel(fb, col, row, color):
    if 0 <= col < PANEL_W and 0 <= row < PANEL_H:
        fb[row][col] = color


def draw_line(fb, x0, y0, x1, y1, color):
    """Bresenham line on the framebuffer."""
    x0 = int(round(x0))
    y0 = int(round(y0))
    x1 = int(round(x1))
    y1 = int(round(y1))
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    while True:
        set_pixel(fb, x0, y0, color)
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


def normalize_pose(landmarks):
    """Map MediaPipe landmarks into volume coords (X right, Y up, Z depth).

    Returns a list of (x, y, z) floats centered on the hip midpoint and
    scaled so |Y| fits VOLUME_SCALE of half-height.
    """
    if landmarks is None or len(landmarks) < NUM_LANDMARKS:
        return None

    hx = 0.5 * (landmarks[HIP_L][0] + landmarks[HIP_R][0])
    hy = 0.5 * (landmarks[HIP_L][1] + landmarks[HIP_R][1])
    hz = 0.5 * (landmarks[HIP_L][2] + landmarks[HIP_R][2])

    centered = []
    max_abs_y = 1e-6
    for lm in landmarks:
        # MediaPipe Y grows downward; flip so volume Y is up.
        x = lm[0] - hx
        y = -(lm[1] - hy)
        z = lm[2] - hz
        centered.append((x, y, z))
        ay = abs(y)
        if ay > max_abs_y:
            max_abs_y = ay

    # Fit height into ±VOLUME_SCALE (panel maps Y ∈ [-1, 1]).
    scale = VOLUME_SCALE / max_abs_y
    return [(p[0] * scale, p[1] * scale, p[2] * scale) for p in centered]


def _plane_distance(x, z, sin_t, cos_t):
    """Signed distance to panel plane at angle θ (axis = Y)."""
    return x * sin_t - z * cos_t


def _project_to_panel(x, y, z, sin_t, cos_t):
    """Map a 3D point assumed near the plane to (col, row) floats.

    Radial coordinate r = x·cosθ + z·sinθ (distance from hinge along panel).
    Y ∈ [-1, 1] → row ∈ [0, H-1] (top = smaller Y? head is positive Y after flip
    of MediaPipe... actually after flip, head has larger MediaPipe-up = positive Y
    near shoulders/head above hips). Map +Y → smaller row (top of panel).
    """
    r = x * cos_t + z * sin_t
    if r < 0.0:
        return None
    # Volume half-extent ≈ 1.0; map r∈[0,1] → col∈[0, W-1]
    col = r * (PANEL_W - 1)
    # y = +1 (head) → row 0; y = -1 (feet) → row H-1
    row = (1.0 - y) * 0.5 * (PANEL_H - 1)
    return col, row


def _clip_segment_to_slice(a, b, sin_t, cos_t, eps):
    """Yield (col, row) samples where segment AB crosses the slice slab."""
    da = _plane_distance(a[0], a[2], sin_t, cos_t)
    db = _plane_distance(b[0], b[2], sin_t, cos_t)

    # Entire segment far from plane
    if da * db > 0 and abs(da) > eps and abs(db) > eps:
        return

    points = []

    # Endpoints inside slab
    if abs(da) <= eps:
        p = _project_to_panel(a[0], a[1], a[2], sin_t, cos_t)
        if p is not None:
            points.append(p)
    if abs(db) <= eps:
        p = _project_to_panel(b[0], b[1], b[2], sin_t, cos_t)
        if p is not None:
            points.append(p)

    # Zero-crossing of the plane (even if endpoints outside slab)
    if da * db < 0.0 or (abs(da) > eps and abs(db) <= eps) or (
        abs(db) > eps and abs(da) <= eps
    ):
        denom = da - db
        if abs(denom) > 1e-9:
            t = da / denom
            if 0.0 <= t <= 1.0:
                x = a[0] + t * (b[0] - a[0])
                y = a[1] + t * (b[1] - a[1])
                z = a[2] + t * (b[2] - a[2])
                # Only accept if within thickened slice
                d = _plane_distance(x, z, sin_t, cos_t)
                if abs(d) <= eps * 2.0:
                    p = _project_to_panel(x, y, z, sin_t, cos_t)
                    if p is not None:
                        points.append(p)

    # If both ends are in the slab, draw the projected segment
    if abs(da) <= eps and abs(db) <= eps:
        if len(points) >= 2:
            return points[0], points[1]
        return

    if len(points) >= 2:
        return points[0], points[1]
    if len(points) == 1:
        # Degenerate: single pixel
        return points[0], points[0]
    return


def render_slice(landmarks, theta, fb=None, eps=None):
    """Rasterize pose cross-section at motor angle theta (radians).

    landmarks: raw MediaPipe normalized landmarks or already a list of tuples.
    """
    if fb is None:
        fb = make_framebuffer()
    else:
        clear_framebuffer(fb)

    if eps is None:
        eps = SLICE_THICKNESS

    pose = normalize_pose(landmarks)
    if pose is None:
        return fb

    sin_t = math.sin(theta)
    cos_t = math.cos(theta)

    # Bones
    for i, j in POSE_CONNECTIONS:
        if i >= len(pose) or j >= len(pose):
            continue
        clipped = _clip_segment_to_slice(pose[i], pose[j], sin_t, cos_t, eps)
        if clipped is None:
            continue
        (c0, r0), (c1, r1) = clipped
        draw_line(fb, c0, r0, c1, r1, SKELETON_COLOR)

    # Joints as dots when near the slice
    for p in pose:
        d = _plane_distance(p[0], p[2], sin_t, cos_t)
        if abs(d) > eps:
            continue
        proj = _project_to_panel(p[0], p[1], p[2], sin_t, cos_t)
        if proj is None:
            continue
        set_pixel(fb, int(round(proj[0])), int(round(proj[1])), JOINT_COLOR)

    return fb


def make_tpose_landmarks():
    """Synthetic MediaPipe-like landmarks for bring-up without a camera."""
    # Rough standing T-pose in normalized image coords (y down).
    pts = [(0.5, 0.5, 0.0)] * NUM_LANDMARKS

    def set_lm(i, x, y, z=0.0):
        pts[i] = (x, y, z)

    # Nose / eyes / ears (simplified)
    set_lm(0, 0.50, 0.18, 0.0)
    set_lm(1, 0.48, 0.16, 0.0)
    set_lm(2, 0.47, 0.16, 0.0)
    set_lm(3, 0.46, 0.16, 0.0)
    set_lm(4, 0.52, 0.16, 0.0)
    set_lm(5, 0.53, 0.16, 0.0)
    set_lm(6, 0.54, 0.16, 0.0)
    set_lm(7, 0.45, 0.18, 0.0)
    set_lm(8, 0.55, 0.18, 0.0)
    set_lm(9, 0.48, 0.22, 0.0)
    set_lm(10, 0.52, 0.22, 0.0)

    # Shoulders / elbows / wrists (arms out)
    set_lm(11, 0.40, 0.30, 0.0)  # L shoulder
    set_lm(12, 0.60, 0.30, 0.0)  # R shoulder
    set_lm(13, 0.28, 0.30, 0.0)  # L elbow
    set_lm(14, 0.72, 0.30, 0.0)  # R elbow
    set_lm(15, 0.16, 0.30, 0.0)  # L wrist
    set_lm(16, 0.84, 0.30, 0.0)  # R wrist
    for hand in (17, 19, 21):
        set_lm(hand, 0.14, 0.30, 0.0)
    for hand in (18, 20, 22):
        set_lm(hand, 0.86, 0.30, 0.0)

    # Hips / knees / ankles
    set_lm(23, 0.44, 0.55, 0.0)
    set_lm(24, 0.56, 0.55, 0.0)
    set_lm(25, 0.44, 0.72, 0.0)
    set_lm(26, 0.56, 0.72, 0.0)
    set_lm(27, 0.44, 0.90, 0.0)
    set_lm(28, 0.56, 0.90, 0.0)
    set_lm(29, 0.42, 0.94, 0.0)
    set_lm(30, 0.58, 0.94, 0.0)
    set_lm(31, 0.44, 0.96, 0.0)
    set_lm(32, 0.56, 0.96, 0.0)

    return pts
