import { useEffect } from "react";

function Modal({ title, onClose, children }) {
  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" role="dialog" aria-modal="true" aria-label={title} onClick={(e) => e.stopPropagation()}>
        <header>
          <h2>{title}</h2>
          <button className="icon-btn" aria-label="סגירה" onClick={onClose}>×</button>
        </header>
        {children}
      </div>
    </div>
  );
}

export function HelpModal({ onClose }) {
  return (
    <Modal title="מדריך שימוש קצר" onClose={onClose}>
      <div className="help">
        <p>האייג'נט מקבל רשימת קניות בעברית ומחזיר את הסדר הקצר ביותר לאסוף את המוצרים בחנות, עם מפה והוראות הליכה.</p>
        <h4>איך משתמשים</h4>
        <ul>
          <li><b>כתבו רשימה</b> בתיבה למטה (פסיקים או שורות) ולחצו Enter. אפשר עם כמויות ושגיאות כתיב: <i>2 חלב 3%, לחם אחיד, טחינה</i>.</li>
          <li><b>גררו קובץ טקסט</b> (txt / csv / md) לחלון, או לחצו על 📎 כדי לבחור קובץ.</li>
          <li><b>הרשימה השבועית</b> בצד: מוסיפים פריטים במהלך השבוע ולוחצים "חישוב מסלול לרשימה".</li>
          <li>אפשר גם לשאול על מוצר בודד: <i>איפה נמצאת הטחינה?</i></li>
        </ul>
        <h4>במהלך הריצה</h4>
        <ul>
          <li>מוצגים השלבים בגרף בזמן אמת: בדיקת תחום, ניתוח, חיפוש בחנות, שיוך, חישוב מסלול ובקרת איכות.</li>
          <li><b>שאלות הבהרה (HITL):</b> כשלא ברור איפה פריט נמצא והבחירה משנה את המסלול, האייג'נט עוצר ושואל.</li>
          <li><b>שמירה לקובץ</b> מתבצעת רק אחרי אישור שלכם.</li>
        </ul>
        <h4>בסרגל העליון</h4>
        <ul>
          <li><b>חנות ומודל:</b> בחירת החנות הפעילה ומודל ה-LLM (מזהה מ-openrouter.ai/models).</li>
          <li><b>עלות:</b> עלות ושימוש מצטברים, כולל עלות תיאורטית למודלים חינמיים.</li>
          <li><b>תקציר שיחה:</b> הורדת קובץ טקסט עם כל המשימות בהפעלה הנוכחית.</li>
        </ul>
        <p className="muted small">האייג'נט עונה רק על תכנון מסלול קניות. שאלות בנושאים אחרים יקבלו סירוב מנומס.</p>
      </div>
    </Modal>
  );
}

export function ConfirmModal({ text, onYes, onNo }) {
  return (
    <Modal title="אישור" onClose={onNo}>
      <p>{text}</p>
      <div className="actions">
        <button className="btn btn-primary" autoFocus onClick={onYes}>כן</button>
        <button className="btn" onClick={onNo}>לא</button>
      </div>
    </Modal>
  );
}
