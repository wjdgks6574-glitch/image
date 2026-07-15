"""
Wafer ID 이미지 검색 프로그램 (v11)

1동(\\\\172.23.11.134\\ELImages), 2동(\\\\172.23.10.159\\JC02_Cell_ELImage) 안에서
waferID(예: ALL4260526A89264, A1L6265208320270)가 파일명에 포함된 이미지를 찾아
바탕화면\\Wafer검색결과\\{waferID}\\ 폴더로 복사합니다.

waferID에 포함된 날짜를 이용해 {동 경로}\\{라인}\\{YYYYMMDD}\\ 폴더 및 그
전날/다음날(+-1일) 폴더만 검색하므로 전체 폴더를 다 뒤지지 않고 빠르게 찾습니다.

v10 변경사항: waferID 접두사(앞 4자리)로 라인 폴더를 추정하는 PREFIX_LINE_HINTS
테이블 추가 (CT_SORTERRESULT SQL 조회 결과 58,497건에서 접두사별 LotCounter
앞 4자리를 집계해 생성, 2026-07-09~07-12 스냅샷). 검색 시 이 표로 추정한
라인 폴더만 먼저 빠르게 검색하고, 못 찾으면 기존처럼 전체 라인 폴더를
검색하는 안전장치로 자동 전환합니다. 표가 오래돼 실제 배치와 달라져도
결과 누락 없이 항상 fallback으로 커버됩니다.

v11 변경사항: waferID를 한 번에 여러 개(줄바꿈/쉼표/공백으로 구분) 입력해서
한 번에 순서대로 검색할 수 있도록 입력창을 여러 줄 입력으로 변경. waferID마다
바탕화면\\Wafer검색결과\\{waferID}\\ 폴더에 각각 결과가 모입니다.
"""

import os
import re
import shutil
import threading
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
import tkinter as tk
from tkinter import ttk, messagebox

APP_VERSION = "v11"

ROOT_PATHS = [
    r"\\172.23.11.134\ELImages",  # 1동
    r"\\172.23.10.159\JC02_Cell_ELImage",  # 2동
]
RESULT_BASE_FOLDER_NAME = "Wafer검색결과"
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
DATE_SEARCH_WINDOW_DAYS = 1  # waferID 날짜 기준 +-1일까지 검색
SEARCH_WORKERS = 8  # 라인x날짜 폴더를 동시에 검색할 스레드 수
FULL_SEARCH_WORKERS = 16  # 날짜를 못 찾아 전체를 뒤질 때 동시 검색 스레드 수

# LotCounter 앞 2자리 -> 동(ROOT_PATHS 인덱스). "19"=1동, "11"=2동
# (CT_SORTERRESULT 조회 결과 전수 확인: SITEID 9011 -> 항상 "19", 9012C -> 항상 "11")
_SITE_PREFIX_TO_ROOT_INDEX = {"19": 0, "11": 1}

# waferID 접두사(앞 4자리) -> 예상 라인 폴더명(4자리) 후보 목록.
# CT_SORTERRESULT SQL 조회 결과 58,497건(2026-07-09~07-12)에서 접두사별
# LotCounter 앞 4자리를 집계해 생성. 후보가 2개인 접두사는 같은 장비 유형이
# 1동/2동 양쪽에 있어 기간 중 실제로 두 라인 모두에서 발견된 경우.
# 이 표에 없거나 여기서 못 찾으면 search_full 방식으로 전체 라인을 검색함.
PREFIX_LINE_HINTS = {
    "7AL1": ["1120"],
    "8011": ["1120"],
    "8431": ["1120"],
    "8641": ["1120"],
    "9A21": ["1120"],
    "9A22": ["1119"],
    "A2L1": ["1104"],
    "A2L2": ["1104"],
    "A2L3": ["1103"],
    "A2L4": ["1103"],
    "A2L5": ["1104"],
    "A2L6": ["1103"],
    "A2L7": ["1104"],
    "A2L8": ["1103"],
    "A2L9": ["1104"],
    "A2Lq": ["1103"],
    "A3L1": ["1105"],
    "A3L2": ["1105"],
    "A3L3": ["1106"],
    "A3L4": ["1106"],
    "A3L5": ["1906", "1106"],
    "A3L6": ["1105", "1905"],
    "A3L7": ["1106", "1906"],
    "A3L8": ["1105", "1905"],
    "A3L9": ["1106"],
    "A3Lq": ["1105"],
    "A4L1": ["1108"],
    "A4L2": ["1108"],
    "A4L3": ["1107"],
    "A4L4": ["1107"],
    "A4L5": ["1108"],
    "A4L6": ["1107"],
    "A4L7": ["1108"],
    "A4L8": ["1107"],
    "A4L9": ["1108"],
    "A4Lq": ["1107"],
    "A5L1": ["1909", "1109"],
    "A5L2": ["1909", "1109"],
    "A5L3": ["1910", "1110"],
    "A5L4": ["1910", "1110"],
    "A5L5": ["1910", "1110"],
    "A5L6": ["1909", "1109"],
    "A5L7": ["1110"],
    "A5L8": ["1109"],
    "A5L9": ["1110"],
    "A5Lq": ["1109"],
    "A6L3": ["1112"],
    "A6L4": ["1112"],
    "A6L5": ["1112"],
    "A7L3": ["1113"],
    "A7L4": ["1113"],
    "A7L5": ["1114"],
    "AAL1": ["1120"],
    "AAL2": ["1120"],
    "AAL3": ["1119"],
    "AAL4": ["1119"],
    "AAL5": ["1120"],
    "AAL6": ["1119"],
    "ABL1": ["1121"],
    "ABL2": ["1122"],
    "ABL3": ["1121"],
    "ABL4": ["1121"],
    "ABL5": ["1121", "1122"],
    "ABL6": ["1122"],
    "ABL7": ["1122"],
    "ACL1": ["1123"],
    "ACL2": ["1124"],
    "ACL3": ["1123"],
    "ACL4": ["1123"],
    "ACL5": ["1123", "1124"],
    "ACL6": ["1124"],
    "ACL7": ["1124"],
    "ALL3": ["1921"],
    "ALL4": ["1921"],
    "ALL5": ["1921"],
    "ALL6": ["1921"],
    "AML3": ["1922"],
    "AML4": ["1922"],
    "AML5": ["1922"],
    "AML6": ["1922"],
    "AVL1": ["1131"],
    "AVL3": ["1931", "1131"],
    "AVL4": ["1931", "1131"],
    "AVL5": ["1931"],
    "AVL6": ["1931"],
    "AWL1": ["1132"],
    "AWL3": ["1932", "1132"],
    "AWL4": ["1932", "1132"],
    "AWL5": ["1932"],
    "AWL6": ["1932"],
    "AZL1": ["1999"],
    "AZL2": ["1999"],
    "AfL3": ["1941"],
    "AfL4": ["1941"],
    "AfL5": ["1941"],
    "AfL6": ["1941"],
    "AgL3": ["1942"],
    "AgL4": ["1942"],
    "AgL5": ["1942"],
    "AgL6": ["1942"],
    "ApL1": ["1951", "1151"],
    "ApL3": ["1151", "1951"],
    "ApL4": ["1151", "1951"],
    "ApL5": ["1951"],
    "ApL6": ["1951"],
    "AqL1": ["1952", "1152"],
    "AqL3": ["1952", "1152"],
    "AqL4": ["1952", "1152"],
    "AqL5": ["1952"],
    "AqL6": ["1952"],
    "AyL1": ["1160"],
    "AyL3": ["1160"],
    "AyL4": ["1160"],
    "AyL5": ["1160"],
    "AyL6": ["1160"],
    "AzL3": ["1961"],
    "AzL4": ["1961"],
    "AzL5": ["1961"],
    "AzL6": ["1961"],
    "CBL1": ["1196"],
    "CBL3": ["1196"],
    "CBL4": ["1196"],
}

# waferID 안에서 YYMMDD를 추출: 6자리 숫자 뒤에 'A'가 오는 패턴 (예: ALL4260526A89264 -> 260526)
DATE_IN_WAFERID_RE = re.compile(r"(\d{6})A")


def _decode_field_char(ch):
    # 0-9는 숫자 그대로, 10부터는 A=10, B=11, C=12... (표준, A를 건너뛰지 않음)
    if ch.isdigit():
        return int(ch)
    ch = ch.upper()
    if "A" <= ch <= "Z":
        return 10 + (ord(ch) - ord("A"))
    return None


def _extract_date_all_style(wafer_id):
    match = DATE_IN_WAFERID_RE.search(wafer_id)
    if not match:
        return None
    yymmdd = match.group(1)
    yy, mm, dd = yymmdd[0:2], yymmdd[2:4], yymmdd[4:6]
    try:
        return date(2000 + int(yy), int(mm), int(dd))
    except ValueError:
        return None


def _extract_date_long_style(wafer_id):
    # 앞 4자리를 제외한 다음 8자리: YYMMDDHH (전부 숫자)
    if len(wafer_id) < 12:
        return None
    chunk = wafer_id[4:12]
    if not chunk.isdigit():
        return None
    yy, mm, dd = chunk[0:2], chunk[2:4], chunk[4:6]
    try:
        return date(2000 + int(yy), int(mm), int(dd))
    except ValueError:
        return None


def _extract_date_plain6_style(wafer_id):
    # 앞 4자리를 제외한 다음 6자리: YY + MM + DD (전부 숫자, 시간 없음)
    if len(wafer_id) < 10:
        return None
    chunk = wafer_id[4:10]
    if not chunk.isdigit():
        return None
    yy, mm, dd = chunk[0:2], chunk[2:4], chunk[4:6]
    try:
        return date(2000 + int(yy), int(mm), int(dd))
    except ValueError:
        return None


def _extract_date_short_style(wafer_id):
    # 앞 4자리를 제외한 다음 6자리: YY + M(1자리 인코딩) + D(1자리 인코딩) + HH
    if len(wafer_id) < 10:
        return None
    chunk = wafer_id[4:10]
    yy, m_char, d_char, hh = chunk[0:2], chunk[2], chunk[3], chunk[4:6]
    if not (yy.isdigit() and hh.isdigit()):
        return None
    mm = _decode_field_char(m_char)
    dd = _decode_field_char(d_char)
    if mm is None or dd is None:
        return None
    try:
        return date(2000 + int(yy), mm, dd)
    except ValueError:
        return None


def extract_date(wafer_id):
    for extractor in (
        _extract_date_all_style,
        _extract_date_long_style,
        _extract_date_plain6_style,
        _extract_date_short_style,
    ):
        result = extractor(wafer_id)
        if result:
            return result
    return None


def date_range_folders(center_date, window_days=DATE_SEARCH_WINDOW_DAYS):
    offsets = range(-window_days, window_days + 1)
    return [(center_date + timedelta(days=n)).strftime("%Y%m%d") for n in offsets]


def find_desktop_path():
    userprofile = os.environ.get("USERPROFILE") or os.path.expanduser("~")
    candidates = []

    onedrive = os.environ.get("OneDrive")
    if onedrive:
        candidates.append(os.path.join(onedrive, "Desktop"))

    candidates.append(os.path.join(userprofile, "Desktop"))

    for path in candidates:
        if os.path.isdir(path):
            return path

    return candidates[-1]


def is_image_match(filename, wafer_id):
    name, ext = os.path.splitext(filename)
    if ext.lower() not in IMAGE_EXTS:
        return False
    return wafer_id.lower() in filename.lower()


def list_subdirs(path):
    try:
        with os.scandir(path) as entries:
            return [entry.path for entry in entries if entry.is_dir()]
    except OSError:
        return []


def _search_one_dir(wafer_id, target_dir, log):
    log("검색 중: {}".format(target_dir))
    matches = []
    for current_root, _dirs, files in os.walk(target_dir):
        for filename in files:
            if is_image_match(filename, wafer_id):
                matches.append(os.path.join(current_root, filename))
    return matches


def _search_dirs_in_parallel(wafer_id, target_dirs, log, max_workers):
    found = []
    if not target_dirs:
        return found

    with ThreadPoolExecutor(max_workers=min(max_workers, len(target_dirs))) as executor:
        futures = {
            executor.submit(_search_one_dir, wafer_id, target_dir, log): target_dir
            for target_dir in target_dirs
        }
        for future in as_completed(futures):
            target_dir = futures[future]
            try:
                found.extend(future.result())
            except OSError as e:
                log("검색 오류: {} ({})".format(target_dir, e))

    return found


def _accessible_roots(log):
    roots = []
    for root_path in ROOT_PATHS:
        if os.path.isdir(root_path):
            roots.append(root_path)
        else:
            log("네트워크 경로에 접근할 수 없습니다: {}".format(root_path))
    return roots


def _hinted_target_dirs(wafer_id, yyyymmdd_list):
    hints = PREFIX_LINE_HINTS.get(wafer_id[:4])
    if not hints:
        return []

    dirs = []
    for hint in hints:
        root_index = _SITE_PREFIX_TO_ROOT_INDEX.get(hint[:2])
        if root_index is None:
            continue
        line_dir = os.path.join(ROOT_PATHS[root_index], hint)
        for yyyymmdd in yyyymmdd_list:
            dirs.append(os.path.join(line_dir, yyyymmdd))
    return dirs


def search_by_date_folders(wafer_id, yyyymmdd_list, log):
    hinted_dirs = _hinted_target_dirs(wafer_id, yyyymmdd_list)
    if hinted_dirs:
        hint_names = PREFIX_LINE_HINTS[wafer_id[:4]]
        log("waferID 접두사로 라인 폴더 추정: {} (먼저 빠르게 검색)".format(", ".join(hint_names)))
        found = _search_dirs_in_parallel(wafer_id, hinted_dirs, log, SEARCH_WORKERS)
        if found:
            return found
        log("추정한 라인 폴더에서 못 찾아 전체 라인 폴더로 다시 검색합니다...")

    roots = _accessible_roots(log)
    if not roots:
        return []

    line_dirs = [d for root_path in roots for d in list_subdirs(root_path)]
    if not line_dirs:
        log("폴더 목록을 읽는 중 오류가 발생했습니다.")
        return []

    # 폴더 존재 여부를 미리 하나씩(비병렬) 확인하지 않고 바로 병렬 검색에 넘김.
    # os.walk는 없는 폴더를 만나면 조용히 건너뛰므로 사전 확인이 필요 없음.
    target_dirs = [
        os.path.join(line_dir, yyyymmdd)
        for line_dir in line_dirs
        for yyyymmdd in yyyymmdd_list
    ]

    log("검색 대상 폴더 {}개, 최대 {}개씩 동시 검색합니다...".format(
        len(target_dirs), min(SEARCH_WORKERS, len(target_dirs))
    ))
    return _search_dirs_in_parallel(wafer_id, target_dirs, log, SEARCH_WORKERS)


def search_full(wafer_id, log):
    roots = _accessible_roots(log)
    if not roots:
        return []

    line_dirs = [d for root_path in roots for d in list_subdirs(root_path)]
    date_dirs = [d for line_dir in line_dirs for d in list_subdirs(line_dir)]

    if not date_dirs:
        log("검색할 날짜 폴더를 찾지 못했습니다.")
        return []

    log(
        "waferID에서 날짜를 인식하지 못해 전체 {}개 날짜 폴더를 동시에 검색합니다. "
        "폴더 수가 많으면 시간이 걸릴 수 있습니다...".format(len(date_dirs))
    )
    return _search_dirs_in_parallel(wafer_id, date_dirs, log, FULL_SEARCH_WORKERS)


_WAFER_ID_SPLIT_RE = re.compile(r"[,\s]+")


def parse_wafer_ids(text):
    seen = set()
    wafer_ids = []
    for token in _WAFER_ID_SPLIT_RE.split(text.strip()):
        token = token.strip()
        if not token or token in seen:
            continue
        seen.add(token)
        wafer_ids.append(token)
    return wafer_ids


def _copy_one(src, dest_dir):
    dst = os.path.join(dest_dir, os.path.basename(src))
    shutil.copy2(src, dst)
    return dst


def copy_results(files, wafer_id, log):
    desktop = find_desktop_path()
    dest_dir = os.path.join(desktop, RESULT_BASE_FOLDER_NAME, wafer_id)

    if os.path.isdir(dest_dir):
        shutil.rmtree(dest_dir)
    os.makedirs(dest_dir, exist_ok=True)

    copied = []
    with ThreadPoolExecutor(max_workers=min(SEARCH_WORKERS, len(files))) as executor:
        futures = {executor.submit(_copy_one, src, dest_dir): src for src in files}
        for future in as_completed(futures):
            src = futures[future]
            try:
                copied.append(future.result())
            except OSError as e:
                log("복사 실패: {} ({})".format(src, e))

    return dest_dir, copied


class WaferSearchApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Wafer ID 이미지 검색 ({})".format(APP_VERSION))
        self.root.geometry("640x480")

        self.msg_queue = queue.Queue()
        self.search_thread = None
        self.results_base_dir = None

        self._build_ui()
        self.root.after(100, self._poll_queue)

    def _build_ui(self):
        top = ttk.Frame(self.root, padding=10)
        top.pack(fill=tk.X)

        ttk.Label(top, text="Wafer ID (여러 개는 줄바꿈/쉼표/공백으로 구분):").pack(
            anchor=tk.W
        )

        input_frame = ttk.Frame(top)
        input_frame.pack(fill=tk.X, pady=(4, 0))

        self.id_text = tk.Text(input_frame, height=5, wrap=tk.WORD)
        id_scrollbar = ttk.Scrollbar(input_frame, command=self.id_text.yview)
        self.id_text.configure(yscrollcommand=id_scrollbar.set)
        self.id_text.pack(side=tk.LEFT, fill=tk.X, expand=True)
        id_scrollbar.pack(side=tk.LEFT, fill=tk.Y)

        btn_frame = ttk.Frame(top)
        btn_frame.pack(fill=tk.X, pady=(6, 0))

        self.search_btn = ttk.Button(btn_frame, text="검색", command=self.on_search)
        self.search_btn.pack(side=tk.LEFT)

        self.open_btn = ttk.Button(
            btn_frame, text="결과 폴더 열기", command=self.on_open_folder, state=tk.DISABLED
        )
        self.open_btn.pack(side=tk.LEFT, padx=8)

        self.status_var = tk.StringVar(value="waferID를 입력하고 검색을 누르세요.")
        ttk.Label(self.root, textvariable=self.status_var, padding=(10, 0)).pack(
            fill=tk.X
        )

        log_frame = ttk.Frame(self.root, padding=10)
        log_frame.pack(fill=tk.BOTH, expand=True)

        self.log_text = tk.Text(log_frame, wrap=tk.WORD, state=tk.DISABLED)
        scrollbar = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def log(self, message):
        self.msg_queue.put(("log", message))

    def _poll_queue(self):
        try:
            while True:
                kind, payload = self.msg_queue.get_nowait()
                if kind == "log":
                    self.log_text.configure(state=tk.NORMAL)
                    self.log_text.insert(tk.END, payload + "\n")
                    self.log_text.see(tk.END)
                    self.log_text.configure(state=tk.DISABLED)
                elif kind == "status":
                    self.status_var.set(payload)
                elif kind == "done":
                    self._on_search_done(payload)
        except queue.Empty:
            pass
        self.root.after(100, self._poll_queue)

    def on_search(self):
        if self.search_thread and self.search_thread.is_alive():
            return

        wafer_ids = parse_wafer_ids(self.id_text.get("1.0", tk.END))
        if not wafer_ids:
            messagebox.showwarning("입력 필요", "waferID를 입력하세요.")
            return

        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state=tk.DISABLED)

        self.search_btn.configure(state=tk.DISABLED)
        self.open_btn.configure(state=tk.DISABLED)
        self.status_var.set("검색 중... (0/{})".format(len(wafer_ids)))

        self.search_thread = threading.Thread(
            target=self._run_search_many, args=(wafer_ids,), daemon=True
        )
        self.search_thread.start()

    def _run_search_many(self, wafer_ids):
        total = len(wafer_ids)
        ids_with_results = 0
        total_copied = 0

        for index, wafer_id in enumerate(wafer_ids, start=1):
            self.log("===== [{}/{}] {} =====".format(index, total, wafer_id))
            self.msg_queue.put(
                ("status", "검색 중... ({}/{}) {}".format(index, total, wafer_id))
            )
            copied_count = self._search_and_copy_one(wafer_id)
            if copied_count:
                ids_with_results += 1
                total_copied += copied_count

        summary = "{}개 waferID 중 {}개에서 파일 발견, 총 {}개 복사했습니다.".format(
            total, ids_with_results, total_copied
        )
        self.msg_queue.put(("status", summary))
        self.msg_queue.put(("done", total_copied > 0))

    def _search_and_copy_one(self, wafer_id):
        center_date = extract_date(wafer_id)
        if center_date:
            yyyymmdd_list = date_range_folders(center_date)
            self.log(
                "waferID에서 날짜 인식: {} (검색 대상: {})".format(
                    center_date.strftime("%Y-%m-%d"), ", ".join(yyyymmdd_list)
                )
            )
            found = search_by_date_folders(wafer_id, yyyymmdd_list, self.log)
        else:
            found = search_full(wafer_id, self.log)

        if not found:
            self.log("일치하는 이미지를 찾지 못했습니다: {}".format(wafer_id))
            return 0

        self.log("{}개 파일을 찾았습니다. 복사 중...".format(len(found)))
        dest_dir, copied = copy_results(found, wafer_id, self.log)
        for path in copied:
            self.log("복사 완료: {}".format(path))

        return len(copied)

    def _on_search_done(self, has_results):
        self.search_btn.configure(state=tk.NORMAL)
        if has_results:
            desktop = find_desktop_path()
            self.results_base_dir = os.path.join(desktop, RESULT_BASE_FOLDER_NAME)
            self.open_btn.configure(state=tk.NORMAL)

    def on_open_folder(self):
        if self.results_base_dir and os.path.isdir(self.results_base_dir):
            os.startfile(self.results_base_dir)


def main():
    root = tk.Tk()
    WaferSearchApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
