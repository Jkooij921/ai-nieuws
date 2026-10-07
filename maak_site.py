"""Maakt de nieuwssite van AI-nieuws: gewone HTML-bestanden, klaar voor GitHub Pages.

  site/index.html                de nieuwste editie
  site/edities/<id>.html         elke editie
  site/artikel/<id>.html         elk bericht apart, met eerder nieuws over hetzelfde onderwerp
  site/onderwerp/<naam>.html     alle berichten over één onderwerp
  site/week/<id>.html            De week in AI
  site/archief.html              alle edities en weken
  site/leren.html                begrippen en tips
  site/zoeken.html, zoek.json    zoeken in alle berichten
  site/stijl.css, site.js        opmaak en de knoppen (filters, lees meer, quiz, gelezen)
"""
import html
import json
import re
import unicodedata
import urllib.parse
from datetime import date, datetime
from pathlib import Path

# Volgorde op de site. `knop`: naam op de filterbalk, `klasse`: korte naam in adressen en code,
# `waarom`: het label van de 'waarom'-zin, `uitleg`: wat er in de rubriek staat.
RUBRIEKEN = {
    "Het grote nieuws": {"knop": "Groot nieuws", "klasse": "groot", "waarom": "Waarom het ertoe doet",
                         "uitleg": "Wat iedereen die AI volgt vandaag moet weten."},
    "Nieuwe modellen": {"knop": "Modellen", "klasse": "modellen", "waarom": "Wat betekent dit",
                        "uitleg": "Nieuwe AI-modellen en grote updates van bestaande modellen."},
    "Nieuwe tools": {"knop": "Tools", "klasse": "tools", "waarom": "Wat heb je eraan",
                     "uitleg": "Programma’s, uitbreidingen en functies die je zelf kunt gebruiken."},
    "Zo gebruik je AI": {"knop": "Zo gebruik je AI", "klasse": "gebruik", "waarom": "Wat heb je eraan",
                         "uitleg": "Slimme toepassingen en ervaringen van mensen die iets met AI bouwen."},
    "Onderzoek en regels": {"knop": "Onderzoek en regels", "klasse": "onderzoek", "waarom": "Waarom het ertoe doet",
                            "uitleg": "Onderzoek, wetten en veiligheid, kort samengevat."},
}
MAILKLEUREN = {"groot": "#C4122F", "modellen": "#C4122F", "tools": "#C4122F", "gebruik": "#C4122F", "onderzoek": "#C4122F"}

DAGEN = ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"]
MAANDEN = ["januari", "februari", "maart", "april", "mei", "juni", "juli",
           "augustus", "september", "oktober", "november", "december"]

e = html.escape

FONTS = ("https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,400..800;1,6..72,400..700"
         "&family=Archivo:wdth,wght@62..125,400..800&display=swap")


# ---------------------------------------------------------------- datums en bronnen

def dagtitel(tijd):
    return f"{DAGEN[tijd.weekday()]} {tijd.day} {MAANDEN[tijd.month - 1]}"


def editiedag(ed):
    """De dag waar een editie bij hoort. Oudere edities hebben alleen het tijdstip waarop ze gemaakt zijn."""
    if ed.get("datum"):
        return date.fromisoformat(ed["datum"])
    return datetime.fromisoformat(ed["tijd"]).date()


def editietitel(ed):
    return f"{ed['moment'].capitalize()}editie {dagtitel(editiedag(ed))}"


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


def _datum(bron):
    return datetime.fromisoformat(bron["datum"]) if isinstance(bron["datum"], str) else bron["datum"]


def datumregel(bronnen, ref):
    """Wanneer het nieuws verscheen: de vroegste datum van alle bronnen bij dit onderwerp."""
    gedateerd = [b for b in bronnen if b["datum"]]
    if not gedateerd:
        return "nieuw sinds de vorige editie"
    eerste = min(gedateerd, key=_datum)
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


def aantal_bronnen(item):
    return len({b["bron"] for b in item["bronnen"]})


def impact(item):
    """Hoe belangrijk een bericht is, afgeleid van de score die Claude bij het kiezen gaf."""
    if item["score"] >= 9:
        return 3, "groot"
    if item["score"] >= 7:
        return 2, "middel"
    return 1, "klein"


def tegeltekst(item):
    """Wat er op het blok staat als een bericht geen beeld heeft: de bron, en bij Reddit de groep."""
    bron = item["bronnen"][0]
    gevonden = re.search(r"reddit\.com/r/([^/]+)", bron["url"])
    if gevonden:
        return "Reddit", f"Gedeeld in r/{gevonden.group(1)}"
    return bron["bron"].split(" (")[0], RUBRIEKEN[item["rubriek"]]["knop"]


def geef_ids(ed):
    """Elk bericht een vast adres: <editie>-<nummer>, korte berichten <editie>-k<nummer>."""
    for nr, item in enumerate(ed["items"], 1):
        item.setdefault("id", f"{ed['id']}-{nr}")
    for nr, item in enumerate(ed["kort"], 1):
        item.setdefault("id", f"{ed['id']}-k{nr}")


def artikel_url(site_url, item):
    return f"{site_url}artikel/{item['id']}.html"


def slug(tekst):
    tekst = unicodedata.normalize("NFKD", tekst).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", tekst).strip("-") or "onderwerp"


def deel_link(item, site_url):
    tekst = f"{item['kop']} {artikel_url(site_url, item)}"
    return "https://wa.me/?text=" + urllib.parse.quote(tekst)


# ---------------------------------------------------------------- stukjes pagina

VINK = ('<svg class="vink" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 12l5 5L20 6"></path></svg>')


def beeld_html(item, verhouding="16 / 10", link=None):
    """Het beeld van een bericht, of een zwart blok met de bron als er geen (werkend) beeld is."""
    groot, klein = tegeltekst(item)
    tegel = (f'<div class="tegel" style="aspect-ratio: {verhouding}"><span>{e(groot)}</span>'
             f'<small>{e(klein)}</small></div>')
    if item.get("beeld"):
        # onerror: werkt het beeld later niet meer, dan verschijnt alsnog het blok.
        inhoud = (f'<img src="{e(item["beeld"])}" alt="" loading="lazy" referrerpolicy="no-referrer" '
                  f'style="aspect-ratio: {verhouding}" data-groot="{e(groot)}" data-klein="{e(klein)}" '
                  f'onerror="beeldMislukt(this)">')
    else:
        inhoud = tegel
    if link:
        return f'<a class="beeld" href="{e(link)}" tabindex="-1" aria-hidden="true">{inhoud}</a>'
    return f'<div class="beeld">{inhoud}</div>'


def impact_html(item):
    niveau, woord = impact(item)
    streepjes = "".join(f'<i class="{"aan" if n < niveau else ""}"></i>' for n in range(3))
    return (f'<span class="impact" title="Impact: hoe belangrijk dit nieuws is volgens de selectie">'
            f'{streepjes}Impact {woord}</span>')


def bronnen_html(item):
    links = ", ".join(f'<a href="{e(url)}">{e(naam)}</a>' for naam, url in bronlinks(item["bronnen"]))
    n = aantal_bronnen(item)
    return f'Gemeld door {n} {"bron" if n == 1 else "bronnen"}: {links}'


def kaart(item, ref, basis, site_url, groot=False):
    stijl = RUBRIEKEN[item["rubriek"]]
    link = f"{basis}artikel/{item['id']}.html"
    n = aantal_bronnen(item)
    waarom = f'<p><b>{stijl["waarom"]}:</b> {e(item["waarom"])}</p>' if item.get("waarom") else ""
    kop = "h1" if groot else "h3"
    lede = (f'<p class="lede">{e(item["uitleg"])}</p><p>{e(item["samenvatting"])}</p>' if groot
            else f'<p>{e(item["samenvatting"])}</p>')
    uitgelegd = "" if groot else f'<p><b>Even uitgelegd:</b> {e(item["uitleg"])}</p>'
    return (
        f'<article class="kaart{" groot" if groot else ""}" data-id="{e(item["id"])}" data-rubriek="{stijl["klasse"]}">'
        f'{beeld_html(item, "16 / 9" if groot else "16 / 10", link)}'
        f'<div class="boven"><span class="rubriek">{e(stijl["knop"])}</span>'
        f'<span>{e(datumregel(item["bronnen"], ref))}</span>{impact_html(item)}</div>'
        f'<{kop}><a href="{e(link)}">{e(item["kop"])}</a></{kop}>'
        f'{lede}'
        f'<div class="meer" hidden>{uitgelegd}{waarom}<p class="bronnen">{bronnen_html(item)}</p>'
        f'<p class="acties"><a class="knop" href="{e(link)}">Hele bericht en eerder nieuws</a>'
        f'<a class="knop licht" href="{e(deel_link(item, site_url))}" target="_blank" rel="noopener">Deel via WhatsApp</a></p></div>'
        f'<div class="onder"><button type="button" class="leesmeer" aria-expanded="false">Lees meer</button>'
        f'<span>{max(1, round(len((item["uitleg"] + " " + item["samenvatting"] + " " + item.get("waarom", "")).split()) / 200))} min'
        f' · {n} {"bron" if n == 1 else "bronnen"}</span>'
        f'<span class="gelezen" hidden>{VINK}Gelezen</span></div>'
        f'</article>'
    )


def kort_html(k, ref):
    eerste = [b for b in k["bronnen"] if b["datum"]]
    tijd = f"{_datum(min(eerste, key=_datum)).astimezone():%H:%M}" if eerste else "nieuw"
    namen = ", ".join(naam for naam, _ in bronlinks(k["bronnen"]))
    return (
        f'<li><span class="tijd">{e(tijd)}</span><div>'
        f'<a href="{e(k["bronnen"][0]["url"])}">{e(k["kop"])}</a>'
        f'<p>{e(k["zin"])}</p><span class="meta">{e(RUBRIEKEN[k["rubriek"]]["knop"])} · '
        f'{e(datumregel(k["bronnen"], ref))} · {e(namen)}</span></div></li>'
    )


def quiz_html(quiz):
    if not quiz:
        return ""
    vragen = []
    for nr, v in enumerate(quiz, 1):
        opties = "".join(f'<button type="button" data-i="{i}">{e(optie)}</button>' for i, optie in enumerate(v["opties"]))
        vragen.append(
            f'<li class="vraag" data-goed="{v["goed"]}"><p class="vraagtekst"><span>{nr}.</span> {e(v["vraag"])}</p>'
            f'<div class="opties">{opties}</div><p class="antwoord" hidden></p>'
            f'<p class="toelichting" hidden>{e(v["uitleg"])}</p></li>'
        )
    return (
        f'<section class="quiz" id="quiz" data-aantal="{len(quiz)}"><div class="kopregel"><h2>Nieuwsquiz</h2>'
        f'<span>{len(quiz)} vragen over deze editie</span></div>'
        f'<p class="quizuitleg">Hoe goed heb je gelezen? Klik op het antwoord dat volgens jou klopt.</p>'
        f'<ol>{"".join(vragen)}</ol><p class="score" hidden></p></section>'
    )


def pagina(titel, basis, actief, inhoud, bovenregel, extra=""):
    huidig = ' aria-current="page"'
    links = "".join(
        f'<a href="{basis}{doel}"{huidig if naam == actief else ""}>{naam}</a>'
        for naam, doel in (("Vandaag", "index.html"), ("De week", "week/index.html"), ("Archief", "archief.html"),
                           ("Begrippen en tips", "leren.html"), ("Zoeken", "zoeken.html"))
    )
    return (
        '<!doctype html><html lang="nl"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta name="robots" content="noindex, nofollow">'
        f'<title>{e(titel)}</title>'
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        f'<link rel="stylesheet" href="{e(FONTS)}">'
        f'<link rel="stylesheet" href="{basis}stijl.css">{extra}'
        # Al in de kop, want een beeld kan al mislukken voordat site.js geladen is.
        '<script>function beeldMislukt(b){var t=document.createElement("div");t.className="tegel";'
        't.style.aspectRatio=b.style.aspectRatio;var g=document.createElement("span");g.textContent=b.dataset.groot||"";'
        'var k=document.createElement("small");k.textContent=b.dataset.klein||"";t.appendChild(g);t.appendChild(k);'
        'b.replaceWith(t);}</script></head><body>'
        f'<div class="utility"><div class="binnen">{bovenregel}</div></div>'
        f'<header class="kop"><div class="binnen"><div><a class="merk" href="{basis}index.html">AI-nieuws</a>'
        '<div class="ondertitel">Het belangrijkste AI-nieuws in gewone taal, twee keer per dag</div></div>'
        f'<nav aria-label="Hoofdmenu">{links}</nav></div></header>'
        f'{inhoud}'
        '<footer class="colofon"><div class="binnen">Geschreven door AI (Claude). Dat kan fouten opleveren, dus lees bij twijfel de bron. '
        'De beelden komen van de bronnen zelf. Wat je gelezen hebt, wordt alleen in je eigen browser bewaard.</div></footer>'
        f'<script src="{basis}site.js"></script></body></html>'
    )


def bovenregel_editie(ed):
    tijd = datetime.fromisoformat(ed["tijd"])
    volgende = "20:00" if ed["moment"] == "ochtend" else "08:00"
    return (f'<span>{e(dagtitel(editiedag(ed)).capitalize())} · {e(ed["moment"].capitalize())}editie · '
            f'gemaakt om {tijd:%H:%M}</span><span>Volgende editie om {volgende}</span>')


ALGEMENE_BOVENREGEL = '<span>Elke dag om 08:00 en 20:00 een nieuwe editie</span>'


# ---------------------------------------------------------------- pagina's

def editie_html(ed, begrippen, basis, site_url):
    ref = datetime.fromisoformat(ed["tijd"])
    items = ed["items"]
    if not items and not ed["kort"]:
        return '<main class="binnen"><p class="leeg">In deze editie stond niets dat de moeite waard was.</p></main>'

    # De opening: het belangrijkste grote nieuws, liefst met een beeld. Daarnaast het volgende grote bericht.
    groot = sorted([i for i in items if i["rubriek"] == "Het grote nieuws"], key=lambda i: -i["score"])
    rest = sorted(items, key=lambda i: -i["score"])
    lead = next((i for i in groot if i.get("beeld")), groot[0] if groot else (rest[0] if rest else None))
    tweede = next((i for i in groot + rest if lead is not None and i is not lead), None)
    getoond = {id(lead), id(tweede)}

    tabs = [("alles", "Alles", len(items) + len(ed["kort"]), "", "")]
    for naam, stijl in RUBRIEKEN.items():
        aantal = sum(1 for i in items if i["rubriek"] == naam)
        if aantal:
            tabs.append((stijl["klasse"], stijl["knop"], aantal, stijl["knop"], stijl["uitleg"]))
    if ed["kort"]:
        tabs.append(("kort", "Kort nieuws", len(ed["kort"]), "Kort nieuws", "Kleiner nieuws in één zin."))
    if ed.get("quiz"):
        tabs.append(("quiz", "Quiz", len(ed["quiz"]), "Nieuwsquiz", ""))
    tabbalk = "".join(
        f'<button type="button" data-filter="{k}" data-titel="{e(t)}" data-uitleg="{e(u)}" '
        f'aria-pressed="{"true" if k == "alles" else "false"}">{e(n)} <span>{a}</span></button>'
        for k, n, a, t, u in tabs
    )

    # Uitgelegd: een begrip dat in deze editie voor het eerst werd uitgelegd.
    nieuw = [b for b in begrippen.values() if b.get("editie") == ed["id"]]
    begrip = nieuw[0] if nieuw else None
    uitgelegd = ""
    if begrip:
        uitgelegd = (f'<section class="uitgelegd" aria-label="Uitgelegd"><div class="label">Uitgelegd</div>'
                     f'<div class="woord">{e(begrip["woord"])}</div><p>{e(begrip["uitleg"])}</p>'
                     f'<a href="{basis}leren.html">Alle uitgelegde begrippen</a></section>')

    opening = ""
    if lead:
        opening = (f'<div class="opening">{kaart(lead, ref, basis, site_url, groot=True)}'
                   f'<aside class="zij">{kaart(tweede, ref, basis, site_url) if tweede else ""}{uitgelegd}</aside></div>')

    probeer = ""
    if ed.get("probeer"):
        p = ed["probeer"]
        bij = next((i for i in items if any(b["url"] == p["url"] for b in i["bronnen"])), None)
        beeld = beeld_html(bij, "2 / 1") if bij and bij.get("beeld") else ""
        probeer = (f'<section class="probeer{" metbeeld" if beeld else ""}" aria-label="Probeer dit vandaag">{beeld}<div class="tekst">'
                   f'<div class="label">Probeer dit vandaag · ongeveer 10 minuten</div><h2>{e(p["titel"])}</h2>'
                   f'<p>{e(p["tekst"])}</p><p><a class="knop licht" href="{e(p["url"])}">Bekijk de bron</a></p></div></section>')

    secties = []
    for naam, stijl in RUBRIEKEN.items():
        lijst = [i for i in items if i["rubriek"] == naam and id(i) not in getoond]
        if lijst:
            kaarten = "".join(kaart(i, ref, basis, site_url) for i in lijst)
            secties.append(f'<section class="sectie"><div class="kopregel"><h2>{e(naam)}</h2>'
                           f'<button type="button" class="tekstknop" data-kies="{stijl["klasse"]}">Alleen {e(stijl["knop"].lower() if stijl["knop"] != "Zo gebruik je AI" else stijl["knop"])} tonen</button></div>'
                           f'<div class="raster">{kaarten}</div></section>')

    alle_kaarten = "".join(kaart(i, ref, basis, site_url) for i in items)
    kort = ""
    if ed["kort"]:
        kort = (f'<section class="sectie kortnieuws" id="kort"><div class="kopregel"><h2>Kort nieuws</h2>'
                f'<span>Kleiner nieuws in één zin</span></div><ul>{"".join(kort_html(k, ref) for k in ed["kort"])}</ul></section>')

    voet = f"Gekozen uit {ed['bekeken']} nieuwe berichten uit {ed['aantal_bronnen']} bronnen."
    if ed.get("fouten"):
        voet += f" Niet bereikbaar: {', '.join(ed['fouten'])}."
    aantal = len(items) + len(ed["kort"])
    return (
        f'<div class="editiekop binnen"><div class="label">{e(ed["moment"].capitalize())}editie</div>'
        f'<h1>{e(dagtitel(editiedag(ed)).capitalize())}</h1><p class="intro">{e(ed["intro"])}</p>'
        f'<p class="teller">{aantal} berichten, gekozen uit {ed["bekeken"]} nieuwe berichten.</p></div>'
        f'<div class="tabbalk" data-totaal="{len(items)}" data-ids="{e(",".join(i["id"] for i in items))}"><div class="binnen">'
        f'<div class="tabs" role="group" aria-label="Kies een onderwerp">{tabbalk}</div>'
        f'<div class="voortgang"><span class="voortgangtekst">0 van {len(items)} gelezen</span>'
        f'<div class="balk" role="progressbar" aria-label="Hoeveel berichten je hebt gelezen" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"><div></div></div></div>'
        f'</div></div>'
        f'<main class="binnen editie">'
        f'<div class="klaar" hidden>{VINK}<span>Je hebt alles van deze editie gelezen. De volgende verschijnt om '
        f'{"20:00" if ed["moment"] == "ochtend" else "08:00"}.</span></div>'
        f'<div id="alles">{opening}{probeer}{"".join(secties)}</div>'
        f'<section id="gefilterd" hidden><div class="kopregel"><h2></h2></div><p class="filteruitleg"></p>'
        f'<div class="raster">{alle_kaarten}</div></section>'
        f'{kort}{quiz_html(ed.get("quiz"))}'
        f'<p class="editievoet">{e(voet)}</p></main>'
    )


def artikel_html(item, ed, alle, basis, site_url):
    stijl = RUBRIEKEN[item["rubriek"]]
    ref = datetime.fromisoformat(ed["tijd"])
    onderwerpen = item.get("onderwerpen", [])
    chips = "".join(f'<a class="chip" href="{basis}onderwerp/{slug(o)}.html">{e(o)}</a>' for o in onderwerpen)

    # Meer over hetzelfde onderwerp: eerst het meest specifieke onderwerp, dan de andere.
    verwant, gezien = [], {item["id"]}
    for onderwerp in onderwerpen:
        for ander, ander_ed in alle:
            if ander["id"] not in gezien and onderwerp in ander.get("onderwerpen", []):
                verwant.append((ander, ander_ed))
                gezien.add(ander["id"])
    verwant.sort(key=lambda paar: paar[1]["tijd"], reverse=True)
    verwant = verwant[:6]
    eerder = all(a_ed["tijd"] <= ed["tijd"] for _, a_ed in verwant)
    verwant_html = ""
    if verwant:
        titel = f"{'Eerder' if eerder else 'Meer'} over {onderwerpen[0]}" if onderwerpen else "Meer over dit onderwerp"
        rijen = "".join(
            f'<li data-id="{e(a["id"])}"><a href="{basis}artikel/{e(a["id"])}.html">{beeld_html(a, "16 / 10")}'
            f'<span><span class="meta">{e(dagtitel(editiedag(a_ed)).capitalize())} · {e(RUBRIEKEN[a["rubriek"]]["knop"])}</span>'
            f'<b>{e(a["kop"])}</b></span></a></li>'
            for a, a_ed in verwant
        )
        verwant_html = f'<section class="verwant"><h2>{e(titel)}</h2><ul>{rijen}</ul></section>'

    meer = [i for i in ed["items"] if i["id"] != item["id"]][:4]
    meer_html = "".join(
        f'<li><a href="{basis}artikel/{e(i["id"])}.html"><span class="meta">{e(RUBRIEKEN[i["rubriek"]]["knop"])}</span>'
        f'<b>{e(i["kop"])}</b></a></li>' for i in meer
    )
    waarom = f'<p><b>{stijl["waarom"]}:</b> {e(item["waarom"])}</p>' if item.get("waarom") else ""
    return (
        f'<main class="artikel binnen" data-artikel="{e(item["id"])}">'
        f'<nav class="kruimel" aria-label="Waar je bent"><a href="{basis}edities/{e(ed["id"])}.html">{e(editietitel(ed))}</a>'
        f' › <span>{e(stijl["knop"])}</span></nav>'
        f'{beeld_html(item, "16 / 9")}'
        f'<div class="boven"><span class="rubriek">{e(stijl["knop"])}</span>'
        f'<span>{e(datumregel(item["bronnen"], ref))}</span>{impact_html(item)}</div>'
        f'<h1>{e(item["kop"])}</h1>'
        f'<p class="lede">{e(item["samenvatting"])}</p>'
        f'<div class="uitlegblok"><div class="label">Even uitgelegd</div><p>{e(item["uitleg"])}</p></div>'
        f'{waarom}'
        f'<p class="bronnen">{bronnen_html(item)}</p>'
        f'<p class="acties"><a class="knop" href="{e(item["bronnen"][0]["url"])}">Lees de bron</a>'
        f'<a class="knop licht" href="{e(deel_link(item, site_url))}" target="_blank" rel="noopener">Deel via WhatsApp</a></p>'
        f'{f"<p class=chips>Onderwerpen: {chips}</p>" if chips else ""}'
        f'{verwant_html}'
        f'<section class="meerlijst"><h2>Meer uit deze editie</h2><ul>{meer_html}</ul></section>'
        f'</main>'
    )


def onderwerp_html(naam, lijst, basis, site_url):
    kaarten = "".join(kaart(item, datetime.fromisoformat(ed["tijd"]), basis, site_url) for item, ed in lijst)
    return (f'<div class="editiekop binnen"><div class="label">Onderwerp</div><h1>{e(naam)}</h1>'
            f'<p class="teller">{len(lijst)} {"bericht" if len(lijst) == 1 else "berichten"}, het nieuwste eerst.</p></div>'
            f'<main class="binnen"><div class="raster">{kaarten}</div></main>')


def week_html(week, index, basis, site_url):
    van, tot = date.fromisoformat(week["van"]), date.fromisoformat(week["tot"])
    rijen = []
    for nr, item_id in enumerate(week["items"], 1):
        if item_id not in index:
            continue
        item, ed = index[item_id]
        link = f"{basis}artikel/{item['id']}.html"
        rijen.append(
            f'<li data-id="{e(item["id"])}"><span class="nummer">{nr}</span>{beeld_html(item, "16 / 10", link)}'
            f'<div><div class="boven"><span class="rubriek">{e(RUBRIEKEN[item["rubriek"]]["knop"])}</span>'
            f'<span>{e(dagtitel(editiedag(ed)).capitalize())}</span>{impact_html(item)}</div>'
            f'<h3><a href="{e(link)}">{e(item["kop"])}</a></h3><p>{e(item["samenvatting"])}</p></div></li>'
        )
    weeknr = week["id"].split("-W")[1].lstrip("0")
    return (f'<div class="editiekop binnen"><div class="label">De week in AI · week {e(weeknr)}</div>'
            f'<h1>{e(dagtitel(van).capitalize())} tot en met {e(dagtitel(tot))}</h1>'
            f'<p class="intro">{e(week["intro"])}</p>'
            f'<p class="teller">De {len(rijen)} belangrijkste berichten van de week.</p></div>'
            f'<main class="binnen"><ol class="weeklijst">{"".join(rijen)}</ol></main>')


def archief_html(edities, weken, basis):
    weekblok = ""
    if weken:
        regels = "".join(
            f'<a class="editie" href="{basis}week/{e(w["id"])}.html"><b>De week in AI, week {e(w["id"].split("-W")[1].lstrip("0"))}</b>'
            f'{e(dagtitel(date.fromisoformat(w["van"])).capitalize())} tot en met {e(dagtitel(date.fromisoformat(w["tot"])))}</a>'
            for w in sorted(weken, key=lambda w: w["id"], reverse=True)
        )
        weekblok = f'<section class="sectie"><div class="kopregel"><h2>De week in AI</h2></div>{regels}</section>'
    per_dag = {}
    for ed in sorted(edities, key=lambda ed: ed["tijd"], reverse=True):
        per_dag.setdefault(editiedag(ed), []).append(ed)
    dagen = []
    for dag, lijst in per_dag.items():
        regels = []
        for ed in lijst:
            top = max(ed["items"], key=lambda i: i["score"])["kop"] if ed["items"] else ""
            aantal = len(ed["items"]) + len(ed["kort"])
            regels.append(f'<a class="editie" href="{basis}edities/{e(ed["id"])}.html"><b>{e(ed["moment"].capitalize())}editie</b>'
                          f'{e(top)}<span class="meta">{aantal} berichten</span></a>')
        dagen.append(f'<div class="dag"><h3>{e(dagtitel(dag).capitalize())}</h3>{"".join(regels)}</div>')
    return (f'<div class="editiekop binnen"><h1>Archief</h1><p class="teller">Alle edities, de nieuwste bovenaan.</p></div>'
            f'<main class="binnen archief">{weekblok}<section class="sectie"><div class="kopregel"><h2>Edities</h2></div>'
            f'{"".join(dagen) or "<p class=leeg>Nog geen edities.</p>"}</section></main>')


def leren_html(begrippen, edities):
    termen = sorted(begrippen.values(), key=lambda b: b["woord"].lower())
    lijst = "".join(f'<div class="begrip"><dt>{e(b["woord"])}</dt><dd>{e(b["uitleg"])}</dd></div>' for b in termen)
    tips = []
    for ed in sorted(edities, key=lambda ed: ed["tijd"], reverse=True):
        if ed.get("probeer"):
            p = ed["probeer"]
            tips.append(f'<div class="tip"><div class="label">{e(editietitel(ed))}</div><h3>{e(p["titel"])}</h3>'
                        f'<p>{e(p["tekst"])}</p><a href="{e(p["url"])}">Bekijk de bron</a></div>')
    return (
        '<div class="editiekop binnen"><h1>Begrippen en tips</h1>'
        '<p class="intro">Alle woorden die in de edities zijn uitgelegd, en alle tips om zelf te proberen.</p></div>'
        '<main class="binnen leren">'
        f'<section class="sectie"><div class="kopregel"><h2>Begrippen</h2><span>{len(termen)} begrippen</span></div>'
        '<label class="zoekveld">Zoek een begrip <input id="begripzoek" type="search" autocomplete="off"></label>'
        f'<dl class="begrippen">{lijst}</dl></section>'
        f'<section class="sectie"><div class="kopregel"><h2>Probeer dit</h2></div>{"".join(tips) or "<p class=leeg>Nog geen tips.</p>"}</section>'
        '</main>'
    )


def zoeken_html():
    return (
        '<div class="editiekop binnen"><h1>Zoeken</h1><p class="intro">Zoek in alle berichten van alle edities.</p></div>'
        '<main class="binnen zoeken"><label class="zoekveld">Zoekwoorden <input id="zoekveld" type="search" '
        'autocomplete="off" placeholder="Bijvoorbeeld Claude Code of Mistral"></label>'
        '<p id="zoekuitleg" class="teller">Typ minstens twee letters.</p><ol id="zoekresultaten" class="zoekresultaten"></ol></main>'
    )


# ---------------------------------------------------------------- schrijven

def schrijf_site(doel, edities, begrippen, weken=None, site_url=""):
    """Schrijft alle pagina's opnieuw. Geeft het pad naar de voorpagina terug."""
    doel = Path(doel)
    weken = weken or []
    for map_ in ("edities", "artikel", "onderwerp", "week"):
        (doel / map_).mkdir(parents=True, exist_ok=True)
    bron = Path(__file__).resolve().parent
    (doel / "stijl.css").write_text((bron / "stijl.css").read_text(encoding="utf-8"), encoding="utf-8")
    (doel / "site.js").write_text((bron / "site.js").read_text(encoding="utf-8"), encoding="utf-8")

    edities = sorted(edities, key=lambda ed: ed["tijd"])
    for ed in edities:
        geef_ids(ed)
    alle = [(item, ed) for ed in edities for item in ed["items"]]
    index = {item["id"]: (item, ed) for item, ed in alle}

    def schrijf(pad, titel, basis, actief, inhoud, bovenregel=ALGEMENE_BOVENREGEL):
        (doel / pad).write_text(pagina(titel, basis, actief, inhoud, bovenregel), encoding="utf-8")

    for ed in edities:
        schrijf(f"edities/{ed['id']}.html", f"AI-nieuws, {editietitel(ed)}", "../", None,
                editie_html(ed, begrippen, "../", site_url), bovenregel_editie(ed))
        for item in ed["items"]:
            schrijf(f"artikel/{item['id']}.html", f"{item['kop']} | AI-nieuws", "../", None,
                    artikel_html(item, ed, alle, "../", site_url), bovenregel_editie(ed))
    if edities:
        laatste = edities[-1]
        schrijf("index.html", "AI-nieuws", "", "Vandaag", editie_html(laatste, begrippen, "", site_url), bovenregel_editie(laatste))
    else:
        schrijf("index.html", "AI-nieuws", "", "Vandaag", '<main class="binnen"><p class="leeg">De eerste editie verschijnt om 08:00 of 20:00.</p></main>')

    per_onderwerp = {}
    for item, ed in reversed(alle):
        for onderwerp in item.get("onderwerpen", []):
            per_onderwerp.setdefault(onderwerp, []).append((item, ed))
    for naam, lijst in per_onderwerp.items():
        schrijf(f"onderwerp/{slug(naam)}.html", f"{naam} | AI-nieuws", "../", None, onderwerp_html(naam, lijst, "../", site_url))

    weken = sorted(weken, key=lambda w: w["id"])
    for week in weken:
        schrijf(f"week/{week['id']}.html", f"De week in AI, week {week['id']} | AI-nieuws", "../", "De week",
                week_html(week, index, "../", site_url))
    if weken:
        schrijf("week/index.html", "De week in AI | AI-nieuws", "../", "De week", week_html(weken[-1], index, "../", site_url))
    else:
        schrijf("week/index.html", "De week in AI | AI-nieuws", "../", "De week",
                '<div class="editiekop binnen"><div class="label">De week in AI</div><h1>Elke zondagavond</h1>'
                '<p class="intro">Op zondagavond verschijnt hier een overzicht met de 10 belangrijkste berichten van de week.</p></div>')

    schrijf("archief.html", "Archief | AI-nieuws", "", "Archief", archief_html(edities, weken, ""))
    schrijf("leren.html", "Begrippen en tips | AI-nieuws", "", "Begrippen en tips", leren_html(begrippen, edities))
    schrijf("zoeken.html", "Zoeken | AI-nieuws", "", "Zoeken", zoeken_html())
    zoek = [
        {"id": item["id"], "kop": item["kop"], "samenvatting": item["samenvatting"],
         "rubriek": RUBRIEKEN[item["rubriek"]]["knop"], "datum": dagtitel(editiedag(ed)).capitalize(),
         "onderwerpen": item.get("onderwerpen", [])}
        for item, ed in reversed(alle)
    ]
    (doel / "zoek.json").write_text(json.dumps(zoek, ensure_ascii=False), encoding="utf-8")
    return doel / "index.html"
