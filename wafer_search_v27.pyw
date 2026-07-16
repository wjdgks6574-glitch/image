"""
Wafer ID 이미지 검색 프로그램 (v19)

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
3) 복사된 이미지 옆에 원본경로.txt를 만들어 각 이미지의 원본 네트워크
   경로를 기록.

v16 변경사항:
1) 네 번째 경로 \\\\172.23.69.112\\Result_Images 추가 검색.
   구조: Result_Images\\{jc01|jc02}\\result\\{boxed|origin}\\{YYYYMMDD}\\{라인폴더}\\{HH}\\
   라인폴더는 PREFIX_LINE_HINTS 값을 그대로 사용(예: 1932, 1132 - Sorter의
   BG/HM 접두사와 달리 접두사 변환 없음). 라인폴더 뒤에 "_F"가 붙는 변형이
   같은 날짜에 같이 존재할 수 있어(예: 1132, 1132_F 둘 다), 두 형태 모두
   검색합니다.
2) 라인 폴더 검색이 여전히 느렸던 문제 수정. 기존엔 스레드 하나가 라인
   폴더 하나를 통째로 os.walk()해서 그 안의 시간 폴더(예: 2026071403)를
   전부 순서대로 훑었음. 이제 시간 폴더 목록을 먼저 병렬로 가져온 뒤,
   시간 폴더 단위로 쪼개서 여러 스레드가 동시에 나눠 검색하도록 개선.
3) 원본경로 기록 파일을 텍스트(.txt)에서 진짜 엑셀 파일(.xlsx)로 변경
   (원본경로.xlsx). openpyxl 등 외부 패키지 없이 표준 라이브러리(zipfile)만
   으로 최소 형태의 xlsx를 직접 생성. 원본 경로를 백슬래시(\\) 기준으로
   나눠 서버/공유폴더/라인/날짜/시간 등이 각각 별도 열에 들어갑니다.

v17 변경사항: 날짜 검색 순서 변경. 기존엔 전날/당일/다음날을 항상
"전날 -> 당일 -> 다음날" 순서로 검색해서, 병렬 작업이 밀리면 당일보다
전날 폴더가 먼저 처리될 수 있었음. waferID에서 인식한 날짜(정확도가 가장
높음)가 항상 가장 먼저 검색되도록 "당일 -> 전날 -> 다음날" 순서로 변경.

v18 변경사항:
1) waferID 끝부분이 "6자리 날짜 + A/B + 5자리 시리얼" 구조일 때, 그
   A/B 글자로 동을 확정할 수 있음을 반영 (A=JC01/1동, B=JC02/2동). 이
   구조와 일치하면 반대쪽 동은 아예 검색하지 않도록 모든 검색 경로
   (1동/2동, Sorter, Result_Images)에 적용.
2) 위와 별개로 발견한 버그 수정: 날짜 인식 정규식이 "6자리 숫자 + A"만
   허용해서, 그 자리가 B인 waferID는 날짜 추출 자체가 실패해 항상 느린
   전체 검색으로 빠지고 있었음. A/B 둘 다 인식하도록 수정.

v19 변경사항: 날짜 검색 순서를 "당일 -> 전날 -> 다음날"에서
"당일 -> 다음날 -> 전날"로 변경.

v20 변경사항: 1동/2동, Sorter, Result_Images 세 경로 검색을 순차 실행에서
동시 실행으로 변경. 기존엔 한 waferID를 검색할 때 세 경로를 하나씩 차례로
검색해서, 앞 경로가 느리거나(최악의 경우 폴더 응답 없음으로 45초 타임아웃)
안 좋으면 다음 경로 검색이 그만큼 늦게 시작됐음. 세 경로는 서로 다른
서버(1동/2동, Sorter, Result_Images)를 대상으로 하는 독립적인 검색이라
스레드로 동시에 실행해도 경로별 동시 검색 스레드 수(SEARCH_WORKERS)는
그대로라 서버 부하는 늘지 않으면서 전체 대기 시간만 줄어듦.

v21 변경사항: 여러 waferID를 배치로 검색할 때 방치된 폴더 검색 스레드가
계속 쌓이는 문제 수정. "하나 찾으면 즉시 다음으로 넘어가는" 최적화(v15)는
이미 실행 중이던(응답 대기 중인) 스레드까지 멈추지는 못해서, 그 스레드는
백그라운드에 방치된 채 계속 서버에 붙어있었음. waferID 한두 개만 검색할
땐 금방 자연히 정리돼 문제가 안 됐지만, 여러 개를 배치로 검색하면 매
waferID마다 새로 방치된 스레드가 쌓여, 예전에 서버 전체가 먹통이 됐던
것과 같은 방식으로 SMB 연결이 과부하될 위험이 있었음(실제로 10개 배치
시뮬레이션에서 GUI는 이미 "완료"로 표시됐는데도 방치된 스레드가 최대
9개까지 동시에 살아있는 것을 확인함). 또한 이 방치된 스레드가 파이썬의
비-데몬 스레드라서, 검색이 끝난 뒤 프로그램 창을 닫아도 방치된 스레드가
다 끝날 때까지 프로세스가 종료되지 않고 멈춰있는 것도 확인됨(작업관리자에
pythonw.exe가 계속 남아있는 형태로 재발할 수 있었음). 이제 앱 전체에서
동시에 실제 네트워크 폴더 조회를 하는 스레드 수에 전역 상한
(GLOBAL_INFLIGHT_DIR_SEARCH_LIMIT)을 둬서, waferID 한 개의 정상적인
동시 검색량은 절대 막지 않으면서, 그 이상(=이전 검색에서 방치된 스레드가
쌓인 상황)이면 새 폴더 조회가 슬롯이 빌 때까지 짧게 대기하도록 함.

v22 변경사항: 여러 waferID를 배치로 검색할 때 하나씩 순차로 처리하던 것을
동시에 여러 개(WAFER_BATCH_WORKERS)를 처리하도록 변경해 배치 전체 검색
시간을 단축. v21에서 실제 네트워크 동시 연결 수를 전역 상한
(GLOBAL_INFLIGHT_DIR_SEARCH_LIMIT)으로 이미 안전하게 제한해뒀기 때문에,
waferID를 순차로만 처리할 이유(서버 과부하 위험)가 없어짐. 기존엔 한
waferID의 복사/로그/스레드 정리 등으로 네트워크 요청이 비는 짧은 틈에도
다음 waferID가 시작을 못 해 그 틈이 그대로 낭비됐는데, 이제 여러 waferID를
동시에 진행 중으로 두면 어느 waferID든 빈 자리가 생기는 즉시 다른
waferID가 바로 채워 전역 상한을 최대한 꽉 채운 상태를 유지한다(실제 동시
연결 수 자체는 v21의 상한으로 그대로 안전하게 유지됨). 배치 로그는
waferID별로 섞여서 찍히므로 각 줄 앞에 "[waferID]"를 붙여 구분한다.

v23 변경사항: 로그에서 별 정보 없는 "지금 이 방법 시도 중" 안내 문구 제거.
"waferID 접두사로 라인 폴더 추정, 시간 폴더 목록부터 조회..." /
"시간 폴더 N개를 동시에 검색합니다..." 같은 문구는 힌트가 있는 waferID마다
(=거의 항상) 1동/2동, Sorter, Result_Images 세 경로에서 각각 찍혀서, v22의
동시 배치 검색과 합쳐지면 여러 waferID의 이 똑같은 문구들이 로그창을 가득
채워 정작 중요한 정보(찾음/못 찾음/fallback 발생/오류)를 찾기 어렵게 만들고
있었음. 정상적으로 진행 중이라는 것만 알려주고 판단에 도움이 안 되는 이
문구들을 제거하고, 힌트로 못 찾아 전체 라인/날짜 폴더로 넓혀 검색하는 등
평소와 다른 상황을 알려주는 로그와 최종 결과(찾은 개수, 복사 결과, 오류)는
그대로 남김.

v24 변경사항: 폴더 하나를 조회할 때마다 찍히던 "검색 중: {폴더}" 로그를
매번 보여주는 대신 SEARCHING_LOG_SAMPLE_INTERVAL(10)번에 한 번만 보여주도록
변경. 특히 fallback(전체 라인/날짜 폴더 검색)처럼 후보 폴더가 많거나,
여러 waferID를 동시에 배치 검색할 때 이 로그가 겹쳐서 순식간에 로그창을
가득 채우고 있었음. 실제 검색 동작(찾는 로직)은 그대로이고, 화면에 보여주는
빈도만 줄임.

v25 변경사항: "복사 완료: {대상경로} (원본: {원본경로})" 로그에서
"(원본: ...)" 부분 제거, "복사 완료: {대상경로}"만 남김. 찾은 파일이
많으면 이 줄마다 원본 네트워크 경로까지 길게 붙어 로그가 장황해졌는데,
원본 경로는 어차피 결과 폴더에 같이 생성되는 원본경로.xlsx에 전부
기록되므로 로그에서는 필요 없음.

v26 변경사항: 복사 결과 로그를 파일 하나하나 나열하던 방식에서 "복사완료 :
총 이미지 N장" 한 줄 요약으로 변경. 기존엔 찾은 이미지마다 "복사 완료:
{경로}" 줄이 하나씩 찍히고 그 아래 "원본 경로 목록: {xlsx 경로}" 줄까지
따로 있어서, 찾은 파일이 많으면 로그가 길어졌음. 개별 파일 경로/원본경로
목록 위치는 결과 폴더 안 원본경로.xlsx와 폴더 자체에서 바로 확인할 수
있으므로 로그에는 총 몇 장 복사됐는지만 간단히 남김.

v27 변경사항: 두 가지 로그 정리.
1) "N개 발견: 검색완료. 남은 M개 폴더는 검색하지 않습니다." 로그에서
   "남은 M개 폴더는 검색하지 않습니다" 부분 제거, "N개 발견: 검색완료."
   까지만 남김.
2) "검색 중: {폴더}" 로그 표시 빈도를 SEARCHING_LOG_SAMPLE_INTERVAL
   10 -> 20으로 변경(20번에 한 번만 표시).
"""

import os
import re
import shutil
import threading
import queue
import zipfile
from xml.sax import saxutils
from concurrent.futures import ThreadPoolExecutor, as_completed, wait, FIRST_COMPLETED
from datetime import date, timedelta
import tkinter as tk
from tkinter import ttk, messagebox

APP_VERSION = "v27"

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

RESULT_IMAGES_ROOT = r"\\172.23.69.112\Result_Images"
# ROOT_PATHS와 같은 인덱스 체계: 0=1동/JC01, 1=2동/JC02 (소문자 폴더명)
RESULT_IMAGES_SITE_FOLDERS = {0: "jc01", 1: "jc02"}
RESULT_IMAGES_CATEGORY_DIRS = ["boxed", "origin"]
# 라인 폴더는 PREFIX_LINE_HINTS 값을 그대로 쓰되(예: 1932, 1132), 뒤에 "_F"가
# 붙는 변형이 같은 날짜에 함께 있을 수 있어 둘 다 시도한다.
RESULT_IMAGES_LINE_SUFFIXES = ["", "_F"]

RESULT_BASE_FOLDER_NAME = "Wafer검색결과"
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
DATE_SEARCH_WINDOW_DAYS = 1  # waferID 날짜 기준 +-1일까지 검색
SEARCH_WORKERS = 4  # 라인x날짜 폴더를 동시에 검색할 스레드 수 (SMB 서버 부하 방지 위해 낮게 유지)
FULL_SEARCH_WORKERS = 6  # 날짜를 못 찾아 전체를 뒤질 때 동시 검색 스레드 수
# 여러 waferID를 동시에 "진행 중" 상태로 둘 최대 개수. 실제 네트워크 동시
# 연결 수는 아래 GLOBAL_INFLIGHT_DIR_SEARCH_LIMIT이 이미 전역으로 제한하므로,
# 이 값을 늘려도 서버 부하는 늘지 않는다. waferID 하나만으로는 항상
# GLOBAL_INFLIGHT_DIR_SEARCH_LIMIT을 다 채우지 못하는 경우(찾는 즉시 끝나는
# 빠른 waferID들)에도 다음 waferID들이 미리 대기하고 있어야 빈 자리를 놓치지
# 않고 바로 채울 수 있어, 여유 있게 잡는다.
WAFER_BATCH_WORKERS = 10

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

# waferID 안에서 YYMMDD를 추출: 6자리 숫자 뒤에 'A' 또는 'B'가 오는 패턴
# (예: ALL4260526A89264 -> 260526). 이 자리의 글자가 A/B로 동을 나타내기도 함
# (뒤에서 6번째 글자, "5자리 시리얼 바로 앞": A=JC01/1동, B=JC02/2동).
DATE_IN_WAFERID_RE = re.compile(r"(\d{6})[AB]")
SITE_LETTER_RE = re.compile(r"\d{6}([AB])\d{5}$")
_SITE_LETTER_TO_ROOT_INDEX = {"A": 0, "B": 1}  # A=JC01/1동, B=JC02/2동


def extract_known_site_index(wafer_id):
    """waferID 끝부분 구조(6자리 날짜 + A/B + 5자리 시리얼)로 동을 확정할 수
    있으면 ROOT_PATHS/사이트 인덱스(0=1동/JC01, 1=2동/JC02)를 반환하고,
    이 형식이 아니면 None을 반환한다."""
    match = SITE_LETTER_RE.search(wafer_id)
    if not match:
        return None
    return _SITE_LETTER_TO_ROOT_INDEX.get(match.group(1))


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
    # waferID에서 인식한 날짜(정확도가 가장 높음)를 가장 먼저 검색하고,
    # 그다음 다음날, 전날 순으로 검색 대상 폴더를 나열한다. 병렬 검색 시
    # 일감이 밀리면 먼저 나열된 폴더부터 처리되므로, 정확한 날짜를 먼저
    # 찾아 빨리 끝낼 수 있도록 순서를 맞춘다.
    offsets = [0]
    for n in range(1, window_days + 1):
        offsets.append(n)
        offsets.append(-n)
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

# "검색 중: {폴더}" 로그는 실제로 조회를 시도하는 폴더마다 찍혀서, 전체
# 검색(fallback)처럼 후보 폴더가 많을 때는 waferID 하나당, 그리고 여러
# waferID를 동시 배치 검색할 때는 그게 다 겹쳐서 로그창을 순식간에 가득
# 채운다. 매번 다 보여주는 대신 SEARCHING_LOG_SAMPLE_INTERVAL번에 한 번만
# 보여줘서 "지금 검색이 진행되고 있다"는 감만 유지하고 나머지는 생략한다.
SEARCHING_LOG_SAMPLE_INTERVAL = 20
_searching_log_counter = 0
_searching_log_counter_lock = threading.Lock()


def _should_log_searching():
    global _searching_log_counter
    with _searching_log_counter_lock:
        _searching_log_counter += 1
        return _searching_log_counter % SEARCHING_LOG_SAMPLE_INTERVAL == 0


# "찾으면 즉시 종료" 최적화는 이미 실행 중이던(응답 대기 중인) 폴더 검색
# 스레드까지 멈추지는 못해서, 그 스레드들은 방치된 채 백그라운드에서 계속
# 서버에 붙어있는다. waferID 한 개만 검색할 때는 금방 자연히 정리되지만,
# 여러 waferID를 배치로 검색하면 이런 방치된 스레드가 다음, 그다음 waferID
# 검색에서도 계속 새로 생겨 쌓일 수 있어, 예전에 서버 전체가 먹통이 됐던
# 것과 같은 방식으로 SMB 연결이 과부하될 위험이 있다.
# 이를 막기 위해 앱 전체에서 동시에 실제 네트워크 폴더 조회(os.walk/
# os.scandir)를 수행 중인 스레드 수에 전역 상한을 둔다. waferID 한 개의
# 정상적인 동시 사용량(1동/2동, Sorter, Result_Images 세 경로가 동시에,
# 각 경로 최대 FULL_SEARCH_WORKERS개까지)은 절대 못 미치지 않도록 넉넉히
# 잡고, 그 이상은 방치된 이전 검색이 정리될 때까지 새 폴더 조회가 잠깐
# 대기하도록 한다.
GLOBAL_INFLIGHT_DIR_SEARCH_LIMIT = 3 * FULL_SEARCH_WORKERS + SEARCH_WORKERS
_inflight_dir_search_semaphore = threading.BoundedSemaphore(GLOBAL_INFLIGHT_DIR_SEARCH_LIMIT)
_INFLIGHT_WAIT_POLL_SECONDS = 5
_INFLIGHT_WAIT_LOG_EVERY_SECONDS = 15


def _acquire_inflight_slot(log, stop_event):
    """실제 네트워크 폴더 조회 직전에 호출. 방치된 스레드가 쌓여 전역
    상한(GLOBAL_INFLIGHT_DIR_SEARCH_LIMIT)에 걸리면 자리가 날 때까지
    짧게 폴링하며 기다리고, 중지 요청이 오면 즉시 포기한다(False 반환)."""
    waited = 0.0
    last_logged = 0.0
    while True:
        if _inflight_dir_search_semaphore.acquire(timeout=_INFLIGHT_WAIT_POLL_SECONDS):
            return True
        if stop_event.is_set():
            return False
        waited += _INFLIGHT_WAIT_POLL_SECONDS
        if waited - last_logged >= _INFLIGHT_WAIT_LOG_EVERY_SECONDS:
            log(
                "이전 검색에서 방치된 폴더 응답을 기다리는 중이라 새 폴더 검색을 "
                "{:.0f}초째 대기하고 있습니다 (서버 과부하 방지)...".format(waited)
            )
            last_logged = waited


def _release_inflight_slot():
    _inflight_dir_search_semaphore.release()


def _list_subdirs_in_parallel(parent_dirs, log, stop_event):
    """parent_dirs 각각의 바로 아래 하위 폴더 목록을 병렬로 가져와 펼친다.

    라인 폴더 하나를 스레드 하나가 통째로 os.walk()하면 그 안의 시간 폴더를
    전부 순서대로 훑게 되어 병렬성을 못 살린다. 시간 폴더 이름을 먼저 빠르게
    나열한 뒤 시간 폴더 단위로 검색을 쪼개면 여러 스레드가 동시에 나눠 맡을
    수 있다. 목록 조회가 실패하거나 응답이 없으면 원래 폴더를 그대로 검색
    대상에 남겨 os.walk가 처리하도록 한다(결과 누락 방지).
    """
    if not parent_dirs:
        return []

    def _guarded_list_subdirs(p):
        if not _acquire_inflight_slot(log, stop_event):
            return []
        try:
            return list_subdirs(p)
        finally:
            _release_inflight_slot()

    children_by_parent = {}
    executor = ThreadPoolExecutor(max_workers=min(SEARCH_WORKERS, len(parent_dirs)))
    try:
        futures = {executor.submit(_guarded_list_subdirs, p): p for p in parent_dirs}
        pending = set(futures)
        while pending:
            done, pending = wait(pending, timeout=DIR_SEARCH_TIMEOUT_SECONDS, return_when=FIRST_COMPLETED)
            if not done:
                log("{}개 폴더의 하위 목록 조회가 응답이 없어 해당 폴더를 통째로 검색합니다.".format(len(pending)))
                break
            for future in done:
                parent = futures[future]
                try:
                    children_by_parent[parent] = future.result()
                except OSError:
                    children_by_parent[parent] = None
            if stop_event.is_set():
                break
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

    expanded = []
    for parent in parent_dirs:
        children = children_by_parent.get(parent)
        if children:
            expanded.extend(children)
        else:
            # 목록이 비었거나(권한/일시 오류) 아직 조회를 못 한 경우 원래
            # 폴더를 그대로 남겨서 os.walk가 재귀적으로 처리하게 한다.
            expanded.append(parent)
    return expanded


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

    if not _acquire_inflight_slot(log, stop_event):
        return []
    try:
        if _should_log_searching():
            log("검색 중: {}".format(target_dir))
        matches = []
        for current_root, _dirs, files in os.walk(target_dir):
            if stop_event.is_set():
                break
            for filename in files:
                if is_image_match(filename, wafer_id):
                    matches.append(os.path.join(current_root, filename))
        return matches
    finally:
        _release_inflight_slot()


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
                    log("{}개 발견: 검색완료.".format(len(found)))
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


def _restrict_roots_to_known_site(roots, wafer_id, log):
    """waferID 구조로 동이 확정되면 해당 동의 경로만 남긴다."""
    known_site_index = extract_known_site_index(wafer_id)
    if known_site_index is None or not (0 <= known_site_index < len(ROOT_PATHS)):
        return roots
    known_root = ROOT_PATHS[known_site_index]
    restricted = [r for r in roots if r == known_root]
    if restricted:
        log("waferID 구조로 동 확정: {} (반대쪽 동은 검색하지 않음)".format(known_root))
        return restricted
    return roots


def _site_folder_values_for_known_site(site_folders, wafer_id):
    """waferID 구조로 동이 확정되면 해당 사이트 폴더명만 남긴다(Sorter/Result_Images용)."""
    known_site_index = extract_known_site_index(wafer_id)
    if known_site_index is not None and known_site_index in site_folders:
        return [site_folders[known_site_index]]
    return list(site_folders.values())


def _hinted_target_dirs(wafer_id, yyyymmdd_list):
    hints = PREFIX_LINE_HINTS.get(wafer_id[:4])
    if not hints:
        return []

    known_site_index = extract_known_site_index(wafer_id)

    dirs = []
    for hint in hints:
        root_index = _SITE_PREFIX_TO_ROOT_INDEX.get(hint[:2])
        if root_index is None:
            continue
        if known_site_index is not None and root_index != known_site_index:
            # waferID 구조로 동이 확정되면 반대쪽 동은 검색하지 않는다.
            continue
        line_dir = os.path.join(ROOT_PATHS[root_index], hint)
        for yyyymmdd in yyyymmdd_list:
            dirs.append(os.path.join(line_dir, yyyymmdd))
    return dirs


def search_by_date_folders(wafer_id, yyyymmdd_list, log, stop_event):
    hinted_dirs = _hinted_target_dirs(wafer_id, yyyymmdd_list)
    if hinted_dirs:
        hour_dirs = _list_subdirs_in_parallel(hinted_dirs, log, stop_event)
        found = _search_dirs_in_parallel(wafer_id, hour_dirs, log, SEARCH_WORKERS, stop_event)
        if found or stop_event.is_set():
            return found
        log("추정한 라인 폴더에서 못 찾아 전체 라인 폴더로 다시 검색합니다...")

    if stop_event.is_set():
        return []

    roots = _accessible_roots(log)
    roots = _restrict_roots_to_known_site(roots, wafer_id, log)
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
    roots = _restrict_roots_to_known_site(roots, wafer_id, log)
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

    known_site_index = extract_known_site_index(wafer_id)

    dirs = []
    seen_site_line = set()
    for hint in hints:
        root_index = _SITE_PREFIX_TO_ROOT_INDEX.get(hint[:2])
        if known_site_index is not None and root_index != known_site_index:
            continue
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
            hour_dirs = _list_subdirs_in_parallel(hinted_dirs, log, stop_event)
            found = _search_dirs_in_parallel(wafer_id, hour_dirs, log, SEARCH_WORKERS, stop_event)
            if found or stop_event.is_set():
                return found
            log("Sorter: 추정한 라인 폴더에서 못 찾아 날짜 폴더 전체를 검색합니다...")

        site_folders = _site_folder_values_for_known_site(SORTER_SITE_FOLDERS, wafer_id)
        target_dirs = [
            os.path.join(SORTER_ROOT, site_folder, category, yyyymmdd)
            for site_folder in site_folders
            for category in SORTER_CATEGORY_DIRS
            for yyyymmdd in yyyymmdd_list
        ]
        log("Sorter: 검색 대상 폴더 {}개 검색합니다...".format(len(target_dirs)))
        return _search_dirs_in_parallel(wafer_id, target_dirs, log, SEARCH_WORKERS, stop_event)

    log("Sorter: 날짜를 몰라 전체 폴더를 검색합니다. 시간이 오래 걸릴 수 있습니다...")
    site_folders = _site_folder_values_for_known_site(SORTER_SITE_FOLDERS, wafer_id)
    target_dirs = [
        os.path.join(SORTER_ROOT, site_folder, category)
        for site_folder in site_folders
        for category in SORTER_CATEGORY_DIRS
    ]
    return _search_dirs_in_parallel(wafer_id, target_dirs, log, FULL_SEARCH_WORKERS, stop_event)


def _result_images_hinted_target_dirs(wafer_id, yyyymmdd_list):
    hints = PREFIX_LINE_HINTS.get(wafer_id[:4])
    if not hints:
        return []

    known_site_index = extract_known_site_index(wafer_id)

    dirs = []
    seen_site_line = set()
    for hint in hints:
        root_index = _SITE_PREFIX_TO_ROOT_INDEX.get(hint[:2])
        if known_site_index is not None and root_index != known_site_index:
            continue
        site_folder = RESULT_IMAGES_SITE_FOLDERS.get(root_index)
        if site_folder is None:
            continue
        if (site_folder, hint) in seen_site_line:
            continue
        seen_site_line.add((site_folder, hint))
        for category in RESULT_IMAGES_CATEGORY_DIRS:
            for yyyymmdd in yyyymmdd_list:
                for suffix in RESULT_IMAGES_LINE_SUFFIXES:
                    dirs.append(
                        os.path.join(
                            RESULT_IMAGES_ROOT, site_folder, "result", category,
                            yyyymmdd, hint + suffix,
                        )
                    )
    return dirs


def search_result_images(wafer_id, yyyymmdd_list, log, stop_event):
    if stop_event.is_set():
        return []

    if not os.path.isdir(RESULT_IMAGES_ROOT):
        log("네트워크 경로에 접근할 수 없습니다: {}".format(RESULT_IMAGES_ROOT))
        return []

    if yyyymmdd_list:
        hinted_dirs = _result_images_hinted_target_dirs(wafer_id, yyyymmdd_list)
        if hinted_dirs:
            hour_dirs = _list_subdirs_in_parallel(hinted_dirs, log, stop_event)
            found = _search_dirs_in_parallel(wafer_id, hour_dirs, log, SEARCH_WORKERS, stop_event)
            if found or stop_event.is_set():
                return found
            log("Result_Images: 추정한 라인 폴더에서 못 찾아 날짜 폴더 전체를 검색합니다...")

        site_folders = _site_folder_values_for_known_site(RESULT_IMAGES_SITE_FOLDERS, wafer_id)
        target_dirs = [
            os.path.join(RESULT_IMAGES_ROOT, site_folder, "result", category, yyyymmdd)
            for site_folder in site_folders
            for category in RESULT_IMAGES_CATEGORY_DIRS
            for yyyymmdd in yyyymmdd_list
        ]
        log("Result_Images: 검색 대상 폴더 {}개 검색합니다...".format(len(target_dirs)))
        return _search_dirs_in_parallel(wafer_id, target_dirs, log, SEARCH_WORKERS, stop_event)

    log("Result_Images: 날짜를 몰라 전체 폴더를 검색합니다. 시간이 오래 걸릴 수 있습니다...")
    site_folders = _site_folder_values_for_known_site(RESULT_IMAGES_SITE_FOLDERS, wafer_id)
    target_dirs = [
        os.path.join(RESULT_IMAGES_ROOT, site_folder, "result", category)
        for site_folder in site_folders
        for category in RESULT_IMAGES_CATEGORY_DIRS
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


SOURCE_LIST_FILENAME = "원본경로.xlsx"


def _copy_one(src, dest_dir):
    dst = os.path.join(dest_dir, os.path.basename(src))
    shutil.copy2(src, dst)
    return src, dst


def _xlsx_col_letter(col_index):
    # 0-indexed 열 번호 -> 엑셀 열 문자 (0->A, 25->Z, 26->AA ...)
    n = col_index + 1
    letters = ""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def _write_xlsx(path, header, rows):
    """openpyxl 등 외부 패키지 없이 표준 라이브러리(zipfile)만으로 최소
    형태의 단일 시트 .xlsx 파일을 직접 만든다."""
    all_rows = [header] + rows

    sheet_rows_xml = []
    for r_idx, row in enumerate(all_rows, start=1):
        cells_xml = []
        for c_idx, value in enumerate(row):
            ref = "{}{}".format(_xlsx_col_letter(c_idx), r_idx)
            text = saxutils.escape("" if value is None else str(value))
            cells_xml.append(
                '<c r="{}" t="inlineStr"><is><t xml:space="preserve">{}</t></is></c>'.format(ref, text)
            )
        sheet_rows_xml.append('<row r="{}">{}</row>'.format(r_idx, "".join(cells_xml)))

    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        "<sheetData>" + "".join(sheet_rows_xml) + "</sheetData>"
        "</worksheet>"
    )

    content_types_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        "</Types>"
    )

    root_rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        "</Relationships>"
    )

    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="원본경로" sheetId="1" r:id="rId1"/></sheets>'
        "</workbook>"
    )

    workbook_rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
        "</Relationships>"
    )

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types_xml)
        zf.writestr("_rels/.rels", root_rels_xml)
        zf.writestr("xl/workbook.xml", workbook_xml)
        zf.writestr("xl/_rels/workbook.xml.rels", workbook_rels_xml)
        zf.writestr("xl/worksheets/sheet1.xml", sheet_xml)


def _write_source_list(dest_dir, copied):
    if not copied:
        return
    list_path = os.path.join(dest_dir, SOURCE_LIST_FILENAME)

    rows = []
    for src, dst in copied:
        parts = src.lstrip("\\").split("\\")
        rows.append([os.path.basename(dst)] + parts)
    rows.sort(key=lambda r: r[0])

    max_parts = max(len(row) - 1 for row in rows)
    header = ["파일명"] + ["경로{}".format(i + 1) for i in range(max_parts)]

    try:
        _write_xlsx(list_path, header, rows)
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
        # waferID를 하나씩 순차로 처리하지 않고 동시에 여러 개를 처리한다.
        # 실제 네트워크 동시 연결 수는 GLOBAL_INFLIGHT_DIR_SEARCH_LIMIT이
        # 전역으로 제한해주므로 서버 부하 없이, waferID 사이의 자잘한 대기
        # 시간(복사, 로그, 스레드 정리 등으로 네트워크 요청이 잠깐 비는 틈)을
        # 다음 waferID가 바로 채워 전체 배치 시간을 줄인다.
        total = len(wafer_ids)
        ids_with_results = 0
        total_copied = 0
        completed = 0
        counters_lock = threading.Lock()

        def process(wafer_id):
            nonlocal ids_with_results, total_copied, completed

            if self.stop_event.is_set():
                with counters_lock:
                    completed += 1
                return

            def log(message, _wafer_id=wafer_id):
                self.log("[{}] {}".format(_wafer_id, message))

            log("===== 검색 시작 =====")
            copied_count = self._search_and_copy_one(wafer_id, log)

            with counters_lock:
                completed += 1
                if copied_count:
                    ids_with_results += 1
                    total_copied += copied_count
                self.msg_queue.put(
                    (
                        "status",
                        "검색 중... ({}/{} 완료, 최대 {}개 동시 진행)".format(
                            completed, total, min(WAFER_BATCH_WORKERS, total)
                        ),
                    )
                )

        with ThreadPoolExecutor(max_workers=min(WAFER_BATCH_WORKERS, total)) as executor:
            list(executor.map(process, wafer_ids))

        summary = "{}개 waferID 중 {}개에서 파일 발견, 총 {}개 복사했습니다.".format(
            total, ids_with_results, total_copied
        )
        if self.stop_event.is_set():
            summary += " (중지됨, 진행 중이던 것까지만 확인)"
        self.msg_queue.put(("status", summary))
        self.msg_queue.put(("done", total_copied > 0))

    def _search_and_copy_one(self, wafer_id, log):
        center_date = extract_date(wafer_id)
        yyyymmdd_list = None
        if center_date:
            yyyymmdd_list = date_range_folders(center_date)
            log(
                "waferID에서 날짜 인식: {} (검색 대상: {})".format(
                    center_date.strftime("%Y-%m-%d"), ", ".join(yyyymmdd_list)
                )
            )

        # 1동/2동, Sorter, Result_Images는 서로 다른 서버를 대상으로 하는
        # 독립적인 검색이라 순차 실행 대신 동시에 실행해서 대기 시간을 줄인다.
        # (실제 네트워크 동시 연결 수는 GLOBAL_INFLIGHT_DIR_SEARCH_LIMIT이
        # 전역으로 제한하므로 서버 부하는 늘지 않는다.)
        results = {}

        def run_elimages():
            if center_date:
                results["elimages"] = search_by_date_folders(
                    wafer_id, yyyymmdd_list, log, self.stop_event
                )
            else:
                results["elimages"] = search_full(wafer_id, log, self.stop_event)

        def run_sorter():
            results["sorter"] = search_sorter(wafer_id, yyyymmdd_list, log, self.stop_event)

        def run_result_images():
            results["result_images"] = search_result_images(
                wafer_id, yyyymmdd_list, log, self.stop_event
            )

        threads = [
            threading.Thread(target=target, daemon=True)
            for target in (run_elimages, run_sorter, run_result_images)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        found = results["elimages"] + results["sorter"] + results["result_images"]

        if not found:
            log("일치하는 이미지를 찾지 못했습니다: {}".format(wafer_id))
            return 0

        found_suffix = " (중지 시점까지)" if self.stop_event.is_set() else ""
        log("{}개 파일을 찾았습니다{}. 복사 중...".format(len(found), found_suffix))
        _, copied = copy_results(found, wafer_id, log)
        log("복사완료 : 총 이미지 {}장".format(len(copied)))

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
