# Wafer ID 이미지 검색 프로그램

`\\172.23.11.134\ELImages` 안에서 waferID(예: `ALL4260526A89264`)가 파일명에
포함된 이미지를 찾아서 바탕화면의 `Wafer검색결과\{waferID}\` 폴더로 복사해주는
Windows용 GUI 프로그램입니다.

## 동작 방식

1. 입력한 waferID에서 날짜(YYMMDD)를 추출합니다.
   - 예: `ALL4260526A89264` → `260526` → `20260526`
   - 패턴: waferID 안에서 "6자리 숫자 + A"로 끝나는 부분을 날짜로 인식합니다.
2. `ELImages\{라인번호}\{YYYYMMDD}\` 폴더만 찾아서 그 아래를 검색하므로,
   전체 폴더를 다 뒤지지 않고 빠르게 동작합니다.
   (날짜를 인식하지 못하면 전체 폴더를 검색하며, 이 경우 시간이 오래 걸릴 수 있습니다.)
3. 파일명에 waferID 문자열이 포함된 이미지 파일(jpg, jpeg, png, bmp, tif, tiff)을
   찾아 **복사**합니다 (원본은 그대로 유지).
4. 바탕화면 `Wafer검색결과\{waferID}\` 폴더에 결과를 모읍니다.
   같은 waferID로 다시 검색하면 해당 폴더를 비우고 새로 채웁니다.

## 실행 방법 (Python이 설치된 PC)

```
python wafer_search.py
```

## exe로 만들기 (Python 없는 PC에서 실행하고 싶을 때)

`\\172.23.11.134\ELImages`에 접근 가능한 Windows PC에서 아래 순서로 진행하세요.
(exe 빌드는 Windows에서만 Windows용 exe가 만들어집니다.)

1. Python 설치 (https://www.python.org/downloads/windows/)
2. 이 저장소의 `wafer_search.py` 파일을 PC로 다운로드
3. 명령 프롬프트(cmd)에서:

```
pip install pyinstaller
pyinstaller --onefile --noconsole --name WaferSearch wafer_search.py
```

4. `dist\WaferSearch.exe` 파일이 생성됩니다. 이 파일을 원하는 위치(바탕화면 등)로
   옮겨서 더블클릭하면 바로 실행됩니다. (Python 설치가 없어도 실행 가능)

## 참고

- 네트워크 경로 `\\172.23.11.134\ELImages`에 접근 권한이 있어야 검색이 됩니다.
- waferID의 날짜 패턴이 다른 형식일 경우 `wafer_search.py`의
  `DATE_IN_WAFERID_RE` 정규식을 상황에 맞게 수정해야 합니다.
- 검색 대상 확장자를 늘리고 싶다면 `IMAGE_EXTS` 목록에 추가하세요.
