import { useCallback, useEffect, useRef, useState } from "react";
import { api, downloadText, stamp, usd } from "./api.js";
import RunCard from "./components/RunCard.jsx";
import { Extensions, WeeklyList } from "./components/Sidebar.jsx";
import { ConfirmModal, HelpModal } from "./components/Modals.jsx";

const EXAMPLES = ["2 חלב 3%, לחם אחיד, טחינה, עגבניות, גלידה", "במבה, נוזל כלים, שמפו, סוללות AA", "איפה נמצאת הטחינה בחנות?"];
const TEXT_FILE = /\.(txt|csv|md)$/i;

export default function App() {
  const [info, setInfo] = useState(null);
  const [drawing, setDrawing] = useState(null);
  const [list, setList] = useState([]);
  const [turns, setTurns] = useState([]);
  const [text, setText] = useState("");
  const [modelDraft, setModelDraft] = useState("");
  const [help, setHelp] = useState(false);
  const [confirm, setConfirm] = useState(null);
  const [toast, setToast] = useState(null);
  const [dragging, setDragging] = useState(false);
  const [fatal, setFatal] = useState(null);
  const bottom = useRef(null);
  const fileInput = useRef(null);
  const busy = turns.some((t) => t.status === "running");

  const notify = useCallback((msg, kind = "ok") => {
    setToast({ msg, kind, id: Date.now() });
  }, []);
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 4000);
    return () => clearTimeout(t);
  }, [toast]);

  const guard = (fn) => async (...args) => {
    try {
      return await fn(...args);
    } catch (e) {
      notify(e.message, "error");
    }
  };

  const loadAll = useCallback(async () => {
    try {
      const [st, m, l] = await Promise.all([api("/api/state"), api("/api/map"), api("/api/list")]);
      setInfo(st);
      setModelDraft(st.model);
      setDrawing(m);
      setList(l.items);
      setFatal(null);
    } catch (e) {
      setFatal(e.message);
    }
  }, []);
  useEffect(() => { loadAll(); }, [loadAll]);

  useEffect(() => { bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [turns]);

  const updateTurn = (id, fn) => setTurns((ts) => ts.map((t) => (t.id === id ? { ...t, ...fn(t) } : t)));

  // ------------------------------------------------------------ הרצה + Streaming
  const run = guard(async (input) => {
    const value = input.trim();
    if (!value || busy) return;
    const { run_id: id } = await api("/api/runs", { method: "POST", body: { text: value } });
    setTurns((ts) => [...ts, { id, text: value, status: "running", nodes: [] }]);
    setText("");

    const es = new EventSource(`/api/runs/${id}/events`);
    es.onmessage = (msg) => {
      const ev = JSON.parse(msg.data);
      switch (ev.type) {
        case "node":
          updateTurn(id, (t) => ({ nodes: [...t.nodes, { name: ev.name, logs: [] }] }));
          break;
        case "log":
          updateTurn(id, (t) => {
            const nodes = t.nodes.slice();
            const last = nodes.length - 1;
            if (last >= 0) nodes[last] = { ...nodes[last], logs: [...nodes[last].logs, ev.message] };
            return { nodes };
          });
          break;
        case "hitl":
          updateTurn(id, () => ({ hitl: ev.payload, sending: false }));
          break;
        case "hitl_answered":
          updateTurn(id, () => ({ hitl: null, sending: false }));
          break;
        case "result":
          updateTurn(id, () => ({ result: ev }));
          break;
        case "error":
          updateTurn(id, () => ({ error: ev.message, errorCost: ev.cost }));
          break;
        case "cancelled":
          updateTurn(id, () => ({ cancelled: true }));
          break;
        case "end":
          es.close();
          updateTurn(id, () => ({ status: "done", hitl: null }));
          setInfo((i) => i && { ...i, cost: ev.session_cost, busy: false });
          break;
        default:
      }
    };
    es.onerror = () => {
      // EventSource מתחבר מחדש לבד (השרת ממשיך מהאירוע האחרון). אם השרת נסגר, נעצור אחרי ניסיון
      if (es.readyState === EventSource.CLOSED) {
        updateTurn(id, (t) => (t.status === "running" ? { status: "done", error: "החיבור לשרת נותק." } : {}));
      }
    };
  });

  const answer = (id) => guard(async (value) => {
    updateTurn(id, () => ({ sending: true }));
    await api(`/api/runs/${id}/answer`, { method: "POST", body: { answer: value } });
  });
  const cancel = (id) => guard(async () => {
    updateTurn(id, () => ({ sending: true }));
    await api(`/api/runs/${id}/cancel`, { method: "POST" });
  });

  // ------------------------------------------------------------ הגדרות
  const changeStore = guard(async (store) => {
    const st = await api("/api/settings", { method: "POST", body: { store } });
    setInfo(st);
    setDrawing(await api("/api/map"));
    notify(`החנות הפעילה: ${store}`);
  });
  const changeModel = guard(async () => {
    if (!modelDraft.trim() || modelDraft.trim() === info.model) return;
    setInfo(await api("/api/settings", { method: "POST", body: { model: modelDraft } }));
    notify("המודל עודכן");
  });

  // ------------------------------------------------------------ קבצים
  const readFile = guard(async (file) => {
    if (!TEXT_FILE.test(file.name)) throw new Error("ניתן לטעון רק קבצי טקסט (txt / csv / md).");
    if (file.size > 100_000) throw new Error("הקובץ גדול מדי לרשימת קניות (מעל 100KB).");
    setText((await file.text()).trim());
    notify(`נטען הקובץ ${file.name}. בדקו את הרשימה ולחצו שליחה.`);
  });
  useEffect(() => {
    const over = (e) => { e.preventDefault(); setDragging(true); };
    const leave = (e) => { if (!e.relatedTarget) setDragging(false); };
    const drop = (e) => {
      e.preventDefault();
      setDragging(false);
      const f = e.dataTransfer.files?.[0];
      if (f) readFile(f);
    };
    window.addEventListener("dragover", over);
    window.addEventListener("dragleave", leave);
    window.addEventListener("drop", drop);
    return () => {
      window.removeEventListener("dragover", over);
      window.removeEventListener("dragleave", leave);
      window.removeEventListener("drop", drop);
    };
  });

  // ------------------------------------------------------------ רשימה שבועית ותקציר
  const addToList = guard(async (value) => setList((await api("/api/list", { method: "POST", body: { items: [value] } })).items));
  const removeFromList = guard(async (i) => setList((await api(`/api/list/${i}`, { method: "DELETE" })).items));
  const clearList = () => setConfirm({
    text: "לרוקן את כל הרשימה השבועית?",
    onYes: guard(async () => { setList((await api("/api/list", { method: "DELETE" })).items); notify("הרשימה רוקנה"); }),
  });
  const exportSummary = guard(async () => {
    const res = await fetch("/api/summary");
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).error || "לא ניתן ליצור תקציר.");
    downloadText(`session_summary_${stamp()}.txt`, await res.text());
  });

  if (fatal) {
    return (
      <div className="fatal">
        <h1>לא ניתן להתחבר לאייג'נט</h1>
        <p>{fatal}</p>
        <button className="btn btn-primary" onClick={loadAll}>ניסיון חוזר</button>
      </div>
    );
  }
  if (!info) return <div className="loading">טוען…</div>;

  const t = info.cost.totals;
  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="logo" aria-hidden="true">
            <svg viewBox="0 0 32 32"><path d="M6 9h3.5l2.8 11h10.4L25 12.5H11" /><circle cx="13.5" cy="24.5" r="1.8" /><circle cx="21.5" cy="24.5" r="1.8" /></svg>
          </span>
          <div>
            <h1>מסלול קניות</h1>
            <span className="muted small">רשימה → מסלול הליכה קצר בחנות</span>
          </div>
        </div>

        <div className="controls">
          <label className="field">
            <span>חנות</span>
            <select value={info.store} disabled={busy} onChange={(e) => changeStore(e.target.value)}>
              {info.stores.map((s) => <option key={s}>{s}</option>)}
            </select>
          </label>
          <label className="field field-model">
            <span>מודל</span>
            <input list="models" dir="ltr" value={info.mock ? "mock/heuristic" : modelDraft} disabled={busy || info.mock}
              onChange={(e) => setModelDraft(e.target.value)} onBlur={changeModel}
              onKeyDown={(e) => e.key === "Enter" && e.currentTarget.blur()} />
            <datalist id="models">{info.suggested_models.map((m) => <option key={m} value={m} />)}</datalist>
          </label>
          <div className="cost-pill" title={`${t.calls} קריאות · ${t.input_tokens}/${t.output_tokens} טוקנים (קלט/פלט)`}>
            <span className="muted small">עלות בהפעלה</span>
            <b dir="ltr">{usd(t.actual_usd)}</b>
            <span className="muted small">תיאורטית <span dir="ltr">{usd(t.theoretical_usd)}</span> · {t.input_tokens + t.output_tokens} טוקנים</span>
          </div>
          <button className="btn" onClick={exportSummary} disabled={!turns.some((x) => x.result)}>תקציר שיחה ⤓</button>
          <button className="icon-btn help-btn" onClick={() => setHelp(true)} aria-label="עזרה" title="עזרה">?</button>
        </div>
      </header>

      {info.mock && <div className="banner">מצב הדגמה (AGENT_MOCK=1): ללא קריאות למודל אמיתי.</div>}
      {!info.mock && !info.has_key && (
        <div className="banner banner-error">לא הוגדר OPENROUTER_API_KEY. צרו קובץ .env ליד התוכנה לפי .env.example והפעילו מחדש.</div>
      )}

      <div className="layout">
        <main className="thread">
          {!turns.length && (
            <div className="welcome">
              <h2>מה צריך לקנות היום?</h2>
              <p className="muted">כתבו רשימה חופשית, גררו לכאן קובץ טקסט, או נסו דוגמה:</p>
              <div className="chips">
                {EXAMPLES.map((ex) => <button key={ex} className="chip" onClick={() => run(ex)}>{ex}</button>)}
              </div>
            </div>
          )}
          {turns.map((turn) => (
            <RunCard key={turn.id} turn={turn} drawing={drawing} model={info.mock ? "mock/heuristic" : info.model}
              onAnswer={answer(turn.id)} onCancel={cancel(turn.id)} onToast={notify} />
          ))}
          <div ref={bottom} />
        </main>

        <aside className="side">
          <WeeklyList items={list} busy={busy} onAdd={addToList} onRemove={removeFromList} onClear={clearList}
            onPlan={() => run(list.join("\n"))} />
          <Extensions tools={info.tools} />
        </aside>
      </div>

      <form className="composer" onSubmit={(e) => { e.preventDefault(); run(text); }}>
        <button type="button" className="icon-btn" title="טעינת רשימה מקובץ" aria-label="טעינת רשימה מקובץ"
          onClick={() => fileInput.current.click()}>📎</button>
        <input ref={fileInput} type="file" accept=".txt,.csv,.md" hidden
          onChange={(e) => { if (e.target.files[0]) readFile(e.target.files[0]); e.target.value = ""; }} />
        <textarea value={text} rows={Math.min(5, Math.max(1, text.split("\n").length))} dir="auto"
          placeholder={busy ? "ממתין לסיום המשימה הנוכחית…" : "למשל: 2 חלב, לחם, טחינה, עגבניות (Enter לשליחה, Shift+Enter לשורה חדשה)"}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); run(text); } }} />
        <button className="btn btn-primary" disabled={busy || !text.trim()}>חישוב מסלול</button>
      </form>

      {dragging && <div className="dropzone"><div>שחררו כאן קובץ רשימה (txt / csv / md)</div></div>}
      {help && <HelpModal onClose={() => setHelp(false)} />}
      {confirm && (
        <ConfirmModal text={confirm.text} onNo={() => setConfirm(null)}
          onYes={() => { confirm.onYes(); setConfirm(null); }} />
      )}
      {toast && <div key={toast.id} className={`toast toast-${toast.kind}`} role="status">{toast.msg}</div>}
    </div>
  );
}
