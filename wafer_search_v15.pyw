"""
Wafer ID 이미지 검색 프로그램 (v15)

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

v12 변경사항: 세 번째 경로 \\\\172.23.69.125\\Sorter 추가 검색.
구조: Sorter\\{JC01|JC02}\\{boxed\\{YYYYMMDD} 또는 origin\\{anomaly|defect|undefect}\\{YYYYMMDD}}\\BG{설비번호}\\{YYYYMMDDHH}\\
JC01=1동(SITEID 9011), JC02=2동(SITEID 9012C). BG 뒤 설비번호는
PREFIX_LINE_HINTS의 라인 폴더명 뒤 2자리(예: 1922 -> BG22)와 동일해서
기존 표를 그대로 재사용합니다. 추정한 BG 폴더를 먼저 검색하고, 못 찾으면
해당 날짜 폴더 전체(모든 BG 폴더)로, 그래도 못 찾으면(날짜조차 모르면)
전체로 자동 확대 검색합니다.

v13 변경사항: "중지" 버튼 추가. 누르면 진행 중인 검색을 최대한 빨리 멈추고,
그 시점까지 이미 찾은 이미지는 그대로 복사합니다. 여러 waferID를 검색 중이면
현재 waferID까지만 마무리하고 나머지는 검색하지 않습니다.

v14 변경사항:
1) 중지 시 서버 접속 불가 문제 수정. 기존엔 중지하면 진행 중이던 검색
   스레드를 기다리지 않고 바로 손을 떼서(cancel_futures + wait=False),
   아직 실행 중이던 스레드가 백그라운드에 남은 채로 다음 검색이 또 시작되면
   네트워크 요청이 계속 쌓여 SMB 서버 부하로 접속 불가까지 이어질 수 있었음.
   이제 중지 시 실행 중이던 검색은 끝까지 기다렸다가(wait=True) 완전히
   정리한 뒤에만 다음 작업으로 넘어감. 동시 검색 스레드 수도 낮춤
   (SEARCH_WORKERS 8->4, FULL_SEARCH_WORKERS 16->6).
2) Sorter 라인 폴더 접두사가 사이트마다 다름: JC01은 BG, JC02는 HM
   (예: JC01/BG22, JC02/HM22). 기존엔 항상 BG만 사용했음.

v15 변경사항:
1) 폴더 하나가 응답이 없으면 무한정 멈춰있던 문제 수정. 폴더 응답 대기에
   시간제한(DIR_SEARCH_TIMEOUT_SECONDS)을 두어, 시간 안에 응답이 하나도
   없으면 나머지는 건너뛰고 넘어감 ("중지" 버튼도 이미 블로킹된 네트워크
   호출은 깨울 수 없어서 별도 시간제한이 필요했음).
2) 이미지를 찾으면 그 즉시 검색을 끝냄. 기존엔 hint 폴더 몇 개에서 이미
   찾았어도 같은 단계에 속한 나머지 후보 폴더를 전부 검색한 뒤에야 다음
   단계로 넘어가서, 이미 찾은 뒤에도 오래 걸렸음. 이제 하나라도 찾으면
   해당 검색 단계(1동/2동 라인 후보, Sorter 카테고리 후보 등)의 나머지
   폴더는 실행조차 하지 않아 로그에도 안 남고, "N개 발견: 검색 완료" 로
   바로 표시됨.
"""

import os
import re
import shutil
import threading
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed, wait, FIRST_COMPLETED
from datetime import date, timedelta
import tkinter as tk
from tkinter import ttk, messagebox

APP_VERSION = "v15"

ROOT_PATHS = [
    r"\\172.23.11.134\ELImages",  # 1동
    r"\\172.23.10.159\JC02_Cell_ELImage",  # 2동
]
SORTER_ROOT = r"\\172.23.69.125\Sorter"
# ROOT_PATHS와 같은 인덱스 체계: 0=1동/SITEID 9011/JC01, 1=2동/SITEID 9012C/JC02
SORTER_SITE_FOLDERS = {0: "JC01", 1: "JC02"}
# 라인 폴더 접두사가 사이트마다 다름: JC01은 BG, JC02는 HM (예: BG22, HM22)
SORTER_LINE_PREFIX_BY_SITE_INDEX = {0: "BG", 1: "HM"}
SORTER_CATEGORY_DIRS = [
    "boxed",
    os.path.join("origin", "anomaly"),
    os.path.join("origin", "defect"),
    os.path.join("origin", "undefect"),
]
RESULT_BASE_FOLDER_NAME = "Wafer검색결과"
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
DATE_SEARCH_WINDOW_DAYS = 1  # waferID 날짜 기준 +-1일까지 검색
SEARCH_WORKERS = 4  # 라인x날짜 폴더를 동시에 검색할 스레드 수 (SMB 서버 부하 방지 위해 낮게 유지)
FULL_SEARCH_WORKERS = 6  # 날짜를 못 찾아 전체를 뒤질 때 동시 검색 스레드 수

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


DIR_SEARCH_TIMEOUT_SECONDS = 45  # 폴더 하나 응답을 기다리는 최대 시간


class _CombinedStop:
    """stop_event(사용자 중지) + local_stop(이 검색 단계에서 이미 찾음/시간초과)를 함께 확인."""

    def __init__(self, *events):
        self._events = events

    def is_set(self):
        return any(e.is_set() for e in self._events)


def _search_one_dir(wafer_id, target_dir, log, stop_event):
    if stop_event.is_set():
        # 아직 시작 전인 작업은 네트워크 호출 없이 즉시 건너뜀 (중지했거나
        # 이미 찾은 뒤에 나머지 폴더까지 서버에 요청을 보내는 것을 막기 위함).
        return []

    log("검색 중: {}".format(target_dir))
    matches = []
    for current_root, _dirs, files in os.walk(target_dir):
        if stop_event.is_set():
            break
        for filename in files:
            if is_image_match(filename, wafer_id):
                matches.append(os.path.join(current_root, filename))
    return matches


def _search_dirs_in_parallel(wafer_id, target_dirs, log, max_workers, stop_event):
    found = []
    if not target_dirs:
        return found

    local_stop = threading.Event()
    combined_stop = _CombinedStop(stop_event, local_stop)

    executor = ThreadPoolExecutor(max_workers=min(max_workers, len(target_dirs)))
    try:
        futures = {
            executor.submit(_search_one_dir, wafer_id, target_dir, log, combined_stop): target_dir
            for target_dir in target_dirs
        }
        pending = set(futures)
        while pending:
            done, pending = wait(pending, timeout=DIR_SEARCH_TIMEOUT_SECONDS, return_when=FIRST_COMPLETED)

            if not done:
                log(
                    "{}개 폴더가 {}초 넘게 응답이 없어 나머지를 건너뜁니다 "
                    "(서버가 느리거나 응답이 없는 것 같습니다).".format(
                        len(pending), DIR_SEARCH_TIMEOUT_SECONDS
                    )
                )
                local_stop.set()
                break

            for future in done:
                target_dir = futures[future]
                try:
                    found.extend(future.result())
                except OSError as e:
                    log("검색 오류: {} ({})".format(target_dir, e))

            if found:
                if pending:
                    log("{}개 발견: 검색완료. 남은 {}개 폴더는 검색하지 않습니다.".format(
                        len(found), len(pending)
                    ))
                local_stop.set()
                break

            if stop_event.is_set():
                log("중지 요청으로 나머지 폴더 검색을 건너뜁니다.")
                break
    finally:
        # 대기 중인(아직 시작 안 한) 작업은 즉시 종료되도록 이미 local_stop/
        # stop_event로 신호를 보냈으므로, 남은 정리는 기다리지 않고 진행한다.
        # (진짜로 응답이 없는 폴더의 스레드는 붙잡아도 끝나지 않으므로 wait=True로
        # 무작정 기다리면 위의 시간제한 자체가 무의미해짐.)
        executor.shutdown(wait=False, cancel_futures=True)

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


def search_by_date_folders(wafer_id, yyyymmdd_list, log, stop_event):
    hinted_dirs = _hinted_target_dirs(wafer_id, yyyymmdd_list)
    if hinted_dirs:
        hint_names = PREFIX_LINE_HINTS[wafer_id[:4]]
        log("waferID 접두사로 라인 폴더 추정: {} (먼저 빠르게 검색)".format(", ".join(hint_names)))
        found = _search_dirs_in_parallel(wafer_id, hinted_dirs, log, SEARCH_WORKERS, stop_event)
        if found or stop_event.is_set():
            return found
        log("추정한 라인 폴더에서 못 찾아 전체 라인 폴더로 다시 검색합니다...")

    if stop_event.is_set():
        return []

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
    return _search_dirs_in_parallel(wafer_id, target_dirs, log, SEARCH_WORKERS, stop_event)


def search_full(wafer_id, log, stop_event):
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
    return _search_dirs_in_parallel(wafer_id, date_dirs, log, FULL_SEARCH_WORKERS, stop_event)


def _sorter_hinted_target_dirs(wafer_id, yyyymmdd_list):
    hints = PREFIX_LINE_HINTS.get(wafer_id[:4])
    if not hints:
        return []

    dirs = []
    seen_site_line = set()
    for hint in hints:
        root_index = _SITE_PREFIX_TO_ROOT_INDEX.get(hint[:2])
        site_folder = SORTER_SITE_FOLDERS.get(root_index)
        line_prefix = SORTER_LINE_PREFIX_BY_SITE_INDEX.get(root_index)
        if site_folder is None or line_prefix is None:
            continue
        line_folder = line_prefix + hint[2:4]
        if (site_folder, line_folder) in seen_site_line:
            continue
        seen_site_line.add((site_folder, line_folder))
        for category in SORTER_CATEGORY_DIRS:
            for yyyymmdd in yyyymmdd_list:
                dirs.append(
                    os.path.join(SORTER_ROOT, site_folder, category, yyyymmdd, line_folder)
                )
    return dirs


def search_sorter(wafer_id, yyyymmdd_list, log, stop_event):
    if stop_event.is_set():
        return []

    if not os.path.isdir(SORTER_ROOT):
        log("네트워크 경로에 접근할 수 없습니다: {}".format(SORTER_ROOT))
        return []

    if yyyymmdd_list:
        hinted_dirs = _sorter_hinted_target_dirs(wafer_id, yyyymmdd_list)
        if hinted_dirs:
            log("Sorter: waferID 접두사로 라인(BG/HM) 폴더 추정, 먼저 빠르게 검색...")
            found = _search_dirs_in_parallel(wafer_id, hinted_dirs, log, SEARCH_WORKERS, stop_event)
            if found or stop_event.is_set():
                return found
            log("Sorter: 추정한 라인 폴더에서 못 찾아 날짜 폴더 전체를 검색합니다...")

        target_dirs = [
            os.path.join(SORTER_ROOT, site_folder, category, yyyymmdd)
            for site_folder in SORTER_SITE_FOLDERS.values()
            for category in SORTER_CATEGORY_DIRS
            for yyyymmdd in yyyymmdd_list
        ]
        log("Sorter: 검색 대상 폴더 {}개 검색합니다...".format(len(target_dirs)))
        return _search_dirs_in_parallel(wafer_id, target_dirs, log, SEARCH_WORKERS, stop_event)

    log("Sorter: 날짜를 몰라 전체 폴더를 검색합니다. 시간이 오래 걸릴 수 있습니다...")
    target_dirs = [
        os.path.join(SORTER_ROOT, site_folder, category)
        for site_folder in SORTER_SITE_FOLDERS.values()
        for category in SORTER_CATEGORY_DIRS
    ]
    return _search_dirs_in_parallel(wafer_id, target_dirs, log, FULL_SEARCH_WORKERS, stop_event)


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


SOURCE_LIST_FILENAME = "원본경로.txt"


def _copy_one(src, dest_dir):
    dst = os.path.join(dest_dir, os.path.basename(src))
    shutil.copy2(src, dst)
    return src, dst


def _write_source_list(dest_dir, copied):
    if not copied:
        return
    list_path = os.path.join(dest_dir, SOURCE_LIST_FILENAME)
    try:
        with open(list_path, "w", encoding="utf-8") as f:
            for src, dst in sorted(copied, key=lambda pair: os.path.basename(pair[1])):
                f.write("{} <- {}\n".format(os.path.basename(dst), src))
    except OSError:
        pass


def copy_results(files, wafer_id, log):
    desktop = find_desktop_path()
    dest_dir = os.path.join(desktop, RESULT_BASE_FOLDER_NAME, wafer_id)

    if os.path.isdir(dest_dir):
        shutil.rmtree(dest_dir)
    os.makedirs(dest_dir, exist_ok=True)

    copied = []  # (원본 경로, 복사된 경로) 쌍의 목록
    with ThreadPoolExecutor(max_workers=min(SEARCH_WORKERS, len(files))) as executor:
        futures = {executor.submit(_copy_one, src, dest_dir): src for src in files}
        for future in as_completed(futures):
            src = futures[future]
            try:
                copied.append(future.result())
            except OSError as e:
                log("복사 실패: {} ({})".format(src, e))

    _write_source_list(dest_dir, copied)

    return dest_dir, copied


class WaferSearchApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Wafer ID 이미지 검색 ({})".format(APP_VERSION))
        self.root.geometry("640x480")

        self.msg_queue = queue.Queue()
        self.search_thread = None
        self.stop_event = threading.Event()
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

        self.stop_btn = ttk.Button(
            btn_frame, text="중지", command=self.on_stop, state=tk.DISABLED
        )
        self.stop_btn.pack(side=tk.LEFT, padx=8)

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
        self.stop_btn.configure(state=tk.NORMAL)
        self.open_btn.configure(state=tk.DISABLED)
        self.status_var.set("검색 중... (0/{})".format(len(wafer_ids)))

        self.stop_event.clear()
        self.search_thread = threading.Thread(
            target=self._run_search_many, args=(wafer_ids,), daemon=True
        )
        self.search_thread.start()

    def on_stop(self):
        if not (self.search_thread and self.search_thread.is_alive()):
            return
        self.stop_event.set()
        self.stop_btn.configure(state=tk.DISABLED)
        self.log("===== 중지 요청: 진행 중인 폴더 검색을 정리하고 있습니다 =====")

    def _run_search_many(self, wafer_ids):
        total = len(wafer_ids)
        ids_with_results = 0
        total_copied = 0
        stopped_early = False

        for index, wafer_id in enumerate(wafer_ids, start=1):
            if self.stop_event.is_set():
                stopped_early = True
                self.log("중지됨: 나머지 waferID는 검색하지 않았습니다.")
                break

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
        if stopped_early or self.stop_event.is_set():
            summary += " (중지됨, 검사한 곳까지만 확인)"
        self.msg_queue.put(("status", summary))
        self.msg_queue.put(("done", total_copied > 0))

    def _search_and_copy_one(self, wafer_id):
        center_date = extract_date(wafer_id)
        yyyymmdd_list = None
        if center_date:
            yyyymmdd_list = date_range_folders(center_date)
            self.log(
                "waferID에서 날짜 인식: {} (검색 대상: {})".format(
                    center_date.strftime("%Y-%m-%d"), ", ".join(yyyymmdd_list)
                )
            )
            found = search_by_date_folders(wafer_id, yyyymmdd_list, self.log, self.stop_event)
        else:
            found = search_full(wafer_id, self.log, self.stop_event)

        found += search_sorter(wafer_id, yyyymmdd_list, self.log, self.stop_event)

        if not found:
            self.log("일치하는 이미지를 찾지 못했습니다: {}".format(wafer_id))
            return 0

        found_suffix = " (중지 시점까지)" if self.stop_event.is_set() else ""
        self.log("{}개 파일을 찾았습니다{}. 복사 중...".format(len(found), found_suffix))
        dest_dir, copied = copy_results(found, wafer_id, self.log)
        for src, dst in copied:
            self.log("복사 완료: {} (원본: {})".format(dst, src))
        if copied:
            self.log("원본 경로 목록: {}".format(os.path.join(dest_dir, SOURCE_LIST_FILENAME)))

        return len(copied)

    def _on_search_done(self, has_results):
        self.search_btn.configure(state=tk.NORMAL)
        self.stop_btn.configure(state=tk.DISABLED)
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
