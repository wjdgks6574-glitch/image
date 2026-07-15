# Wafer ID 이미지 검색 프로그램

`\\172.23.11.134\ELImages` 안에서 waferID(예: `ALL4260526A89264`)가 파일명에
포함된 이미지를 찾아서 바탕화면의 `Wafer검색결과\{waferID}\` 폴더로 복사해주는
Windows용 GUI 프로그램입니다.

## 버전

수정할 때마다 파일명에 버전을 표기합니다 (`wafer_search_v1.py`, `wafer_search_v2.py`, ...).
항상 **가장 높은 버전 번호의 파일이 최신**이며, 이전 버전 파일은 기록용으로 남겨둡니다.
현재 최신 버전: `wafer_search_v2.py`

- v1: 최초 버전 (waferID 날짜 +-1일 폴더 검색, 검색/복사 병렬화)
- v2: 창 제목에 버전 표시 추가. cmd 콘솔 창 없이 실행되도록 런처 정비.

## 동작 방식

1. 입력한 waferID에서 날짜(YYMMDD)를 추출합니다.
   - 예: `ALL4260526A89264` → `260526` → `2026-05-26`
   - 패턴: waferID 안에서 "6자리 숫자 + A"로 끝나는 부분을 날짜로 인식합니다.
2. 인식한 날짜의 **전날/당일/다음날(+-1일), 총 3일치** `ELImages\{라인번호}\{YYYYMMDD}\`
   폴더만 찾아서 그 아래를 검색하므로, 전체 폴더를 다 뒤지지 않고 빠르게 동작합니다.
   (날짜를 인식하지 못하면 전체 폴더를 검색하며, 이 경우 시간이 오래 걸릴 수 있습니다.)
3. 파일명에 waferID 문자열이 포함된 이미지 파일(jpg, jpeg, png, bmp, tif, tiff)을
   찾아 **복사**합니다 (원본은 그대로 유지).
4. 바탕화면 `Wafer검색결과\{waferID}\` 폴더에 결과를 모읍니다.
   같은 waferID로 다시 검색하면 해당 폴더를 비우고 새로 채웁니다.

## 실행 방법

exe로 빌드하면 회사 보안 프로그램이 미인가 프로그램으로 차단할 수 있어,
Python 스크립트(.py)를 그대로 실행하는 방식을 사용합니다. (별도 표준 라이브러리
외 패키지 설치가 필요 없습니다.)

1. 실행할 PC에 Python이 없다면 설치합니다. (https://www.python.org/downloads/windows/,
   설치 시 "Add python.exe to PATH" 및 "Install launcher for all users" 체크)
2. 이 저장소의 `wafer_search_v2.py`(최신 버전), `run_wafer_search.bat`,
   `run_wafer_search.vbs` 세 파일을 같은 폴더(예: 바탕화면)에 다운로드합니다.
3. **`run_wafer_search.vbs`를 더블클릭**하세요. cmd 콘솔 창이 전혀 뜨지 않고
   GUI만 바로 실행됩니다. (`.vbs`가 `.bat`을 완전히 숨김 모드로 실행합니다.)

`run_wafer_search.bat`을 직접 더블클릭해도 되지만, pyw/pythonw가 없는 예외적인
경우 콘솔 창이 잠깐 보일 수 있습니다. 평소에는 `.vbs` 쪽을 사용하세요.
`run_wafer_search.vbs`에 바로가기를 만들어두면 매번 더블클릭만으로 실행할 수 있습니다.

### 새 버전으로 올릴 때

`run_wafer_search.bat` 안의 파일명(`wafer_search_v2.py`)을 최신 버전 파일명으로
바꿔주면 됩니다.

## 참고

- 네트워크 경로 `\\172.23.11.134\ELImages`에 접근 권한이 있어야 검색이 됩니다.
- waferID의 날짜 패턴이 다른 형식일 경우 `wafer_search.py`의
  `DATE_IN_WAFERID_RE` 정규식을 상황에 맞게 수정해야 합니다.
- 검색 대상 확장자를 늘리고 싶다면 `IMAGE_EXTS` 목록에 추가하세요.
