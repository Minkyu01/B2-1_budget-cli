/*
 * 흐름 탐색기 바깥 틀 — 장면 목록, 시나리오 탭, 재생 조작, 설명 패널, 단축키, 주소(#) 기억. (B7-1 탐색기와 같은 틀)
 * 장면 그리기는 engine.js / custom.js, 장면 내용은 scenes.js 에 있다.
 */
(function () {
  "use strict";
  const FX = window.FX;
  const { h } = FX;
  const $ = (id) => document.getElementById(id);
  const store = {
    get(key) { try { return localStorage.getItem(key); } catch { return null; } },
    set(key, value) { try { localStorage.setItem(key, value); } catch { /* 저장 못 해도 동작은 같다 */ } },
  };
  FX.store = store;

  const scenes = FX.scenes;
  const byId = Object.fromEntries(scenes.map((sc) => [sc.id, sc]));
  const stage = $("stage");
  const mascot = document.querySelector(".mascot");

  let scene = null;
  let ctl = null;
  let scenarioId = null;
  let idx = -1;
  let playing = false;
  let playToken = null;

  /* ── 장면 목록 ── */
  function buildNav() {
    const groups = [];
    for (const sc of scenes) {
      let g = groups.find((x) => x.name === sc.group);
      if (!g) groups.push((g = { name: sc.group, items: [] }));
      g.items.push(sc);
    }
    let no = 0;
    $("nav-list").replaceChildren(...groups.map((g) => h("section", { class: "nav-group" },
      h("h2", { text: g.name }),
      h("ol", null, g.items.map((sc) => {
        const label = sc.id === "home" ? "★" : String(++no);
        sc._no = label;
        return h("li", null, h("button", {
          class: "nav-link", type: "button", dataset: { scene: sc.id },
          onclick: () => { navigate(sc.id, null, -1, true); document.body.classList.remove("nav-open"); stage.focus({ preventScroll: true }); },
        }, h("span", { class: "no", text: label }), h("span", { class: "nav-title", text: sc.navTitle || sc.title })));
      })))));
  }

  /* ── 설명 패널 ── */
  function normalizeCode(list) {
    return [].concat(list || []).filter(Boolean).map((ref) => {
      if (typeof ref === "string") return { path: ref };
      if (Array.isArray(ref)) return { path: ref[0], fn: ref[1], note: ref[2] };
      return ref;
    });
  }
  // 이 맥(file:// · localhost)에서는 VS Code 로 그 줄을 연다. 다른 곳에서는 [복사]로 경로:줄 만 가져간다
  const LOCAL = location.protocol === "file:" || /^(localhost|127\.0\.0\.1|\[::1\])$/.test(location.hostname);
  const USE_VSCODE = LOCAL && !!FX.repoRoot;
  function codeItem(ref) {
    // { path, fn } 은 함수 이름으로 줄을 찾고, { path, line, label } 은 그 줄을 그대로 쓴다
    const key = `${ref.path}#${ref.fn}`;
    const line = ref.line || (ref.fn ? FX.lines && FX.lines[key] : null);
    const href = USE_VSCODE ? `vscode://file${FX.repoRoot}/${ref.path}${line ? ":" + line : ""}` : "#";
    const fileName = ref.path.split("/").pop();
    // 함수 · 메서드만 () 를 붙인다 (클래스 · 상수 · property 는 그대로)
    const call = ref.fn && FX.kinds && FX.kinds[key] === "def" ? "()" : "";
    const link = h("a", {
      class: "code-link", href,
      title: `${ref.path}${line ? ":" + line : ""}${USE_VSCODE ? " — VS Code 에서 열기" : ""}`,
      onclick: USE_VSCODE ? null : (e) => { e.preventDefault(); copyRef(); },
    },
      h("span", { class: "fn", text: ref.fn ? `${ref.fn}${call}` : ref.label || fileName }),
      ref.note ? ` · ${ref.note}` : "",
      h("span", { class: "path", text: `${ref.path}${line ? ":" + line : ""}` }));
    async function copyRef() {
      const text = `${ref.path}${line ? ":" + line : ""}`;
      try { await navigator.clipboard.writeText(text); toast("경로를 복사했어요 — " + text); } catch { toast(text); }
    }
    const copy = h("button", {
      class: "copy-btn", type: "button", title: "경로 복사", "aria-label": `${ref.path} 경로 복사`,
      onclick: copyRef,
    }, "복사");
    return h("li", null, link, copy);
  }
  function say(payload) {
    const p = payload || {};
    const text = p.say || "";
    const sayEl = $("say");
    if (sayEl.textContent !== text) {
      sayEl.textContent = text;
      FX.replay(sayEl, "swap");
      if (mascot) FX.replay(mascot, "talking");
    }
    $("say-tag").textContent = p.tag || (p.intro ? "장면 소개" : idx >= 0 ? `${idx + 1}단계 · 말할 것` : "말할 것");
    const code = normalizeCode(p.code && [].concat(p.code).length ? p.code : scene && scene.code);
    $("code-list").replaceChildren(...code.map(codeItem));
    $("code-sec").hidden = !code.length;
    const demo = p.demo || (scene && scene.demo) || "";
    $("demo").textContent = demo;
    $("demo-sec").hidden = !demo;
  }

  let toastTimer = 0;
  function toast(message) {
    const el = $("toast");
    el.textContent = message;
    el.classList.add("on");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.remove("on"), 2200);
  }

  /* ── 장면 열기 ── */
  const ctx = {
    say,
    toast,
    store,
    jump: (k, anim) => { stopPlay(); goStep(k, anim); },
    pause: () => stopPlay(),
    refresh: () => updateControls(),
    navigate: (id, sid) => navigate(id, sid, -1, true),
  };

  function navigate(id, sid, step, push) {
    mount(id, sid, step);
    writeHash(push);
  }

  function mount(id, sid, step) {
    stopPlay();
    if (ctl && ctl.destroy) ctl.destroy();
    scene = byId[id] || scenes[0];
    const inner = h("div", { class: "stage-inner" });
    stage.replaceChildren(inner);
    stage.scrollTop = 0;
    $("scene-group").textContent = scene.group + (scene._no && scene._no !== "★" ? ` · ${scene._no}` : "");
    $("scene-title").textContent = scene.title;
    $("scene-sub").textContent = scene.sub || "";
    document.title = scene.id === "home" ? scene.title : `${scene.navTitle || scene.title} · 가계부 흐름 탐색기`;
    const points = scene.points || [];
    $("points").replaceChildren(...points.map((t) => h("li", { text: t })));
    $("points-sec").hidden = !points.length;
    for (const el of document.querySelectorAll(".nav-link")) {
      if (el.dataset.scene === scene.id) el.setAttribute("aria-current", "page");
      else el.removeAttribute("aria-current");
    }
    ctl = FX.types[scene.type](inner, scene, ctx);
    const list = ctl.scenarios || null;
    scenarioId = list ? (list.find((x) => x.id === sid) || list[0]).id : null;
    buildTabs(list);
    if (ctl.setScenario) ctl.setScenario(scenarioId);
    const n = count();
    idx = Math.max(-1, Math.min(n - 1, Number.isFinite(step) ? step : -1));
    updateControls();
    if (ctl.go) ctl.go(idx, false);
  }

  function buildTabs(list) {
    const box = $("scenarios");
    if (!list || list.length < 2) { box.replaceChildren(); return; }
    box.replaceChildren(...list.map((x, k) => h("button", {
      class: `tab tone-${x.tone || "info"}`, type: "button", role: "tab", dataset: { sid: x.id },
      "aria-selected": x.id === scenarioId ? "true" : "false",
      onclick: () => selectScenario(x.id),
    }, x.label, k < 9 ? h("kbd", { text: String(k + 1) }) : null)));
  }

  function selectScenario(id) {
    stopPlay();
    scenarioId = id;
    for (const b of $("scenarios").children) b.setAttribute("aria-selected", String(b.dataset.sid === id));
    ctl.setScenario(id);
    idx = -1;
    updateControls();
    ctl.go(-1, false);
    writeHash(false);
  }

  /* ── 단계 조작 ── */
  const count = () => (ctl && ctl.count ? ctl.count() : 0);

  async function goStep(k, anim) {
    const n = count();
    if (!n) return;
    k = Math.max(-1, Math.min(n - 1, k));
    idx = k;
    updateControls();
    writeHash(false);
    await ctl.go(k, anim);
  }

  function dwell() {
    const len = ($("say").textContent || "").length;
    const ms = Math.min(5600, Math.max(1500, 900 + len * 32));
    return FX.reduced ? ms : ms / FX.speed;
  }

  async function play() {
    if (!count()) return;
    stopPlay();
    const my = (playToken = new FX.Token());
    playing = true;
    updatePlay();
    if (idx >= count() - 1) {
      await goStep(-1, false);
      await FX.wait(500, my);
    }
    while (!my.cancelled && idx < count() - 1) {
      await goStep(idx + 1, true);
      if (my.cancelled) break;
      await FX.wait(dwell(), my);
    }
    if (!my.cancelled) {
      playing = false;
      updatePlay();
    }
  }
  function stopPlay() {
    if (playToken) playToken.cancel();
    playToken = null;
    if (playing) {
      playing = false;
      updatePlay();
    }
  }
  function updatePlay() {
    const b = $("play-btn");
    b.replaceChildren(h("span", { "aria-hidden": "true", text: playing ? "⏸" : "▶" }), playing ? " 멈춤" : " 재생");
    b.setAttribute("aria-pressed", String(playing));
  }

  function updateControls() {
    const n = count();
    $("controls").classList.toggle("hidden-steps", !n);
    $("prev-btn").disabled = idx < 0;
    $("first-btn").disabled = idx < 0;
    $("next-btn").disabled = idx >= n - 1;
    $("step-count").textContent = !n ? "" : idx < 0 ? `시작 · ${n}단계` : `${idx + 1} / ${n}`;
    const bar = $("progress");
    if (bar.children.length !== n) {
      bar.replaceChildren(...Array.from({ length: n }, (_, j) => h("button", {
        type: "button", "aria-label": `${j + 1}단계로`,
        onclick: () => { stopPlay(); goStep(j, j === idx + 1); },
      })));
    }
    [...bar.children].forEach((b, j) => {
      b.classList.toggle("done", j < idx);
      b.classList.toggle("now", j === idx);
    });
    updatePlay();
  }

  /* ── 주소(#) 기억: #scene=add&s=ok&i=3 ── */
  function readHash() {
    const p = new URLSearchParams(location.hash.slice(1));
    return { id: p.get("scene") || "home", sid: p.get("s"), step: p.has("i") ? Number(p.get("i")) : -1, play: p.get("play") === "1" };
  }
  function writeHash(push) {
    const p = new URLSearchParams();
    p.set("scene", scene.id);
    if (scenarioId) p.set("s", scenarioId);
    if (idx >= 0) p.set("i", String(idx));
    const url = "#" + p.toString();
    if (url === location.hash) return;
    try {
      if (push) history.pushState(null, "", url);
      else history.replaceState(null, "", url);
    } catch { /* file:// 등에서 막히면 주소만 못 바꾼다 */ }
  }
  window.addEventListener("popstate", () => {
    const r = readHash();
    mount(r.id, r.sid, r.step);
  });

  /* ── 보기 설정 ── */
  function effectiveDark() {
    const t = document.documentElement.dataset.theme;
    if (t) return t === "dark";
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  }
  function toggleTheme() {
    const next = effectiveDark() ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    store.set("fx-theme", next);
  }
  function togglePresent(force) {
    const on = typeof force === "boolean" ? force : !document.body.classList.contains("present");
    document.body.classList.toggle("present", on);
    $("present-btn").setAttribute("aria-pressed", String(on));
    store.set("fx-present", on ? "1" : "0");
    window.dispatchEvent(new Event("resize"));
  }
  function toggleFull() {
    try {
      if (document.fullscreenElement) document.exitFullscreen();
      else document.documentElement.requestFullscreen();
    } catch { toast("이 브라우저에서는 전체 화면을 못 써요"); }
  }
  function toggleHelp(force) {
    const help = $("help");
    const open = typeof force === "boolean" ? force : help.hidden;
    help.hidden = !open;
    if (open) $("help-close").focus();
  }

  /* ── 단축키 ── */
  document.addEventListener("keydown", (e) => {
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    const t = e.target;
    const typing = t && (t.isContentEditable || /^(INPUT|SELECT|TEXTAREA)$/.test(t.tagName));
    if (e.key === "Escape") {
      toggleHelp(false);
      document.body.classList.remove("nav-open");
      return;
    }
    if (typing) return;
    const onButton = t && /^(BUTTON|A|SUMMARY)$/.test(t.tagName);
    switch (e.key) {
      case "ArrowRight": e.preventDefault(); stopPlay(); goStep(idx + 1, true); break;
      case "ArrowLeft": e.preventDefault(); stopPlay(); goStep(idx - 1, false); break;
      case "Home": e.preventDefault(); stopPlay(); goStep(-1, false); break;
      case " ":
        if (onButton) return;
        e.preventDefault();
        if (playing) stopPlay();
        else play();
        break;
      case "]": case "[": {
        const k = scenes.indexOf(scene) + (e.key === "]" ? 1 : -1);
        if (k >= 0 && k < scenes.length) navigate(scenes[k].id, null, -1, true);
        break;
      }
      case "p": case "P": togglePresent(); break;
      case "f": case "F": toggleFull(); break;
      case "t": case "T": toggleTheme(); break;
      case "?": toggleHelp(); break;
      default:
        if (/^[1-9]$/.test(e.key) && ctl && ctl.scenarios) {
          const x = ctl.scenarios[Number(e.key) - 1];
          if (x) selectScenario(x.id);
        }
    }
  });

  /* ── 시작 ── */
  $("play-btn").addEventListener("click", () => (playing ? stopPlay() : play()));
  $("next-btn").addEventListener("click", () => { stopPlay(); goStep(idx + 1, true); });
  $("prev-btn").addEventListener("click", () => { stopPlay(); goStep(idx - 1, false); });
  $("first-btn").addEventListener("click", () => { stopPlay(); goStep(-1, false); });
  $("speed").addEventListener("change", (e) => {
    FX.speed = Number(e.target.value) || 1;
    store.set("fx-speed", String(FX.speed));
  });
  $("theme-btn").addEventListener("click", toggleTheme);
  $("present-btn").addEventListener("click", () => togglePresent());
  $("full-btn").addEventListener("click", toggleFull);
  $("help-btn").addEventListener("click", () => toggleHelp(true));
  $("help-close").addEventListener("click", () => toggleHelp(false));
  $("help").addEventListener("click", (e) => { if (e.target.id === "help") toggleHelp(false); });
  $("nav-toggle").addEventListener("click", () => {
    const open = !document.body.classList.contains("nav-open");
    document.body.classList.toggle("nav-open", open);
    $("nav-toggle").setAttribute("aria-expanded", String(open));
  });
  document.addEventListener("click", (e) => {
    if (document.body.classList.contains("nav-open") && !e.target.closest(".nav") && !e.target.closest("#nav-toggle")) {
      document.body.classList.remove("nav-open");
    }
  });

  const theme = store.get("fx-theme");
  if (theme === "light" || theme === "dark") document.documentElement.dataset.theme = theme;
  const speed = Number(store.get("fx-speed"));
  if (speed) {
    FX.speed = speed;
    $("speed").value = String(speed);
    if ($("speed").value !== String(speed)) { FX.speed = 1; $("speed").value = "1"; }
  }
  if (store.get("fx-present") === "1") togglePresent(true);

  $("code-hint").textContent = USE_VSCODE ? "누르면 VS Code 에서 그 줄이 열려요" : "누르면 경로:줄 을 복사해요";
  buildNav();
  const start = readHash();
  mount(start.id, start.sid, start.step);
  writeHash(false);
  // #...&play=1 로 열면 바로 재생 (발표 때 링크 하나로 시작)
  if (start.play) play();
})();
