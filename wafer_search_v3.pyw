"""
Wafer ID 이미지 검색 프로그램 (v3)

\\\\172.23.11.134\\ELImages 안에서 waferID(예: ALL4260526A89264)가
파일명에 포함된 이미지를 찾아 바탕화면\\Wafer검색결과\\{waferID}\\ 폴더로 복사합니다.

waferID에 포함된 날짜(YYMMDD, 예: 260526 -> 2026-05-26)를 이용해
ELImages\\{라인}\\{YYYYMMDD}\\ 폴더 및 그 전날/다음날(+-1일) 폴더만 검색하므로
전체 폴더를 다 뒤지지 않고 빠르게 찾습니다.

v3 변경사항: 실행 파일을 .pyw 하나로 통합. Windows에서 .pyw는 기본적으로
pythonw.exe로 실행되므로, 이 파일 하나만 더블클릭하면 cmd 콘솔 창 없이 바로
실행됩니다 (별도 .bat/.vbs 런처 불필요).
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

APP_VERSION = "v3"

ROOT_PATH = r"\\172.23.11.134\ELImages"
RESULT_BASE_FOLDER_NAME = "Wafer검색결과"
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
DATE_SEARCH_WINDOW_DAYS = 1  # waferID 날짜 기준 +-1일까지 검색
SEARCH_WORKERS = 8  # 라인x날짜 폴더를 동시에 검색할 스레드 수

# waferID 안에서 YYMMDD를 추출: 6자리 숫자 뒤에 'A'가 오는 패턴 (예: ALL4260526A89264 -> 260526)
DATE_IN_WAFERID_RE = re.compile(r"(\d{6})A")


def extract_date(wafer_id):
    match = DATE_IN_WAFERID_RE.search(wafer_id)
    if not match:
        return None
    yymmdd = match.group(1)
    yy, mm, dd = yymmdd[0:2], yymmdd[2:4], yymmdd[4:6]
    try:
        return date(2000 + int(yy), int(mm), int(dd))
    except ValueError:
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


def _search_one_dir(wafer_id, date_dir, log):
    log("검색 중: {}".format(date_dir))
    matches = []
    for current_root, _dirs, files in os.walk(date_dir):
        for filename in files:
            if is_image_match(filename, wafer_id):
                matches.append(os.path.join(current_root, filename))
    return matches


def search_by_date_folders(wafer_id, yyyymmdd_list, log):
    found = []
    if not os.path.isdir(ROOT_PATH):
        log("네트워크 경로에 접근할 수 없습니다: {}".format(ROOT_PATH))
        return found

    try:
        line_dirs = [
            os.path.join(ROOT_PATH, name)
            for name in os.listdir(ROOT_PATH)
            if os.path.isdir(os.path.join(ROOT_PATH, name))
        ]
    except OSError as e:
        log("폴더 목록을 읽는 중 오류: {}".format(e))
        return found

    target_dirs = [
        os.path.join(line_dir, yyyymmdd)
        for line_dir in line_dirs
        for yyyymmdd in yyyymmdd_list
        if os.path.isdir(os.path.join(line_dir, yyyymmdd))
    ]

    if not target_dirs:
        return found

    with ThreadPoolExecutor(max_workers=min(SEARCH_WORKERS, len(target_dirs))) as executor:
        futures = {
            executor.submit(_search_one_dir, wafer_id, date_dir, log): date_dir
            for date_dir in target_dirs
        }
        for future in as_completed(futures):
            date_dir = futures[future]
            try:
                found.extend(future.result())
            except OSError as e:
                log("검색 오류: {} ({})".format(date_dir, e))

    return found


def search_full(wafer_id, log):
    found = []
    if not os.path.isdir(ROOT_PATH):
        log("네트워크 경로에 접근할 수 없습니다: {}".format(ROOT_PATH))
        return found

    log("날짜 정보를 알 수 없어 전체 폴더를 검색합니다. 시간이 오래 걸릴 수 있습니다...")
    for current_root, _dirs, files in os.walk(ROOT_PATH):
        for filename in files:
            if is_image_match(filename, wafer_id):
                found.append(os.path.join(current_root, filename))

    return found


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
        self.root.geometry("640x420")

        self.msg_queue = queue.Queue()
        self.search_thread = None
        self.last_dest_dir = None

        self._build_ui()
        self.root.after(100, self._poll_queue)

    def _build_ui(self):
        top = ttk.Frame(self.root, padding=10)
        top.pack(fill=tk.X)

        ttk.Label(top, text="Wafer ID:").pack(side=tk.LEFT)
        self.entry = ttk.Entry(top, width=40)
        self.entry.pack(side=tk.LEFT, padx=8)
        self.entry.bind("<Return>", lambda _e: self.on_search())

        self.search_btn = ttk.Button(top, text="검색", command=self.on_search)
        self.search_btn.pack(side=tk.LEFT)

        self.open_btn = ttk.Button(
            top, text="결과 폴더 열기", command=self.on_open_folder, state=tk.DISABLED
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

        wafer_id = self.entry.get().strip()
        if not wafer_id:
            messagebox.showwarning("입력 필요", "waferID를 입력하세요.")
            return

        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state=tk.DISABLED)

        self.search_btn.configure(state=tk.DISABLED)
        self.open_btn.configure(state=tk.DISABLED)
        self.status_var.set("검색 중...")

        self.search_thread = threading.Thread(
            target=self._run_search, args=(wafer_id,), daemon=True
        )
        self.search_thread.start()

    def _run_search(self, wafer_id):
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
            self.msg_queue.put(("status", "일치하는 이미지를 찾지 못했습니다."))
            self.msg_queue.put(("done", None))
            return

        self.log("{}개 파일을 찾았습니다. 복사 중...".format(len(found)))
        dest_dir, copied = copy_results(found, wafer_id, self.log)
        for path in copied:
            self.log("복사 완료: {}".format(path))

        self.msg_queue.put(
            ("status", "{}개 파일을 {} 폴더로 복사했습니다.".format(len(copied), dest_dir))
        )
        self.msg_queue.put(("done", dest_dir))

    def _on_search_done(self, dest_dir):
        self.search_btn.configure(state=tk.NORMAL)
        if dest_dir:
            self.last_dest_dir = dest_dir
            self.open_btn.configure(state=tk.NORMAL)

    def on_open_folder(self):
        if self.last_dest_dir and os.path.isdir(self.last_dest_dir):
            os.startfile(self.last_dest_dir)


def main():
    root = tk.Tk()
    WaferSearchApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
