/*
 * 특수 장면 — 일반 엔진(seq · gate · states · graph)으로 그리기 어려운 것들.
 *   home      처음 화면 (질문 카드)
 *   stream    제너레이터가 한 줄씩 흐르는 모습 (메모리에 무엇이 남나)
 *   atomic    _rewrite 원자적 교체 (원본 · 임시 파일 두 칸)
 *   csvimport import 두 단계 (검증 → 한꺼번에 저장)
 *   typecheck 타입 힌트와 mypy 가 잡은 줄
 *   table     표 정렬 — 글자 수 대 화면 폭
 *   bench     10만 건 측정 (가로 막대)
 *   formats   같은 거래의 JSONL · CSV 두 모양
 *   demo      시연 체크리스트
 * 모든 장면은 engine.js 와 같은 약속(count · go(k) · setScenario)을 지키고, k 단계 그림을 매번 처음부터 다시 계산한다.
 */
(function () {
  "use strict";
  const FX = window.FX;
  const { h } = FX;

  // 단계가 있는 특수 장면의 공통 틀
  function controller(spec) {
    let token = new FX.Token();
    return {
      scenarios: spec.scenarios || null,
      setScenario: spec.setScenario || (() => {}),
      count: spec.count || (() => 0),
      async go(k, anim) {
        token.cancel();
        token = new FX.Token();
        await spec.draw(k, anim, token);
      },
      destroy() {
        token.cancel();
        if (spec.destroy) spec.destroy();
      },
    };
  }
  const pick = (list, id) => list.find((x) => x.id === id) || list[0];
  const scenarioList = (scene) => scene.scenarios.map((x) => ({ id: x.id, label: x.label, tone: x.tone }));
  const asList = (v) => (v === undefined || v === null ? [] : [].concat(v));
  const fmt = (n) => n.toLocaleString("ko-KR");
  const won = (n) => fmt(n) + "원";
  const idNum = (id) => Number(String(id).split("-")[1]);

  // host 안에서 fromEl 자리 → toEl 자리로 작은 칩을 날린다 (단계가 바뀌는 순간의 움직임)
  async function fly(host, fromEl, toEl, label, cls, tk) {
    if (!host || !fromEl || !toEl || FX.reduced) return;
    const hr = host.getBoundingClientRect();
    const a = fromEl.getBoundingClientRect();
    const b = toEl.getBoundingClientRect();
    const chip = h("div", { class: "fly " + (cls || ""), text: label });
    host.append(chip);
    const x0 = a.left - hr.left + a.width / 2;
    const y0 = a.top - hr.top + a.height / 2;
    const x1 = b.left - hr.left + b.width / 2;
    const y1 = b.top - hr.top + b.height / 2;
    await FX.tween(FX.dur(620), (t) => {
      chip.style.left = x0 + (x1 - x0) * t + "px";
      chip.style.top = y0 + (y1 - y0) * t - Math.sin(Math.PI * t) * 24 + "px";
    }, tk);
    chip.remove();
  }

  // 시나리오의 cmd + 단계별 out 을 쌓아 보여 주는 터미널 하나
  function outPane(title) {
    const t = FX.terminal(title || "터미널", "out");
    return {
      el: t.el,
      show(sc, k, steps) {
        const head = asList(sc.cmd).map((c) => "$ " + c);
        const list = steps || sc.steps;
        const lines = head.concat(list.slice(0, k + 1).flatMap((st) => asList(st.out)));
        const cur = k >= 0 ? list[k] : null;
        t.show(lines, cur ? asList(cur.out).length : 0, "아직 출력이 없어요");
      },
    };
  }

  /* ===================== home ===================== */
  FX.types.home = function (stage, scene, ctx) {
    const svg = document.querySelector(".mascot svg").cloneNode(true);
    svg.setAttribute("class", "big-mascot");
    const scenes = FX.scenes.filter((x) => x.id !== "home");
    const scenarioCount = scenes.reduce((n, x) => n + (x.scenarios ? x.scenarios.length : 0), 0);
    stage.append(
      h("div", { class: "card home-hero" }, svg,
        h("div", null,
          h("h2", { text: "질문이 오면, 흐름을 재생하면서 답해요" }),
          h("p", { text: scene.lead }),
          h("div", { class: "stats" },
            h("span", { text: `장면 ${scenes.length}개` }),
            h("span", { text: `시나리오 ${scenarioCount}개` }),
            h("span", { text: "인터넷 없이 동작" })))),
      h("h2", { class: "section-title", text: "동료가 이렇게 물으면 → 이 장면" }),
      h("div", { class: "ask-grid" }, scene.questions.map((q, k) => {
        const target = FX.scenes.find((x) => x.id === q.to);
        return h("button", {
          class: "ask-card", type: "button", style: { animationDelay: k * 25 + "ms" },
          onclick: () => ctx.navigate(q.to, q.s),
        }, q.no ? h("em", { class: "qno", text: q.no }) : null, h("q", { text: q.q }), h("span", { text: `→ ${target ? target.navTitle || target.title : q.to}` }));
      })),
      h("h2", { class: "section-title", text: "쓰는 법" }),
      h("ul", { class: "notes" }, scene.howto.map((t) => h("li", { text: t }))));
    return controller({ draw: () => ctx.say({ say: scene.intro, intro: true }) });
  };

  /* ===================== stream : 제너레이터 ===================== */
  // 시나리오 mode
  //   heap    list --limit N   : heapq.nlargest 가 N 건만 들고 있는다
  //   collect search (limit 없음): 조건에 맞은 것을 모두 모은 뒤 sorted
  //   find    find(id)         : 찾는 순간 멈춘다
  //   all     list(stream())   : 비교용 — 전부 메모리에
  // 파일 줄에 { broken: true } 가 있으면 그 줄에서 손상 오류로 멈춘다
  const recency = (t) => `${t.date}|${String(idNum(t.id)).padStart(6, "0")}`;
  function matchesFilter(f, t) {
    if (!f) return true;
    if (f.category && t.cat !== f.category) return false;
    if (f.tag && !t.tags.includes(f.tag)) return false;
    return true;
  }
  function filterMiss(f, t) {
    if (f.category && t.cat !== f.category) return `카테고리가 ${t.cat}`;
    if (f.tag && !t.tags.includes(f.tag)) return `태그에 ${f.tag} 가 없음 (${t.tags.join(",") || "태그 없음"})`;
    return "";
  }
  function simulateStream(lines, sc) {
    const out = [{ kind: "start", read: -1, mem: [] }];
    let mem = [];
    for (let i = 0; i < lines.length; i++) {
      const t = lines[i];
      if (t.broken) {
        out.push({ kind: "error", read: i, mem: [], lost: mem.slice() });
        return out;
      }
      let verdict = "keep";
      let evicted = null;
      if (sc.mode === "find") {
        verdict = t.id === sc.find ? "found" : "pass";
      } else if (!matchesFilter(sc.filter, t)) {
        verdict = "filtered";
      } else if (sc.mode === "heap") {
        if (mem.length < sc.limit) mem = mem.concat(t);
        else {
          const oldest = mem.reduce((a, b) => (recency(a) < recency(b) ? a : b));
          if (recency(t) > recency(oldest)) {
            evicted = oldest;
            mem = mem.filter((x) => x !== oldest).concat(t);
          } else verdict = "drop";
        }
      } else mem = mem.concat(t);
      out.push({ kind: "read", read: i, verdict, evicted, mem: mem.slice() });
      if (verdict === "found") {
        out.push({ kind: "found", read: i, mem: [], found: t });
        return out;
      }
    }
    out.push({ kind: "end", read: lines.length, mem: mem.slice().sort((a, b) => (recency(a) < recency(b) ? 1 : -1)) });
    return out;
  }
  function streamSay(st, sc, lines) {
    const t = st.read >= 0 && st.read < lines.length ? lines[st.read] : null;
    const no = st.read + 1;
    const tag = (x) => `${x.id}(${x.date.slice(5)})`;
    switch (st.kind) {
      case "start":
        return "stream() 을 불렀어요. 돌아온 건 제너레이터 객체뿐이고 파일은 아직 열지도 않았어요. 받는 쪽이 next() 로 달라고 할 때마다 한 줄씩 읽어요.";
      case "read":
        if (st.verdict === "pass") return `${no}번째 줄 ${t.id} — 찾는 id 가 아니라서 다음 줄을 달라고 해요.`;
        if (st.verdict === "filtered") return `${no}번째 줄 ${tag(t)} — matching 의 조건에 안 맞아요(${filterMiss(sc.filter, t)}). 여기서 버려서 고르는 단계까지 가지 않아요.`;
        if (st.verdict === "drop") return `${no}번째 줄 ${tag(t)} — 들고 있는 ${sc.limit}건보다 오래돼서 받자마자 버려요. 메모리는 그대로 ${sc.limit}건이에요.`;
        if (st.evicted) return `${no}번째 줄 ${tag(t)} — 들고 있던 것 중 가장 오래된 ${tag(st.evicted)}보다 최신이라 그걸 버리고 넣어요. 메모리는 여전히 ${sc.limit}건이에요.`;
        if (sc.mode === "heap") return `${no}번째 줄을 읽어 Transaction ${tag(t)} 으로 바꿔 yield 했어요. nlargest 가 받아 들고 있어요 — 아직 ${sc.limit}건이 안 돼서 그냥 넣어요.`;
        if (sc.mode === "all") return `${no}번째 줄 ${tag(t)} — list() 는 하나도 버리지 않고 다 담아요. 지금 메모리에 ${st.mem.length}건.`;
        return `${no}번째 줄 ${tag(t)} — 조건에 맞아요. --limit 이 없어서 정렬하려고 모아 둬요(지금 ${st.mem.length}건).`;
      case "found":
        return `${no}번째 줄에서 ${t.id} 를 찾았어요. next() 가 하나를 받으면 더 달라고 하지 않아서, 뒤의 ${lines.length - no}줄은 객체로 바꾸지도 않아요. 그 줄이 깨져 있어도 오류가 나지 않아요.`;
      case "error":
        return `${no}번째 줄이 JSON 이 아니에요. 건너뛰지 않고 손상 오류로 멈춰요. 들고 있던 것도 버리고, 화면에는 몇 번째 줄인지 알려 줘요 — 건너뛰면 합계가 조용히 틀리기 때문이에요.`;
      case "end":
        if (sc.mode === "heap") return `파일 끝(StopIteration). 들고 있던 ${sc.limit}건을 최신순으로 정렬해 돌려줘요. ${lines.length}줄을 읽었지만 메모리에는 끝까지 ${sc.limit}건만 있었어요.`;
        if (sc.mode === "all") return `파일 끝. list() 는 ${st.mem.length}건을 전부 메모리에 올렸어요. 10만 건이면 55MB 예요(list --limit 10 은 0.05MB).`;
        return `파일 끝. 모아 둔 ${st.mem.length}건을 sorted 로 최신순 정렬해요. 파일 전체가 아니라 맞은 것만 모았지만, 조건이 없으면 전부가 돼요 — --limit 을 주면 heapq 로 그만큼만 들고 있어요.`;
      default:
        return "";
    }
  }
  FX.types.stream = function (stage, scene, ctx) {
    const root = h("div", { class: "stream" });
    const fileList = h("ol", { class: "st-lines" });
    const fileCard = h("div", { class: "card st-file own-file" }, h("h3", null, "transactions.jsonl ", h("small", { text: "등록 순서 = 줄 순서" })), fileList);
    const pipe = h("div", { class: "st-pipe" });
    const memSlots = h("div", { class: "st-slots" });
    const trash = h("div", { class: "st-trash" });
    const meter = h("div", { class: "st-meter" });
    const memCard = h("div", { class: "card st-mem own-S" }, h("h3", { text: "메모리에 들고 있는 거래" }), memSlots, meter, h("div", { class: "st-trash-wrap" }, h("span", { class: "st-trash-label", text: "버림" }), trash));
    root.append(fileCard, pipe, memCard);
    const out = outPane();
    stage.append(root, out.el);

    let sc = null;
    let lines = [];
    let steps = [];
    const lineEls = [];

    function buildFile() {
      lineEls.length = 0;
      fileList.replaceChildren(...lines.map((t, i) => {
        const el = t.broken
          ? h("li", { class: "st-line broken" }, h("span", { class: "no", text: String(i + 1) }), h("code", { text: t.raw }))
          : h("li", { class: "st-line" }, h("span", { class: "no", text: String(i + 1) }),
            h("code", null, h("b", { text: t.id }), ` ${t.date} · ${t.cat} · ${fmt(t.amt)}`, t.tags.length ? h("i", { text: ` [${t.tags.join(",")}]` }) : null),
            h("span", { class: "mark" }));
        lineEls.push(el);
        return el;
      }));
      const stages = {
        heap: ["stream()  한 줄 → yield", `heapq.nlargest(${sc.limit})  최신 ${sc.limit}건만`],
        collect: ["stream()  한 줄 → yield", "matching  조건 거르기", "sorted(…)  전부 모아 정렬"],
        find: ["stream()  한 줄 → yield", "next(… if id == …, None)  첫 번째만"],
        all: ["stream()  한 줄 → yield", "list(…)  전부 담기"],
      }[sc.mode];
      pipe.replaceChildren(...stages.flatMap((label, j) => {
        const [fn, ...rest] = label.split("  ");
        const box = h("div", { class: `st-stage ${j === 0 ? "own-R" : "own-S"}` }, h("b", { text: fn }), h("small", { text: rest.join(" ") }));
        return j ? [h("span", { class: "st-arrow", "aria-hidden": "true", text: "↓" }), box] : [box];
      }));
    }

    function render(k) {
      const st = k >= 0 ? steps[k] : steps[0];
      const seen = steps.slice(0, k + 1).filter((x) => x.kind === "read" || x.kind === "error");
      const verdictOf = {};
      seen.forEach((x) => { verdictOf[x.read] = x.kind === "error" ? "error" : x.verdict; });
      const memIds = new Set(st.mem.map((t) => t.id));
      const evictedIds = new Set(steps.slice(0, k + 1).filter((x) => x.evicted).map((x) => x.evicted.id));
      const found = steps.slice(0, k + 1).find((x) => x.kind === "found");
      lineEls.forEach((el, i) => {
        const v = verdictOf[i];
        const t = lines[i];
        el.className = "st-line" + (t.broken ? " broken" : "") + (v === undefined ? " unread" : " read") + (st.read === i && st.kind !== "end" ? " now" : "");
        const mark = el.querySelector(".mark");
        let text = "";
        if (v === "error") { el.classList.add("bad"); text = "손상!"; }
        else if (v === "filtered") { el.classList.add("gone"); text = "조건 ✕"; }
        else if (v === "drop") { el.classList.add("gone"); text = "버림"; }
        else if (v === "pass") text = "아님";
        else if (v === "found" || (found && found.found.id === t.id)) { el.classList.add("hit"); text = "찾음"; }
        else if (memIds.has(t.id)) { el.classList.add("held"); text = "메모리"; }
        else if (t && evictedIds.has(t.id)) { el.classList.add("gone"); text = "밀려남"; }
        if (mark) mark.textContent = text;
      });
      memSlots.replaceChildren(
        ...(st.mem.length ? st.mem.map((t) => h("span", { class: "st-chip", dataset: { id: t.id } }, h("b", { text: t.id }), ` ${t.date.slice(5)}`)) : [h("span", { class: "st-empty", text: st.kind === "error" ? "오류로 멈춤 — 비움" : "비어 있음" })]),
        ...(sc.mode === "heap" ? Array.from({ length: Math.max(0, sc.limit - st.mem.length) }, () => h("span", { class: "st-chip slot" })) : []));
      const gone = [];
      if (st.kind === "read" && st.evicted) gone.push(st.evicted);
      if (st.kind === "read" && (st.verdict === "filtered" || st.verdict === "drop")) gone.push(lines[st.read]);
      if (st.kind === "error") gone.push(...st.lost);
      trash.replaceChildren(...gone.map((t) => h("span", { class: "st-chip out" }, h("b", { text: t.id }))));
      const readCount = Math.min(lines.length, seen.length);
      const peak = Math.max(0, ...steps.slice(0, k + 1).map((x) => x.mem.length));
      meter.replaceChildren(
        h("span", null, "읽은 줄 ", h("b", { text: `${readCount} / ${lines.length}` })),
        h("span", null, "지금 메모리 ", h("b", { text: `${st.mem.length}건` })),
        h("span", null, "가장 많을 때 ", h("b", { text: `${peak}건` })));
      out.show(sc, k, steps);
    }

    async function animate(k, tk) {
      const st = steps[k];
      if (st.kind !== "read") return;
      const from = lineEls[st.read];
      FX.reveal(from);
      const t = lines[st.read];
      let to = trash;
      let cls = "bad";
      if (st.verdict === "keep" || st.verdict === "found") {
        to = memSlots.querySelector(`[data-id="${t.id}"]`) || memSlots;
        cls = "";
      } else if (st.verdict === "pass") {
        to = pipe.lastElementChild;
        cls = "muted";
      }
      await fly(root, from, to, t.id, cls, tk);
    }

    return controller({
      scenarios: scenarioList(scene),
      setScenario(id) {
        sc = pick(scene.scenarios, id);
        lines = sc.lines || scene.file;
        steps = simulateStream(lines, sc).map((st, j) => ({ ...st, out: j === 0 ? [] : null }));
        // 마지막 단계에 실제 화면 출력을 붙인다
        steps[steps.length - 1].out = sc.out || [];
        buildFile();
      },
      count: () => steps.length,
      async draw(k, anim, tk) {
        if (anim && k >= 0) {
          render(k);
          ctx.say({ say: (sc.says && sc.says[k]) || streamSay(steps[k], sc, lines), code: sc.code });
          await animate(k, tk);
        } else {
          render(k);
          if (k < 0) ctx.say({ say: sc.intro || scene.intro, code: sc.code, intro: true });
          else ctx.say({ say: (sc.says && sc.says[k]) || streamSay(steps[k], sc, lines), code: sc.code });
        }
      },
    });
  };

  /* ===================== atomic : 원자적 교체 ===================== */
  // 단계 op: open · copy(n) · change(text) · skip · flush · fsync · replace · finally · fail(msg)
  //          direct(원본을 'w' 로 열기) · crash(전원이 꺼짐)
  const PHASES = [
    { id: "open", label: "① 임시 파일 열기" },
    { id: "write", label: "② 한 줄씩 쓰기" },
    { id: "flush", label: "③ flush" },
    { id: "fsync", label: "④ os.fsync" },
    { id: "replace", label: "⑤ os.replace" },
    { id: "finally", label: "⑥ finally: tmp 지우기" },
  ];
  function simulateAtomic(orig, ops) {
    const states = [];
    let st = { orig: orig.map((text) => ({ text, s: "disk" })), tmp: null, cursor: 0, phase: null, banner: null, direct: false };
    const clone = (x) => ({ ...x, orig: x.orig.map((l) => ({ ...l })), tmp: x.tmp && x.tmp.map((l) => ({ ...l })) });
    for (const op of ops) {
      st = clone(st);
      st.banner = null;
      const target = () => (st.direct ? st.orig : st.tmp);
      switch (op.op) {
        case "open": st.tmp = []; st.phase = "open"; break;
        case "direct": st.direct = true; st.saved = orig.slice(); st.orig = []; st.phase = "open"; break;
        case "copy":
          for (let j = 0; j < op.n; j++) {
            const text = st.direct ? st.saved[st.cursor] : st.orig[st.cursor].text;
            target().push({ text, s: "buf" });
            st.cursor += 1;
          }
          st.phase = "write";
          break;
        case "change":
          target().push({ text: op.text, s: "buf", changed: true });
          st.cursor += 1;
          st.phase = "write";
          break;
        case "skip":
          st.orig[st.cursor].skipped = true;
          st.cursor += 1;
          st.phase = "write";
          break;
        case "flush": st.tmp.forEach((l) => { l.s = "os"; }); st.phase = "flush"; break;
        case "fsync": st.tmp.forEach((l) => { l.s = "disk"; }); st.phase = "fsync"; break;
        case "replace": st.orig = st.tmp.map((l) => ({ ...l, s: "disk" })); st.tmp = null; st.replaced = true; st.phase = "replace"; break;
        case "finally": st.tmpRemoved = !!st.tmp; st.tmp = null; st.phase = "finally"; break;
        case "fail": st.failed = op.msg || "오류"; st.phase = op.phase || st.phase; break;
        case "crash":
          st.crashed = true;
          st.lost = st.saved.slice(st.orig.length);
          st.orig = st.orig.filter((l) => l.s !== "buf" || op.keepBuffered);
          break;
        default: break;
      }
      st.op = op;
      states.push(st);
    }
    return states;
  }
  // 말할 문장을 적지 않은 단계는 그 동작을 그대로 읽어 준다 (빈 말풍선 방지)
  function atomicSay(op) {
    switch (op.op) {
      case "open": return "같은 폴더에 transactions.jsonl.tmp 를 'w' 로 열어요. 원본은 그대로예요.";
      case "copy": return `원본에서 ${op.n}줄을 읽어 그대로 임시 파일에 써요.`;
      case "change": return "고칠 줄은 새 값으로 바꿔 써요.";
      case "skip": return "지울 줄은 쓰지 않고 넘어가요.";
      case "flush": return "flush — 파이썬 버퍼 → 운영체제.";
      case "fsync": return "os.fsync — 운영체제 → 디스크.";
      case "replace": return "os.replace — 임시 파일을 원본 자리로 한 번에 바꿔치기해요.";
      case "finally": return "finally — 남은 임시 파일이 있으면 지워요.";
      case "fail": return `실패: ${op.msg}. 예외가 위로 올라가요.`;
      default: return "";
    }
  }
  FX.types.atomic = function (stage, scene, ctx) {
    const stepper = h("ol", { class: "at-phases" }, PHASES.map((p) => h("li", { dataset: { phase: p.id }, text: p.label })));
    const origList = h("ol", { class: "at-lines" });
    const tmpList = h("ol", { class: "at-lines" });
    const origBadge = h("span", { class: "at-badge" });
    const tmpBadge = h("span", { class: "at-badge" });
    const origCard = h("div", { class: "card at-file own-R" }, h("h3", null, "transactions.jsonl ", origBadge), origList);
    const tmpCard = h("div", { class: "card at-file at-tmp own-T" }, h("h3", null, "transactions.jsonl.tmp ", tmpBadge), tmpList);
    const legend = h("div", { class: "at-legend" },
      h("span", { class: "s-buf" }, "파이썬 버퍼"), h("span", { class: "s-os" }, "운영체제"), h("span", { class: "s-disk" }, "디스크"));
    const banner = h("div", { class: "at-banner", hidden: true });
    const root = h("div", { class: "atomic" }, stepper, h("div", { class: "at-files" }, origCard, h("div", { class: "at-mid", "aria-hidden": "true" }, "⇄"), tmpCard), legend, banner);
    const out = outPane();
    stage.append(root, out.el);

    let sc = null;
    let states = [];

    function lineEl(l, j) {
      return h("li", { class: `at-line s-${l.s}${l.changed ? " changed" : ""}${l.skipped ? " skipped" : ""}` },
        h("span", { class: "no", text: String(j + 1) }), h("code", { text: l.text }));
    }
    function render(k) {
      const st = k >= 0 ? states[k] : { orig: scene.orig.map((text) => ({ text, s: "disk" })), tmp: null, phase: null };
      for (const li of stepper.children) {
        const idx = PHASES.findIndex((p) => p.id === li.dataset.phase);
        const cur = PHASES.findIndex((p) => p.id === st.phase);
        li.className = (li.dataset.phase === st.phase ? "now" : idx < cur ? "done" : "") + (st.failed && li.dataset.phase === st.phase ? " fail" : "");
      }
      stepper.hidden = !!(sc && sc.direct);
      origList.replaceChildren(...(st.orig.length ? st.orig.map(lineEl) : [h("li", { class: "at-empty", text: "비어 있음 — 'w' 로 여는 순간 원본이 지워졌어요" })]),
        ...asList(st.lost).map((text) => h("li", { class: "at-line lost" }, h("span", { class: "no", text: "✕" }), h("code", { text }))));
      origBadge.textContent = st.crashed ? "반쪽만 남음!" : st.replaced ? "새 내용" : st.direct ? "쓰는 중 (원본 자리)" : "옛 내용 그대로";
      origBadge.className = "at-badge " + (st.crashed ? "bad" : st.replaced ? "ok" : "");
      tmpCard.classList.toggle("gone", !st.tmp);
      tmpList.replaceChildren(...(st.tmp ? (st.tmp.length ? st.tmp.map(lineEl) : [h("li", { class: "at-empty", text: "열었어요 — 아직 빈 파일" })]) : [h("li", { class: "at-empty", text: st.tmpRemoved ? "finally 가 지웠어요" : st.replaced ? "원본 자리로 옮겨 갔어요" : "아직 없음" })]));
      tmpBadge.textContent = st.tmp ? `${st.tmp.length}줄` : "";
      tmpCard.classList.toggle("unused", !!(sc && sc.direct));
      const b = k >= 0 ? (st.op && st.op.banner) || (st.failed ? `실패: ${st.failed}` : null) : null;
      banner.hidden = !b;
      banner.textContent = b || "";
      // 실패했어도 '원본 그대로'라는 결과 문구(op.banner)는 좋은 소식이라 초록으로
      banner.className = "at-banner " + (st.crashed ? "bad" : st.op && st.op.banner ? "ok" : st.failed ? "bad" : "");
      out.show(sc, k);
    }

    return controller({
      scenarios: scenarioList(scene),
      setScenario(id) {
        sc = pick(scene.scenarios, id);
        states = simulateAtomic(scene.orig, sc.steps);
      },
      count: () => states.length,
      async draw(k, anim, tk) {
        render(k);
        const st = k >= 0 ? sc.steps[k] : null;
        ctx.say(st ? { say: st.say || atomicSay(st), code: st.code || sc.code } : { say: sc.intro || scene.intro, code: sc.code, intro: true });
        if (anim && st && (st.op === "replace")) {
          FX.replay(origCard, "swap-in");
          await FX.wait(FX.dur(500), tk);
        }
      },
    });
  };

  /* ===================== csvimport : 두 단계 import ===================== */
  // 단계 at: "header" · 행 번호(2, 3, …) · "append" · "fail"
  function importSay(st, sc, k) {
    if (st.at === "header") return st.fail ? "헤더에 필수 컬럼이 없어요." : "헤더에 필수 컬럼(date,type,category,amount)이 다 있어요.";
    if (st.at === "append") {
      const n = sc.rows.filter((r) => r.ok && sc.steps.slice(0, k + 1).some((x) => x.at === r.n)).length;
      return `검증이 끝난 뒤 append(valid) 한 번으로 ${n}건을 끝에 붙여요.`;
    }
    if (st.at === "fail") return "읽기 단계에서 끝나서 저장 파일은 바이트 하나 안 바뀌어요. 종료 코드 1.";
    if (st.at === "done") return "부분 성공 + 줄 번호 · 이유 보고로 끝나요. 종료 코드 0.";
    const r = sc.rows.find((x) => x.n === st.at);
    if (!r) return "";
    if (st.fail) return `${r.n}번째 줄을 읽다가 실패했어요.`;
    return r.ok ? `${r.n}번째 줄 — 통과. ${r.id} 를 붙여 valid 에 담아요(아직 메모리에만).` : `${r.n}번째 줄 — 건너뜀: ${r.why}`;
  }
  FX.types.csvimport = function (stage, scene, ctx) {
    const csvList = h("ol", { class: "ci-csv" });
    const validBox = h("div", { class: "ci-chips" });
    const skipBox = h("ul", { class: "ci-skips" });
    const fileList = h("ol", { class: "ci-file" });
    const phase = h("div", { class: "ci-phase" });
    const root = h("div", { class: "csvimport" },
      h("div", { class: "card ci-col own-file" }, h("h3", null, "CSV 파일 ", h("small", { class: "ci-name" })), csvList),
      h("div", { class: "card ci-col own-S" }, h("h3", { text: "1단계: 검증만 (메모리)" }), phase,
        h("h4", { text: "valid — 넣을 거래" }), validBox, h("h4", { text: "skipped — 건너뛸 줄과 이유" }), skipBox),
      h("div", { class: "card ci-col own-R" }, h("h3", null, "transactions.jsonl ", h("small", { text: "2단계에서만 바뀜" })), fileList));
    const out = outPane();
    stage.append(root, out.el);

    let sc = null;
    const rowEls = {};

    function build() {
      root.querySelector(".ci-name").textContent = sc.file;
      csvList.replaceChildren(...sc.rows.map((r) => {
        const el = h("li", { class: "ci-row" }, h("span", { class: "no", text: String(r.n) }), h("code", { text: r.text }), h("span", { class: "mark" }));
        rowEls[r.n] = el;
        return el;
      }));
    }
    function render(k) {
      const done = sc.steps.slice(0, k + 1);
      const cur = k >= 0 ? sc.steps[k] : null;
      const failed = done.find((x) => x.at === "fail");
      const appended = done.some((x) => x.at === "append");
      const headerOk = done.some((x) => x.at === "header" && !x.fail);
      const valid = [];
      const skipped = [];
      for (const r of sc.rows) {
        const el = rowEls[r.n];
        const step = done.find((x) => x.at === r.n || (r.n === 1 && x.at === "header"));
        el.className = "ci-row" + (step ? " seen" : " unread") + (cur && (cur.at === r.n || (r.n === 1 && cur.at === "header")) ? " now" : "");
        const mark = el.querySelector(".mark");
        mark.textContent = "";
        if (!step) continue;
        if (r.n === 1) { mark.textContent = step.fail ? "✕ 헤더" : "✓ 헤더"; el.classList.add(step.fail ? "bad" : "ok"); continue; }
        if (step.fail) { mark.textContent = "✕ 못 읽음"; el.classList.add("bad"); continue; }
        if (r.ok) { valid.push(r); mark.textContent = `✓ ${r.id}`; el.classList.add("ok"); }
        else { skipped.push(r); mark.textContent = "✕ 건너뜀"; el.classList.add("ci-skip"); }
      }
      const discarded = !!failed;
      validBox.replaceChildren(...(valid.length ? valid.map((r) => h("span", { class: "st-chip" + (discarded ? " out" : r.dup ? " dup" : "") }, h("b", { text: r.id }))) : [h("span", { class: "st-empty", text: "아직 없음" })]));
      skipBox.replaceChildren(...(skipped.length ? skipped.map((r) => h("li", null, h("b", { text: `${r.n}번째 줄` }), ` ${r.why}`)) : [h("li", { class: "st-empty", text: "없음" })]));
      phase.textContent = failed ? "읽다가 실패 → 모아 둔 것을 버리고 끝 (저장 0건)" : appended ? "2단계 끝: 한 번에 저장했어요" : headerOk ? "한 행씩 검증 중 — 아직 파일은 그대로" : k >= 0 ? "헤더 검사" : "시작 전";
      phase.className = "ci-phase " + (failed ? "bad" : appended ? "ok" : "");
      const before = asList(sc.before);
      const added = appended ? valid.map((r) => r.id + (r.dup ? " (중복!)" : "")) : [];
      fileList.replaceChildren(
        ...(before.length + added.length ? [] : [h("li", { class: "st-empty", text: "비어 있음" })]),
        ...before.map((id) => h("li", { class: "ci-old" }, h("code", { text: id }))),
        ...added.map((id) => h("li", { class: "ci-new" + (id.includes("중복") ? " dup" : "") }, h("code", { text: id }))));
      out.show(sc, k);
    }
    return controller({
      scenarios: scenarioList(scene),
      setScenario(id) { sc = pick(scene.scenarios, id); build(); },
      count: () => sc.steps.length,
      async draw(k, anim, tk) {
        render(k);
        const st = k >= 0 ? sc.steps[k] : null;
        ctx.say(st ? { say: st.say || importSay(st, sc, k), code: st.code || sc.code } : { say: sc.intro || scene.intro, code: sc.code, intro: true });
        if (anim && st && typeof st.at === "number") {
          const r = sc.rows.find((x) => x.n === st.at);
          const el = rowEls[st.at];
          FX.reveal(el);
          if (r && !st.fail) await fly(root, el, r.ok ? validBox : skipBox, r.ok ? r.id : `${r.n}번째 줄`, r.ok ? "" : "bad", tk);
        }
      },
    });
  };

  /* ===================== typecheck : 타입 힌트 ===================== */
  FX.types.typecheck = function (stage, scene, ctx) {
    const codeHead = h("div", { class: "tc-head" });
    const codeList = h("ol", { class: "tc-code" });
    const contract = h("div", { class: "tc-contract" });
    const term = FX.terminal("mypy — 실행하지 않고 읽기만 해요", "out");
    stage.append(h("div", { class: "typecheck" },
      h("div", { class: "card tc-src" }, codeHead, codeList),
      h("div", { class: "tc-side" }, contract, term.el)));

    let sc = null;
    const lineEls = {};
    function build() {
      const block = scene.code[sc.code];
      codeHead.replaceChildren(h("b", { text: block.file }), h("small", { text: block.note || "" }));
      for (const key of Object.keys(lineEls)) delete lineEls[key];
      // 줄은 문자열(start 부터 차례로 번호) 또는 { n: "storage 76", t: "…" }(여러 파일에서 모은 줄)
      codeList.replaceChildren(...block.lines.map((line, j) => {
        const n = String(typeof line === "object" ? line.n : block.start + j);
        const text = typeof line === "object" ? line.t : line;
        const el = h("li", { class: "tc-line" + (/^\s*#/.test(text) ? " cm" : "") }, h("span", { class: "no", text: n }), h("code", { text: text || " " }));
        lineEls[n] = el;
        return el;
      }));
      codeList.classList.toggle("wide-no", block.lines.some((line) => typeof line === "object"));
    }
    function render(k) {
      const cur = k >= 0 ? sc.steps[k] : null;
      const seen = sc.steps.slice(0, k + 1);
      const keys = (v) => asList(v).map(String);
      const hit = new Set(seen.flatMap((x) => keys(x.err)));
      const note = new Set(seen.flatMap((x) => keys(x.note)));
      const now = new Set(cur ? keys(cur.err).concat(keys(cur.note)) : []);
      for (const [n, el] of Object.entries(lineEls)) {
        el.classList.toggle("err", hit.has(n));
        el.classList.toggle("rev", note.has(n));
        el.classList.toggle("now", now.has(n));
      }
      const lines = ["$ " + sc.cmd].concat(seen.flatMap((x) => asList(x.out)));
      term.show(lines, cur ? asList(cur.out).length : 0);
      if (cur && cur.contract) {
        contract.replaceChildren(h("span", { class: "tc-tag", text: "이 약속 덕분" }), h("code", { text: cur.contract.text }), h("small", { text: cur.contract.where }));
        contract.hidden = false;
      } else contract.hidden = true;
      if (cur) {
        const first = keys(cur.err)[0] || keys(cur.note)[0];
        if (first && lineEls[first]) requestAnimationFrame(() => lineEls[first].scrollIntoView({ block: "nearest", behavior: FX.reduced ? "auto" : "smooth" }));
      }
    }
    return controller({
      scenarios: scenarioList(scene),
      setScenario(id) { sc = pick(scene.scenarios, id); build(); },
      count: () => sc.steps.length,
      async draw(k) {
        render(k);
        const st = k >= 0 ? sc.steps[k] : null;
        ctx.say(st ? { say: st.say, code: st.code || sc.refs } : { say: sc.intro, code: sc.refs, intro: true });
      },
    });
  };

  /* ===================== table : 글자 수 대 화면 폭 ===================== */
  // formatter.py 의 display_width · _pad · render_table 을 그대로 옮긴 것 (넓은 글자 = 2칸)
  const isWide = (ch) => {
    const c = ch.codePointAt(0);
    return (c >= 0x1100 && c <= 0x115f) || (c >= 0x2e80 && c <= 0xa4cf) || (c >= 0xac00 && c <= 0xd7a3) ||
      (c >= 0xf900 && c <= 0xfaff) || (c >= 0xfe30 && c <= 0xfe4f) || (c >= 0xff00 && c <= 0xff60) || (c >= 0xffe0 && c <= 0xffe6);
  };
  const displayWidth = (t) => [...t].reduce((n, ch) => n + (isWide(ch) ? 2 : 1), 0);
  const charLen = (t) => [...t].length;
  function renderTable(headers, rows, aligns, measure) {
    const cols = headers.map((hd, j) => [hd, ...rows.map((r) => r[j])]);
    const widths = cols.map((col) => Math.max(...col.map(measure)));
    const pad = (t, w, a) => { const sp = " ".repeat(Math.max(0, w - measure(t))); return a === "right" ? sp + t : t + sp; };
    const lines = [headers.map((hd, j) => pad(hd, widths[j], "left")).join(" | ").replace(/\s+$/, "")];
    lines.push(widths.map((w) => "-".repeat(w)).join("-+-"));
    for (const r of rows) lines.push(r.map((c, j) => pad(c, widths[j], aligns[j])).join(" | ").replace(/\s+$/, ""));
    return lines;
  }
  function gridLine(text) {
    return h("div", { class: "tb-row" }, [...text].map((ch) => h("span", { class: "tb-c" + (isWide(ch) ? " w" : "") + (ch === "|" || ch === "+" ? " sep" : ""), text: ch === " " ? " " : ch })));
  }
  FX.types.table = function (stage, scene, ctx) {
    const words = h("div", { class: "tb-words" });
    const lenBox = h("div", { class: "card tb-box" });
    const widthBox = h("div", { class: "card tb-box" });
    stage.append(h("div", { class: "tbl" }, words, h("div", { class: "tb-tables" }, lenBox, widthBox)));
    const headers = ["ID", "날짜", "타입", "카테고리", "금액", "메모", "태그"];
    const aligns = ["left", "left", "left", "left", "right", "left", "left"];
    const rows = scene.rows.map((r) => [r.id, r.date, r.type, r.cat, won(r.amt), r.memo, r.tags.join(",")]);
    const byLen = renderTable(headers, rows, aligns, charLen);
    const byWidth = renderTable(headers, rows, aligns, displayWidth);
    let sc = null;
    function render(k) {
      const st = k >= 0 ? sc.steps[k] : { show: [] };
      const show = new Set(asList(st.show));
      words.replaceChildren(...scene.words.map((w) => h("div", { class: "tb-word" + (asList(st.focus).includes(w) ? " now" : "") },
        h("div", { class: "tb-row big" }, [...w].map((ch) => h("span", { class: "tb-c" + (isWide(ch) ? " w" : ""), text: ch === " " ? " " : ch }))),
        h("small", null, "len ", h("b", { text: String(charLen(w)) }), " · 화면 폭 ", h("b", { text: String(displayWidth(w)) })))));
      words.hidden = !show.has("words");
      lenBox.replaceChildren(h("h3", null, "len(글자 수)으로 맞추면 ", h("span", { class: "at-badge bad", text: "어긋남" })), ...byLen.map(gridLine));
      widthBox.replaceChildren(h("h3", null, "display_width(화면 폭)로 맞추면 ", h("span", { class: "at-badge ok", text: "맞음" })), ...byWidth.map(gridLine));
      lenBox.hidden = !show.has("len");
      widthBox.hidden = !show.has("width");
      widthBox.classList.toggle("focus-amount", show.has("amount"));
    }
    return controller({
      scenarios: scenarioList(scene),
      setScenario(id) { sc = pick(scene.scenarios, id); },
      count: () => sc.steps.length,
      async draw(k) {
        render(k);
        const st = k >= 0 ? sc.steps[k] : null;
        ctx.say(st ? { say: st.say, code: st.code || scene.code } : { say: scene.intro, code: scene.code, intro: true });
      },
    });
  };

  /* ===================== bench : 10만 건 측정 ===================== */
  // 막대 하나 = 한 기능. 한 번에 한 가지 잣대(시간 또는 메모리)만 그린다 — 축은 하나
  FX.types.bench = function (stage, scene, ctx) {
    const chart = h("div", { class: "bench-chart", role: "img" });
    const axis = h("div", { class: "bench-axis" });
    const tip = h("div", { class: "bench-tip", hidden: true });
    const table = h("table", { class: "mini-table" });
    stage.append(h("div", { class: "card bench" }, h("h3", { class: "bench-title" }), chart, axis, tip),
      h("details", { class: "bench-table" }, h("summary", { text: "표로 보기 (1만 건 · 10만 건)" }), table));
    let sc = null;
    const metricOf = (id) => scene.metrics[id];
    function buildTable() {
      table.replaceChildren(
        h("thead", null, h("tr", null, ["기능", "1만 건", "10만 건", "최대 메모리 (10만 건)", "이유"].map((t) => h("th", { text: t })))),
        h("tbody", null, scene.rows.map((r) => h("tr", null,
          h("td", { text: r.label }), h("td", { text: r.t1 }), h("td", { text: `${fmt(r.ms)} ms` }), h("td", { text: `${r.mb.toFixed(2)} MB` }), h("td", { text: r.why || "" })))));
    }
    function render(k) {
      const m = metricOf(sc.metric);
      const st = k >= 0 ? sc.steps[k] : null;
      const focus = new Set(st ? asList(st.focus) : []);
      const max = Math.max(...scene.rows.map((r) => r[m.key]));
      stage.querySelector(".bench-title").textContent = m.title;
      chart.setAttribute("aria-label", `${m.title} — 기능별 가로 막대`);
      chart.replaceChildren(...scene.rows.map((r) => {
        const v = r[m.key];
        const pct = Math.max(0.6, (v / max) * 100);
        const on = !st || focus.has(r.id);
        const showVal = focus.has(r.id) || (!st && v === max) || r.ref;
        const bar = h("div", { class: "bench-bar" + (r.ref ? " ref" : ""), style: { width: pct + "%" } });
        const row = h("div", { class: "bench-row" + (on ? "" : " dim") + (focus.has(r.id) ? " now" : ""), tabindex: "0" },
          h("span", { class: "bench-label", text: r.label }),
          h("div", { class: "bench-track" }, bar, showVal ? h("span", { class: "bench-val", text: m.fmt(v) }) : null));
        const showTip = () => {
          tip.hidden = false;
          tip.replaceChildren(h("b", { text: r.label }), h("span", { text: `${m.name} ${m.fmt(v)}` }), r.why ? h("small", { text: r.why }) : null);
          const host = chart.parentElement.getBoundingClientRect();
          const rr = row.getBoundingClientRect();
          tip.style.top = rr.bottom - host.top + 4 + "px";
        };
        row.addEventListener("mouseenter", showTip);
        row.addEventListener("focus", showTip);
        row.addEventListener("mouseleave", () => { tip.hidden = true; });
        row.addEventListener("blur", () => { tip.hidden = true; });
        return row;
      }));
      axis.replaceChildren(h("span", { text: "0" }), h("span", { text: m.fmt(max / 2) }), h("span", { text: m.fmt(max) }));
    }
    return controller({
      scenarios: scenarioList(scene),
      setScenario(id) { sc = pick(scene.scenarios, id); buildTable(); },
      count: () => sc.steps.length,
      async draw(k) {
        render(k);
        const st = k >= 0 ? sc.steps[k] : null;
        ctx.say(st ? { say: st.say, code: st.code || scene.code } : { say: sc.intro, code: scene.code, intro: true });
      },
    });
  };

  /* ===================== formats : JSONL · CSV ===================== */
  // 같은 Transaction 을 storage.py 와 같은 규칙으로 두 모양으로 찍는다
  //   JSONL: json.dumps(asdict(tx), ensure_ascii=False) — 구분자 ", " · ": "
  //   CSV  : csv.writer — 쉼표 · 따옴표가 든 칸만 따옴표로 감싼다, 태그는 쉼표로 이어 붙인다
  const FIELDS = ["id", "type", "date", "amount", "category", "memo", "tags"];
  const CSV_FIELDS = ["date", "type", "category", "amount", "memo", "tags"];
  const asciiEscape = (t) => [...t].map((ch) => (ch.charCodeAt(0) > 127 ? "\\u" + ch.charCodeAt(0).toString(16).padStart(4, "0") : ch)).join("");
  function jsonlSegments(tx, escapeAscii) {
    const q = (t) => `"${escapeAscii ? asciiEscape(t) : t}"`;
    const segs = [["{", ""]];
    FIELDS.forEach((f, j) => {
      segs.push([`"${f}"`, "key " + f], [": ", ""]);
      const v = tx[f];
      if (f === "amount") segs.push([String(v), "val num " + f]);
      else if (f === "tags") segs.push([`[${v.map(q).join(", ")}]`, "val list " + f]);
      else segs.push([q(v), "val str " + f + (f === "memo" ? " hangul" : "")]);
      if (j < FIELDS.length - 1) segs.push([", ", ""]);
    });
    segs.push(["}", ""]);
    return segs;
  }
  const csvCell = (t) => (/[",\n]/.test(t) ? `"${t.replace(/"/g, '""')}"` : t);
  function csvSegments(tx) {
    const segs = [];
    CSV_FIELDS.forEach((f, j) => {
      const v = f === "tags" ? tx.tags.join(",") : String(tx[f]);
      segs.push([csvCell(v), "val " + f + (f === "memo" ? " hangul" : "") + (f === "amount" ? " num" : "")]);
      if (j < CSV_FIELDS.length - 1) segs.push([",", "comma"]);
    });
    return segs;
  }
  FX.types.formats = function (stage, scene, ctx) {
    const jBox = h("div", { class: "fm-lines" });
    const cBox = h("div", { class: "fm-lines" });
    const altBox = h("div", { class: "fm-alt", hidden: true });
    stage.append(h("div", { class: "formats" },
      h("div", { class: "card fm-col own-R" }, h("h3", null, "transactions.jsonl ", h("small", { text: "내부 저장" })), jBox, altBox),
      h("div", { class: "card fm-col own-file" }, h("h3", null, "export.csv ", h("small", { text: "외부와 주고받기" })), cBox)));
    let sc = null;
    const seg = ([text, cls]) => h("span", { class: "fm-seg " + cls, text });
    function render(k) {
      const st = k >= 0 ? sc.steps[k] : null;
      const hl = new Set(st ? asList(st.hl) : []);
      jBox.replaceChildren(...scene.records.map((tx) => h("div", { class: "fm-line" }, jsonlSegments(tx, false).map(seg))));
      cBox.replaceChildren(
        h("div", { class: "fm-line header" }, CSV_FIELDS.map((f, j) => [seg([f, "head " + f]), j < CSV_FIELDS.length - 1 ? seg([",", "comma"]) : null])),
        ...scene.records.map((tx) => h("div", { class: "fm-line" }, csvSegments(tx).map(seg))));
      for (const el of stage.querySelectorAll(".fm-seg")) {
        const cls = el.className;
        const on = [...hl].some((key) => (key === "keys" ? /\bkey\b|\bhead\b/.test(cls) : new RegExp(`\\b${key}\\b`).test(cls)));
        el.classList.toggle("hl", on);
      }
      for (const box of [jBox, cBox]) box.classList.toggle("dim-rest", hl.size > 0);
      altBox.hidden = !(st && st.alt);
      if (st && st.alt) {
        altBox.replaceChildren(h("small", { text: "ensure_ascii=True(기본값)였다면" }),
          h("div", { class: "fm-line" }, jsonlSegments(scene.records[0], true).map(seg)));
        for (const el of altBox.querySelectorAll(".fm-seg.hangul")) el.classList.add("hl");
      }
    }
    return controller({
      scenarios: scenarioList(scene),
      setScenario(id) { sc = pick(scene.scenarios, id); },
      count: () => sc.steps.length,
      async draw(k) {
        render(k);
        const st = k >= 0 ? sc.steps[k] : null;
        ctx.say(st ? { say: st.say, code: st.code || scene.code } : { say: scene.intro, code: scene.code, intro: true });
      },
    });
  };

  /* ===================== demo : 시연 체크리스트 ===================== */
  FX.types.demo = function (stage, scene, ctx) {
    const KEY = "b2fx-demo";
    let done = {};
    try { done = JSON.parse(FX.store.get(KEY) || "{}") || {}; } catch { done = {}; }
    const fill = h("i");
    const label = h("span");
    const listEl = h("ol", { class: "demo-list" });
    function save() { FX.store.set(KEY, JSON.stringify(done)); }
    function paint() {
      const n = scene.items.filter((x) => done[x.id]).length;
      fill.style.width = (n / scene.items.length) * 100 + "%";
      label.textContent = `${n} / ${scene.items.length}`;
      listEl.replaceChildren(...scene.items.map((it, j) => {
        const box = h("input", { type: "checkbox", "aria-label": `${j + 1}. ${it.title} 끝`, checked: !!done[it.id] });
        box.addEventListener("change", () => { done[it.id] = box.checked; save(); paint(); });
        return h("li", { class: "demo-item" + (done[it.id] ? " checked" : ""), style: { animationDelay: j * 40 + "ms" } },
          box,
          h("div", null, h("b", { text: `${j + 1}. ${it.title}` }), h("small", { text: it.detail }), it.cmd ? h("code", { class: "demo-cmd", text: it.cmd }) : null),
          h("button", { class: "btn", type: "button", onclick: () => ctx.navigate(it.to, it.s) }, "장면 →"));
      }));
    }
    stage.append(
      h("div", { class: "demo-progress" }, h("b", { text: "시연 진행" }), h("div", { class: "bar" }, fill), label,
        h("button", { class: "btn", type: "button", onclick: () => { done = {}; save(); paint(); } }, "모두 지우기")),
      listEl,
      h("ul", { class: "notes" }, scene.notes.map((t) => h("li", { text: t }))));
    paint();
    return controller({ draw: () => ctx.say({ say: scene.intro, intro: true }) });
  };
})();
