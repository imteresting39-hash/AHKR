# -*- coding: utf-8 -*-
"""IMP2 Arrow Helper v6  (가림 + 해상도 대응판)

동작 원리
- 빨간색 "회피" 글자를 기준점(anchor)으로 줄을 찾는다. (색 마스크 기반이라 해상도/배경에 강함)
  흰색 채팅 글자에 가려진 픽셀은 '모름'으로 처리해서 점수 계산에서 제외한다.
- 방향 단어(위쪽/아래쪽/왼쪽/오른쪽)는 금색 글자 모양을 템플릿과 비교해서 읽는다.
  3줄의 증거를 합산하므로 한 줄이 가려져도 나머지 줄로 읽는다.
- 해상도: 게임 창 클라이언트 높이를 기준으로 1080p 크기로 정규화해서 처리한다.
  글자 크기가 예상과 다르면 여러 배율을 자동으로 탐색한 뒤 고정한다.
- 새 회피 이벤트(맨 아래 칸부터 줄이 한꺼번에 2줄 이상 늘어남)일 때만 방향키를 딱 1번 누른다.
  같은 3줄이 화면에 남아 있거나 위로 밀려도 다시 누르지 않는다.

단축키: F8 = ON/OFF,  F9 = 종료,  F7 = 현재 인식 상태를 debug 폴더에 저장
테스트: python IMP2_Arrow_Helper.py --test 스크린샷.png
"""
import base64, os, sys, time, threading, ctypes
from collections import deque

IS_WIN = sys.platform == 'win32'
try:
    import cv2
    import numpy as np
except Exception as e:  # pragma: no cover
    msg = 'OpenCV/NumPy 로드 실패\n\n' + repr(e) + '\n\npip install opencv-python numpy'
    if IS_WIN:
        try:
            ctypes.windll.user32.MessageBoxW(0, msg, 'IMP2 Arrow Helper 시작 오류', 0x10)
        except Exception:
            pass
    raise

TEMPLATES_B64 = {
    'up': (
        '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'
    ),
    'down': (
        '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'
    ),
    'left': (
        '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'
        'f5qA/w9b7r+DDnH04QAAAABJRU5ErkJggg=='
    ),
    'right': (
        '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'
        'n4m6qdPw/wFwyC4p6Ea66wAAAABJRU5ErkJggg=='
    ),
}

ORDER = ['up', 'down', 'left', 'right']
VK = {'up': 0x26, 'down': 0x28, 'left': 0x25, 'right': 0x27}
KOR = {'up': '위쪽', 'down': '아래쪽', 'left': '왼쪽', 'right': '오른쪽'}

# ───────────────────────── 설정 ─────────────────────────
# 검사 영역(게임 화면 대비 비율): 좌, 상, 우, 하.  메시지는 화면 왼쪽 중앙부에 뜸.
ROI_FRAC = (0.00, 0.20, 0.62, 0.85)
LH_BASE = 26.25            # 1080p 기준 메시지 한 줄 높이(px)
SCALE_CANDIDATES = (1.0, 1.12, 0.89, 1.25, 0.80)   # 글자 크기 배율 후보 (자동 탐색)
ANCHOR_IOU = 0.40          # '회피' 글자 인식 최소 점수 (가려진 부분 제외)
ANCHOR_IOU_LOOSE = 0.33    # 저해상도(확대) 프레임용
MIN_VISIBLE = 0.35         # '회피' 글자가 최소 이만큼은 보여야 인식
SCAN_INTERVAL = 0.004      # 프레임 사이 대기(초)
EVENT_DEBOUNCE = 0.60      # 키 입력 후 이 시간 동안은 새 이벤트 무시
MARGIN_OK = 9.0            # 방향 점수 차이가 이 이상이면 즉시 입력
DECIDE_WAIT = 0.18         # 점수 차이가 작으면 이 시간까지 프레임을 더 모아서 결정
FOCUS_HOLD = 8.0           # 줄을 발견한 뒤 이 시간 동안은 그 주변만 캡처(속도 향상)
WARMUP = 0.35              # 창 복귀/시작 직후 이미 떠 있던 줄은 무시하는 시간
P_HIT, P_FALSE = 0.85, 0.03   # 픽셀 확률 모델 (템플릿 금색일 때 / 아닐 때 이미지가 금색일 확률)


# ───────────────────────── 비전 ─────────────────────────
def _b64_to_bgr(b64):
    im = cv2.imdecode(np.frombuffer(base64.b64decode(b64), np.uint8), cv2.IMREAD_COLOR)
    if im is None:
        raise RuntimeError('템플릿 디코딩 실패')
    return im


def color_masks(bgr, loose=False):
    """순색 빨강/금색/흰색(가림) 마스크 (BGR 순서).
    loose=True: 저해상도를 확대해서 색이 어두운 외곽선과 섞인 경우를 위해 기준을 완화."""
    if not loose:
        red = cv2.inRange(bgr, (0, 0, 170), (75, 75, 255)) // 255
        gold = cv2.inRange(bgr, (0, 130, 190), (100, 235, 255)) // 255
    else:
        red = cv2.inRange(bgr, (0, 0, 140), (90, 90, 255)) // 255
        g = cv2.inRange(bgr, (0, 100, 150), (100, 235, 255))
        _, gch, rch = cv2.split(bgr)
        gold = ((g > 0) & (gch <= rch) & (gch.astype(np.int16) * 2 >= rch)).astype(np.uint8)
    white = cv2.inRange(bgr, (185, 185, 185), (255, 255, 255))
    occl = cv2.dilate(white, np.ones((3, 3), np.uint8)) // 255
    return red, gold, occl


class Vision:
    def __init__(self):
        canon = None
        self.tps = {False: {}, True: {}}
        for d in ORDER:
            bgr = _b64_to_bgr(TEMPLATES_B64[d])
            for loose in (False, True):
                red, gold, _ = color_masks(bgr, loose)
                if not loose:
                    ys, xs = np.nonzero(red)
                    ax0, ax1, ay0, ay1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
                    if canon is None:
                        canon = red[ay0:ay1, ax0:ax1].astype(np.float32)
                g = gold.copy()
                g[:, :ax1 + 2] = 0                      # 공통 부분(회피)은 제외
                t = np.clip(cv2.GaussianBlur(g.astype(np.float32), (0, 0), 0.7) * 1.6, 0, 1)
                p = P_FALSE + (P_HIT - P_FALSE) * t
                lp, lq = np.log(p), np.log(1 - p)
                valid = np.ones_like(t)
                valid[:, :ax1 + 2] = 0
                self.tps[loose][d] = dict(ax=int(ax0), ay=int(ay0), h=bgr.shape[0], w=bgr.shape[1],
                                          dlt=((lp - lq) * valid).astype(np.float32),
                                          lq=(lq * valid).astype(np.float32))
        self.anchor = canon
        self._acache = {}
        self.locked_u = None
        self.last_row_time = 0.0
        self.last_h = None
        self.focus, self.focus_time, self.y_bottom = None, 0.0, None
        self.wide_size = (1, 1)

    # --- 기준점('회피') 찾기 ---
    def _anchor_at(self, u):
        if u not in self._acache:
            a = self.anchor
            if abs(u - 1.0) > 1e-3:
                interp = cv2.INTER_AREA if u < 1 else cv2.INTER_LINEAR
                a = cv2.resize(a, None, fx=u, fy=u, interpolation=interp)
            self._acache[u] = (a, float(a.sum()))
        return self._acache[u]

    def find_anchors(self, red, occl, u=1.0, thr=ANCHOR_IOU, limit=14):
        """빨간 '회피' 글자 위치 탐색. 흰 글자에 가려진 픽셀은 점수 계산에서 제외한다."""
        A, asum = self._anchor_at(u)
        ah, aw = A.shape
        if red.shape[0] < ah or red.shape[1] < aw or cv2.countNonZero(red) < asum * 0.4:
            return []
        R = red.astype(np.float32)
        N = (1 - occl).astype(np.float32)
        ov = cv2.matchTemplate(R, A, cv2.TM_CCORR)
        vis_t = cv2.matchTemplate(N, A, cv2.TM_CCORR)           # 가려지지 않은 템플릿 면적
        hv, wv = ov.shape
        win = cv2.boxFilter(R, -1, (aw, ah), normalize=False, borderType=cv2.BORDER_CONSTANT)
        win = win[ah // 2:ah // 2 + hv, aw // 2:aw // 2 + wv]
        iou = ov / (vis_t + win - ov + 1e-6)
        iou[vis_t < asum * MIN_VISIBLE] = 0               # 거의 다 가려진 곳은 판단 불가
        out = []
        sup_h, sup_w = int(LH_BASE * u * 0.5), int(aw * 0.8)
        while len(out) < limit:
            _, v, _, loc = cv2.minMaxLoc(iou)
            if v < thr:
                break
            x, y = loc
            out.append((int(x), int(y), float(v)))
            iou[max(0, y - sup_h):y + sup_h + 1, max(0, x - sup_w):x + sup_w + 1] = -1
        return out

    @staticmethod
    def align_filter(anchors, tol=5):
        """같은 x 위치에 정렬된 앵커만 남긴다 (다른 빨간 글자 오탐 제거)."""
        if len(anchors) < 2:
            return anchors
        best, best_s = None, -1
        for a in anchors:
            grp = [b for b in anchors if abs(b[0] - a[0]) <= tol]
            s = sum(b[2] for b in grp)
            if s > best_s:
                best, best_s = grp, s
        return sorted(best, key=lambda r: r[1])

    # --- 방향 읽기 ---
    @staticmethod
    def _crop(m, x0, y0, w, h):
        out = np.zeros((h, w), np.float32)
        sx0, sy0 = max(0, x0), max(0, y0)
        sx1, sy1 = min(m.shape[1], x0 + w), min(m.shape[0], y0 + h)
        if sx1 > sx0 and sy1 > sy0:
            out[sy0 - y0:sy1 - y0, sx0 - x0:sx1 - x0] = m[sy0:sy1, sx0:sx1]
        return out

    def read_row(self, gold, occl, ax, ay, loose=False):
        """앵커 위치 (ax, ay)에서 4방향 로그우도를 계산. 가려진 픽셀(occl)은 계산에서 제외."""
        CX, CY, CW, CH = 24, 16, 290, 64
        x0, y0 = ax - CX, ay - CY
        g = self._crop(gold, x0, y0, CW, CH)
        o = self._crop(occl, x0, y0, CW, CH)
        vis = g * (1 - o)
        notocc = 1 - o
        res = {}
        for d in ORDER:
            tp = self.tps[loose][d]
            best = -1e18
            for dy in (-1, 0, 1):
                for dx in (-2, -1, 0, 1, 2):
                    ox, oy = CX - tp['ax'] + dx, CY - tp['ay'] + dy
                    if ox < 0 or oy < 0 or oy + tp['h'] > CH or ox + tp['w'] > CW:
                        continue
                    ll = float((vis[oy:oy + tp['h'], ox:ox + tp['w']] * tp['dlt']).sum()
                               + (notocc[oy:oy + tp['h'], ox:ox + tp['w']] * tp['lq']).sum())
                    if ll > best:
                        best = ll
            res[d] = best
        return res

    # --- 프레임 분석 ---
    @staticmethod
    def _normalize(roi, f):
        interp = cv2.INTER_AREA if f < 1 else cv2.INTER_LINEAR
        return roi if abs(f - 1) < 1e-3 else cv2.resize(roi, None, fx=f, fy=f, interpolation=interp)

    def _rows_from(self, img, origin=(0.0, 0.0), loose=False):
        red, gold, occl = color_masks(img, loose)
        thr = ANCHOR_IOU_LOOSE if loose else ANCHOR_IOU
        anchors = self.align_filter(self.find_anchors(red, occl, 1.0, thr))
        return [dict(x=x + origin[0], y=y + origin[1], lx=x, ly=y, iou=s,
                     ll=self.read_row(gold, occl, x, y, loose)) for x, y, s in anchors]

    def capture_plan(self, wide, client_h, now):
        """다음 캡처 영역 결정.  wide=(x,y,w,h)  반환: ((x,y,w,h), origin(정규화 좌표))
        줄이 최근에 발견됐다면 그 주변만 캡처해서 속도를 올리고, 아니면 넓은 영역을 본다."""
        if self.locked_u is None or self.focus is None or now - self.focus_time > FOCUS_HOLD:
            self.focus, self.y_bottom = None, None
            return wide, (0.0, 0.0)
        f = (1080.0 / client_h) / self.locked_u      # 실제 픽셀 -> 정규화 배율
        nx0, ny0, nx1, ny1 = self.focus
        px0, py0 = int(wide[0] + nx0 / f), int(wide[1] + ny0 / f)
        px1, py1 = int(wide[0] + nx1 / f), int(wide[1] + ny1 / f)
        px0, py0 = max(px0, wide[0]), max(py0, wide[1])
        px1, py1 = min(px1, wide[0] + wide[2]), min(py1, wide[1] + wide[3])
        if px1 - px0 < 64 or py1 - py0 < 48:
            return wide, (0.0, 0.0)
        return (px0, py0, px1 - px0, py1 - py0), ((px0 - wide[0]) * f, (py0 - wide[1]) * f)

    def _update_focus(self, rows, now):
        xs = sorted(r['x'] for r in rows)
        xm = xs[len(xs) // 2]
        yb = max(r['y'] for r in rows)
        self.y_bottom = yb if self.y_bottom is None else max(self.y_bottom, yb)
        W, H = self.wide_size
        self.focus = (max(0.0, xm - 30), max(0.0, self.y_bottom - 14 * LH_BASE),
                      min(W, xm + 340), min(H, self.y_bottom + 3 * LH_BASE))
        self.focus_time = now

    def analyze(self, roi, client_h, now=None, origin=(0.0, 0.0)):
        """roi: 화면에서 캡처한 BGR(실제 해상도).  반환: (rows, 정규화 이미지)
        rows 의 x,y 는 '넓은 검사 영역' 기준 정규화 좌표, lx,ly 는 반환 이미지 기준 좌표."""
        now = time.perf_counter() if now is None else now
        if self.last_h != client_h:
            self.last_h, self.locked_u, self.focus = client_h, None, None
        base_f = 1080.0 / client_h
        if self.locked_u is not None:
            nf = base_f / self.locked_u
            img = self._normalize(roi, nf)
            rows = self._rows_from(img, origin, nf > 1.05)
            if rows:
                self.last_row_time = now
                if origin == (0.0, 0.0):
                    self.wide_size = (img.shape[1], img.shape[0])
                self._update_focus(rows, now)
            elif now - self.last_row_time > 30:
                self.locked_u = None           # 오래 못 찾으면 배율 재탐색
            return rows, img
        # 배율 탐색
        img = self._normalize(roi, base_f)
        red, gold, occl = color_masks(img, base_f > 1.05)
        thr = ANCHOR_IOU_LOOSE if base_f > 1.05 else ANCHOR_IOU
        best_u, best_score = None, 0.0
        for u in SCALE_CANDIDATES:
            an = self.align_filter(self.find_anchors(red, occl, u, thr))
            if len(an) >= 2:
                sc = sum(a[2] for a in an[:3])
                if sc > best_score:
                    best_u, best_score = u, sc
        if best_u is None:
            return [], img
        nf = base_f / best_u
        if abs(best_u - 1.0) > 1e-3:
            img = self._normalize(roi, nf)
        rows = self._rows_from(img, loose=nf > 1.05)
        if len(rows) >= 2:
            self.locked_u = best_u
            self.last_row_time = now
            self.wide_size = (img.shape[1], img.shape[0])
            self._update_focus(rows, now)
        return rows, img


# ───────────────────────── 이벤트 추적 ─────────────────────────
class Tracker:
    """새 회피 이벤트 감지.

    새 이벤트가 오면 맨 아래 칸(slot 0)부터 줄이 한꺼번에 늘어난다.
    그래서 '맨 아래 칸부터 이어진 줄 수'가 기준값보다 2 이상 커지면 새 이벤트로 본다.
    - 기준값 = 직전 몇 초 동안의 최대 줄 수 (가장 최근 RECENT_GUARD 구간은 제외:
      새 줄이 조금씩 보이기 시작해도 기준값이 같이 올라가서 놓치는 일이 없도록)
    - 인식이 한두 프레임 흔들려도 기준값이 유지되므로 중복 입력이 나가지 않는다.
    - 3줄 이상이 한꺼번에 사라져서 유지되면(오래된 이벤트 만료) 기준값을 낮춘다.
    - 다른 메시지에 줄이 위로 밀려 올라간 경우도 기준값을 현재 줄 수로 낮춘다.
    - 줄이 하나도 없는 상태가 이어지면 기준값을 0으로 되돌린다.
    """
    BASELINE_WINDOW = 1.2     # 기준값을 보는 시간 창(초)
    RECENT_GUARD = 0.12       # 최근 이 구간은 기준값에서 제외
    DROP_CONFIRM = 0.20       # 3줄 이상 감소가 이만큼 지속되면 만료로 판단
    EMPTY_RESET = 0.20        # 줄이 하나도 없는 상태가 이만큼 지속되면 기준값 초기화

    def __init__(self):
        self.reset()

    def reset(self):
        self.y_ref = None
        self.hist = deque()          # (time, run_length, top_slot, 인식된 줄 수)
        self.accounted = (0, 0.0)    # (run, expire_time): 이미 처리한 줄 수
        self.empty_since = None
        self.warm_until = time.perf_counter() + WARMUP
        self.bottom = []

    def _slots(self, rows):
        lh = LH_BASE
        ys = [r['y'] for r in rows]
        if not ys:
            return {}
        if self.y_ref is None or max(ys) > self.y_ref + 0.5 * lh:
            self.y_ref = max(ys)               # 줄은 맨 아래 칸보다 더 아래로 갈 수 없다
        slots = {}
        for r in rows:
            k = int(round((self.y_ref - r['y']) / lh))
            if k >= 0:
                slots[k] = r
        return slots

    @staticmethod
    def _run(slots):
        """맨 아래 칸(0)부터 이어진 줄 수. 한 칸 빈 곳은 건너뜀(일시적 인식 실패 대비)."""
        n, k, miss = 0, 0, 0
        while k < 12:
            if k in slots:
                n += 1
                miss = 0
            else:
                miss += 1
                if miss >= 2:
                    break
            k += 1
        return n

    def update(self, rows, now):
        slots = self._slots(rows)
        run = self._run(slots)
        top = max(slots) if slots else -1
        self.bottom = [slots[k] for k in (0, 1, 2) if k in slots]
        if rows:
            self.empty_since = None
        else:
            if self.empty_since is None:
                self.empty_since = now
            if now - self.empty_since >= self.EMPTY_RESET:
                self.hist.clear()
                self.accounted = (0, 0.0)
        while self.hist and now - self.hist[0][0] > self.BASELINE_WINDOW:
            self.hist.popleft()
        # 한 이벤트(3줄) 이상이 한꺼번에 사라져서 그 상태가 이어지면 = 만료. 기준값을 낮춘다.
        # (1~2줄이 잠깐 안 보이는 인식 흔들림은 여기에 해당하지 않는다)
        if self.hist:
            recent = [e for e in self.hist if now - e[0] < self.DROP_CONFIRM]
            peak = max(e[3] for e in self.hist)
            if len(recent) >= 2 and max(max(e[3] for e in recent), len(rows)) <= peak - 3:
                self.hist = deque(recent)
                self.accounted = (max(e[1] for e in recent), now + self.BASELINE_WINDOW)
        old = [(e[1], e[2]) for e in self.hist if now - e[0] >= self.RECENT_GUARD]
        base = max([r for r, _ in old], default=0)
        prev_top = max([tp for _, tp in old], default=-1)
        if now < self.accounted[1]:
            base = max(base, self.accounted[0])
        warm = now < self.warm_until
        event = (not warm) and run - base >= 2
        if event or warm:
            self.accounted = (run, now + self.BASELINE_WINDOW)
        elif prev_top >= 0 and top > prev_top and run <= base:
            # 맨 아래 줄은 늘지 않았는데 가장 높은 줄이 더 위로 올라감 = 다른 메시지에 밀려 올라간 것.
            self.hist.clear()
            self.accounted = (run, now + self.BASELINE_WINDOW)
        self.hist.append((now, run, top, len(rows)))
        return event


def decide(acc):
    ranked = sorted(acc.items(), key=lambda kv: -kv[1])
    return ranked[0][0], ranked[0][1] - ranked[1][1]


def sum_ll(rows):
    acc = {d: 0.0 for d in ORDER}
    for r in rows:
        for d in ORDER:
            acc[d] += r['ll'][d]
    return acc


# ───────────────────────── Windows 입출력 ─────────────────────────
if IS_WIN:
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [('biSize', wintypes.DWORD), ('biWidth', wintypes.LONG), ('biHeight', wintypes.LONG),
                    ('biPlanes', wintypes.WORD), ('biBitCount', wintypes.WORD), ('biCompression', wintypes.DWORD),
                    ('biSizeImage', wintypes.DWORD), ('biXPelsPerMeter', wintypes.LONG),
                    ('biYPelsPerMeter', wintypes.LONG), ('biClrUsed', wintypes.DWORD),
                    ('biClrImportant', wintypes.DWORD)]

    class BITMAPINFO(ctypes.Structure):
        _fields_ = [('bmiHeader', BITMAPINFOHEADER), ('bmiColors', wintypes.DWORD * 3)]

    SRCCOPY = 0x00CC0020

    def grab_region(x, y, w, h):
        w, h = max(1, int(w)), max(1, int(h))
        hdc = user32.GetDC(0)
        if not hdc:
            raise RuntimeError('GetDC 실패')
        memdc = gdi32.CreateCompatibleDC(hdc)
        hbmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
        try:
            gdi32.SelectObject(memdc, hbmp)
            if not gdi32.BitBlt(memdc, 0, 0, w, h, hdc, int(x), int(y), SRCCOPY):
                raise RuntimeError('BitBlt 실패')
            bmi = BITMAPINFO()
            bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
            bmi.bmiHeader.biWidth, bmi.bmiHeader.biHeight = w, -h
            bmi.bmiHeader.biPlanes, bmi.bmiHeader.biBitCount = 1, 32
            buf = (ctypes.c_ubyte * (w * h * 4))()
            if not gdi32.GetDIBits(memdc, hbmp, 0, h, ctypes.byref(buf), ctypes.byref(bmi), 0):
                raise RuntimeError('GetDIBits 실패')
            return np.frombuffer(buf, np.uint8).reshape((h, w, 4))[:, :, :3].copy()
        finally:
            gdi32.DeleteObject(hbmp)
            gdi32.DeleteDC(memdc)
            user32.ReleaseDC(0, hdc)

    def game_client():
        """포그라운드가 워크래프트면 (x, y, w, h) = 클라이언트 영역의 화면 좌표/크기, 아니면 None."""
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return None
        b = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(hwnd, b, 512)
        s = b.value.lower()
        if 'warcraft' not in s and '워크래프트' not in s:
            return None
        rc = wintypes.RECT()
        user32.GetClientRect(hwnd, ctypes.byref(rc))
        pt = wintypes.POINT(0, 0)
        user32.ClientToScreen(hwnd, ctypes.byref(pt))
        w, h = rc.right - rc.left, rc.bottom - rc.top
        if w < 320 or h < 240 or user32.IsIconic(hwnd):
            return None
        return pt.x, pt.y, w, h

    def send_key(d):
        vk = VK[d]
        user32.keybd_event(vk, 0, 0, 0)
        time.sleep(.015)
        user32.keybd_event(vk, 0, 2, 0)

    def key_down(vk):
        return bool(user32.GetAsyncKeyState(vk) & 0x8000)


def roi_of(w, h):
    fx0, fy0, fx1, fy1 = ROI_FRAC
    x0, y0 = int(w * fx0), int(h * fy0)
    return x0, y0, max(8, int(w * fx1) - x0), max(8, int(h * fy1) - y0)


def draw_debug(img, rows):
    vis = img.copy()
    for r in rows:
        best, _ = decide(r['ll'])
        cv2.rectangle(vis, (int(r['lx']), int(r['ly'])), (int(r['lx']) + 230, int(r['ly']) + 26), (0, 255, 0), 1)
        cv2.putText(vis, '%s %.2f' % (best, r['iou']), (int(r['lx']) + 235, int(r['ly']) + 18),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
    return vis


# ───────────────────────── 실행 ─────────────────────────
def run_test(path):
    full = cv2.imdecode(np.fromfile(path, np.uint8), cv2.IMREAD_COLOR)
    if full is None:
        print('이미지를 읽을 수 없습니다:', path)
        return
    h, w = full.shape[:2]
    x, y, rw, rh = roi_of(w, h)
    roi = full[y:y + rh, x:x + rw]
    vis = Vision()
    t0 = time.perf_counter()
    rows, img = vis.analyze(roi, h)
    dt = (time.perf_counter() - t0) * 1000
    print('해상도 %dx%d / 분석 %.1fms / 배율 u=%s / 인식된 줄 %d개' % (w, h, dt, vis.locked_u, len(rows)))
    for r in rows:
        d, m = decide(r['ll'])
        print('  y=%4d  anchor=%.2f  -> %-5s(%s)  margin=%.1f' % (r['y'], r['iou'], d, KOR[d], m))
    if rows:
        d, m = decide(sum_ll(rows[-3:]))
        print('=> 최종 방향: %s (%s)  margin=%.1f' % (d, KOR[d], m))
    out = os.path.splitext(path)[0] + '_debug.png'
    cv2.imencode('.png', draw_debug(img, rows))[1].tofile(out)
    print('디버그 이미지:', out)


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == '--test':
        return run_test(sys.argv[2])
    if not IS_WIN:
        print('실시간 모드는 Windows 전용입니다. --test 이미지경로 로 테스트하세요.')
        return
    state = {'run': True, 'active': True, 'dump': False}

    def hotkeys():
        o7 = o8 = o9 = False
        while state['run']:
            f7, f8, f9 = key_down(0x76), key_down(0x77), key_down(0x78)
            if f8 and not o8:
                state['active'] = not state['active']
                print('[IMP2] 자동입력 ' + ('ON' if state['active'] else 'OFF'), flush=True)
            if f9 and not o9:
                state['run'] = False
            if f7 and not o7:
                state['dump'] = True
            o7, o8, o9 = f7, f8, f9
            time.sleep(.03)
    threading.Thread(target=hotkeys, daemon=True).start()

    vis, trk = Vision(), Tracker()
    print('IMP2 Arrow Helper v6 | F8=ON/OFF | F9=종료 | F7=디버그 저장', flush=True)
    last_press, pending, was_game = 0.0, None, False
    last_img, last_rows = None, []
    while state['run']:
        try:
            g = game_client() if state['active'] else None
            if g is None:
                was_game, pending = False, None
                time.sleep(.1)
                continue
            if not was_game:
                trk.reset()
                was_game = True
            cx, cy, cw, ch = g
            now = time.perf_counter()
            (rx, ry, rw, rh), origin = vis.capture_plan(roi_of(cw, ch), ch, now)
            roi = grab_region(cx + rx, cy + ry, rw, rh)
            rows, img = vis.analyze(roi, ch, now, origin)
            last_img, last_rows = img, rows
            new_event = trk.update(rows, now)

            if new_event and pending is None and now - last_press >= EVENT_DEBOUNCE:
                pending = {'t0': now, 'acc': {d: 0.0 for d in ORDER}}
                print('[IMP2] 새 회피 감지 (줄 %d개)' % len(trk.bottom), flush=True)
            if pending is not None:
                if trk.bottom:
                    for d, v in sum_ll(trk.bottom).items():
                        pending['acc'][d] += v
                    d, m = decide(pending['acc'])
                    if m >= MARGIN_OK or now - pending['t0'] >= DECIDE_WAIT:
                        print('[IMP2] -> %s (%s) margin=%.1f, %.0fms' % (d, KOR[d], m, (now - pending['t0']) * 1000),
                              flush=True)
                        send_key(d)
                        last_press, pending = time.perf_counter(), None
                elif now - pending['t0'] >= DECIDE_WAIT:
                    pending = None          # 읽을 줄이 없으면 취소
            if state['dump'] and last_img is not None:
                state['dump'] = False
                folder = 'debug_' + time.strftime('%H%M%S')
                os.makedirs(folder, exist_ok=True)
                cv2.imwrite(os.path.join(folder, 'roi_normalized.png'), last_img)
                cv2.imwrite(os.path.join(folder, 'overlay.png'), draw_debug(last_img, last_rows))
                print('[IMP2] 디버그 저장:', folder, flush=True)
            time.sleep(SCAN_INTERVAL)
        except Exception as e:
            print('[IMP2] ERROR:', repr(e), flush=True)
            time.sleep(.5)
    print('IMP2 Arrow Helper 종료.', flush=True)


if __name__ == '__main__':
    main()
