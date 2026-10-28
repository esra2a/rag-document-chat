"""Local web chat for the RAG system.

Run:
    .venv/Scripts/python tools/chat_app.py
Then open http://localhost:5000
"""
import sys
from pathlib import Path

from flask import Flask, jsonify, request

from ingest import SUPPORTED, ingest_file
from query import answer
from rag_common import ROOT

DOCS_DIR = ROOT / "docs"
DOCS_DIR.mkdir(exist_ok=True)

app = Flask(__name__)

PAGE = r"""<!doctype html>
<html lang="ar">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Document Chat</title>
<style>
  :root { --bg:#f6f7f9; --panel:#fff; --text:#1d2330; --muted:#6b7280; --accent:#4f46e5; --user:#4f46e5; --bot:#fff; --border:#e5e7eb; }
  @media (prefers-color-scheme: dark) {
    :root { --bg:#0f1115; --panel:#171a21; --text:#e6e8ec; --muted:#9aa1ad; --accent:#818cf8; --user:#4f46e5; --bot:#1e222b; --border:#2a2f3a; }
  }
  * { box-sizing:border-box; }
  body { margin:0; font-family:"Segoe UI", Tahoma, sans-serif; background:var(--bg); color:var(--text); height:100vh; display:flex; flex-direction:column; }
  header { padding:14px 20px; background:var(--panel); border-bottom:1px solid var(--border); display:flex; align-items:center; gap:12px; flex-wrap:wrap; }
  header h1 { font-size:18px; margin:0; flex:1; }
  .upload { font-size:14px; color:var(--muted); display:flex; gap:8px; align-items:center; }
  .upload label { cursor:pointer; padding:7px 12px; border:1px solid var(--border); border-radius:8px; background:var(--bg); color:var(--text); }
  .upload input { display:none; }
  #chat { flex:1; overflow-y:auto; padding:20px 16px; max-width:860px; width:100%; margin:0 auto; }
  .msg { margin:10px 0; padding:12px 16px; border-radius:14px; line-height:1.65; white-space:pre-wrap; max-width:85%; unicode-bidi:plaintext; }
  .user { background:var(--user); color:#fff; margin-inline-start:auto; }
  .bot { background:var(--bot); border:1px solid var(--border); }
  .sources { margin-top:8px; font-size:12px; color:var(--muted); }
  .sources details summary { cursor:pointer; }
  .sources .src { margin:6px 0; padding:6px 8px; border-inline-start:3px solid var(--accent); background:var(--bg); white-space:pre-wrap; }
  .empty { text-align:center; color:var(--muted); margin-top:18vh; }
  form { display:flex; gap:8px; padding:14px 16px; max-width:860px; width:100%; margin:0 auto; }
  textarea { flex:1; resize:none; padding:12px 14px; border-radius:12px; border:1px solid var(--border); background:var(--panel); color:var(--text); font:inherit; height:52px; unicode-bidi:plaintext; }
  button { padding:0 20px; border:none; border-radius:12px; background:var(--accent); color:#fff; font:inherit; cursor:pointer; }
  button:disabled { opacity:.5; cursor:default; }
</style>
</head>
<body>
<header>
  <h1>💬 Document Chat</h1>
  <div class="upload">
    <label>📄 Upload file<input type="file" id="file" accept=".pdf,.docx,.txt,.md,.csv,.xlsx"></label>
    <span id="upstatus"></span>
  </div>
</header>
<div id="chat"><div class="empty" id="empty">اسأل أي سؤال عن ملفاتك<br>Ask anything about your documents</div></div>
<form id="f">
  <textarea id="q" dir="auto" placeholder="اكتب سؤالك هنا... / Type your question..."></textarea>
  <button id="send">Send</button>
</form>
<script>
const chat = document.getElementById('chat'), q = document.getElementById('q'), send = document.getElementById('send');
const history = [];

function add(role, text, sources) {
  document.getElementById('empty')?.remove();
  const d = document.createElement('div');
  d.className = 'msg ' + role; d.dir = 'auto'; d.textContent = text;
  if (sources && sources.length) {
    const s = document.createElement('div'); s.className = 'sources';
    const det = document.createElement('details');
    det.innerHTML = '<summary>Sources (' + sources.length + ')</summary>';
    sources.forEach((x, i) => {
      const e = document.createElement('div'); e.className = 'src'; e.dir = 'auto';
      e.textContent = '[' + (i+1) + '] ' + x.source + ' — p.' + x.page + ' (score ' + x.score + ')\n' + x.text.slice(0, 400) + (x.text.length > 400 ? '…' : '');
      det.appendChild(e);
    });
    s.appendChild(det); d.appendChild(s);
  }
  chat.appendChild(d); chat.scrollTop = chat.scrollHeight; return d;
}

document.getElementById('f').onsubmit = async (e) => {
  e.preventDefault();
  const question = q.value.trim(); if (!question) return;
  add('user', question); q.value = ''; send.disabled = true;
  const wait = add('bot', '…');
  try {
    const r = await fetch('/api/chat', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({question, history})});
    const data = await r.json();
    wait.remove();
    if (data.error) { add('bot', '⚠️ ' + data.error); }
    else {
      add('bot', data.answer, data.sources);
      history.push({role:'user', content:question}, {role:'assistant', content:data.answer});
    }
  } catch (err) { wait.remove(); add('bot', '⚠️ ' + err); }
  send.disabled = false; q.focus();
};
q.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); document.getElementById('f').requestSubmit(); }});

document.getElementById('file').onchange = async (e) => {
  const file = e.target.files[0]; if (!file) return;
  const st = document.getElementById('upstatus');
  st.textContent = '⏳ Processing ' + file.name + '...';
  const fd = new FormData(); fd.append('file', file);
  try {
    const r = await fetch('/api/upload', {method:'POST', body: fd});
    const data = await r.json();
    st.textContent = data.error ? '⚠️ ' + data.error : '✓ ' + file.name + ' — ' + data.chunks + ' chunks';
  } catch (err) { st.textContent = '⚠️ ' + err; }
  e.target.value = '';
};
</script>
</body>
</html>"""


@app.get("/")
def home():
    return PAGE


@app.post("/api/chat")
def api_chat():
    data = request.get_json(force=True)
    question = (data.get("question") or "").strip()
    if not question:
        return jsonify(error="Empty question"), 400
    try:
        return jsonify(answer(question, data.get("history") or []))
    except Exception as e:
        return jsonify(error=str(e)), 500


@app.post("/api/upload")
def api_upload():
    f = request.files.get("file")
    if not f or Path(f.filename).suffix.lower() not in SUPPORTED:
        return jsonify(error="Unsupported file type"), 400
    dest = DOCS_DIR / Path(f.filename).name
    f.save(dest)
    try:
        return jsonify(chunks=ingest_file(dest))
    except Exception as e:
        return jsonify(error=str(e)), 500


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    print("Open http://localhost:5000")
    app.run(host="127.0.0.1", port=5000, debug=False)
