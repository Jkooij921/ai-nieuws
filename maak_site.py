"""Maakt de nieuwssite van AI-nieuws: gewone HTML-bestanden, klaar voor GitHub Pages.

  site/index.html                de nieuwste editie
  site/edities/<id>.html         elke editie
  site/artikel/<id>.html         elk bericht apart, met eerder nieuws over hetzelfde onderwerp
  site/onderwerp/<naam>.html     alle berichten over één onderwerp
  site/week/<id>.html            De week in AI
  site/archief.html              alle edities en weken
  site/leren.html                begrippen en tips
  site/zoeken.html, zoek.json    zoeken in alle berichten
  site/zo-maken-we-dit.html      dat alles met AI geschreven is, hoe we kiezen en welke bronnen
  site/stijl.css, site.js        opmaak en de knoppen (filters, lees meer, quiz, gelezen)
  site/deel.png                  het plaatje bij een gedeelde link zonder eigen beeld
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
                         "uitleg": "Praktische tips en concrete voorbeelden: hoe mensen AI gebruiken op werk, op school en thuis."},
    "AI in Nederland": {"knop": "Nederland", "klasse": "nederland", "waarom": "Waarom het ertoe doet",
                        "uitleg": "AI bij Nederlandse en Vlaamse bedrijven, overheid, onderwijs en zorg."},
    "Maatschappij": {"knop": "Maatschappij", "klasse": "maatschappij", "waarom": "Waarom het ertoe doet",
                     "uitleg": "Wat AI doet met banen, privacy en ethiek, en de regels en het onderzoek daarachter."},
}
# Rubrieken die een andere naam kregen; oudere edities worden bij het inlezen omgezet.
OUDE_RUBRIEKEN = {"Onderzoek en regels": "Maatschappij"}
# Over wiens AI een bericht gaat. Claude kiest er één bij het schrijven; de lezer filtert erop.
BEDRIJVEN = ["Anthropic", "OpenAI", "Google", "Microsoft", "Meta", "Mistral", "Anders"]
PRODUCT = {"Anthropic": "Claude", "OpenAI": "ChatGPT", "Google": "Gemini", "Microsoft": "Copilot",
           "Meta": "Meta", "Mistral": "Mistral"}
# De keuzes bovenaan een editie: (code, naam op de knop, uitleg, bedrijven die erbij horen). Overig is de rest.
MERKFILTERS = [("claude", "Claude", "Alles over Claude, Claude Code en Anthropic.", ("Anthropic",)),
               ("chatgpt", "ChatGPT", "Alles over ChatGPT, Codex en OpenAI.", ("OpenAI",)),
               ("overig", "Overig", "Gemini, Copilot, Mistral, Meta en de rest van de AI-wereld.", ())]
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


def bedrijf_van(item):
    """Het bedrijf achter een bericht. Oudere berichten hebben dat veld nog niet; dan raden we het uit de tekst."""
    if item.get("bedrijf") in BEDRIJVEN:
        return item["bedrijf"]
    tekst = " ".join(item.get("onderwerpen", [])) + " " + item["kop"]
    for bedrijf, woorden in (("Anthropic", ("Claude", "Anthropic")), ("OpenAI", ("OpenAI", "ChatGPT", "Codex", "GPT")),
                             ("Google", ("Gemini", "Google", "DeepMind", "Gemma")), ("Microsoft", ("Copilot", "Microsoft")),
                             ("Meta", ("Meta", "Llama")), ("Mistral", ("Mistral",))):
        if any(re.search(rf"\b{woord}", tekst) for woord in woorden):
            return bedrijf
    return "Anders"


def merk_van(item):
    bedrijf = bedrijf_van(item)
    return next((code for code, _, _, bedrijven in MERKFILTERS if bedrijf in bedrijven), "overig")


def geef_ids(ed):
    """Elk bericht een vast adres: <editie>-<nummer>, korte berichten <editie>-k<nummer>.

    Zet ook rubrieken die een andere naam kregen om naar de nieuwe naam.
    """
    for nr, item in enumerate(ed["items"], 1):
        item.setdefault("id", f"{ed['id']}-{nr}")
    for nr, item in enumerate(ed["kort"], 1):
        item.setdefault("id", f"{ed['id']}-k{nr}")
    for item in ed["items"] + ed["kort"]:
        item["rubriek"] = OUDE_RUBRIEKEN.get(item["rubriek"], item["rubriek"])


def veilig(url):
    """Alleen gewone webadressen. Een adres als javascript:... uit een feed wordt een dode link."""
    return url if isinstance(url, str) and url.lower().startswith(("https://", "http://")) else "#"


def artikel_url(site_url, item):
    return f"{site_url}artikel/{item['id']}.html"


def slug(tekst):
    tekst = unicodedata.normalize("NFKD", tekst).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", tekst).strip("-") or "onderwerp"


def deel_link(item, site_url):
    tekst = f"{item['kop']} {artikel_url(site_url, item)}"
    return "https://wa.me/?text=" + urllib.parse.quote(tekst)


def inkorten(tekst, lengte=200):
    """Tekst afkappen op een heel woord, voor de korte omschrijving bij een gedeelde link."""
    if len(tekst) <= lengte:
        return tekst
    return tekst[:lengte].rsplit(" ", 1)[0].rstrip(",.:") + "…"


def deel_tags(deel, site_url):
    """Wat WhatsApp en andere apps tonen als iemand een link deelt: kop, eerste zinnen en een beeld.

    Zonder eigen beeld komt deel.png, het plaatje met de naam van de site. Dat geldt ook voor WebP en AVIF,
    want die toont WhatsApp niet altijd.
    """
    beeld = deel.get("beeld") if veilig(deel.get("beeld")) != "#" else None
    if beeld and urllib.parse.urlparse(beeld).path.lower().endswith((".webp", ".avif", ".svg")):
        beeld = None
    tags = [("name", "description", inkorten(deel["tekst"])),
            ("property", "og:site_name", "AI-nieuws"), ("property", "og:locale", "nl_NL"),
            ("property", "og:type", deel["soort"]), ("property", "og:title", deel["titel"]),
            ("property", "og:description", inkorten(deel["tekst"]))]
    if deel.get("tijd"):
        tags.append(("property", "article:published_time", deel["tijd"]))
    if site_url:
        tags.append(("property", "og:url", deel["url"]))
    if beeld:
        tags.append(("property", "og:image", beeld))
    elif site_url:
        tags += [("property", "og:image", f"{site_url}deel.png"), ("property", "og:image:width", "1200"),
                 ("property", "og:image:height", "630")]
    if beeld or site_url:
        tags.append(("name", "twitter:card", "summary_large_image"))
    return "".join(f'<meta {soort}="{naam}" content="{e(inhoud)}">' for soort, naam, inhoud in tags)


# ---------------------------------------------------------------- stukjes pagina

# Achter een link naar een andere site: een pijltje, en voor schermlezers de woorden erbij.
EXTERN = '<span class="extern" aria-hidden="true">↗</span><span class="sr"> (naar de bron)</span>'

VINK = ('<svg class="vink" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 12l5 5L20 6"></path></svg>')


def beeld_html(item, verhouding="16 / 10"):
    """Het beeld van een bericht, of een zwart blok met de bron als er geen (werkend) beeld is."""
    groot, klein = tegeltekst(item)
    tegel = (f'<div class="tegel" style="aspect-ratio: {verhouding}"><span>{e(groot)}</span>'
             f'<small>{e(klein)}</small></div>')
    if item.get("beeld") and veilig(item["beeld"]) != "#":
        # Werkt het beeld later niet meer, dan zet vroeg.js er alsnog het blok voor in de plaats.
        inhoud = (f'<img src="{e(item["beeld"])}" alt="" loading="lazy" referrerpolicy="no-referrer" '
                  f'style="aspect-ratio: {verhouding}" data-groot="{e(groot)}" data-klein="{e(klein)}">')
    else:
        inhoud = tegel
    return f'<div class="beeld">{inhoud}</div>'


def impact_html(item):
    niveau, woord = impact(item)
    streepjes = "".join(f'<i class="{"aan" if n < niveau else ""}"></i>' for n in range(3))
    return (f'<span class="impact" title="Impact: hoe belangrijk dit nieuws is volgens de selectie">'
            f'{streepjes}Impact {woord}</span>')


def bronnen_html(item):
    links = ", ".join(f'<a href="{e(veilig(url))}">{e(naam)}</a>' for naam, url in bronlinks(item["bronnen"]))
    n = aantal_bronnen(item)
    return f'Gemeld door {n} {"bron" if n == 1 else "bronnen"}: {links}'


def kaart(item, ref, basis, site_url, groot=False):
    """Een bericht in een editie. De hele kaart is één link naar de pagina van het bericht, zoals bij andere nieuwssites.

    De kop is de echte link; via CSS (a::after) is de hele kaart aanklikbaar. Eerst het nieuws, dan waarom het ertoe doet.
    """
    stijl = RUBRIEKEN[item["rubriek"]]
    link = f"{basis}artikel/{item['id']}.html"
    n = aantal_bronnen(item)
    kop = "h1" if groot else "h3"
    lede = f'<p class="lede">{e(item["samenvatting"])}</p>' if groot else f'<p>{e(item["samenvatting"])}</p>'
    waarom = (f'<p class="waarom"><b>{stijl["waarom"]}:</b> {e(item["waarom"])}</p>'
              if groot and item.get("waarom") else "")
    product = PRODUCT.get(bedrijf_van(item))
    productlabel = f'<span class="product">{e(product)}</span>' if product else ""
    return (
        f'<article class="kaart{" groot" if groot else ""}" data-id="{e(item["id"])}" data-rubriek="{stijl["klasse"]}" '
        f'data-merk="{merk_van(item)}">'
        f'{beeld_html(item, "16 / 9" if groot else "16 / 10")}'
        f'<div class="boven"><span class="rubriek">{e(stijl["knop"])}</span>{productlabel}'
        f'<span>{e(datumregel(item["bronnen"], ref))}</span>{impact_html(item)}</div>'
        f'<{kop}><a class="kaartlink" href="{e(link)}">{e(item["kop"])}</a></{kop}>'
        f'{lede}{waarom}'
        f'<div class="onder"><span class="leesverder" aria-hidden="true">Lees het bericht <span class="pijl">→</span></span>'
        f'<span>{max(1, round(len((item["uitleg"] + " " + item["samenvatting"] + " " + item.get("waarom", "")).split()) / 200))} min'
        f' · {n} {"bron" if n == 1 else "bronnen"}</span>'
        f'<span class="gelezen" hidden>{VINK}Gelezen</span></div>'
        f'</article>'
    )


def kort_html(k, ref):
    eerste = [b for b in k["bronnen"] if b["datum"]]
    tijd = f"{_datum(min(eerste, key=_datum)).astimezone():%H:%M}" if eerste else "nieuw"
    namen = ", ".join(naam for naam, _ in bronlinks(k["bronnen"]))
    # Kort nieuws heeft geen eigen pagina: de link gaat naar de bron. Het pijltje zegt dat vooraf.
    return (
        f'<li data-merk="{merk_van(k)}"><span class="tijd">{e(tijd)}</span><div>'
        f'<a class="kaartlink" href="{e(veilig(k["bronnen"][0]["url"]))}">{e(k["kop"])}{EXTERN}</a>'
        f'<p>{e(k["zin"])}</p><span class="meta">{e(RUBRIEKEN[k["rubriek"]]["knop"])} · '
        f'{e(datumregel(k["bronnen"], ref))} · {e(namen)}</span></div></li>'
    )


def quiz_html(quiz, ed, site_url):
    """De nieuwsquiz. Na de laatste vraag kun je je score delen, met een link naar de quiz van deze editie."""
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
    titel = f"AI-nieuwsquiz, {ed['moment']}editie {dagtitel(editiedag(ed))}"
    return (
        f'<section class="quiz" id="quiz" data-aantal="{len(quiz)}" data-titel="{e(titel)}" '
        f'data-url="{e(site_url)}edities/{e(ed["id"])}.html#quiz"><div class="kopregel"><h2>Nieuwsquiz</h2>'
        f'<span>{len(quiz)} vragen over deze editie</span></div>'
        f'<p class="quizuitleg">Hoe goed heb je gelezen? Klik op het antwoord dat volgens jou klopt.</p>'
        f'<ol>{"".join(vragen)}</ol><p class="score" hidden></p>'
        f'<p class="quizdeel" hidden><a class="knop" href="#" target="_blank" rel="noopener">Deel je score via WhatsApp</a>'
        f'<span>Je vrienden krijgen dezelfde vragen.</span></p></section>'
    )


def pagina(titel, basis, actief, inhoud, bovenregel, extra="", deel=None, site_url=""):
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
        # Beveiliging: alleen scripts van de site zelf, geen formulieren, geen ingesloten pagina's.
        '<meta http-equiv="Content-Security-Policy" content="default-src \'self\'; script-src \'self\'; '
        'style-src \'self\' \'unsafe-inline\' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; '
        'img-src \'self\' https: data:; connect-src \'self\'; object-src \'none\'; base-uri \'none\'; form-action \'none\'">'
        f'<title>{e(titel)}</title>{deel_tags(deel, site_url) if deel else ""}'
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        f'<link rel="stylesheet" href="{e(FONTS)}">'
        f'<link rel="icon" href="{basis}favicon.svg" type="image/svg+xml">'
        f'<link rel="stylesheet" href="{basis}stijl.css">{extra}'
        # Al in de kop, want een beeld kan al mislukken voordat site.js geladen is.
        f'<script src="{basis}vroeg.js"></script></head><body>'
        f'<div class="utility"><div class="binnen">{bovenregel}'
        f'<a class="ailabel" href="{basis}zo-maken-we-dit.html">Geschreven met AI</a></div></div>'
        f'<header class="kop"><div class="binnen"><div><a class="merk" href="{basis}index.html">AI-nieuws</a>'
        '<div class="ondertitel">Het belangrijkste AI-nieuws in gewone taal, twee keer per dag</div></div>'
        f'<nav aria-label="Hoofdmenu">{links}</nav></div></header>'
        f'{inhoud}'
        '<footer class="colofon"><div class="binnen">Geschreven door AI (Claude). Dat kan fouten opleveren, dus lees bij twijfel de bron. '
        'De beelden komen van de bronnen zelf. Wat je gelezen hebt, wordt alleen in je eigen browser bewaard. '
        f'<a href="{basis}zo-maken-we-dit.html">Zo maken we dit</a></div></footer>'
        f'<script src="{basis}site.js"></script></body></html>'
    )


def bovenregel_editie(ed):
    tijd = datetime.fromisoformat(ed["tijd"])
    volgende = "20:00" if ed["moment"] == "ochtend" else "08:00"
    return (f'<span>{e(dagtitel(editiedag(ed)).capitalize())} · {e(ed["moment"].capitalize())}editie · '
            f'gemaakt om {tijd:%H:%M}</span><span>Volgende editie om {volgende}</span>')


ALGEMENE_BOVENREGEL = '<span>Elke dag om 08:00 en 20:00 een nieuwe editie</span>'
OMSCHRIJVING = "Het belangrijkste AI-nieuws in gewone taal, elke dag om 08:00 en 20:00."


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
                   f'<p>{e(p["tekst"])}</p><p><a class="knop licht" href="{e(veilig(p["url"]))}">Bekijk de bron{EXTERN}</a></p></div></section>')

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
                f'<span>Kleiner nieuws in één zin</span></div>'
                f'<p class="geenkort" hidden>Over deze AI staat geen kort nieuws in deze editie.</p>'
                f'<ul>{"".join(kort_html(k, ref) for k in ed["kort"])}</ul></section>')

    # De keuze welke AI je wilt zien. Werkt samen met de onderwerpen op de filterbalk.
    alles_bij_elkaar = items + ed["kort"]
    merkknoppen = '<button type="button" data-merk="alle" aria-pressed="true">Alle AI</button>' + "".join(
        f'<button type="button" data-merk="{code}" data-naam="{e(naam)}" data-uitleg="{e(uitleg)}" aria-pressed="false">'
        f'{e(naam)} <span>{sum(1 for i in alles_bij_elkaar if merk_van(i) == code)}</span></button>'
        for code, naam, uitleg, _ in MERKFILTERS
    )
    merken = (f'<div class="merken"><span class="merkvraag">Welke AI wil je zien?</span>'
              f'<div class="merkknoppen" role="group" aria-label="Kies een AI">{merkknoppen}</div>'
              f'<span class="merkuitleg">Je keuze wordt onthouden op dit apparaat.</span></div>')

    voet = f"Gekozen uit {ed['bekeken']} nieuwe berichten uit {ed['aantal_bronnen']} bronnen."
    if ed.get("fouten"):
        voet += f" Niet bereikbaar: {', '.join(ed['fouten'])}."
    aantal = len(items) + len(ed["kort"])
    return (
        f'<div class="editiekop binnen"><div class="label">{e(ed["moment"].capitalize())}editie</div>'
        f'<h1>{e(dagtitel(editiedag(ed)).capitalize())}</h1><p class="intro">{e(ed["intro"])}</p>'
        f'<p class="teller">{aantal} berichten, gekozen uit {ed["bekeken"]} nieuwe berichten en geschreven met AI.</p>{merken}</div>'
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
        f'<p class="geenresultaat" hidden>Over deze keuze staat niets in deze editie. Kies een ander onderwerp of een andere AI.</p>'
        f'<div class="raster">{alle_kaarten}</div></section>'
        f'{kort}{quiz_html(ed.get("quiz"), ed, site_url)}'
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
        f' › <a href="{basis}edities/{e(ed["id"])}.html#{stijl["klasse"]}">{e(stijl["knop"])}</a></nav>'
        f'{beeld_html(item, "16 / 9")}'
        f'<div class="boven"><span class="rubriek">{e(stijl["knop"])}</span>'
        f'<span>{e(datumregel(item["bronnen"], ref))}</span>{impact_html(item)}</div>'
        f'<h1>{e(item["kop"])}</h1>'
        f'<p class="byline">Geschreven met AI (Claude) op basis van de bronnen hieronder · '
        f'<a href="{basis}zo-maken-we-dit.html">Zo maken we dit</a></p>'
        f'<p class="lede">{e(item["samenvatting"])}</p>'
        f'<div class="uitlegblok"><div class="label">Even uitgelegd</div><p>{e(item["uitleg"])}</p></div>'
        f'{waarom}'
        f'<p class="bronnen">{bronnen_html(item)}</p>'
        f'<p class="acties"><a class="knop" href="{e(veilig(item["bronnen"][0]["url"]))}">Lees de bron{EXTERN}</a>'
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
            f'<li data-id="{e(item["id"])}"><span class="nummer">{nr}</span>{beeld_html(item, "16 / 10")}'
            f'<div><div class="boven"><span class="rubriek">{e(RUBRIEKEN[item["rubriek"]]["knop"])}</span>'
            f'<span>{e(dagtitel(editiedag(ed)).capitalize())}</span>{impact_html(item)}</div>'
            f'<h3><a class="kaartlink" href="{e(link)}">{e(item["kop"])}</a></h3><p>{e(item["samenvatting"])}</p></div></li>'
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
                        f'<p>{e(p["tekst"])}</p><a href="{e(veilig(p["url"]))}">Bekijk de bron</a></div>')
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


# Hoe de groepen uit config.json op de pagina Zo maken we dit heten, in deze volgorde.
GROEPEN = [("lab", "De AI-bedrijven zelf"), ("nl-eu", "Nederlandse en Vlaamse nieuwssites en instanties"),
           ("media", "Internationale nieuwssites"), ("curator", "Kenners die AI op de voet volgen"),
           ("onderzoek", "Onderzoek"), ("community", "Gesprekken van gebruikers")]


def werkwijze_html(bronnen):
    """De pagina Zo maken we dit: dat de berichten met AI geschreven zijn, hoe we kiezen en waar het nieuws vandaan komt."""
    per_groep = {}
    for bron in bronnen or []:
        namen = per_groep.setdefault(bron.get("groep"), [])
        naam = bron["naam"].split(" (")[0]
        if naam not in namen:
            namen.append(naam)
    lijst = "".join(f'<div class="begrip"><dt>{e(label)}</dt><dd>{e(", ".join(per_groep[groep]))}</dd></div>'
                    for groep, label in GROEPEN if per_groep.get(groep))
    aantal = f"{len(bronnen)} bronnen" if bronnen else "tientallen bronnen"
    return (
        '<div class="editiekop binnen"><h1>Zo maken we dit</h1>'
        '<p class="intro">AI-nieuws zet elke dag om 08:00 en 20:00 het belangrijkste AI-nieuws op een rij, in gewone taal. '
        'Hier lees je hoe dat gaat.</p></div>'
        '<main class="binnen werkwijze">'
        '<section class="sectie"><div class="kopregel"><h2>Geschreven met AI</h2></div>'
        f'<p>Een computerprogramma haalt twee keer per dag het nieuws op uit {aantal}. Claude, de AI van het bedrijf Anthropic, '
        'kiest daaruit de belangrijkste berichten en schrijft ze in gewone taal.</p>'
        '<p>Er leest geen redacteur mee voordat een editie online komt. Daardoor kan er een fout in een bericht staan. '
        'Bij elk bericht staan daarom de bronnen. Twijfel je, lees dan de bron.</p></section>'
        '<section class="sectie"><div class="kopregel"><h2>Hoe we kiezen</h2></div><ul>'
        '<li>Elk bericht krijgt een score van 1 tot 10: hoeveel heb je eraan? Vanaf een 6 krijgt het een heel bericht met uitleg. '
        'Een 5 wordt een korte vermelding onder Kort nieuws. De rest valt weg.</li>'
        '<li>Nieuws over Claude en ChatGPT gaat voor, daarna Gemini. Andere AI’s komen er alleen in bij groot nieuws.</li>'
        '<li>Extra aandacht gaat naar praktische tips, AI in Nederland en Vlaanderen, en wat AI doet met banen, privacy en ethiek.</li>'
        '<li>Het impact-label laat zien hoe belangrijk een bericht is: groot (score 9 of 10), middel (7 of 8) of klein (6).</li>'
        '<li>Gemeld door laat zien hoeveel bronnen over hetzelfde nieuws schreven. Meer bronnen betekent meestal groter nieuws.</li>'
        '</ul></section>'
        '<section class="sectie"><div class="kopregel"><h2>Wat er niet in komt</h2></div><ul>'
        '<li>Reclame en verkooppraatjes.</li>'
        '<li>Geruchten. Wat alleen op Reddit staat, is pas nieuws als een bedrijf of een nieuwssite het bevestigt.</li>'
        '<li>Onbekende programma’s. Een tool komt er alleen in als hij van een groot AI-bedrijf is of al door veel mensen gebruikt wordt.</li>'
        '<li>Nieuws over geld, zoals investeringen en beurskoersen, tenzij het verandert wat jij kunt gebruiken.</li>'
        '</ul></section>'
        f'<section class="sectie"><div class="kopregel"><h2>Waar het nieuws vandaan komt</h2></div><dl class="begrippen">{lijst}</dl></section>'
        '<section class="sectie"><div class="kopregel"><h2>Beelden en privacy</h2></div>'
        '<p>De beelden komen van de bronnen zelf: het plaatje dat een site opgeeft voor als je een link deelt. '
        'Heeft een bericht geen goed beeld, dan staat er een zwart blok met de naam van de bron.</p>'
        '<p>De site zet geen cookies en houdt niet bij wat je leest. Wat je gelezen hebt en welke AI je kiest, '
        'staat alleen in je eigen browser.</p></section>'
        '</main>'
    )


# ---------------------------------------------------------------- schrijven

def schrijf_site(doel, edities, begrippen, weken=None, site_url="", bronnen=None):
    """Schrijft alle pagina's opnieuw. Geeft het pad naar de voorpagina terug.

    `bronnen` is de lijst uit config.json, voor de pagina Zo maken we dit.
    """
    doel = Path(doel)
    weken = weken or []
    for map_ in ("edities", "artikel", "onderwerp", "week"):
        (doel / map_).mkdir(parents=True, exist_ok=True)
    bron = Path(__file__).resolve().parent
    (doel / "stijl.css").write_text((bron / "stijl.css").read_text(encoding="utf-8"), encoding="utf-8")
    for bestand in ("site.js", "vroeg.js", "favicon.svg"):
        (doel / bestand).write_text((bron / bestand).read_text(encoding="utf-8"), encoding="utf-8")
    (doel / "deel.png").write_bytes((bron / "deel.png").read_bytes())

    edities = sorted(edities, key=lambda ed: ed["tijd"])
    for ed in edities:
        geef_ids(ed)
    alle = [(item, ed) for ed in edities for item in ed["items"]]
    index = {item["id"]: (item, ed) for item, ed in alle}

    def schrijf(pad, titel, basis, actief, inhoud, bovenregel=ALGEMENE_BOVENREGEL, deel=None):
        # Wat een app toont bij een gedeelde link. Zonder eigen tekst of beeld: de omschrijving en het plaatje van de site.
        deel = {"titel": titel, "tekst": OMSCHRIJVING, "soort": "website", **(deel or {}),
                "url": site_url + ("" if pad == "index.html" else pad)}
        (doel / pad).write_text(pagina(titel, basis, actief, inhoud, bovenregel, deel=deel, site_url=site_url),
                                encoding="utf-8")

    for ed in edities:
        beste = next((i for i in sorted(ed["items"], key=lambda i: -i["score"]) if i.get("beeld")), None)
        schrijf(f"edities/{ed['id']}.html", f"AI-nieuws, {editietitel(ed)}", "../", None,
                editie_html(ed, begrippen, "../", site_url), bovenregel_editie(ed),
                {"tekst": ed.get("intro") or OMSCHRIJVING, "beeld": beste["beeld"] if beste else None})
        for item in ed["items"]:
            schrijf(f"artikel/{item['id']}.html", f"{item['kop']} | AI-nieuws", "../", None,
                    artikel_html(item, ed, alle, "../", site_url), bovenregel_editie(ed),
                    {"titel": item["kop"], "tekst": item["samenvatting"], "beeld": item.get("beeld"),
                     "soort": "article", "tijd": datetime.fromisoformat(ed["tijd"]).astimezone().isoformat()})
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
        schrijf(f"onderwerp/{slug(naam)}.html", f"{naam} | AI-nieuws", "../", None, onderwerp_html(naam, lijst, "../", site_url),
                deel={"tekst": f"Alle berichten over {naam} op AI-nieuws, het nieuwste eerst."})

    weken = sorted(weken, key=lambda w: w["id"])
    for week in weken:
        schrijf(f"week/{week['id']}.html", f"De week in AI, week {week['id']} | AI-nieuws", "../", "De week",
                week_html(week, index, "../", site_url), deel={"tekst": week.get("intro") or OMSCHRIJVING})
    if weken:
        schrijf("week/index.html", "De week in AI | AI-nieuws", "../", "De week", week_html(weken[-1], index, "../", site_url),
                deel={"tekst": weken[-1].get("intro") or OMSCHRIJVING})
    else:
        schrijf("week/index.html", "De week in AI | AI-nieuws", "../", "De week",
                '<div class="editiekop binnen"><div class="label">De week in AI</div><h1>Elke zondagavond</h1>'
                '<p class="intro">Op zondagavond verschijnt hier een overzicht met de 10 belangrijkste berichten van de week.</p></div>')

    schrijf("archief.html", "Archief | AI-nieuws", "", "Archief", archief_html(edities, weken, ""))
    schrijf("leren.html", "Begrippen en tips | AI-nieuws", "", "Begrippen en tips", leren_html(begrippen, edities))
    schrijf("zoeken.html", "Zoeken | AI-nieuws", "", "Zoeken", zoeken_html())
    schrijf("zo-maken-we-dit.html", "Zo maken we dit | AI-nieuws", "", None, werkwijze_html(bronnen),
            deel={"tekst": "Hoe AI-nieuws met AI het belangrijkste AI-nieuws kiest en schrijft, en waar het nieuws vandaan komt."})
    zoek = [
        {"id": item["id"], "kop": item["kop"], "samenvatting": item["samenvatting"],
         "rubriek": RUBRIEKEN[item["rubriek"]]["knop"], "datum": dagtitel(editiedag(ed)).capitalize(),
         "onderwerpen": item.get("onderwerpen", [])}
        for item, ed in reversed(alle)
    ]
    (doel / "zoek.json").write_text(json.dumps(zoek, ensure_ascii=False), encoding="utf-8")
    return doel / "index.html"
