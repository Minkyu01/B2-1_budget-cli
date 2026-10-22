// 장면 데이터 검사 — 코드 칩이 실제 파일 · 함수를 가리키는지, 단계가 있는 칸 · 노드 · 장면을 가리키는지 본다.
// 쓰는 법 (flow-explorer 폴더에서):  node tools/check_scenes.js
"use strict";
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const here = path.resolve(__dirname, "..");
const root = path.resolve(here, "..", "..");
// 브라우저처럼 window 가 곧 전역이게 한다 (lines.js 는 전역 FX 를 바로 쓴다)
const sandbox = {};
sandbox.window = sandbox;
vm.createContext(sandbox);
for (const file of ["lines.js", "scenes.js"]) {
  vm.runInContext(fs.readFileSync(path.join(here, file), "utf8"), sandbox, { filename: file });
}
const FX = sandbox.FX;
const problems = [];
let refs = 0;
let steps = 0;

function checkRef(ref, where) {
  const r = typeof ref === "string" ? { path: ref } : Array.isArray(ref) ? { path: ref[0], fn: ref[1] } : ref;
  refs += 1;
  if (!fs.existsSync(path.join(root, r.path))) problems.push(`${where}: 없는 파일 ${r.path}`);
  else if (r.fn && !FX.lines[`${r.path}#${r.fn}`]) problems.push(`${where}: ${r.path} 에 ${r.fn} 정의가 없음`);
  else if (r.line) {
    const total = fs.readFileSync(path.join(root, r.path), "utf8").split("\n").length;
    if (r.line > total) problems.push(`${where}: ${r.path} 는 ${total}줄인데 ${r.line}줄을 가리킴`);
  }
}
const codes = (list, where) => [].concat(list || []).filter(Boolean).forEach((ref) => checkRef(ref, where));
const ids = new Set(FX.scenes.map((s) => s.id));

for (const scene of FX.scenes) {
  const at = scene.id;
  codes(scene.code && !Array.isArray(scene.code) && typeof scene.code === "object" ? null : scene.code, `${at}.code`);
  for (const sc of scene.scenarios || []) {
    const sat = `${at}/${sc.id}`;
    codes(sc.code && typeof sc.code !== "string" ? sc.code : null, `${sat}.code`);
    codes(sc.refs, `${sat}.refs`);
    for (const [j, st] of (sc.steps || []).entries()) {
      steps += 1;
      const w = `${sat}#${j + 1}`;
      codes(st.code, w);
      if (scene.type === "seq") {
        const lanes = new Set(scene.lanes.map((l) => l.id));
        for (const id of [st.from, st.to, ...[].concat(st.over || [])].filter(Boolean)) if (!lanes.has(id)) problems.push(`${w}: 없는 칸 ${id}`);
        if (st.chip && !lanes.has(st.chip.lane)) problems.push(`${w}: 칩의 칸 ${st.chip.lane} 없음`);
        if (!st.say && !st.text) problems.push(`${w}: 말할 문장 없음`);
      }
      if (scene.type === "gate" && !scene.gates.some((g) => g.id === st.gate)) problems.push(`${w}: 없는 검문소 ${st.gate}`);
      if (scene.type === "graph") {
        const nodes = new Set(scene.nodes.map((n) => n.id));
        for (const id of [st.from, st.to]) if (!nodes.has(id)) problems.push(`${w}: 없는 노드 ${id}`);
        if (!st.say) problems.push(`${w}: 말할 문장 없음`);
      }
      if (scene.type === "typecheck") {
        const block = scene.code[sc.code];
        const keys = new Set(block.lines.map((l, i) => String(typeof l === "object" ? l.n : block.start + i)));
        for (const n of [].concat(st.err || [], st.note || [])) if (!keys.has(String(n))) problems.push(`${w}: 코드 칸에 없는 줄 ${n}`);
      }
      if (scene.type === "csvimport" && typeof st.at === "number" && !sc.rows.some((r) => r.n === st.at)) problems.push(`${w}: 없는 행 ${st.at}`);
    }
  }
  for (const n of scene.nodes || []) codes(n.info && n.info.code, `${at}.node.${n.id}`);
  for (const g of scene.gates || []) codes(g.code, `${at}.gate.${g.id}`);
  if (scene.type === "graph") {
    const nodes = new Set(scene.nodes.map((n) => n.id));
    for (const e of scene.edges) for (const id of [e.from, e.to]) if (!nodes.has(id)) problems.push(`${at}: 선이 없는 노드 ${id} 를 가리킴`);
  }
  for (const q of scene.questions || []) {
    if (!ids.has(q.to)) problems.push(`home: 없는 장면 ${q.to}`);
    else if (q.s && !FX.scenes.find((s) => s.id === q.to).scenarios.some((x) => x.id === q.s)) problems.push(`home: ${q.to} 에 없는 시나리오 ${q.s}`);
  }
  for (const it of scene.items || []) {
    if (!ids.has(it.to)) problems.push(`demo: 없는 장면 ${it.to}`);
    else if (it.s && !FX.scenes.find((s) => s.id === it.to).scenarios.some((x) => x.id === it.s)) problems.push(`demo: ${it.to} 에 없는 시나리오 ${it.s}`);
  }
}

// type_demo.py 의 코드 칸이 실제 파일과 글자 하나까지 같은지
const typeScene = FX.scenes.find((s) => s.id === "types");
if (typeScene) {
  const block = typeScene.code.demo;
  const real = fs.readFileSync(path.join(root, block.file), "utf8").split("\n");
  block.lines.forEach((line, i) => {
    if (real[block.start - 1 + i] !== line) problems.push(`types: ${block.file}:${block.start + i} 가 실제와 다름`);
  });
}

const scenarios = FX.scenes.reduce((n, s) => n + (s.scenarios ? s.scenarios.length : 0), 0);
console.log(`장면 ${FX.scenes.length}개 · 시나리오 ${scenarios}개 · 단계 ${steps}개 · 코드 참조 ${refs}개`);
if (problems.length) {
  console.log(`문제 ${problems.length}개`);
  problems.forEach((p) => console.log(" - " + p));
  process.exit(1);
}
console.log("문제 없음");
