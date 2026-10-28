import { useState } from "react";
import { NODE_LABELS, downloadText, stamp, usd } from "../api.js";
import StoreMap from "./StoreMap.jsx";

function logKind(msg) {
  if (msg.startsWith("[GUARD]")) return "guard";
  if (msg.startsWith("[GATE]") || msg.startsWith("[EVAL]")) return "check";
  if (msg.startsWith("[TOOL]")) return "tool";
  return "info";
}

function Progress({ nodes, running }) {
  return (
    <ol className="progress">
      {nodes.map((n, i) => {
        const current = running && i === nodes.length - 1;
        return (
          <li key={i} className={current ? "is-current" : "is-done"}>
            <span className="step-dot" aria-hidden="true">{current ? "" : "✓"}</span>
            <span className="step-name">
              {NODE_LABELS[n.name] || n.name}
              <code>{n.name}</code>
            </span>
            {n.logs.map((m, j) => (
              <span key={j} className={`step-log log-${logKind(m)}`}>{m.replace(/^\[\w+\]\s*/, "")}</span>
            ))}
          </li>
        );
      })}
    </ol>
  );
}

function ClarifyForm({ payload, onAnswer, disabled }) {
  const [answers, setAnswers] = useState({});
  const ready = payload.questions.every((q) => String(q.idx) in answers);
  return (
    <form className="hitl" onSubmit={(e) => { e.preventDefault(); onAnswer(answers); }}>
      <h4><span className="badge badge-hitl">HITL</span> נדרשת הבהרה לפני חישוב המסלול</h4>
      {payload.questions.map((q) => (
        <fieldset key={q.idx}>
          <legend>
            {q.type === "choose" ? <>למה התכוונתם ב-<b>{q.text}</b>?</> : <>באיזו מחלקה לחפש את <b>{q.text}</b>?</>}
          </legend>
          <div className="options">
            {[...q.options, { id: null, name: "לדלג על הפריט" }].map((o) => (
              <label key={String(o.id)} className={o.id === null ? "option is-skip" : "option"}>
                <input type="radio" name={`q${q.idx}`} disabled={disabled}
                  checked={String(q.idx) in answers && answers[q.idx] === o.id}
                  onChange={() => setAnswers({ ...answers, [q.idx]: o.id })} />
                {o.name}
              </label>
            ))}
          </div>
        </fieldset>
      ))}
      <div className="actions">
        <button className="btn btn-primary" disabled={!ready || disabled}>המשך</button>
      </div>
    </form>
  );
}

function SaveForm({ payload, onAnswer, disabled }) {
  const [path, setPath] = useState(payload.path);
  return (
    <div className="hitl">
      {payload.text && <pre className="instructions" dir="auto">{payload.text}</pre>}
      <h4><span className="badge badge-hitl">HITL</span> לשמור את המסלול לקובץ במחשב?</h4>
      <input className="path-input" dir="ltr" value={path} disabled={disabled} onChange={(e) => setPath(e.target.value)} />
      <div className="actions">
        <button className="btn btn-primary" disabled={disabled || !path.trim()} onClick={() => onAnswer(path.trim())}>שמירה</button>
        <button className="btn" disabled={disabled} onClick={() => onAnswer(false)}>לא, תודה</button>
      </div>
    </div>
  );
}

function CostTable({ cost, seconds, model }) {
  const rows = Object.entries(cost.by_node);
  const t = cost.totals;
  return (
    <details className="cost">
      <summary>
        עלות: {usd(t.actual_usd)}
        <span className="muted"> · תיאורטית {usd(t.theoretical_usd)} · {t.input_tokens + t.output_tokens} טוקנים
          {seconds != null && <> · {seconds} שניות</>}</span>
      </summary>
      {rows.length ? (
        <table>
          <thead><tr><th>נוד</th><th>קריאות</th><th>טוקנים (קלט/פלט)</th><th>בפועל</th><th>תיאורטית</th></tr></thead>
          <tbody>
            {rows.map(([n, d]) => (
              <tr key={n}><td>{NODE_LABELS[n] || n}</td><td>{d.calls}</td><td dir="ltr">{d.input_tokens}/{d.output_tokens}</td>
                <td dir="ltr">{usd(d.actual_usd)}</td><td dir="ltr">{usd(d.theoretical_usd)}</td></tr>
            ))}
          </tbody>
          <tfoot><tr><td>סה״כ</td><td>{t.calls}</td><td dir="ltr">{t.input_tokens}/{t.output_tokens}</td>
            <td dir="ltr">{usd(t.actual_usd)}</td><td dir="ltr">{usd(t.theoretical_usd)}</td></tr></tfoot>
        </table>
      ) : <p className="muted">לא בוצעו קריאות למודל.</p>}
      {model && <p className="muted small">מודל: <span dir="ltr">{model}</span>. עלות תיאורטית = מה שהיה עולה לפי תעריף שווה-ערך בתשלום.</p>}
    </details>
  );
}

export default function RunCard({ turn, drawing, model, onAnswer, onCancel, onToast }) {
  const { result, hitl, status } = turn;
  const running = status === "running";
  const route = result?.route;

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(result.text);
      onToast("ההוראות הועתקו");
    } catch {
      onToast("לא הצלחנו להעתיק. סמנו את הטקסט והעתיקו ידנית.");
    }
  };

  return (
    <article className="turn">
      <div className="bubble-user" dir="auto">{turn.text}</div>

      <section className={`agent-card ${result?.blocked ? "is-blocked" : ""}`}>
        {turn.nodes.length > 0 && (
          <details className="progress-wrap" open={running || undefined}>
            <summary>{running ? "האייג'נט עובד…" : `${turn.nodes.length} שלבים בגרף`}</summary>
            <Progress nodes={turn.nodes} running={running && !hitl} />
          </details>
        )}
        {running && !turn.nodes.length && !hitl && <p className="muted">מתחיל…</p>}

        {hitl && hitl.kind === "clarify" && <ClarifyForm payload={hitl} disabled={turn.sending} onAnswer={onAnswer} />}
        {hitl && hitl.kind === "confirm_save" && <SaveForm payload={hitl} disabled={turn.sending} onAnswer={onAnswer} />}
        {hitl && <button className="btn btn-ghost btn-small" onClick={onCancel} disabled={turn.sending}>ביטול המשימה</button>}

        {result && result.blocked && (
          <div className="notice notice-warn"><b>מחוץ לתחום.</b> {result.text}</div>
        )}

        {result && !result.blocked && (
          <div className="result">
            {route && (
              <div className="stats">
                <div><span className="stat-num">{route.total_m.toFixed(0)}</span> מטר הליכה</div>
                {route.naive_m > route.total_m && (
                  <div><span className="stat-num">{(route.naive_m - route.total_m).toFixed(0)}</span> מטר חיסכון לעומת סדר הרשימה</div>
                )}
                <div><span className="stat-num">{route.stops.filter((s) => s.products.length).length}</span> עצירות</div>
              </div>
            )}
            <div className="result-body">
              <pre className="instructions" dir="auto">{result.text}</pre>
              {route && <StoreMap drawing={drawing} route={route} />}
            </div>
            {result.saved_path && <p className="notice notice-ok">נשמר לקובץ: <span dir="ltr">{result.saved_path}</span></p>}
            <div className="actions">
              <button className="btn" onClick={copy}>העתקה</button>
              <button className="btn" onClick={() => downloadText(`route_${stamp()}.txt`, result.text)}>הורדה כקובץ</button>
            </div>
          </div>
        )}

        {turn.cancelled && <div className="notice">המשימה בוטלה.</div>}
        {turn.error && (
          <div className="notice notice-error" role="alert"><b>שגיאה:</b> {turn.error}</div>
        )}

        {(result?.cost || turn.errorCost) && (
          <CostTable cost={result?.cost || turn.errorCost} seconds={result?.seconds} model={model} />
        )}
      </section>
    </article>
  );
}
