# `/claude.img` Phase 2 — Studio GUI — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a barebones local browser studio to `/claude.img` — a localhost web app with a prompt box (model toggle, domain mode, size/count), a gallery, and a running cost total — that drives the Phase 1 engine without spending agent/session tokens.

**Architecture:** A stdlib `http.server` serves a single vanilla-JS page and a small JSON API. Because delegation generation is slow (1–3 min), generation runs in a background thread via a `JobManager`; the browser starts a job (`POST /api/generate` → `job_id`) and polls (`GET /api/job/<id>`). All business logic lives in a testable `StudioApp` that takes an injected `generate_fn` (defaults to `core.generate`), so the whole API is tested with a fake generator — no real image calls in CI. Binds `127.0.0.1` only; image serving is path-guarded.

**Tech Stack:** Python 3.11+ stdlib only (`http.server`, `threading`, `json`, `urllib`, `webbrowser`), `pytest`. Frontend is dependency-free HTML/CSS/JS.

---

## File Structure

```
~/.agents/skills/claude.img/
  scripts/
    studio_jobs.py      # JobManager: threaded submit/get (Task 1)
    studio_app.py       # StudioApp: list_gallery, start_generation, get_job (Task 2)
    serve.py            # http.server handler + make_server + serve_studio entry (Task 3)
    cli.py              # MODIFY: wire the `studio` subcommand (Task 4)
  assets/
    studio.html         # the GUI (Task 3)
  tests/
    test_studio_jobs.py     # (Task 1)
    test_studio_app.py      # (Task 2)
    test_serve.py           # threaded integration test (Task 3)
    test_cli.py             # MODIFY: regression test no longer uses `studio` (Task 4)
```

Phase 1 files are not modified except `cli.py` (Task 4).

---

### Task 1: JobManager (threaded job store)

**Files:**
- Create: `scripts/studio_jobs.py`
- Test: `tests/test_studio_jobs.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_studio_jobs.py
import time
from scripts.studio_jobs import JobManager


def _wait(jobs, job_id, timeout=2.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = jobs.get(job_id)
        if job and job["status"] != "running":
            return job
        time.sleep(0.01)
    raise AssertionError("job did not finish in time")


def test_submit_runs_fn_and_stores_result():
    jobs = JobManager()
    job_id = jobs.submit(lambda: {"value": 42})
    job = _wait(jobs, job_id)
    assert job["status"] == "done"
    assert job["result"] == {"value": 42}
    assert job["error"] is None


def test_submit_captures_exception_as_error():
    jobs = JobManager()

    def boom():
        raise RuntimeError("kaboom")

    job_id = jobs.submit(boom)
    job = _wait(jobs, job_id)
    assert job["status"] == "error"
    assert "kaboom" in job["error"]
    assert job["result"] is None


def test_get_unknown_job_returns_none():
    assert JobManager().get("nope") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_studio_jobs.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.studio_jobs'`.

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/studio_jobs.py
import threading
import uuid


class JobManager:
    def __init__(self):
        self._jobs: dict[str, dict] = {}
        self._lock = threading.Lock()

    def submit(self, fn) -> str:
        job_id = uuid.uuid4().hex
        with self._lock:
            self._jobs[job_id] = {"status": "running", "result": None, "error": None}

        def run():
            try:
                result = fn()
                self._set(job_id, status="done", result=result, error=None)
            except Exception as exc:  # noqa: BLE001 - surface any failure to the UI
                self._set(job_id, status="error", result=None, error=str(exc))

        threading.Thread(target=run, daemon=True).start()
        return job_id

    def _set(self, job_id, **fields):
        with self._lock:
            self._jobs[job_id] = fields

    def get(self, job_id: str):
        with self._lock:
            job = self._jobs.get(job_id)
            return dict(job) if job is not None else None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_studio_jobs.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/studio_jobs.py tests/test_studio_jobs.py
git commit -m "feat: add threaded JobManager for studio generation jobs"
```

---

### Task 2: StudioApp (business logic)

**Files:**
- Create: `scripts/studio_app.py`
- Test: `tests/test_studio_app.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_studio_app.py
import time
from pathlib import Path
from scripts.studio_app import StudioApp


def _fake_generate(**kwargs):
    # Mimic core.generate: write an image into working_dir, return a dict Result.
    wd = Path(kwargs["working_dir"])
    wd.mkdir(parents=True, exist_ok=True)
    img = wd / "out.png"
    img.write_bytes(b"\x89PNG\r\n")
    return {
        "path": str(img),
        "model": kwargs["model"],
        "prompt": kwargs["prompt"],
        "settings": kwargs.get("settings", {}),
        "cost": {"usd": 0.0, "source": "fake"},
        "engine": kwargs.get("engine", "delegation"),
    }


def _wait(app, job_id, timeout=2.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = app.get_job(job_id)
        if job and job["status"] != "running":
            return job
        time.sleep(0.01)
    raise AssertionError("job did not finish")


def test_list_gallery_returns_images_newest_first(tmp_path):
    (tmp_path / "a.png").write_bytes(b"x")
    time.sleep(0.01)
    (tmp_path / "b.png").write_bytes(b"y")
    (tmp_path / "note.txt").write_text("ignore")
    app = StudioApp(gallery_dir=str(tmp_path), generate_fn=_fake_generate)
    names = [img["name"] for img in app.list_gallery()]
    assert names == ["b.png", "a.png"]
    assert app.list_gallery()[0]["url"] == "/img/b.png"


def test_list_gallery_empty_for_missing_dir(tmp_path):
    app = StudioApp(gallery_dir=str(tmp_path / "nope"), generate_fn=_fake_generate)
    assert app.list_gallery() == []


def test_start_generation_runs_job_and_serializes_result(tmp_path):
    app = StudioApp(gallery_dir=str(tmp_path), generate_fn=_fake_generate)
    job_id = app.start_generation({"prompt": "a red cube", "model": "gemini"})
    job = _wait(app, job_id)
    assert job["status"] == "done"
    assert job["result"]["model"] == "gemini"
    assert job["result"]["prompt"] == "a red cube"
    assert (tmp_path / "out.png").exists()


def test_start_generation_defaults_model_to_auto(tmp_path):
    captured = {}

    def capture(**kwargs):
        captured.update(kwargs)
        return _fake_generate(**kwargs)

    app = StudioApp(gallery_dir=str(tmp_path), generate_fn=capture)
    job_id = app.start_generation({"prompt": "x"})
    _wait(app, job_id)
    assert captured["model"] == "auto"
    assert captured["working_dir"] == str(tmp_path)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_studio_app.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.studio_app'`.

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/studio_app.py
import json
from pathlib import Path
from scripts.studio_jobs import JobManager

IMAGE_EXTS = {".png", ".jpg", ".jpeg"}


def _serialize(result):
    # Accept a Phase 1 Result (has to_json) or a plain dict (tests / fakes).
    if hasattr(result, "to_json"):
        return json.loads(result.to_json())
    return result


class StudioApp:
    def __init__(self, gallery_dir: str, generate_fn, jobs: JobManager | None = None):
        self.gallery_dir = Path(gallery_dir)
        self.generate_fn = generate_fn
        self.jobs = jobs or JobManager()

    def list_gallery(self) -> list[dict]:
        if not self.gallery_dir.is_dir():
            return []
        files = [
            p for p in self.gallery_dir.iterdir()
            if p.is_file() and p.suffix.lower() in IMAGE_EXTS
        ]
        files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return [
            {"name": p.name, "url": f"/img/{p.name}", "mtime": p.stat().st_mtime}
            for p in files
        ]

    def start_generation(self, payload: dict) -> str:
        prompt = payload.get("prompt", "")
        model = payload.get("model", "auto")
        engine = payload.get("engine", "delegation")
        mode = payload.get("mode") or None
        settings = {
            "size": payload.get("size", "1024x1024"),
            "count": int(payload.get("count", 1)),
        }

        def task():
            result = self.generate_fn(
                prompt=prompt,
                model=model,
                engine=engine,
                mode=mode,
                settings=settings,
                working_dir=str(self.gallery_dir),
            )
            return _serialize(result)

        return self.jobs.submit(task)

    def get_job(self, job_id: str):
        return self.jobs.get(job_id)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_studio_app.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/studio_app.py tests/test_studio_app.py
git commit -m "feat: add StudioApp gallery listing and generation jobs"
```

---

### Task 3: HTTP server + studio GUI

**Files:**
- Create: `scripts/serve.py`
- Create: `assets/studio.html`
- Test: `tests/test_serve.py`

- [ ] **Step 1: Write the failing integration test**

```python
# tests/test_serve.py
import json
import threading
import time
import urllib.request
from pathlib import Path
from scripts.studio_app import StudioApp
from scripts.serve import make_server


def _fake_generate(**kwargs):
    wd = Path(kwargs["working_dir"])
    wd.mkdir(parents=True, exist_ok=True)
    img = wd / "fake.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")
    return {
        "path": str(img), "model": kwargs["model"], "prompt": kwargs["prompt"],
        "settings": kwargs.get("settings", {}),
        "cost": {"usd": 0.0, "source": "fake"}, "engine": "delegation",
    }


def _get(url):
    return urllib.request.urlopen(url, timeout=5).read()


def _post(url, obj):
    req = urllib.request.Request(
        url, data=json.dumps(obj).encode(),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    return urllib.request.urlopen(req, timeout=5).read()


def test_studio_index_and_generate_flow(tmp_path):
    app = StudioApp(gallery_dir=str(tmp_path), generate_fn=_fake_generate)
    server = make_server(app, "127.0.0.1", 0)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{port}"
    try:
        # index serves the GUI
        assert b"claude.img" in _get(base + "/")
        # start a generation job
        resp = json.loads(_post(base + "/api/generate", {"prompt": "a cube", "model": "gemini"}))
        job_id = resp["job_id"]
        # poll until done
        job = None
        for _ in range(100):
            job = json.loads(_get(base + f"/api/job/{job_id}"))
            if job["status"] != "running":
                break
            time.sleep(0.02)
        assert job["status"] == "done"
        assert job["result"]["model"] == "gemini"
        # gallery lists the produced image
        gallery = json.loads(_get(base + "/api/gallery"))
        assert any(i["name"] == "fake.png" for i in gallery["images"])
        # the image is served and path-guarded
        assert _get(base + "/img/fake.png").startswith(b"\x89PNG")
        try:
            urllib.request.urlopen(base + "/img/../serve.py", timeout=5)
            assert False, "path traversal should be blocked"
        except urllib.error.HTTPError as e:
            assert e.code == 404
    finally:
        server.shutdown()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_serve.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.serve'`.

- [ ] **Step 3: Write the server**

```python
# scripts/serve.py
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, unquote

ASSETS_HTML = Path(__file__).resolve().parent.parent / "assets" / "studio.html"


def build_handler(app):
    class StudioHandler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # quiet

        def _json(self, code, obj):
            body = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _bytes(self, code, content_type, data):
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            path = urlparse(self.path).path
            if path in ("/", "/index.html"):
                self._bytes(200, "text/html; charset=utf-8", ASSETS_HTML.read_bytes())
            elif path == "/api/gallery":
                self._json(200, {"images": app.list_gallery()})
            elif path.startswith("/api/job/"):
                job = app.get_job(path.rsplit("/", 1)[-1])
                self._json(200, job) if job else self._json(404, {"error": "not found"})
            elif path.startswith("/img/"):
                self._serve_image(unquote(path[len("/img/"):]))
            else:
                self._json(404, {"error": "not found"})

        def _serve_image(self, name):
            target = (app.gallery_dir / name).resolve()
            gallery = app.gallery_dir.resolve()
            if target.is_file() and target.parent == gallery:
                self._bytes(200, "image/png", target.read_bytes())
            else:
                self._json(404, {"error": "not found"})

        def do_POST(self):
            path = urlparse(self.path).path
            if path == "/api/generate":
                length = int(self.headers.get("Content-Length", 0) or 0)
                payload = json.loads(self.rfile.read(length) or b"{}")
                self._json(202, {"job_id": app.start_generation(payload)})
            else:
                self._json(404, {"error": "not found"})

    return StudioHandler


def make_server(app, host="127.0.0.1", port=8765):
    return ThreadingHTTPServer((host, port), build_handler(app))


def serve_studio(gallery_dir=".", host="127.0.0.1", port=8765, open_browser=True):
    from scripts.studio_app import StudioApp
    from scripts.core import generate

    app = StudioApp(gallery_dir=gallery_dir, generate_fn=generate)
    server = make_server(app, host, port)
    url = f"http://{host}:{server.server_address[1]}/"
    print(f"[claude.img] studio at {url}  (gallery: {Path(gallery_dir).resolve()})")
    print("Ctrl+C to stop.")
    if open_browser:
        import webbrowser
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
```

- [ ] **Step 4: Write the GUI `assets/studio.html`**

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>claude.img studio</title>
<style>
  :root { --bg:#0f1115; --panel:#171a21; --line:#262b36; --ink:#e7ecf3; --mut:#8b94a7; --accent:#ffd23f; }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--ink); font:15px/1.5 ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,sans-serif; }
  header { display:flex; align-items:center; justify-content:space-between; padding:14px 20px; border-bottom:1px solid var(--line); }
  header h1 { font-size:15px; margin:0; letter-spacing:.04em; }
  header .cost { color:var(--mut); font-size:13px; }
  main { display:grid; grid-template-columns:340px 1fr; gap:0; height:calc(100vh - 49px); }
  .controls { border-right:1px solid var(--line); padding:18px; overflow:auto; }
  .controls label { display:block; font-size:12px; color:var(--mut); margin:14px 0 6px; text-transform:uppercase; letter-spacing:.05em; }
  textarea, select, input { width:100%; background:var(--panel); border:1px solid var(--line); color:var(--ink); border-radius:8px; padding:9px 10px; font:inherit; }
  textarea { min-height:96px; resize:vertical; }
  .seg { display:flex; gap:6px; }
  .seg button { flex:1; background:var(--panel); border:1px solid var(--line); color:var(--ink); padding:8px; border-radius:8px; cursor:pointer; }
  .seg button.on { border-color:var(--accent); color:var(--accent); }
  .row { display:flex; gap:10px; }
  .row > div { flex:1; }
  .go { margin-top:18px; width:100%; background:var(--accent); color:#101218; border:0; border-radius:8px; padding:12px; font-weight:600; cursor:pointer; }
  .go:disabled { opacity:.5; cursor:default; }
  .gallery { padding:18px; overflow:auto; }
  .grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(200px,1fr)); gap:12px; }
  .card { background:var(--panel); border:1px solid var(--line); border-radius:10px; overflow:hidden; }
  .card img { width:100%; display:block; }
  .empty, .status { color:var(--mut); padding:20px 0; }
  .latest { margin-bottom:18px; }
  .latest img { max-width:100%; border:1px solid var(--line); border-radius:10px; }
  .prompt { color:var(--mut); font-size:13px; margin-top:8px; white-space:pre-wrap; }
</style>
</head>
<body>
<header>
  <h1>claude.img · studio</h1>
  <span class="cost" id="cost">session cost: $0.00</span>
</header>
<main>
  <section class="controls">
    <label>Model</label>
    <div class="seg" id="model">
      <button data-v="auto" class="on">Auto</button>
      <button data-v="gemini">Nano Banana</button>
      <button data-v="gpt">GPT Image 2</button>
    </div>
    <label>Prompt</label>
    <textarea id="prompt" placeholder="a matte-black water bottle on wet river stone, studio product photography"></textarea>
    <label>Domain mode</label>
    <select id="mode">
      <option value="">none</option>
      <option>cinema</option><option>product</option><option>portrait</option>
      <option>editorial</option><option>ui</option><option>logo</option>
      <option>landscape</option><option>abstract</option><option>infographic</option>
    </select>
    <div class="row">
      <div>
        <label>Size</label>
        <select id="size"><option>1024x1024</option><option>1280x720</option><option>720x1280</option></select>
      </div>
      <div>
        <label>Count</label>
        <input id="count" type="number" min="1" max="8" value="1" />
      </div>
    </div>
    <button class="go" id="go">Generate</button>
    <div class="status" id="status"></div>
  </section>
  <section class="gallery">
    <div class="latest" id="latest"></div>
    <div class="grid" id="grid"><div class="empty">No images yet.</div></div>
  </section>
</main>
<script>
  let model = "auto", totalCost = 0;
  const $ = (id) => document.getElementById(id);
  document.querySelectorAll("#model button").forEach(b =>
    b.onclick = () => {
      document.querySelectorAll("#model button").forEach(x => x.classList.remove("on"));
      b.classList.add("on"); model = b.dataset.v;
    });

  async function refreshGallery() {
    const r = await fetch("/api/gallery"); const { images } = await r.json();
    const grid = $("grid");
    if (!images.length) { grid.innerHTML = '<div class="empty">No images yet.</div>'; return; }
    grid.innerHTML = images.map(i => `<div class="card"><img src="${i.url}" loading="lazy" /></div>`).join("");
  }

  $("go").onclick = async () => {
    const prompt = $("prompt").value.trim();
    if (!prompt) { $("status").textContent = "Enter a prompt first."; return; }
    $("go").disabled = true; $("status").textContent = "Generating… (delegation can take 1–3 min)";
    const body = { prompt, model, mode: $("mode").value, size: $("size").value, count: $("count").value };
    const start = await fetch("/api/generate", { method:"POST", headers:{ "Content-Type":"application/json" }, body: JSON.stringify(body) });
    const { job_id } = await start.json();
    poll(job_id);
  };

  async function poll(jobId) {
    const r = await fetch("/api/job/" + jobId); const job = await r.json();
    if (job.status === "running") { setTimeout(() => poll(jobId), 1500); return; }
    $("go").disabled = false;
    if (job.status === "error") { $("status").textContent = "Error: " + job.error; return; }
    const res = job.result;
    $("status").textContent = "Done — " + res.model;
    totalCost += (res.cost && res.cost.usd) || 0;
    $("cost").textContent = "session cost: $" + totalCost.toFixed(2);
    const name = res.path.split("/").pop();
    $("latest").innerHTML = `<img src="/img/${name}?t=${Date.now()}" /><div class="prompt">${res.prompt}</div>`;
    refreshGallery();
  }

  refreshGallery();
</script>
</body>
</html>
```

- [ ] **Step 5: Run the integration test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_serve.py -v`
Expected: PASS (1 test).

- [ ] **Step 6: Commit**

```bash
git add scripts/serve.py assets/studio.html tests/test_serve.py
git commit -m "feat: add studio HTTP server, JSON API, and prompt-box GUI"
```

---

### Task 4: Wire the `studio` subcommand into the CLI

**Files:**
- Modify: `scripts/cli.py` (the `main()` dispatch)
- Modify: `tests/test_cli.py` (the cross-cwd regression test must stop relying on `studio`, which now blocks)

- [ ] **Step 1: Update the regression test to use a still-stubbed subcommand**

Replace the body of `test_cli_runs_as_script_from_any_cwd` in `tests/test_cli.py` so it invokes `preset` (still a no-op) instead of `studio` (now a blocking server):

```python
def test_cli_runs_as_script_from_any_cwd(tmp_path):
    # Regression (Task 12): `python scripts/cli.py` from an unrelated cwd must
    # resolve `import scripts.*`. 'preset' exits early, so nothing blocks.
    cli = Path(__file__).resolve().parent.parent / "scripts" / "cli.py"
    proc = subprocess.run(
        [sys.executable, str(cli), "preset"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "later phase" in proc.stdout
```

- [ ] **Step 2: Add a test that the `studio` command resolves to the server entry**

Add to `tests/test_cli.py`:

```python
def test_studio_command_invokes_serve(monkeypatch, tmp_path):
    import scripts.cli as cli_mod
    called = {}

    def fake_serve(gallery_dir=".", **kwargs):
        called["gallery_dir"] = gallery_dir
        called["open_browser"] = kwargs.get("open_browser", True)

    monkeypatch.setattr(cli_mod, "_serve_studio", fake_serve, raising=False)
    cli_mod.main(["studio"])
    assert "gallery_dir" in called
```

- [ ] **Step 3: Run the two tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_cli.py -k "from_any_cwd or studio_command" -v`
Expected: FAIL — `test_studio_command_invokes_serve` errors because `cli.main` does not yet import/call `_serve_studio`.

- [ ] **Step 4: Implement the studio dispatch in `cli.py`**

Replace the `main()` function in `scripts/cli.py` with:

```python
def _serve_studio(gallery_dir=".", **kwargs):
    # Thin indirection so tests can monkeypatch the launch.
    from scripts.serve import serve_studio
    serve_studio(gallery_dir=gallery_dir, **kwargs)


def main(argv: list[str] | None = None) -> int:
    import sys as _sys
    from scripts.core import generate

    ns = parse_args(argv if argv is not None else _sys.argv[1:])

    if ns.command == "studio":
        _serve_studio(gallery_dir=".")
        return 0
    if ns.command != "generate":
        print(f"[claude.img] '{ns.command}' lands in a later phase")
        return 0

    result = generate(
        prompt=ns.prompt,
        model=ns.model,
        engine=ns.engine,
        mode=ns.mode,
        settings={"size": ns.size, "count": ns.count},
    )
    print(result.to_json())
    return 0
```

- [ ] **Step 5: Run the CLI tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_cli.py -v`
Expected: PASS (all CLI tests, including the new `studio` test and updated regression test).

- [ ] **Step 6: Run the full suite**

Run: `.venv/bin/python -m pytest`
Expected: PASS (all Phase 1 + Phase 2 tests).

- [ ] **Step 7: Commit**

```bash
git add scripts/cli.py tests/test_cli.py
git commit -m "feat: wire /claude.img studio to launch the local studio server"
```

---

### Task 5: Manual live verification (no automated test)

> Spends subscription quota; do after the unit/integration suite is green.

- [ ] **Step 1: Launch the studio in a scratch gallery dir**

Run: `mkdir -p /tmp/cimg-studio && cd /tmp/cimg-studio && python ~/.agents/skills/claude.img/scripts/cli.py studio`
Expected: prints `studio at http://127.0.0.1:8765/`, opens the browser to the GUI.

- [ ] **Step 2: Generate from the browser (Nano Banana)**

In the page: leave model **Auto**, prompt `a single teal cube on white`, click Generate.
Expected: status shows "Generating…", then within ~1–3 min the image appears in the Latest panel and the gallery grid; `session cost` updates.

- [ ] **Step 3: Generate text-in-image (routes to GPT Image 2)**

Prompt: `a poster that says "STUDIO" in bold black letters`. Click Generate.
Expected: the result panel reports model `gpt`; the rendered text is legible. Confirms auto-routing through the studio.

- [ ] **Step 4: Confirm files + gallery persistence**

Run (new terminal): `ls /tmp/cimg-studio`
Expected: the generated PNG(s) are on disk in the gallery dir; reloading the browser still shows them (gallery reads the dir).

- [ ] **Step 5: Stop the server and tag**

`Ctrl+C` in the studio terminal, then:

```bash
cd ~/.agents/skills/claude.img && git tag phase-2-studio
```

---

## Self-Review

**Spec coverage (DESIGN §9 Studio GUI, Phase 2 slice of §14):**
- Local stdlib server, localhost-only → `make_server` binds `127.0.0.1` (Task 3). ✓
- Prompt box + model toggle + domain dropdown + quality/size/count → `assets/studio.html` (Task 3). ✓
- Generate → `core.generate`, returns image path + final prompt + cost → `StudioApp.start_generation` + poll (Tasks 2–3). ✓
- Gallery reads the output dir → `StudioApp.list_gallery` + `/api/gallery` + `/img/<name>` (Tasks 2–3). ✓
- Running cost total → `#cost` updates from `res.cost.usd` (Task 3). ✓
- Runs outside the agent loop (≈0 session tokens) → server + browser; agent only launches it (Task 4). ✓
- Slow-generation handling → threaded `JobManager` + `job_id` poll (Tasks 1–3). ✓
- Keys never sent to browser → server holds nothing; delegation uses CLI auth; API only server-side. ✓
- Director chat + editing layer → **out of scope, Phase 3** (separate plan). ✓

**Placeholder scan:** No TBD/TODO; every code step is complete, including the full `studio.html`. No "add error handling" hand-waving — job errors surface via `JobManager` → `/api/job` → `#status`.

**Type consistency:** `StudioApp(gallery_dir, generate_fn, jobs=None)`, `start_generation(payload)->job_id`, `get_job(id)`, `list_gallery()->[{name,url,mtime}]`, `JobManager.submit(fn)->id` / `get(id)->{status,result,error}`, `make_server(app,host,port)`, `serve_studio(gallery_dir,...)`, `_serve_studio(...)` — all consistent across Tasks 1–4. `generate_fn` is called with the exact kwargs `core.generate` accepts (`prompt, model, engine, mode, settings, working_dir`), verified against Phase 1 `scripts/core.py`.

---

## Execution Handoff

Plan complete and saved to `~/.agents/skills/claude.img/docs/PLAN-phase2-studio.md`. Two execution options:

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks.
2. **Inline Execution** — execute tasks in this session with checkpoints.

Which approach?
