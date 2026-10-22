/*
 * 흐름 탐색기 엔진 — 장면 종류마다 그리기와 움직임을 맡는다. (B7-1 탐색기의 엔진을 가져와 터미널 · app.log 창을 더했다)
 *   seq    : 순서도(참여자 칸 사이로 패킷이 오간다)
 *   gate   : 검문소(요청이 검사 줄을 타고 내려가다 걸리는 곳에서 나간다)
 *   states : 상태 기계(사건 버튼으로 상태를 옮긴다)
 *   graph  : 노드 지도(흐름을 재생하거나 노드를 눌러 설명을 본다)
 * 모든 장면은 같은 약속을 지킨다: count() 단계 수, go(k, animate) k 단계 상태로 그리기(+움직임), setScenario(id).
 * 상태는 매번 0..k 단계를 다시 계산해 그리므로, 이전·다음·건너뛰기가 언제나 같은 그림이 된다.
 */
(function () {
  "use strict";
  const FX = (window.FX = window.FX || {});
  FX.types = FX.types || {};
  FX.mocks = FX.mocks || {};
  FX.extras = FX.extras || {};
  FX.speed = 1;
  FX.reduced = !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  FX.ownerShort = { C: "CLI", S: "서비스", R: "저장소", M: "모델", T: "공통 도구", user: "사용자", file: "파일" };

  /* ── 요소 만들기 ── */
  function applyAttrs(el, attrs) {
    if (!attrs) return;
    for (const [key, value] of Object.entries(attrs)) {
      if (value === null || value === undefined || value === false) continue;
      if (key === "text") el.textContent = value;
      else if (key === "style" && typeof value === "object") {
        for (const [prop, v] of Object.entries(value)) {
          if (prop.startsWith("--")) el.style.setProperty(prop, v);
          else el.style[prop] = v;
        }
      } else if (key.startsWith("on") && typeof value === "function") el.addEventListener(key.slice(2), value);
      else if (key === "dataset") Object.assign(el.dataset, value);
      else el.setAttribute(key, value === true ? "" : value);
    }
  }
  function appendKids(el, kids) {
    for (const kid of kids.flat(Infinity)) {
      if (kid === null || kid === undefined || kid === false || kid === "") continue;
      el.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
    }
  }
  function h(tag, attrs, ...kids) {
    const el = document.createElement(tag);
    applyAttrs(el, attrs);
    appendKids(el, kids);
    return el;
  }
  function s(tag, attrs, ...kids) {
    const el = document.createElementNS("http://www.w3.org/2000/svg", tag);
    applyAttrs(el, attrs);
    appendKids(el, kids);
    return el;
  }
  FX.h = h;
  FX.s = s;

  /* ── 움직임 도구 ── */
  class Token {
    constructor() {
      this.cancelled = false;
      this.callbacks = [];
    }
    cancel() {
      this.cancelled = true;
      this.callbacks.splice(0).forEach((fn) => fn());
    }
    onCancel(fn) {
      if (this.cancelled) fn();
      else this.callbacks.push(fn);
    }
  }
  FX.Token = Token;

  const easeInOut = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
  FX.ease = { inOut: easeInOut, out: (t) => 1 - Math.pow(1 - t, 3) };
  FX.dur = (ms) => (FX.reduced ? 0 : ms / FX.speed);
  FX.wait = (ms, token) =>
    new Promise((resolve) => {
      if (!ms || (token && token.cancelled)) return resolve();
      const timer = setTimeout(resolve, ms);
      if (token) token.onCancel(() => { clearTimeout(timer); resolve(); });
    });
  FX.tween = (ms, onFrame, token, ease = easeInOut) =>
    new Promise((resolve) => {
      if (!ms || (token && token.cancelled)) { onFrame(1); return resolve(); }
      const start = performance.now();
      let raf = 0;
      let finished = false;
      const finish = () => {
        if (finished) return;
        finished = true;
        cancelAnimationFrame(raf);
        clearTimeout(guard);
        onFrame(1);
        resolve();
      };
      const tick = (now) => {
        if (finished) return;
        const t = Math.min(1, (now - start) / ms);
        onFrame(ease(t));
        if (t < 1) raf = requestAnimationFrame(tick);
        else { finished = true; clearTimeout(guard); resolve(); }
      };
      raf = requestAnimationFrame(tick);
      // 탭이 가려져 requestAnimationFrame 이 멈춰도 단계는 끝나게
      const guard = setTimeout(finish, ms + 150);
      if (token) token.onCancel(finish);
    });
  FX.replay = (el, cls) => {
    el.classList.remove(cls);
    void el.offsetWidth;
    el.classList.add(cls);
  };
  // 무대(stage) 안에서 요소가 보이게 스크롤 — 이미 보이면 움직이지 않는다
  FX.reveal = (el) => {
    const stage = document.getElementById("stage");
    if (!el || !stage) return;
    const r = el.getBoundingClientRect();
    const scroller = stage.scrollHeight > stage.clientHeight + 2 ? stage : null;
    const top = scroller ? stage.getBoundingClientRect().top + 70 : 70;
    const bottom = scroller ? stage.getBoundingClientRect().bottom - 20 : window.innerHeight - 90;
    if (r.top >= top && r.bottom <= bottom) return;
    el.scrollIntoView({ block: "center", behavior: FX.reduced ? "auto" : "smooth" });
  };

  /* ── 터미널 · app.log 창 ── */
  // 줄 하나는 문자열, 또는 대화형 입력 한 줄 { p: "날짜(YYYY-MM-DD): ", i: "2024-13-40" } (i 는 사용자가 친 값)
  const LINE_TONE = [
    [/^\[오류\]/, "t-bad"],
    [/^\[힌트\]/, "t-hint"],
    [/^\[안내\]/, "t-info"],
    [/^\[(저장 완료|완료|삭제 완료|수정 완료|백업 완료)\]/, "t-ok"],
    [/^→ 종료 코드/, "t-exit"],
    [/^(Traceback|\s{2,}\S)/, "t-trace"],
  ];
  function consoleLine(item, fresh) {
    const ln = h("div", { class: "ln" + (fresh ? " new" : "") });
    if (item && typeof item === "object") {
      ln.append(h("span", { class: "prompt", text: item.p || "" }), item.i !== undefined ? h("span", { class: "typed", text: item.i === "" ? "⏎" : item.i }) : null);
      return ln;
    }
    const text = String(item);
    if (text.startsWith("$ ")) {
      ln.classList.add("cmd");
      ln.append(h("span", { class: "ps", text: "$ " }), text.slice(2));
      return ln;
    }
    const m = /^(\d[\d:,.-]*\s)?(INFO|WARNING|ERROR)\s(.*)$/.exec(text);
    if (m) {
      if (m[1]) ln.append(h("span", { class: "ts", text: m[1] }));
      ln.append(h("span", { class: "lv-" + m[2], text: m[2] }), " ", m[3]);
      return ln;
    }
    const tone = LINE_TONE.find(([re]) => re.test(text));
    if (tone) ln.classList.add(tone[1]);
    ln.textContent = text;
    return ln;
  }
  FX.terminal = function (title, kind) {
    const body = h("div", { class: "term-body" });
    const el = h("div", { class: "term" + (kind ? " term-" + kind : ""), role: "log", "aria-label": title },
      h("div", { class: "term-title" }, h("i"), h("i"), h("i"), title),
      body);
    return {
      el,
      show(lines, freshCount, emptyText) {
        if (!lines.length) {
          body.replaceChildren(h("div", { class: "empty", text: emptyText || "아직 아무것도 없어요" }));
          return;
        }
        body.replaceChildren(...lines.map((t, k) => consoleLine(t, k >= lines.length - freshCount)));
        el.scrollTop = el.scrollHeight;
      },
    };
  };
  // 장면의 출력 창 묶음. scene.console: "out"(터미널) · "log"(app.log) · "both"
  // 단계마다 out: [...] 은 터미널에, log: [...] 은 app.log 에 쌓인다. 시나리오의 cmd 는 터미널 맨 위 "$ 명령" 줄
  FX.consoles = function (scene) {
    const mode = scene.console;
    if (!mode) return null;
    const panes = [];
    const wrap = h("div", { class: "consoles" + (mode === "both" ? " two" : "") });
    if (mode !== "log") panes.push({ key: "out", t: FX.terminal(scene.termTitle || "터미널", "out"), empty: "아직 출력이 없어요" });
    if (mode !== "out") panes.push({ key: "log", t: FX.terminal(scene.logTitle || "data/app.log — 실행 기록 (화면에는 안 나와요)", "log"), empty: "아직 기록이 없어요" });
    panes.forEach((p) => wrap.append(p.t.el));
    return {
      el: wrap,
      show(sc, k) {
        const cur = k >= 0 ? sc.steps[k] : null;
        for (const p of panes) {
          const head = p.key === "out" ? asList(sc.cmd).map((c) => "$ " + c) : [];
          const lines = head.concat(sc.steps.slice(0, k + 1).flatMap((st) => asList(st[p.key])));
          p.t.show(lines, cur ? asList(cur[p.key]).length : 0, p.empty);
        }
      },
    };
  };

  /* ── 선 그리기 계산 ── */
  const geom = {
    rect(el, host) {
      const a = el.getBoundingClientRect();
      const b = host.getBoundingClientRect();
      // 확대(.now) 중인 노드도 원래 크기로 계산되게 offset 값을 쓴다
      const w = el.offsetWidth || a.width;
      const hgt = el.offsetHeight || a.height;
      const cx = a.left - b.left + a.width / 2;
      const cy = a.top - b.top + a.height / 2;
      return { cx, cy, w, h: hgt };
    },
    clip(r, toward) {
      const dx = toward.x - r.cx;
      const dy = toward.y - r.cy;
      if (!dx && !dy) return { x: r.cx, y: r.cy };
      const sx = (r.w / 2 + 5) / Math.abs(dx || 1e-9);
      const sy = (r.h / 2 + 5) / Math.abs(dy || 1e-9);
      const t = Math.min(sx, sy);
      return { x: r.cx + dx * t, y: r.cy + dy * t };
    },
    path(ra, rb, bend) {
      let control = null;
      if (bend) {
        const mx = (ra.cx + rb.cx) / 2;
        const my = (ra.cy + rb.cy) / 2;
        const dx = rb.cx - ra.cx;
        const dy = rb.cy - ra.cy;
        const len = Math.hypot(dx, dy) || 1;
        control = { x: mx + (-dy / len) * bend, y: my + (dx / len) * bend };
      }
      const p1 = geom.clip(ra, control || { x: rb.cx, y: rb.cy });
      const p2 = geom.clip(rb, control || { x: ra.cx, y: ra.cy });
      if (!control) return `M${p1.x},${p1.y} L${p2.x},${p2.y}`;
      return `M${p1.x},${p1.y} Q${control.x},${control.y} ${p2.x},${p2.y}`;
    },
  };
  FX.geom = geom;

  let markerSeq = 0;
  function edgeLayer() {
    const id = "m" + ++markerSeq;
    const svg = s("svg", { class: "edges", "aria-hidden": "true" });
    const defs = s("defs", null,
      s("marker", { id: id + "-d", viewBox: "0 0 10 10", refX: "8.5", refY: "5", markerWidth: "7", markerHeight: "7", orient: "auto-start-reverse" },
        s("path", { d: "M0,0 L10,5 L0,10 z" })),
      s("marker", { id: id + "-l", class: "lit", viewBox: "0 0 10 10", refX: "8.5", refY: "5", markerWidth: "7", markerHeight: "7", orient: "auto-start-reverse" },
        s("path", { d: "M0,0 L10,5 L0,10 z" })));
    svg.append(defs);
    return { svg, defs, marker: (lit) => `url(#${id}-${lit ? "l" : "d"})` };
  }

  /* ── 공통: 시나리오 고르기 ── */
  function pickScenario(scene, id) {
    return scene.scenarios.find((x) => x.id === id) || scene.scenarios[0];
  }
  const scenarioList = (scene) => scene.scenarios.map((x) => ({ id: x.id, label: x.label, tone: x.tone }));
  const asList = (v) => (v === undefined || v === null ? [] : [].concat(v));

  /* ===================== seq : 순서도 ===================== */
  FX.types.seq = function (stage, scene, ctx) {
    const lanes = scene.lanes;
    const n = lanes.length;
    const pos = {};
    lanes.forEach((l, k) => { pos[l.id] = ((k + 0.5) / n) * 100; });
    const ownerOf = (id) => (lanes.find((l) => l.id === id) || {}).owner || "user";
    const laneEls = {};

    const root = h("div", { class: "seq", style: { "--n": n } });
    const head = h("div", { class: "seq-head" });
    for (const l of lanes) {
      const slot = h("span", { class: "chip-slot" });
      const el = h("div", { class: `lane own-${l.owner}` }, h("b", { text: l.label }), l.sub ? h("small", { text: l.sub }) : null, slot);
      el._slot = slot;
      laneEls[l.id] = el;
      head.append(el);
    }
    const body = h("div", { class: "seq-body" });
    for (const l of lanes) body.append(h("i", { class: `lifeline own-${l.owner}`, style: { left: pos[l.id] + "%" } }));
    const list = h("ol", { class: "seq-rows" });
    const packet = h("div", { class: "packet" });
    const tag = h("div", { class: "packet-tag" });
    body.append(list, packet, tag);
    root.append(head, body);
    const con = FX.consoles(scene);
    // 좁은 화면에서는 이 칸만 가로로 넘긴다 (styles.css 의 .seq-scroll)
    stage.append(h("div", { class: "seq-scroll" }, root));
    if (con) stage.append(con.el);
    if (scene.extra && FX.extras[scene.extra]) stage.append(FX.extras[scene.extra]());

    let sc = null;
    let rows = [];
    let token = new Token();

    function makeRow(st, k) {
      const kind = st.kind || (st.from === st.to ? "self" : "req");
      const row = h("li", { class: `seq-row kind-${kind}` });
      const no = h("span", { class: "no", text: String(k + 1) });
      const laneW = 100 / n;
      let msg;
      if (kind === "note") {
        const xs = asList(st.over || st.from).map((id) => pos[id]);
        const left = Math.max(0, Math.min(...xs) - laneW * 0.45);
        const right = Math.min(100, Math.max(...xs) + laneW * 0.45);
        msg = h("div", { class: "msg note", style: { marginLeft: left + "%", width: right - left + "%" } }, no, st.text);
      } else if (st.from === st.to) {
        const x = pos[st.from];
        const flip = x > 62;
        const w = flip ? Math.min(x, laneW * 2.1) : Math.min(100 - x, laneW * 2.1);
        msg = h("div", {
          class: `msg self own-${ownerOf(st.from)}${flip ? " flip" : ""}`,
          style: { marginLeft: (flip ? x - w : x) + "%", width: w + "%" },
        }, h("span", { class: "loop" }), h("span", { class: "label" }, no, h("span", { class: "txt", text: st.text })));
      } else {
        const a = pos[st.from];
        const b = pos[st.to];
        msg = h("div", {
          class: `msg ${b < a ? "left" : "right"} own-${ownerOf(st.from)}`,
          style: { marginLeft: Math.min(a, b) + "%", width: Math.abs(b - a) + "%" },
        }, h("span", { class: "label" }, no, h("span", { class: "txt", text: st.text })), h("div", { class: "line" }));
      }
      row.append(msg);
      if (st.group) row.append(h("span", { class: "group-tag", text: st.group }));
      row._msg = msg;
      row.addEventListener("click", () => ctx.jump(k, true));
      return row;
    }

    function render(k) {
      rows.forEach((r, j) => {
        r.classList.toggle("done", j < k);
        r.classList.toggle("now", j === k);
        r.classList.toggle("todo", j > k);
      });
      const chips = {};
      sc.steps.slice(0, k + 1).forEach((st) => asList(st.chip).forEach((c) => { chips[c.lane] = c; }));
      const cur = k >= 0 ? sc.steps[k] : null;
      for (const l of lanes) {
        const c = chips[l.id];
        const el = laneEls[l.id];
        const key = c ? c.text + "|" + c.tone : "";
        if (el._key !== key) {
          el._slot.replaceChildren(c ? h("span", { class: `chip tone-${c.tone || "info"} pop`, text: c.text }) : "");
          el._key = key;
        }
        el.classList.toggle("active", !!cur && (cur.from === l.id || cur.to === l.id));
      }
      if (con) con.show(sc, k);
    }

    async function animate(k, tk) {
      const st = sc.steps[k];
      const row = rows[k];
      FX.reveal(row);
      if (st.from === st.to || st.kind === "note") {
        await FX.wait(FX.dur(380), tk);
        return;
      }
      const line = row._msg.querySelector(".line");
      const y = line.getBoundingClientRect().top - body.getBoundingClientRect().top + 1;
      const a = pos[st.from];
      const b = pos[st.to];
      const end = st.kind === "lost" ? a + (b - a) * 0.62 : b;
      const bad = st.kind === "err" || st.kind === "lost";
      packet.className = `packet on own-${ownerOf(st.from)}${bad ? " err" : ""}`;
      packet.style.top = y + "px";
      if (st.tag) {
        tag.textContent = st.tag;
        tag.className = `packet-tag on own-${ownerOf(st.from)}`;
        tag.style.top = y + "px";
      }
      await FX.tween(FX.dur(760), (t) => {
        const x = a + (end - a) * t;
        packet.style.left = x + "%";
        if (st.tag) tag.style.left = x + "%";
      }, tk);
      if (!tk.cancelled) await FX.wait(FX.dur(120), tk);
      packet.classList.remove("on");
      tag.classList.remove("on");
    }

    function narrate(k) {
      const st = k >= 0 ? sc.steps[k] : null;
      if (st) ctx.say({ say: st.say || st.text, code: st.code, demo: st.demo });
      else ctx.say({ say: sc.intro || scene.intro, code: sc.code, demo: sc.demo, intro: true });
    }

    return {
      scenarios: scenarioList(scene),
      setScenario(id) {
        sc = pickScenario(scene, id);
        rows = sc.steps.map(makeRow);
        list.replaceChildren(...rows);
        render(-1);
      },
      count: () => sc.steps.length,
      async go(k, anim) {
        token.cancel();
        token = new Token();
        const tk = token;
        render(k);
        narrate(k);
        if (anim && k >= 0) await animate(k, tk);
        else if (k >= 0) requestAnimationFrame(() => FX.reveal(rows[k]));
      },
      destroy() { token.cancel(); },
    };
  };

  /* ===================== gate : 검문소 ===================== */
  FX.types.gate = function (stage, scene, ctx) {
    const root = h("div", { class: "gate-scene" + (scene.console ? " with-term" : "") });
    const input = h("div", { class: "gate-input" });
    const grid = h("div", { class: "gates" });
    const tokenEl = h("div", { class: "gate-token" });
    const rowsById = {};
    scene.gates.forEach((g, k) => {
      const dot = h("span", { class: "rail-dot" });
      const st = h("span", { class: "st", text: String(k + 1) });
      const card = h("div", { class: `gate own-${g.owner}` }, st,
        h("div", null, h("b", { text: g.label }), g.sub ? h("small", { text: g.sub }) : null),
        g.owner && FX.ownerShort[g.owner] ? h("span", { class: "who", text: FX.ownerShort[g.owner] }) : null);
      const exitSlot = h("div", { class: "exit-slot" });
      grid.append(dot, card, exitSlot);
      rowsById[g.id] = { g, dot, card, st, exitSlot, k };
    });
    grid.append(tokenEl);
    root.append(input, grid);
    const con = FX.consoles(scene);
    if (con) root.append(con.el);
    stage.append(root);

    let sc = null;
    let token = new Token();
    const icon = { pass: "✓", fail: "✕", exitok: "↩", back: "↺", done: "✓" };
    const yOf = (id) => {
      const r = rowsById[id];
      return r.card.offsetTop + r.card.offsetHeight / 2;
    };

    function render(k) {
      input.replaceChildren(h("span", { text: "이번 요청" }), h("b", { text: sc.input || sc.label }));
      for (const id of Object.keys(rowsById)) {
        const r = rowsById[id];
        r.card.className = `gate own-${r.g.owner}`;
        r.dot.className = "rail-dot";
        r.st.textContent = String(r.k + 1);
        r.exitSlot.replaceChildren();
      }
      const lastAt = {};
      sc.steps.slice(0, k + 1).forEach((st, j) => { lastAt[st.gate] = j; });
      for (const [gate, j] of Object.entries(lastAt)) {
        const st = sc.steps[j];
        const r = rowsById[gate];
        const state = st.st || "pass";
        r.card.classList.add(state);
        r.dot.classList.add(state === "fail" ? "fail" : state === "back" ? "back" : "pass");
        r.st.textContent = icon[state] || "✓";
        if (st.exit) {
          const e = st.exit;
          r.exitSlot.append(h("div", { class: `exit tone-${e.tone || "bad"}` },
            h("div", { class: "status", text: e.status }),
            e.code ? h("div", { class: "code", text: e.code }) : null,
            e.text ? h("p", { text: e.text }) : null));
        }
      }
      const cur = k >= 0 ? sc.steps[k] : null;
      if (cur) rowsById[cur.gate].card.classList.add("now");
      if (k === sc.steps.length - 1) {
        const used = new Set(sc.steps.map((st) => st.gate));
        for (const r of Object.values(rowsById)) if (!used.has(r.g.id)) r.card.classList.add("unused");
      }
      tokenEl.className = "gate-token" + tokenTone(cur);
      tokenEl.style.top = (cur ? yOf(cur.gate) : 14) + "px";
      if (con) con.show(sc, k);
    }
    function tokenTone(st) {
      if (!st) return "";
      if (st.st === "fail") return " bad";
      if (st.st === "exitok" || st.st === "done") return " ok";
      return "";
    }

    async function animate(k, tk) {
      const st = sc.steps[k];
      const from = k > 0 ? yOf(sc.steps[k - 1].gate) : 14;
      const to = yOf(st.gate);
      tokenEl.className = "gate-token";
      FX.reveal(rowsById[st.gate].card);
      await FX.tween(FX.dur(Math.min(1100, 380 + Math.abs(to - from) * 1.2)), (t) => { tokenEl.style.top = from + (to - from) * t + "px"; }, tk);
      tokenEl.className = "gate-token" + tokenTone(st);
      FX.replay(rowsById[st.gate].card, "now");
      await FX.wait(FX.dur(260), tk);
    }

    function narrate(k) {
      const st = k >= 0 ? sc.steps[k] : null;
      // 말할 문장이 없는 단계는 검문소 이름 · 설명을 대신 보여 준다 (빈 말풍선 방지)
      const gateText = () => { const g = rowsById[st.gate].g; return [g.label, g.sub].filter(Boolean).join(" — "); };
      if (st) ctx.say({ say: st.say || (st.exit && st.exit.text) || gateText(), code: st.code || rowsById[st.gate].g.code, demo: st.demo });
      else ctx.say({ say: sc.intro || scene.intro, code: sc.code, demo: sc.demo, intro: true });
    }

    return {
      scenarios: scenarioList(scene),
      setScenario(id) {
        sc = pickScenario(scene, id);
        render(-1);
      },
      count: () => sc.steps.length,
      async go(k, anim) {
        token.cancel();
        token = new Token();
        const tk = token;
        if (anim && k >= 0) {
          // 움직이는 동안은 지난 단계 그림을 두고, 도착하면 새 단계로 그린다
          render(k - 1);
          narrate(k);
          await animate(k, tk);
          render(k);
        } else {
          render(k);
          narrate(k);
          if (k >= 0) requestAnimationFrame(() => FX.reveal(rowsById[sc.steps[k].gate].card));
        }
      },
      destroy() { token.cancel(); },
    };
  };

  /* ===================== states : 상태 기계 ===================== */
  FX.types.states = function (stage, scene, ctx) {
    const layout = h("div");
    const wrap = h("div", { class: "graph-wrap" });
    const canvas = h("div", { class: "canvas", style: { height: (scene.height || 380) + "px" } });
    const layer = edgeLayer();
    canvas.append(layer.svg);
    const nodeEls = {};
    for (const st of scene.states) {
      const el = h("div", {
        class: `node state own-${st.owner || "A"}${st.start ? " start" : ""}`,
        style: { left: st.x + "%", top: st.y + "%" },
        title: st.start ? "시작" : null,
      }, st.start ? null : [h("b", { text: st.label }), st.sub ? h("small", { text: st.sub }) : null]);
      nodeEls[st.id] = el;
      canvas.append(el);
    }
    const packet = h("div", { class: "flow-packet" });
    canvas.append(packet);
    const trans = {};
    for (const t of scene.transitions) {
      trans[t.id] = t;
      t._path = s("path", { "marker-end": layer.marker(false) });
      t._label = h("div", { class: "edge-label", text: t.label });
      layer.svg.append(t._path);
      canvas.append(t._label);
    }
    const events = h("div", { class: "events" });
    wrap.append(canvas);
    layout.append(wrap);
    let mock = null;
    if (scene.mock && FX.mocks[scene.mock]) {
      const holder = h("div");
      layout.append(h("div", { class: "sm-below" }, events, holder));
      mock = FX.mocks[scene.mock](holder);
    } else layout.append(events);
    stage.append(layout);

    function drawEdges() {
      for (const t of Object.values(trans)) {
        const ra = geom.rect(nodeEls[t.from], canvas);
        const rb = geom.rect(nodeEls[t.to], canvas);
        t._path.setAttribute("d", geom.path(ra, rb, t.bend || 0));
        const len = t._path.getTotalLength();
        const mid = t._path.getPointAtLength(len * (t.at || 0.5));
        t._label.style.left = mid.x + "px";
        t._label.style.top = mid.y + "px";
      }
    }
    const ro = new ResizeObserver(() => drawEdges());
    ro.observe(canvas);

    let sc = null;
    let path = [];
    let index = -1;
    let token = new Token();
    const stateAt = (k) => (k < 0 ? sc.start : trans[path[k]].to);
    const info = (id) => (scene.info && scene.info[id]) || {};

    function render(k) {
      index = k;
      const cur = stateAt(k);
      const taken = new Set(path.slice(0, k + 1));
      const visited = new Set([sc.start, ...path.slice(0, k + 1).map((id) => trans[id].to)]);
      for (const [id, el] of Object.entries(nodeEls)) {
        el.classList.toggle("now", id === cur);
        el.classList.toggle("idle", !visited.has(id) && !el.classList.contains("start"));
      }
      for (const t of Object.values(trans)) {
        const lit = taken.has(t.id);
        t._path.setAttribute("class", lit ? "lit" : "");
        t._path.setAttribute("marker-end", layer.marker(lit));
        t._label.classList.toggle("lit", lit);
      }
      const outs = scene.transitions.filter((t) => t.from === cur);
      events.replaceChildren(
        h("span", { class: "hint", text: outs.length ? "다음 사건:" : "끝난 상태예요" }),
        ...outs.map((t) => h("button", {
          class: "btn", type: "button",
          onclick: () => {
            path = path.slice(0, index + 1).concat(t.id);
            ctx.refresh();
            ctx.jump(index + 1, true);
          },
        }, t.event || t.label, " →")),
        h("button", { class: "btn", type: "button", onclick: () => { path = sc.path.slice(); ctx.refresh(); ctx.jump(-1, false); } }, "↺ 처음부터"));
      if (mock) mock.show(cur, k >= 0 ? trans[path[k]] : null);
    }

    async function animate(k, tk) {
      const t = trans[path[k]];
      const p = t._path;
      const len = p.getTotalLength();
      packet.classList.add("on");
      await FX.tween(FX.dur(900), (e) => {
        const pt = p.getPointAtLength(len * e);
        packet.style.left = pt.x + "px";
        packet.style.top = pt.y + "px";
      }, tk);
      packet.classList.remove("on");
    }

    function narrate(k) {
      const cur = stateAt(k);
      const t = k >= 0 ? trans[path[k]] : null;
      const said = (sc.says && sc.says[k]) || (t && t.say) || info(cur).say;
      ctx.say({ say: k < 0 ? sc.intro || said : said, code: info(cur).code || (t && t.code), demo: info(cur).demo, intro: k < 0 });
    }

    return {
      scenarios: scenarioList(scene),
      setScenario(id) {
        sc = pickScenario(scene, id);
        path = sc.path.slice();
        requestAnimationFrame(drawEdges);
        render(-1);
      },
      count: () => path.length,
      async go(k, anim) {
        token.cancel();
        token = new Token();
        const tk = token;
        drawEdges();
        if (anim && k >= 0) {
          render(k - 1);
          narrate(k);
          await animate(k, tk);
          render(k);
        } else {
          render(k);
          narrate(k);
        }
      },
      destroy() { token.cancel(); ro.disconnect(); },
    };
  };

  /* ===================== graph : 노드 지도 ===================== */
  FX.types.graph = function (stage, scene, ctx) {
    const wrap = h("div", { class: "graph-wrap" });
    const canvas = h("div", { class: "canvas graph", style: { height: (scene.height || 520) + "px" } });
    const layer = edgeLayer();
    canvas.append(layer.svg);
    const nodeEls = {};
    for (const n of scene.nodes) {
      const el = h("div", {
        class: `node own-${n.owner}${n.shape ? " " + n.shape : ""}`,
        style: { left: n.x + "%", top: n.y + "%" },
        tabindex: "0", role: "button", "aria-label": `${n.label} 설명 보기`,
      }, h("b", { text: n.label }), n.sub ? h("small", { text: n.sub }) : null);
      el.addEventListener("mouseenter", () => hover(n.id));
      el.addEventListener("mouseleave", () => hover(null));
      el.addEventListener("focus", () => hover(n.id));
      el.addEventListener("blur", () => hover(null));
      el.addEventListener("click", () => showNode(n));
      el.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); showNode(n); } });
      nodeEls[n.id] = el;
      canvas.append(el);
    }
    const edges = scene.edges.map((e) => {
      const p = s("path", { class: e.dashed ? "dashed" : "", "marker-end": layer.marker(false) });
      const label = e.label ? h("div", { class: "edge-label", text: e.label }) : null;
      layer.svg.append(p);
      if (label) canvas.append(label);
      return { ...e, p, label };
    });
    const temp = s("path", { class: "flow", style: { opacity: "0" } });
    layer.svg.append(temp);
    const packet = h("div", { class: "flow-packet" });
    canvas.append(packet);
    wrap.append(canvas);
    stage.append(wrap);
    if (scene.extra && FX.extras[scene.extra]) stage.append(FX.extras[scene.extra]());

    function drawEdges() {
      for (const e of edges) {
        const ra = geom.rect(nodeEls[e.from], canvas);
        const rb = geom.rect(nodeEls[e.to], canvas);
        e.p.setAttribute("d", geom.path(ra, rb, e.bend || 0));
        if (e.label) {
          const len = e.p.getTotalLength();
          const mid = e.p.getPointAtLength(len * (e.at || 0.5));
          e.label.style.left = mid.x + "px";
          e.label.style.top = mid.y + "px";
        }
      }
    }
    const ro = new ResizeObserver(() => drawEdges());
    ro.observe(canvas);

    let sc = null;
    let current = -1;
    let token = new Token();
    const findEdge = (a, b) => edges.find((e) => e.from === a && e.to === b) || edges.find((e) => e.from === b && e.to === a);

    function render(k) {
      current = k;
      const steps = sc ? sc.steps : [];
      const inFlow = new Set(steps.flatMap((st) => [st.from, st.to]));
      const seen = new Set(steps.slice(0, k + 1).flatMap((st) => [st.from, st.to]));
      const cur = k >= 0 ? steps[k] : null;
      for (const [id, el] of Object.entries(nodeEls)) {
        el.classList.toggle("dim", k >= 0 && !inFlow.has(id));
        el.classList.toggle("lit", seen.has(id));
        el.classList.toggle("now", !!cur && cur.to === id);
      }
      const used = new Set(steps.slice(0, k + 1).map((st) => findEdge(st.from, st.to)).filter(Boolean));
      const curEdge = cur ? findEdge(cur.from, cur.to) : null;
      for (const e of edges) {
        const lit = used.has(e);
        e.p.setAttribute("class", [e.dashed ? "dashed" : "", lit ? "lit" : "", e === curEdge ? "flow" : "", k >= 0 && !lit ? "dim" : ""].join(" ").trim());
        e.p.setAttribute("marker-end", layer.marker(lit));
        if (e.label) e.label.classList.toggle("lit", lit);
      }
    }

    function hover(id) {
      if (id === null) { render(current); return; }
      for (const e of edges) {
        const on = e.from === id || e.to === id;
        e.p.setAttribute("class", [e.dashed ? "dashed" : "", on ? "lit" : "dim"].join(" ").trim());
        e.p.setAttribute("marker-end", layer.marker(on));
        if (e.label) e.label.classList.toggle("lit", on);
      }
    }

    function showNode(n) {
      ctx.pause();
      for (const el of Object.values(nodeEls)) el.classList.remove("now");
      nodeEls[n.id].classList.add("now");
      const i = n.info || {};
      ctx.say({ say: i.say || n.sub || n.label, code: i.code, demo: i.demo, tag: n.label });
    }

    async function animate(k, tk) {
      const st = sc.steps[k];
      const e = findEdge(st.from, st.to);
      let p;
      let reverse = false;
      if (e) {
        p = e.p;
        reverse = e.from !== st.from;
      } else {
        temp.setAttribute("d", geom.path(geom.rect(nodeEls[st.from], canvas), geom.rect(nodeEls[st.to], canvas), st.bend || 40));
        temp.style.opacity = "1";
        p = temp;
      }
      const len = p.getTotalLength();
      packet.classList.add("on");
      FX.reveal(nodeEls[st.to]);
      await FX.tween(FX.dur(950), (t) => {
        const pt = p.getPointAtLength(len * (reverse ? 1 - t : t));
        packet.style.left = pt.x + "px";
        packet.style.top = pt.y + "px";
      }, tk);
      packet.classList.remove("on");
      temp.style.opacity = "0";
    }

    function narrate(k) {
      const st = k >= 0 ? sc.steps[k] : null;
      if (st) ctx.say({ say: st.say, code: st.code, demo: st.demo });
      else ctx.say({ say: sc.intro || scene.intro, code: sc.code, demo: sc.demo, intro: true });
    }

    return {
      scenarios: scenarioList(scene),
      setScenario(id) {
        sc = pickScenario(scene, id);
        requestAnimationFrame(drawEdges);
        render(-1);
      },
      count: () => sc.steps.length,
      async go(k, anim) {
        token.cancel();
        token = new Token();
        const tk = token;
        drawEdges();
        if (anim && k >= 0) {
          render(k - 1);
          narrate(k);
          await animate(k, tk);
          render(k);
        } else {
          render(k);
          narrate(k);
        }
      },
      destroy() { token.cancel(); ro.disconnect(); },
    };
  };
})();
