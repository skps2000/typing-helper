# 타이핑 도우미 (Typing Helper)

Windows에서 **내가 타이핑·복붙한 내용을 수집** → **AI로 교정** → 그 데이터로 **어디서든 자동완성**을 제공하는 개인용 도구.

## 목표 파이프라인

```
[1단계 수집]  내 타이핑/복붙 기록  →  typing_YYYY-MM-DD.txt
      │
[2단계 교정]  타 AI에게 교정 요청(프롬프트+파일)  →  phrases.txt
      │
[3단계 자동완성]  타이핑 중 회색 제안 → Tab으로 채움 (전역)
```

## 주요 기능

- **수집**: 전역 키보드 후킹으로 타이핑 기록. 두벌식 **한글 자동 조합**(예: `dkssud` → `안녕`). 복사/붙여넣기는 클립보드 감시로 완전 포착. 원본 키는 `raw_*.txt`에 백업.
- **경량**: 후킹 콜백은 메모리 적재만, 파일 저장은 백그라운드 스레드 배치 → 타이핑 지연 없음.
- **대시보드 UI**(tkinter): 수집/자동완성 ON·OFF, 교정 프롬프트 가이드·데이터 폴더·`phrases.txt` 열기, 오늘 수집량 표시.
- **자동완성**: `phrases.txt`(교정 결과)를 읽어 입력 중 커서 옆 회색 제안 → `Tab` 삽입. 파일 저장 시 자동 재로딩.
- **중복 실행 방지**(단일 인스턴스), 연속 중복 줄 제거.

## 저장 위치

`내 문서\TypingLog\`
- `typing_YYYY-MM-DD.txt` — 한글 조합된 읽기용 기록 + 복붙 내용
- `raw_YYYY-MM-DD.txt` — 원본 키 백업
- `phrases.txt` — 교정 결과(자동완성 소스)
- `교정프롬프트_가이드.txt` — 타 AI 교정용 프롬프트

> 개인 수집 데이터(`TypingLog` 전체)는 `.gitignore`로 저장소에서 제외됩니다. 로컬에만 저장되고 외부로 전송하지 않습니다.

## 사용법

1. [Releases](https://github.com/skps2000/typing-helper/releases)에서 `TypingHelper.exe` 내려받아 실행 (창 뜸)
2. 며칠 평소처럼 사용 → 데이터 수집
3. 대시보드 **교정 프롬프트 가이드 열기** → 프롬프트 복사 → 타 AI에 `typing_*.txt`와 함께 전송
4. AI 결과(표현 한 줄씩)를 **교정결과(phrases.txt) 열기**로 붙여넣고 저장
5. 이제 타이핑 시 회색 제안 → **Tab**으로 자동완성

## 소스에서 빌드 (Windows)

```bat
pip install -r requirements.txt
pyinstaller --onefile --noconsole --collect-all tkinter --hidden-import pynput.keyboard._win32 --name TypingHelper typing_helper.py
```
> 참고: 빌드된 exe는 저장소에 커밋하지 않고 [Releases](https://github.com/skps2000/typing-helper/releases)로 배포합니다. 저장소에는 소스만 둡니다.

## 한계 / TODO

- 타이핑은 물리 키만 잡혀 **한/영 모드 구분 불가** → 조합기는 기본 한글 가정, 영문은 `raw`로 복구 필요 (모드 판별 개선 예정)
- 자동완성 **회색 제안창 위치**가 일부 앱에서 캐럿과 어긋날 수 있음(GetGUIThreadInfo 기반), 일부 앱은 Tab 가로채기 제약 → 앱별 튜닝 예정
- 2단계 교정 자동화(선택), 부팅 자동시작 옵션

## 보안 주의

모든 키 입력을 저장하므로 **비밀번호 등 민감정보도 기록**될 수 있습니다. 로그는 로컬에만 저장되며, 교정을 위해 외부 AI에 보낼 때는 민감정보를 제거하도록 프롬프트에 명시되어 있습니다.
# typing-helper
