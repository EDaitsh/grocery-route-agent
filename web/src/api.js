// קריאות לשרת ה-FastAPI. שגיאה מהשרת מגיעה כ-{"error": "..."} בעברית, ונזרקת כ-Error עם ההודעה הזו.
export async function api(path, { method = "GET", body } = {}) {
  let res;
  try {
    res = await fetch(path, {
      method,
      headers: body === undefined ? {} : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new Error("אין חיבור לשרת האייג'נט. ודאו שחלון האייג'נט עדיין פתוח.");
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = typeof data.detail === "string" ? data.detail : null;
    throw new Error(data.error || detail || `שגיאה ${res.status} בתקשורת עם השרת`);
  }
  return data;
}

export const NODE_LABELS = {
  Input_Guardrail: "בדיקת תחום ואבטחה",
  Refuse: "סירוב",
  Parse_List: "ניתוח הרשימה",
  RAG_Lookup: "חיפוש בחנות (RAG)",
  Match_Classify: "שיוך למחלקות",
  Confidence_Gate: "בדיקת ודאות",
  HITL_Clarify: "שאלת הבהרה",
  Plan_Route_Tool: "חישוב מסלול",
  Write_Instructions: "ניסוח הוראות",
  Evaluator: "בקרת איכות",
  Finalize: "סיכום",
  HITL_Save: "אישור שמירה",
};

export const usd = (v) => `$${(v || 0).toFixed(6)}`;

export function downloadText(name, text) {
  const url = URL.createObjectURL(new Blob([text], { type: "text/plain;charset=utf-8" }));
  const a = Object.assign(document.createElement("a"), { href: url, download: name });
  a.click();
  URL.revokeObjectURL(url);
}

export function stamp() {
  const d = new Date();
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}_${p(d.getHours())}${p(d.getMinutes())}`;
}
