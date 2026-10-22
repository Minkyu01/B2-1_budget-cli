# archify 구조 그림

[archify](https://github.com/tt-a1i/archify) (MIT, 스킬 3.1.0 · 커밋 `b25142d`) 로 그린 B2-1 가계부 그림 여섯 장입니다. `index.html` 을 열면 목록이 나오고, 카드를 누르면 `view.html#<그림>` 이 열려 위쪽 막대에 **← 전체 그림 · 이전 · 다음 · 새 창으로** 가 붙습니다(`[` · `]` 키로도 이전 · 다음). 그 아래 **상황 버튼**(그림마다 3~4개, `0`~`4` 키)을 누르면 archify 의 경로 탐색으로 그 상황의 길만 켜진 채 그림이 다시 열리고, 한 줄 설명과 **단계별로 보기 — 흐름 탐색기 ↗** 링크(같은 상황의 탐색기 장면 · 단계)가 붙습니다. 각 그림 HTML 은 파일 하나로도 열리고(인터넷 없이), 노드를 누르면 설명 · 확대 · 밝게/어둡게 · 이미지 내보내기가 됩니다.

| 그림 | 종류 | 동료 평가 문항 | 원본 |
|---|---|---|---|
| [계층 구조](architecture.html) | architecture | 2-1 | `architecture.json` |
| [서비스는 저장소를 받는다](classes.html) | class | 2-2 | `classes.json` |
| [저장소 하나를 넷이 상속](repositories.html) | class | 2-2 · 3-3 | `repositories.json` |
| [list --limit 3 호출 순서](list-sequence.html) | sequence | 3-1 · 3-2 | `list-sequence.json` |
| [update 와 원자적 교체](update-workflow.html) | workflow | 2-3 | `update-workflow.json` |
| [import 두 단계](import-dataflow.html) | dataflow | 4-3 · 4-1 | `import-dataflow.json` |

- 같은 내용의 Mermaid 글 버전은 [../workflows.md](../workflows.md), 단계별로 재생하는 화면은 [../flow-explorer/](../flow-explorer/README.md) 입니다. 셋의 차이: workflows.md 는 문서 안 그림, 흐름 탐색기는 시나리오를 한 단계씩 재생, archify 는 한 장짜리 그림을 확대 · 탐색 · 내보내기.
- `checks/` 는 archify 의 검사 기록입니다(스키마 검사 · 출력 검사 · 실제 브라우저 검사). 여섯 장 모두 통과했습니다. 이 맥의 폴더 경로가 들어 있어 공개 저장소에는 올리지 않았습니다(`.gitignore`).

## 다시 만들기

archify 는 Claude 스킬로 설치되어 있습니다(`~/.claude/skills/archify`, 2026-10-18). Claude 에게 "archify 로 그려 줘"라고 하면 쓰고, 직접 돌릴 때는 `inner/B2_1` 폴더에서:

```bash
ARCHIFY_UPDATE_CHECK_DISABLED=1 node ~/.claude/skills/archify/bin/archify.mjs finalize sequence docs/archify/list-sequence.json docs/archify/list-sequence.html --quality showcase --json
```

- 같은 그림을 다시 만들 때는 먼저 그 그림의 `checks/` 파일과 HTML 을 지웁니다. archify 는 자기가 만들지 않은 검사 기록을 덮어쓰지 않습니다.
- `ARCHIFY_UPDATE_CHECK_DISABLED=1` 은 실행할 때마다 GitHub Pages 에 새 버전을 묻는 기능을 끄는 설정입니다.

## 결정 기록 (바꿀 수 있음)

| 결정 | 이유 | 대안과 안 고른 이유 |
|---|---|---|
| archify 로 그림 여섯 장을 만듦 (2026-10-18, 사용자: "https://github.com/tt-a1i/archify 이 스킬 써봐, 그래서 흐름도 표현 해봐") | 종류마다(구조 · 클래스 · 호출 순서 · 흐름 · 데이터 흐름) 맞는 그림이 있고, 검사(겹침 · 글자 크기 · 브라우저)를 통과한 HTML 이 나옴 | 흐름 탐색기에 다 넣기 — 이미 22장면, 한 장짜리 전체 그림이 따로 있으면 질문 하나에 바로 보여 주기 좋음 |
| 클래스 그림을 두 장으로 나눔 (서비스 ↔ 저장소 / 저장소 상속) | 거래 · 카테고리 서비스가 서로의 저장소를 읽어서(2 × 2 교차), 서비스 한 줄 · 저장소 한 줄로 놓으면 선이 반드시 겹침. archify 의 showcase 검사가 겹침을 실패로 봄. 그래서 서비스 ↔ 저장소는 사각형으로 놓고 상속은 따로 | 한 장에 넣고 겹침 허용(standard) — 읽기 어려움 |
| 코드 줄 링크(`sources`)는 넣지 않음 | archify 의 코드 근거 기능은 커밋된 git 기록과 대조하는데, B2_1 은 아직 커밋된 적이 없음 | 커밋하고 연결 — 사용자가 커밋을 요청하지 않음 |
| 보너스(반복 내역)는 서비스 그림에서 빼고 상속 그림에만 넣음 | 서비스 그림이 다섯 열이 되면 글자가 작아짐. 같은 모양이라 카드로 설명 | — |
| archify 를 `~/.claude/skills/archify` 에 스킬로 설치 (2026-10-18, 사용자 요청). 그림을 만들 때 미리 훑어본 커밋 `b25142d` 의 `archify/` 폴더를 그대로 복사 | 공식 방법(`npx skills add`)은 npm 도구를 하나 더 받아 실행함. 같은 내용을 이미 확인한 파일로 넣음 | `npx skills add tt-a1i/archify -g` — 결과는 같고, 확인 안 한 코드가 하나 늘어남 |
| 그림에서 목록으로 돌아가는 버튼은 틀 페이지 `view.html` 의 위쪽 막대로 붙임. 그림 HTML 은 고치지 않음 (2026-10-18, 사용자: "이 다이어그램에서 전체 그림으로 가는 버튼 같은 거 없어?") | archify 에는 바깥으로 가는 링크 설정이 없음. 만든 HTML 을 고치면 `checks/` 의 검사 기록(파일 해시)이 맞지 않게 되고, 다시 만들 때마다 또 고쳐야 함. 틀 페이지는 그림이 몇 장이든 같은 막대에 이전 · 다음까지 붙음 | 각 그림 HTML 머리에 버튼을 끼워 넣기 — 위 이유. 그림 파일을 바로 열면 버튼이 없다는 점은 남음(새 창으로 연 경우 포함) |
| 상황 버튼 = archify 경로 탐색 주소(`그림.html#route=시작~끝`) + 흐름 탐색기 장면 링크. 22개 (2026-10-18, 사용자: "우리가 만든 흐름도처럼 각 상황별 흐름도 없는 거야?" → "상황 버튼 달아 줘. 탐색기 장면 링크도 같이") | archify 의 예전 '가이드 뷰'는 지금 버전이 무시함. 경로 탐색은 주소로 열 수 있어서, 그림을 고치지 않고 상황마다 그 길만 켤 수 있음. 단계마다 말할 문장 · 터미널 출력은 탐색기가 이미 갖고 있어 링크로 이음 | 상황마다 그림을 따로 만들기 — 그림이 20장 넘게 늘고 같은 내용을 두 군데서 고쳐야 함 |
| 상황 하나 = 화살표를 따라 이어진 길 하나 | 경로 탐색은 시작~끝 사이의 최단 길만 켬. '같은 질문을 다시 묻기'처럼 같은 칸을 되도는 흐름은 못 그림 → 그런 건 탐색기 링크로 | — |
| 로컬 미리보기(`b2-archify`, 8796)는 `docs/` 를 띄움 (주소 `/archify/…`) | 탐색기 링크(`../flow-explorer/`)가 localhost 에서도 열리게 | `docs/archify` 만 띄우기 — 탐색기 링크가 404 |
| 값은 실제 실행 값 · 시연 데이터 | list 의 0.36ms · 7줄, import 의 6건 · 2건은 2026-10-18 에 시연 데이터로 실행해 나온 값 | — |

## 확인한 것 (2026-10-18)

- archify `finalize` — 여섯 장 모두 validate · deliver · check · browser-check 통과 (`checks/*.finalize-summary.json`)
- 브라우저(localhost:8796)로 여섯 장을 열어 직접 봄. 손본 것: 호출 순서 그림 첫 메모가 좁은 칸에서 네 줄로 꺾여 짧게 줄임
- archify 를 돌리기 전에 받은 코드를 훑어봄: 실행하는 프로그램은 node · git(읽기만) · Chrome(검사용) · 파일 열기(요청할 때만)뿐이고, 밖으로 나가는 요청은 새 버전 확인 하나(위 설정으로 끔)
- `view.html`: 목록 카드 → 틀 → 다음 · 이전(끝에서는 비활성) · `[` `]` 키 · 없는 주소는 첫 그림 · ← 전체 그림 → 목록 순서로 눌러 봄. 콘솔 오류 0, 375px 폭에서 막대가 두 줄로 접히고 가로 스크롤 없음
- 상황 버튼 22개를 모두 눌러 봄: 경로가 다 켜짐(노드 · 홉 수가 의도한 길과 같음), 탐색기 링크 22개가 실제 장면 · 시나리오를 가리킴, `import` 의 '건너뛴 행 보고' 링크는 탐색기의 8/11 단계(2월 30일 줄)로 열림. `0`~`4` 키 동작, 콘솔 오류 0, 375px 에서 가로 스크롤 없음(버튼 줄만 안에서 넘김)
- 확인하지 못한 것: 손으로 고친 뒤의 사람 눈 검토는 화면 캡처 수준(archify 의 별도 시각 검사 단계는 돌리지 않음), Windows · Safari
