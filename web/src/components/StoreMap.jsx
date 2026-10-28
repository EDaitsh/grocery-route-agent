// ציור החנות והמסלול ב-SVG. מפת אקסל: כל תא = יחידה אחת (קירות, אזורים, מעברים ריקים).
// מפת map.json: קטעי מעברים בין נקודות. הנקודות מגיעות מהשרת כ-(x, y).

function frame(drawing) {
  if (drawing.kind === "grid") {
    const [r0, r1] = drawing.rows;
    const [c0, c1] = drawing.cols;
    // (עמודה, שורה) -> מרכז התא
    return { w: c1 - c0 + 1, h: r1 - r0 + 1, pt: ([c, r]) => [c - c0 + 0.5, r - r0 + 0.5], unit: 1 };
  }
  const pts = [...Object.values(drawing.zones).map((z) => z.at), ...drawing.edges.flatMap((e) => [e.slice(0, 2), e.slice(2)])];
  const xs = pts.map((p) => p[0]);
  const ys = pts.map((p) => p[1]);
  const pad = 2;
  const [x0, y0, y1] = [Math.min(...xs) - pad, Math.min(...ys) - pad, Math.max(...ys) + pad];
  // ב-map.json ציר y עולה מהכניסה פנימה; מציירים כך שהכניסה למטה
  return { w: Math.max(...xs) + pad - x0, h: y1 - y0, pt: ([x, y]) => [x - x0, y1 - y], unit: 1.6 };
}

export default function StoreMap({ drawing, route }) {
  if (!drawing) return null;
  const f = frame(drawing);
  const u = f.unit;
  const stops = (route?.stops || []).filter((s) => s.products.length);
  const path = (route?.path || []).map(f.pt);
  const zoneAt = (z) => f.pt(drawing.zones[z]?.at || [0, 0]);
  const stopZones = new Set(stops.map((s) => s.node));

  return (
    <svg className="store-map" viewBox={`0 0 ${f.w} ${f.h}`} role="img" aria-label={`מפת ${drawing.name} עם המסלול`}>
      <rect width={f.w} height={f.h} className="map-floor" />

      {drawing.kind === "grid" ? (
        <>
          {drawing.walls.map(([r, c]) => {
            const [x, y] = f.pt([c, r]);
            return <rect key={`${r},${c}`} x={x - 0.5} y={y - 0.5} width={1.02} height={1.02} className="map-wall" />;
          })}
          {Object.entries(drawing.zone_cells).map(([z, cells]) =>
            cells.map(([r, c]) => {
              const [x, y] = f.pt([c, r]);
              return (
                <rect key={`${z}${r},${c}`} x={x - 0.5} y={y - 0.5} width={1.02} height={1.02}
                  className={stopZones.has(z) ? "map-zone is-stop" : "map-zone"} />
              );
            })
          )}
        </>
      ) : (
        drawing.edges.map((e, i) => {
          const [x1, y1] = f.pt(e.slice(0, 2));
          const [x2, y2] = f.pt(e.slice(2));
          return <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} className="map-aisle" strokeWidth={u} />;
        })
      )}

      {/* שמות אזורים: בחנות אקסל כולם (באזור צר וארוך, כמו מעבר, לאורכו), במפת נקודות רק העצירות */}
      {Object.entries(drawing.zones)
        .filter(([z]) => drawing.kind === "grid" || stopZones.has(z) || z === drawing.start || z === drawing.end)
        .map(([z, info]) => {
          const [x, y] = zoneAt(z);
          const cells = drawing.zone_cells?.[z] || [];
          const rows = cells.map(([r]) => r);
          const tall = cells.length && Math.max(...rows) - Math.min(...rows) + 1 >= 6;
          if (tall) {
            const [, top] = f.pt([0, Math.min(...rows)]);
            const ly = (top + y) / 2;
            return (
              <text key={z} x={x} y={ly} className="map-label" fontSize={0.62} dy="0.32em"
                transform={`rotate(-90 ${x} ${ly})`}>
                {info.label}
              </text>
            );
          }
          return (
            <text key={z} x={x} y={y - 0.9 * u} className="map-label" fontSize={0.72 * u}>
              {info.label}
            </text>
          );
        })}

      {path.length > 1 && (
        <polyline points={path.map((p) => p.join(",")).join(" ")} className="map-route" strokeWidth={0.32 * u} />
      )}

      {[drawing.start, drawing.end].map((z, i) => {
        const [x, y] = zoneAt(z);
        return <circle key={z} cx={x} cy={y} r={0.55 * u} className={i ? "map-end" : "map-start"} />;
      })}

      {stops.map((s, i) => {
        const [x, y] = zoneAt(s.node);
        return (
          <g key={s.node} className={s.collect_last ? "map-stop is-last" : "map-stop"}>
            <circle cx={x} cy={y} r={0.75 * u} />
            <text x={x} y={y} fontSize={0.85 * u} dy="0.32em">{i + 1}</text>
          </g>
        );
      })}
    </svg>
  );
}
