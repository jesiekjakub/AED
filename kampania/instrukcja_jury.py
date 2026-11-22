"""INSTRUKCJA_DLA_JURY.md -> kampania/instrukcja_dla_jury_AED.pdf (prosty konwerter Markdown -> HTML -> PDF)."""
import html
import re
from pathlib import Path

from ksiega import chrome, data_uri
from logo import GOV, GRANAT, svg

KAT = Path(__file__).resolve().parent


def inline(t: str) -> str:
    t = html.escape(t, quote=False)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"`(.+?)`", r"<code>\1</code>", t)
    return re.sub(r"(https?://[^\s<)]+)", r'<a href="\1">\1</a>', t)


def main():
    out, lista = [], None
    for linia in (KAT.parent / "INSTRUKCJA_DLA_JURY.md").read_text(encoding="utf-8").splitlines():
        m = re.match(r"^(\s*)(- |\d+\. )(.*)", linia)
        if m:
            typ = "ol" if m.group(2)[0].isdigit() else "ul"
            if lista != typ:
                if lista:
                    out.append(f"</{lista}>")
                out.append(f"<{typ}>")
                lista = typ
            out.append(f"<li>{inline(m.group(3))}</li>")
            continue
        if lista:
            out.append(f"</{lista}>")
            lista = None
        if linia.startswith("# "):
            out.append(f"<h1>{inline(linia[2:])}</h1>")
        elif linia.startswith("## "):
            out.append(f"<h2>{inline(linia[3:])}</h2>")
        elif linia.strip():
            out.append(f"<p>{inline(linia)}</p>")
    if lista:
        out.append(f"</{lista}>")
    doc = f"""<!doctype html><html lang="pl"><head><meta charset="utf-8"><title>Instrukcja dla jury</title><style>
@font-face{{font-family:Roboto;src:url('{(KAT / "fonty" / "Roboto-Regular.ttf").as_uri()}');font-weight:400}}
@font-face{{font-family:Roboto;src:url('{(KAT / "fonty" / "Roboto-Bold.ttf").as_uri()}');font-weight:700}}
@page{{size:A4;margin:14mm 16mm}} body{{font-family:Roboto,Arial,sans-serif;font-size:10pt;line-height:1.42;color:#1b1b1b}}
.top{{display:flex;justify-content:space-between;align-items:center;border-bottom:4px solid {GOV};padding-bottom:3mm;margin-bottom:2mm}} .top img{{height:14mm}}
h1{{font-size:16pt;color:{GRANAT};margin:0}} h2{{font-size:12.5pt;color:{GOV};margin:5mm 0 1.5mm;border-bottom:1px solid #cfd8e3;padding-bottom:1mm}}
p{{margin:1.6mm 0}} ul,ol{{margin:.5mm 0 2mm;padding-left:6mm}} li{{margin:.6mm 0}} code{{font-size:8.8pt;background:#f2f4f7;padding:0 1mm;border-radius:1mm}} a{{color:{GOV}}}
</style></head><body><div class="top">{''.join(out[:1])}<img src="{data_uri(svg())}"></div>{''.join(out[1:])}</body></html>"""
    p = KAT / "instrukcja_jury.html"
    p.write_text(doc, encoding="utf-8")
    chrome(["--allow-file-access-from-files", f"--print-to-pdf={KAT / 'instrukcja_dla_jury_AED.pdf'}", "--no-pdf-header-footer", p.as_uri()])


if __name__ == "__main__":
    main()
