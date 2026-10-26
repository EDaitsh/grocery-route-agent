"""בדיקת קובץ חנות (store.xlsx) לפני שמוסיפים אותו:  python check_store.py <נתיב לקובץ>"""
import sys
from pathlib import Path

from agent.tools import StoreFileError, load_store_xlsx

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    try:
        products, smap = load_store_xlsx(Path(sys.argv[1].strip('"')))
    except StoreFileError as e:
        print(e)
        return 1
    last = [p.name for p in products if p.collect_last]
    print(f"הקובץ תקין: {smap.name}")
    print(f"- {len(smap.zones)} אזורים: {', '.join(sorted(smap.zones))}")
    print(f"- {len(products)} מוצרים" + (f" (לאסוף בסוף: {', '.join(last)})" if last else ""))
    empty = sorted(smap.zones - {p.location for p in products} - {smap.start, smap.end})
    if empty:
        print(f"- שימו לב: אין מוצרים באזורים: {', '.join(empty)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
