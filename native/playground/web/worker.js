// The playground's worker: the interpreter (alchem_emu.wasm) running the
// Linux alchem, which builds the program, and then the program it built.
// Messages in: {source, args, stdin}. Out: {kind: "ready" | "phase" | "out"
// | "err" | "done", ...}.

let wasm = null;
let machine = 0;
const encoder = new TextEncoder();
const decoder = new TextDecoder();

function bytes(text) {
  return typeof text === "string" ? encoder.encode(text) : text;
}

function pass(data) {
  const b = bytes(data);
  const ptr = wasm.emu_alloc(b.length);
  new Uint8Array(wasm.memory.buffer, ptr, b.length).set(b);
  return [ptr, b.length];
}

function call(name, ...texts) {
  const held = texts.map(pass);
  const result = wasm[name](machine, ...held.flat());
  for (const [ptr, len] of held) wasm.emu_free(ptr, len);
  return result;
}

function taken(ptr) {
  const view = new DataView(wasm.memory.buffer);
  const len = view.getUint32(ptr, true);
  if (len === 0xffffffff) return null;
  return new Uint8Array(wasm.memory.buffer, ptr + 4, len).slice();
}

function file(path, data, mode) {
  const [p, pl] = pass(path);
  const [d, dl] = pass(data);
  wasm.emu_file(machine, p, pl, d, dl, mode);
  wasm.emu_free(p, pl);
  wasm.emu_free(d, dl);
}

function flush() {
  const out = taken(wasm.emu_take(machine, 0));
  const err = taken(wasm.emu_take(machine, 1));
  if (out.length) postMessage({ kind: "out", text: decoder.decode(out) });
  if (err.length) postMessage({ kind: "err", text: decoder.decode(err) });
}

// Runs the program at path to its end, a slice at a time, so that what it
// writes reaches the page as it goes.
function run(path, argv) {
  if (call("emu_start", path, argv.join("\0")) !== 0) {
    return { status: -2, message: decoder.decode(taken(wasm.emu_take(machine, 2))) };
  }
  for (;;) {
    const status = wasm.emu_run(machine, 20000000);
    flush();
    if (status !== -1) {
      const message = status === -2 ? decoder.decode(taken(wasm.emu_take(machine, 2))) : "";
      return { status, message };
    }
  }
}

async function load() {
  const [module, alchem] = await Promise.all([
    WebAssembly.instantiateStreaming(fetch("alchem_emu.wasm"), {}),
    fetch("alchem").then((r) => {
      if (!r.ok) throw new Error("alchem: " + r.status);
      return r.arrayBuffer();
    }),
  ]);
  wasm = module.instance.exports;
  machine = wasm.emu_new();
  file("/work/alchem", new Uint8Array(alchem), 0o755);
  postMessage({ kind: "ready", size: alchem.byteLength });
}

const loading = load().catch((e) => postMessage({ kind: "done", phase: "load", status: -2, message: String(e) }));

onmessage = async (event) => {
  await loading;
  if (!wasm) return;
  const { source, args, stdin } = event.data;
  wasm.emu_time(machine, Date.now() / 1000);
  file("/work/main.alc", source, 0o644);
  const [s, sl] = pass(stdin || "");
  wasm.emu_stdin(machine, s, sl);
  wasm.emu_free(s, sl);
  const began = performance.now();
  postMessage({ kind: "phase", phase: "build" });
  const built = run("/work/alchem", ["alchem", "build", "-o", "main", "main.alc"]);
  const buildMs = performance.now() - began;
  const buildSteps = wasm.emu_steps(machine);
  if (built.status !== 0) {
    postMessage({ kind: "done", phase: "build", status: built.status, message: built.message, buildMs, buildSteps });
    return;
  }
  postMessage({ kind: "phase", phase: "run", buildMs, buildSteps });
  const started = performance.now();
  const ran = run("/work/main", ["main", ...(args || [])]);
  postMessage({ kind: "done", phase: "run", status: ran.status, message: ran.message, buildMs, runMs: performance.now() - started, steps: wasm.emu_steps(machine) });
};
