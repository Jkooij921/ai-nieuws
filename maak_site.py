"""Maakt de nieuwssite van AI-nieuws: gewone HTML-bestanden die zonder internet in de browser openen.

  site/index.html           de nieuwste editie
  site/edities/<id>.html    elke editie
  site/archief.html         alle edities op een rij
  site/leren.html           de begrippenlijst en alle tips
"""
import html
from datetime import datetime
from pathlib import Path

# Volgorde op de site, tekst op de knop bovenaan, css-klasse en het label van de 'waarom'-zin.
RUBRIEKEN = {
    "Het grote nieuws": {"knop": "Groot nieuws", "klasse": "groot", "waarom": "Waarom belangrijk"},
    "Nieuwe modellen": {"knop": "Modellen", "klasse": "modellen", "waarom": "Wat betekent dit"},
    "Nieuwe tools": {"knop": "Tools", "klasse": "tools", "waarom": "Wat heb je eraan"},
    "Zo gebruik je AI": {"knop": "Zo gebruik je AI", "klasse": "gebruik", "waarom": "Wat heb je eraan"},
    "Onderzoek en regels": {"knop": "Onderzoek en regels", "klasse": "onderzoek", "waarom": None},
}
# Mailprogramma's lezen geen CSS-variabelen; daarom staan de kleuren voor de mail hier nog een keer.
MAILKLEUREN = {"groot": "#dc2626", "modellen": "#c2410c", "tools": "#2563eb", "gebruik": "#047857", "onderzoek": "#7c3aed"}

DAGEN = ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"]
MAANDEN = ["januari", "februari", "maart", "april", "mei", "juni", "juli",
           "augustus", "september", "oktober", "november", "december"]

e = html.escape

CSS = """
:root{--bg:#f5f5f2;--vlak:#ffffff;--tekst:#18181b;--zacht:#5b5b63;--lijn:#e3e3de;--tip:#fdf3cf;--tiptekst:#6b4e00;
--groot:#dc2626;--modellen:#c2410c;--tools:#2563eb;--gebruik:#047857;--onderzoek:#7c3aed;--snel:#6b7280}
@media (prefers-color-scheme:dark){:root{--bg:#111113;--vlak:#1b1b1f;--tekst:#ececf0;--zacht:#a1a1aa;--lijn:#2c2c33;
--tip:#2b2410;--tiptekst:#f3d27a;--groot:#f87171;--modellen:#fb923c;--tools:#60a5fa;--gebruik:#34d399;--onderzoek:#a78bfa;--snel:#9ca3af}}
.r-groot{--k:var(--groot)}.r-modellen{--k:var(--modellen)}.r-tools{--k:var(--tools)}
.r-gebruik{--k:var(--gebruik)}.r-onderzoek{--k:var(--onderzoek)}.r-snel{--k:var(--snel)}
*{box-sizing:border-box}
html{scroll-padding-top:120px}
body{margin:0;background:var(--bg);color:var(--tekst);font:16px/1.6 -apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
a{color:inherit}
.binnen{max-width:760px;margin:0 auto;padding:0 16px}
header.balk{background:var(--vlak);border-bottom:1px solid var(--lijn);position:sticky;top:0;z-index:3}
header.balk .binnen{display:flex;align-items:center;justify-content:space-between;height:56px}
.merk{font-weight:800;font-size:20px;letter-spacing:-.02em;text-decoration:none}
nav a{margin-left:18px;text-decoration:none;color:var(--zacht);font-size:15px}
nav a.actief{color:var(--tekst);font-weight:600}
.editiekop{padding:28px 0 4px}
.label{font-size:13px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--zacht)}
h1{font-size:32px;line-height:1.15;letter-spacing:-.02em;margin:4px 0 12px}
.intro{font-size:19px;line-height:1.5;margin:0 0 8px}
.teller{color:var(--zacht);font-size:14px;margin:0}
.knoppen{display:flex;gap:8px;overflow-x:auto;padding:14px 0;position:sticky;top:56px;background:var(--bg);z-index:2}
.knoppen a{flex:none;font-size:13px;padding:5px 12px;border:1px solid var(--lijn);border-radius:999px;text-decoration:none;background:var(--vlak)}
.knoppen a::before{content:"";display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--k);margin-right:6px}
section{margin:26px 0 10px}
section>h2{font-size:13px;letter-spacing:.06em;text-transform:uppercase;color:var(--k);border-bottom:2px solid var(--k);padding-bottom:6px;margin:0 0 4px}
article{background:var(--vlak);border:1px solid var(--lijn);border-radius:10px;padding:16px 18px;margin:12px 0}
article h3{font-size:19px;line-height:1.3;margin:0 0 4px}
.r-groot article h3{font-size:23px}
article h3 a{text-decoration:none}
article h3 a:hover{text-decoration:underline}
.meta{color:var(--zacht);font-size:13px}
article .meta{margin-bottom:10px}
.uitleg{border-left:3px solid var(--lijn);padding-left:12px;color:var(--zacht);font-size:15px}
article p{margin:0 0 10px}
.bron{font-size:13px;color:var(--zacht)}
.snel ul{list-style:none;padding:0;margin:8px 0 0}
.snel li{background:var(--vlak);border:1px solid var(--lijn);border-radius:10px;padding:12px 16px;margin:8px 0}
.snel li a{text-decoration:none}
.snel li a:hover{text-decoration:underline}
.snel li .meta{display:block;margin-top:2px}
.tip{background:var(--tip);border-radius:10px;padding:16px 18px;margin:26px 0}
.tip .label{color:var(--tiptekst)}
.tip h3{font-size:19px;margin:4px 0 6px}
.tip p{margin:0 0 8px}
.tip a{color:var(--tiptekst);font-size:14px}
footer{color:var(--zacht);font-size:13px;border-top:1px solid var(--lijn);margin:30px 0 10px;padding-top:14px}
.leeg{color:var(--zacht);padding:40px 0}
.dag{margin:26px 0}
.dag h2{font-size:15px;text-transform:capitalize;margin:0 0 8px}
.dag a.editie{display:block;background:var(--vlak);border:1px solid var(--lijn);border-radius:10px;padding:12px 16px;margin:8px 0;text-decoration:none}
.dag a.editie:hover{border-color:var(--zacht)}
.dag a.editie b{display:block}
#zoek{width:100%;font:inherit;padding:10px 14px;border:1px solid var(--lijn);border-radius:10px;background:var(--vlak);color:var(--tekst);margin:8px 0 14px}
dl{margin:0}
.begrip{background:var(--vlak);border:1px solid var(--lijn);border-radius:10px;padding:12px 16px;margin:8px 0}
.begrip dt{font-weight:700}
.begrip dd{margin:2px 0 0;color:var(--tekst)}
.colofon{color:var(--zacht);font-size:13px;text-align:center;margin:10px 0 40px}
@media (max-width:520px){h1{font-size:26px}.intro{font-size:17px}nav a{margin-left:12px}}
"""


def dagtitel(tijd):
    return f"{DAGEN[tijd.weekday()]} {tijd.day} {MAANDEN[tijd.month - 1]}"


def wanneer(datum, ref):
    """Een datum in gewone woorden, gezien vanaf ref: 'vandaag 09:43', 'gisteren 17:00' of 'zaterdag 4 oktober'."""
    if datum is None:
        return "onbekend"
    if isinstance(datum, str):
        datum = datetime.fromisoformat(datum)
    lokaal = datum.astimezone()
    dagen = (ref.date() - lokaal.date()).days
    if dagen <= 0:
        return f"vandaag {lokaal:%H:%M}"
    if dagen == 1:
        return f"gisteren {lokaal:%H:%M}"
    return dagtitel(lokaal)


def datumregel(bronnen, ref):
    """Wanneer het nieuws verscheen: de vroegste datum van alle bronnen bij dit onderwerp."""
    gedateerd = [b for b in bronnen if b["datum"]]
    if not gedateerd:
        return "nieuw sinds de vorige editie"
    eerste = min(gedateerd, key=lambda b: datetime.fromisoformat(b["datum"]) if isinstance(b["datum"], str) else b["datum"])
    regel = wanneer(eerste["datum"], ref)
    # Op Reddit en Hacker News is dit het moment van delen, niet per se van het nieuws zelf.
    if eerste["groep"] == "community":
        regel += f", gedeeld op {eerste['bron']}"
    return regel


def bronlinks(bronnen):
    """(naam, adres) per bron; dezelfde bron twee keer noemen helpt niemand."""
    links, namen = [], set()
    for bron in bronnen:
        if bron["bron"] in namen:
            continue
        namen.add(bron["bron"])
        naam = bron["bron"]
        if bron.get("discussie"):
            naam += f" ({bron['punten']} punten)"
        if bron.get("sterren") is not None:
            naam += f" ({bron['sterren']:,} sterren op GitHub)".replace(",", ".")
        links.append((naam, bron.get("discussie") or bron["url"]))
    return links


def _extern(url, tekst):
    return f'<a href="{e(url)}" target="_blank" rel="noopener">{tekst}</a>'


def _artikel(item, ref):
    stijl = RUBRIEKEN[item["rubriek"]]
    uitleg = f'<p class="uitleg">{e(item["uitleg"])}</p>' if item.get("uitleg", "").strip() else ""
    waarom = ""
    if stijl["waarom"] and item.get("waarom", "").strip():
        waarom = f'<p><b>{stijl["waarom"]}:</b> {e(item["waarom"])}</p>'
    bronnen = ", ".join(_extern(link, e(naam)) for naam, link in bronlinks(item["bronnen"]))
    return (
        f'<article><h3>{_extern(item["bronnen"][0]["url"], e(item["kop"]))}</h3>'
        f'<div class="meta">{e(datumregel(item["bronnen"], ref))}</div>'
        f'{uitleg}<p>{e(item["samenvatting"])}</p>{waarom}'
        f'<div class="bron">Bron: {bronnen}</div></article>'
    )


def _tip(probeer):
    return (
        '<div class="tip" id="tip"><div class="label">Probeer dit vandaag</div>'
        f'<h3>{e(probeer["titel"])}</h3><p>{e(probeer["tekst"])}</p>'
        f'{_extern(probeer["url"], "Naar de bron")}</div>'
    )


def editie_html(ed):
    tijd = datetime.fromisoformat(ed["tijd"])
    knoppen, delen = [], []
    for rubriek, stijl in RUBRIEKEN.items():
        items = [i for i in ed["items"] if i["rubriek"] == rubriek]
        if not items:
            continue
        knoppen.append(f'<a class="r-{stijl["klasse"]}" href="#{stijl["klasse"]}">{stijl["knop"]}</a>')
        delen.append(
            f'<section id="{stijl["klasse"]}" class="r-{stijl["klasse"]}"><h2>{e(rubriek)}</h2>'
            + "".join(_artikel(i, tijd) for i in items) + "</section>"
        )
    if ed.get("probeer"):
        # De tip na de eerste rubriek: vroeg genoeg om hem te zien, zonder het grote nieuws te verdringen.
        delen.insert(min(1, len(delen)), _tip(ed["probeer"]))
        knoppen.insert(min(1, len(knoppen)), '<a href="#tip" style="--k:var(--tiptekst)">Probeer dit</a>')
    if ed["kort"]:
        knoppen.append('<a class="r-snel" href="#snel">Snel nog even</a>')
        regels = "".join(
            f'<li>{_extern(k["bronnen"][0]["url"], "<b>" + e(k["kop"]) + "</b>")} {e(k["zin"])}'
            f'<span class="meta">{e(k["rubriek"])} · {e(datumregel(k["bronnen"], tijd))} · '
            f'{e(", ".join(naam for naam, _ in bronlinks(k["bronnen"])))}</span></li>'
            for k in ed["kort"]
        )
        delen.append(f'<section id="snel" class="snel r-snel"><h2>Snel nog even</h2><ul>{regels}</ul></section>')

    aantal = len(ed["items"]) + len(ed["kort"])
    voet = f"Bekeken: {ed['bekeken']} berichten uit {ed['aantal_bronnen']} bronnen."
    if ed.get("fouten"):
        voet += f" Niet bereikbaar: {', '.join(ed['fouten'])}."
    return (
        f'<div class="editiekop"><div class="label">{e(ed["moment"].capitalize())}editie</div>'
        f'<h1>{e(dagtitel(tijd).capitalize())}</h1>'
        f'<p class="intro">{e(ed["intro"])}</p>'
        f'<p class="teller">{aantal} berichten, gekozen uit {ed["bekeken"]} nieuwe berichten. Gemaakt om {tijd:%H:%M}.</p></div>'
        f'<div class="knoppen">{"".join(knoppen)}</div>'
        + "".join(delen)
        + f'<footer>{e(voet)}</footer>'
    )


def archief_html(edities):
    if not edities:
        return '<h1>Archief</h1><p class="leeg">Nog geen edities.</p>'
    per_dag = {}
    for ed in sorted(edities, key=lambda ed: ed["tijd"], reverse=True):
        per_dag.setdefault(ed["tijd"][:10], []).append(ed)
    dagen = []
    for _, lijst in per_dag.items():
        tijd = datetime.fromisoformat(lijst[0]["tijd"])
        regels = []
        for ed in lijst:
            top = max(ed["items"], key=lambda i: i["score"])["kop"] if ed["items"] else ""
            aantal = len(ed["items"]) + len(ed["kort"])
            regels.append(
                f'<a class="editie" href="edities/{e(ed["id"])}.html"><b>{e(ed["moment"].capitalize())}editie</b>'
                f'{e(top)}<div class="meta">{aantal} berichten</div></a>'
            )
        dagen.append(f'<div class="dag"><h2>{e(dagtitel(tijd))}</h2>{"".join(regels)}</div>')
    return '<div class="editiekop"><h1>Archief</h1><p class="teller">Alle edities, de nieuwste bovenaan.</p></div>' + "".join(dagen)


def leren_html(begrippen, edities):
    termen = sorted(begrippen.values(), key=lambda b: b["woord"].lower())
    if termen:
        lijst = "".join(f'<div class="begrip"><dt>{e(b["woord"])}</dt><dd>{e(b["uitleg"])}</dd></div>' for b in termen)
        begrippen_html = (
            '<input id="zoek" type="search" placeholder="Zoek een begrip" autocomplete="off">'
            f'<dl id="begrippen">{lijst}</dl>'
            "<script>document.getElementById('zoek').addEventListener('input',function(){"
            "var q=this.value.toLowerCase();document.querySelectorAll('.begrip').forEach(function(d){"
            "d.hidden=q&&d.textContent.toLowerCase().indexOf(q)<0;});});</script>"
        )
    else:
        begrippen_html = '<p class="leeg">Nog geen begrippen. Ze komen er vanzelf bij met elke editie.</p>'

    tips = []
    for ed in sorted(edities, key=lambda ed: ed["tijd"], reverse=True):
        if ed.get("probeer"):
            tijd = datetime.fromisoformat(ed["tijd"])
            p = ed["probeer"]
            tips.append(
                f'<div class="tip"><div class="label">{e(dagtitel(tijd))}, {e(ed["moment"])}</div>'
                f'<h3>{e(p["titel"])}</h3><p>{e(p["tekst"])}</p>{_extern(p["url"], "Naar de bron")}</div>'
            )
    tips_html = "".join(tips) or '<p class="leeg">Nog geen tips.</p>'
    return (
        '<div class="editiekop"><h1>Leren</h1>'
        '<p class="intro">Alle woorden die in de nieuwsbrief zijn uitgelegd, en alle tips om zelf te proberen.</p></div>'
        f'<section class="r-gebruik"><h2>Begrippen ({len(termen)})</h2>{begrippen_html}</section>'
        f'<section class="r-groot" style="--k:var(--tiptekst)"><h2>Probeer dit</h2>{tips_html}</section>'
    )


def pagina(titel, basis, actief, inhoud):
    links = "".join(
        f'<a href="{basis}{doel}" class="{"actief" if naam == actief else ""}">{naam}</a>'
        for naam, doel in (("Vandaag", "index.html"), ("Archief", "archief.html"), ("Leren", "leren.html"))
    )
    return (
        '<!doctype html><html lang="nl"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        # Wie de link heeft kan de site lezen, maar zoekmachines nemen hem niet op.
        '<meta name="robots" content="noindex, nofollow">'
        f'<title>{e(titel)}</title><style>{CSS}</style></head><body>'
        f'<header class="balk"><div class="binnen"><a class="merk" href="{basis}index.html">AI-nieuws</a><nav>{links}</nav></div></header>'
        f'<main class="binnen">{inhoud}'
        '<p class="colofon">Samengevat door AI (Claude). Dat kan fouten opleveren, dus lees bij twijfel de bron. '
        'Elke dag een nieuwe editie om 08:00 en 20:00.</p></main></body></html>'
    )


def schrijf_site(doel, edities, begrippen):
    """Schrijft alle pagina's opnieuw. Geeft het pad naar de voorpagina terug."""
    doel = Path(doel)
    (doel / "edities").mkdir(parents=True, exist_ok=True)
    edities = sorted(edities, key=lambda ed: ed["tijd"])
    for ed in edities:
        titel = f"AI-nieuws, {dagtitel(datetime.fromisoformat(ed['tijd']))} {ed['moment']}"
        (doel / "edities" / f"{ed['id']}.html").write_text(pagina(titel, "../", None, editie_html(ed)), encoding="utf-8")
    if edities:
        voorpagina = editie_html(edities[-1])
    else:
        voorpagina = '<p class="leeg">De eerste editie verschijnt om 08:00 of 20:00.</p>'
    (doel / "index.html").write_text(pagina("AI-nieuws", "", "Vandaag", voorpagina), encoding="utf-8")
    (doel / "archief.html").write_text(pagina("AI-nieuws archief", "", "Archief", archief_html(edities)), encoding="utf-8")
    (doel / "leren.html").write_text(pagina("AI-nieuws leren", "", "Leren", leren_html(begrippen, edities)), encoding="utf-8")
    return doel / "index.html"
