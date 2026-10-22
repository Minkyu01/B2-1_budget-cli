"""파일 기반 가계부 콘솔 프로그램.

실행:  python -m budget_app <명령> [옵션]        (명령 목록: python -m budget_app --help)

계층 — 위에서 아래로만 의존한다 (아래 계층은 위 계층을 모른다)
    cli.py        사용자와 대화 : 명령줄 해석, 입력 받기, 출력
    services.py   업무 규칙     : 등록된 카테고리만 허용, 최신순, 예산 초과 계산 ...
    storage.py    파일 읽기/쓰기 : JSONL 저장소, CSV, 백업
    models.py     데이터 모양 + 값 검증

여러 계층이 함께 쓰는 도구
    errors.py      원인 + 해결 힌트를 담는 예외
    decorators.py  오류 처리 / 실행 기록 / 시간 측정
    formatter.py   화면에 찍을 문자열 만들기
"""
