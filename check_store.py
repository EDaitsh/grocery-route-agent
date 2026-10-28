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
        rag, smap = load_store_xlsx(Path(sys.argv[1].strip('"')))
    except StoreFileError as e:
        print(e)
        return 1
    departments, products = rag.departments.values(), rag.products.values()
    print(f"הקובץ תקין: {smap.name}")
    print(f"- {len(smap.zones)} אזורים: {', '.join(sorted(smap.zones))}")
    print(f"- {len(departments)} מחלקות: {', '.join(d.name for d in departments)}")
    print(f"- {len(products)} מוצרים חריגים" + (f": {', '.join(p.name for p in products)}" if products else ""))
    no_examples = [d.name for d in departments if not d.examples]
    if no_examples:
        print(f"- מומלץ להוסיף דוגמאות למחלקות: {', '.join(no_examples)}")
    used = {d.location for d in departments} | {p.location for p in products}
    empty = sorted(smap.zones - used - {smap.start, smap.end})
    if empty:
        print(f"- שימו לב: אין מחלקה ואין מוצרים באזורים: {', '.join(empty)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
