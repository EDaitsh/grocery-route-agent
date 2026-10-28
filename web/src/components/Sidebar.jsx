import { useState } from "react";

export function WeeklyList({ items, busy, onAdd, onRemove, onClear, onPlan }) {
  const [text, setText] = useState("");
  const add = (e) => {
    e.preventDefault();
    if (text.trim()) onAdd(text).then(() => setText(""));
  };
  return (
    <section className="panel">
      <h3>הרשימה השבועית <span className="count">{items.length}</span></h3>
      <p className="muted small">נשמרת בין הפעלות. מוסיפים במהלך השבוע ומחשבים מסלול לפני הקנייה.</p>
      <form className="inline-form" onSubmit={add}>
        <input value={text} onChange={(e) => setText(e.target.value)} placeholder="למשל: חלב, טחינה" aria-label="פריטים להוספה" />
        <button className="btn" disabled={!text.trim()}>הוספה</button>
      </form>
      {items.length ? (
        <ul className="weekly">
          {items.map((it, i) => (
            <li key={`${i}${it}`}>
              <span dir="auto">{it}</span>
              <button className="icon-btn" title="הסרה" aria-label={`הסרת ${it}`} onClick={() => onRemove(i)}>×</button>
            </li>
          ))}
        </ul>
      ) : <p className="muted small empty">הרשימה ריקה.</p>}
      <div className="actions">
        <button className="btn btn-primary" disabled={!items.length || busy} onClick={onPlan}>חישוב מסלול לרשימה</button>
        <button className="btn btn-ghost" disabled={!items.length} onClick={onClear}>ריקון</button>
      </div>
    </section>
  );
}

export function Extensions({ tools }) {
  return (
    <section className="panel">
      <h3>הרחבות פעילות</h3>
      <ul className="tools">
        {tools.map((t) => (
          <li key={t.name} className={t.active ? "" : "is-off"}>
            <span className={`dot ${t.active ? "on" : ""}`} aria-hidden="true" />
            <div><b>{t.name}</b><span className="muted small">{t.description}</span></div>
          </li>
        ))}
      </ul>
    </section>
  );
}
