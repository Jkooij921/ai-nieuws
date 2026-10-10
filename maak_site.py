"""Maakt de nieuwssite van AI-nieuws: gewone HTML-bestanden, klaar voor GitHub Pages.

  site/index.html                de nieuwste editie
  site/edities/<id>.html         elke editie
  site/artikel/<id>.html         elk bericht apart, met onderaan Lees ook
  site/onderwerp/<naam>.html     alle berichten over één onderwerp
  site/week/<id>.html            De week in AI
  site/archief.html              alle edities en weken
  site/leren.html                begrippen en tips
  site/zoeken.html, zoek.json    zoeken in alle berichten
  site/zo-maken-we-dit.html      dat alles met AI geschreven is, hoe we kiezen en welke bronnen
  site/correcties.html           wat er verbeterd is na een melding ("correcties" bij een bericht in edities/*.json)
  site/stijl.css, site.js        opmaak (licht en donker) en de knoppen (filters, quiz, gelezen, nieuwe editie)
  site/count.js                  de teller van GoatCounter (statistieken zonder cookies), ingesteld in vroeg.js
  site/laatste.json              welke editie de nieuwste is, voor de controle in site.js
  site/deel.png                  het plaatje bij een gedeelde link zonder eigen beeld
  site/manifest.webmanifest      naam en icoon (icoon-*.png) voor op het beginscherm van je telefoon
  site/sitemap.xml, robots.txt   voor Google: welke pagina's er zijn (alleen de vindbare, zie VINDBAAR)
"""
import html
import json
import re
import unicodedata
import urllib.parse
from datetime import date, datetime, timedelta
from pathlib import Path

# Volgorde op de site. `knop`: naam op de filterbalk, `klasse`: korte naam in adressen en code,
# `waarom`: het label van de 'waarom'-zin, `uitleg`: wat er in de rubriek staat.
RUBRIEKEN = {
    "Het grote nieuws": {"knop": "Groot nieuws", "klasse": "groot", "waarom": "Waarom het ertoe doet",
                         "uitleg": "Wat iedereen die AI volgt vandaag moet weten."},
    # Elke editie één uitlegstuk: geen nieuws, maar achtergrond bij het nieuws.
    "Uitleg": {"knop": "Uitleg", "klasse": "uitleg", "waarom": "Wat heb je eraan",
               "uitleg": "Achtergrond bij het nieuws: hoe iets werkt, stap voor stap en in gewone taal."},
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

# Statistieken met GoatCounter: hoe vaak elke pagina bekeken wordt, zonder cookies en zonder bij te
# houden wie je bent. count.js staat op de site zelf; alleen de telling gaat naar dit adres.
TELLER = "https://ainieuwsvandaag.goatcounter.com/count"
TELLER_SERVER = TELLER.rsplit("/", 1)[0]

# Waar lezers een fout melden. Cloudflare stuurt dit adres door naar de mailbox van de redactie.
FOUTEN_ADRES = "fouten@ainieuwsvandaag.nl"

# De code van Google Search Console (methode HTML-tag), zodat Google weet dat de site van ons is.
# Hij staat alleen op de voorpagina en is niet geheim.
GOOGLE_VERIFICATIE = "rbil7mlYy1-BOu9jqK-p_Tt-9ArzxbpID7Bj5oqQKZM"


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


def leestijd(item):
    """Minuten lezen, bij 200 woorden per minuut. Oudere berichten hebben nog geen artikel, alleen de korte delen."""
    delen = [item["samenvatting"], item["uitleg"], item.get("waarom", "")]
    for blok in item.get("artikel", []):
        delen += [blok["tussenkop"], *blok["alineas"]]
    return max(1, round(len(" ".join(delen).split()) / 200))


def impact(item):
    """Hoe belangrijk een bericht is, afgeleid van de score die Claude bij het kiezen gaf."""
    if item["score"] >= 9:
        return 3, "groot"
    if item["score"] >= 7:
        return 2, "middel"
    return 1, "klein"


def tegeltekst(item):
    """Wat er op het blok staat als een bericht geen beeld heeft: de bron, en bij Reddit de groep."""
    if item["rubriek"] == "Uitleg":
        return "Uitleg", "Achtergrond bij het nieuws"
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

    Zet ook rubrieken die een andere naam kregen om naar de nieuwe naam, en haalt beelden weg die
    niet van een AI-bedrijf of van GitHub zijn (ook in oudere edities).
    """
    for nr, item in enumerate(ed["items"], 1):
        item.setdefault("id", f"{ed['id']}-{nr}")
    for nr, item in enumerate(ed["kort"], 1):
        item.setdefault("id", f"{ed['id']}-k{nr}")
    for item in ed["items"] + ed["kort"]:
        item["rubriek"] = OUDE_RUBRIEKEN.get(item["rubriek"], item["rubriek"])
        if item.get("beeld") and not beeld_toegestaan(item["beeld"], item.get("bronnen", [])):
            item["beeld"] = ""


# Alleen beelden zonder risico op een claim van een fotograaf of persbureau: het eigen deelplaatje van een
# AI-bedrijf, en de kaart die GitHub voor elk project maakt. Al het andere wordt het zwarte blok met de bron.
EIGEN_BEELDEN = ("anthropic.com", "claude.com", "claude.ai", "openai.com", "chatgpt.com", "blog.google",
                 "deepmind.google", "gemini.google", "ai.google", "mistral.ai", "huggingface.co", "hf.co",
                 "microsoft.com", "meta.com", "opengraph.githubassets.com")
# Opslag die AI-bedrijven delen met andere sites: alleen goed als een bron van het bedrijf zelf is.
GEDEELDE_OPSLAG = ("images.ctfassets.net", "storage.googleapis.com", "lh3.googleusercontent.com")


def beeld_toegestaan(url, bronnen):
    host = urllib.parse.urlsplit(url or "").netloc.lower()
    if not host:
        return False
    if any(host == d or host.endswith("." + d) for d in EIGEN_BEELDEN):
        return True
    return host in GEDEELDE_OPSLAG and any(b.get("groep") == "lab" for b in bronnen)


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


def fout_link(item, site_url):
    """Een mail aan de redactie met de kop en de link al ingevuld, zodat de lezer alleen de fout hoeft te noemen."""
    # Wie op de knop klikt, heeft al een fout gezien: het onderwerp stelt het vast in plaats van het te vragen.
    onderwerp = f"Er klopt iets niet: {item['kop']}"
    tekst = (
        f"Artikel: {artikel_url(site_url, item)}\n\n"
        "Wat klopt er niet?\n"
        "Tip: kopieer de zin met de fout hierheen, of zeg in je eigen woorden wat er mis is.\n\n\n"
        "Hoe zit het wel? (mag je overslaan)\n"
        "Weet je waar het goed staat? Zet de link erbij, dan kunnen we het sneller nakijken.\n"
    )
    return f"mailto:{FOUTEN_ADRES}?subject={urllib.parse.quote(onderwerp)}&body={urllib.parse.quote(tekst)}"


def correcties_html(item):
    """Wat er na een melding verbeterd is, onder het artikel. We halen nooit stilletjes iets weg."""
    return "".join(
        f'<div class="correctie"><div class="label">Correctie, {e(dagtitel(date.fromisoformat(c["datum"])))}</div>'
        f'<p>{e(c["tekst"])}</p></div>'
        for c in item.get("correcties", [])
    )


def inkorten(tekst, lengte=200):
    """Tekst afkappen op een heel woord, voor de korte omschrijving bij een gedeelde link."""
    if len(tekst) <= lengte:
        return tekst
    return tekst[:lengte].rsplit(" ", 1)[0].rstrip(",.:") + "…"


def artikel_gegevens(item, tijd, site_url):
    """Voor Google: wat voor pagina dit is (schema.org), met kop, tijd en beeld. Een uitlegstuk is achtergrond, geen nieuws.

    Als schrijver staat AI-nieuws zelf, want de tekst is met AI geschreven en niet door een redacteur.
    """
    beeld = item.get("beeld") if veilig(item.get("beeld")) != "#" else None
    gegevens = {
        "@context": "https://schema.org", "@type": "Article" if item["rubriek"] == "Uitleg" else "NewsArticle",
        "headline": inkorten(item["kop"], 110), "description": inkorten(item["samenvatting"]),
        "datePublished": tijd, "dateModified": tijd, "inLanguage": "nl-NL",
        "mainEntityOfPage": artikel_url(site_url, item), "image": [beeld or f"{site_url}deel.png"],
        "author": {"@type": "Organization", "name": "AI-nieuws", "url": site_url},
        "publisher": {"@type": "Organization", "name": "AI-nieuws", "url": site_url,
                      "logo": {"@type": "ImageObject", "url": f"{site_url}icoon-512.png"}},
    }
    # Een JSON-blok wordt niet uitgevoerd, dus de CSP laat het toe. "</" kan het blok niet afsluiten.
    return '<script type="application/ld+json">' + json.dumps(gegevens, ensure_ascii=False).replace("</", "<\\/") + "</script>"


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
        # Een GitHub-kaart is tekst op wit: heel laten in plaats van bijsnijden, anders valt de tekst half weg.
        heel = ' class="heel"' if "opengraph.githubassets.com" in item["beeld"] else ""
        inhoud = (f'<img src="{e(item["beeld"])}"{heel} alt="" loading="lazy" referrerpolicy="no-referrer" '
                  f'style="aspect-ratio: {verhouding}" data-groot="{e(groot)}" data-klein="{e(klein)}">')
    else:
        inhoud = tegel
    return f'<div class="beeld">{inhoud}</div>'


def datumtekst(item, ref):
    """De regel met datum en bron boven een bericht. Een uitlegstuk is geen nieuws: daar staat dat het achtergrond is."""
    if item["rubriek"] == "Uitleg":
        return "Achtergrond bij het nieuws"
    return datumregel(item["bronnen"], ref)


def impact_html(item):
    if item["rubriek"] == "Uitleg":
        return ""
    niveau, woord = impact(item)
    streepjes = "".join(f'<i class="{"aan" if n < niveau else ""}"></i>' for n in range(3))
    return (f'<span class="impact" title="Impact: hoe belangrijk dit nieuws is volgens de selectie">'
            f'{streepjes}Impact {woord}</span>')


def bronnen_html(item):
    links = ", ".join(f'<a href="{e(veilig(url))}">{e(naam)}</a>' for naam, url in bronlinks(item["bronnen"]))
    n = aantal_bronnen(item)
    return f'Gemeld door {n} {"bron" if n == 1 else "bronnen"}: {links}'


def kaart(item, ref, basis, site_url, groot=False):
    """Een bericht in een editie. De hele kaart is één link naar de pagina van het bericht, zoals bij NOS en nu.nl.

    De kop is de echte link; via CSS (a::after) is de hele kaart aanklikbaar. In de lijst alleen beeld en kop,
    zoals bij NOS; alleen het openingsbericht krijgt op een groot scherm ook de samenvatting.
    """
    stijl = RUBRIEKEN[item["rubriek"]]
    link = f"{basis}artikel/{item['id']}.html"
    n = aantal_bronnen(item)
    kop = "h2" if groot else "h3"
    lede = f'<p class="lede">{e(item["samenvatting"])}</p>' if groot else ""
    waarom = (f'<p class="waarom"><b>{stijl["waarom"]}:</b> {e(item["waarom"])}</p>'
              if groot and item.get("waarom") else "")
    product = PRODUCT.get(bedrijf_van(item))
    productlabel = f'<span class="product">{e(product)}</span>' if product else ""
    return (
        f'<article class="kaart{" groot" if groot else ""}" data-id="{e(item["id"])}" data-rubriek="{stijl["klasse"]}">'
        f'{beeld_html(item, "16 / 9" if groot else "16 / 10")}'
        f'<div class="boven"><span class="rubriek">{e(stijl["knop"])}</span>{productlabel}'
        f'<span>{e(datumtekst(item, ref))}</span>{impact_html(item)}</div>'
        f'<{kop}><a class="kaartlink" href="{e(link)}">{e(item["kop"])}</a></{kop}>'
        f'{lede}{waarom}'
        f'<div class="onder"><span>{leestijd(item)} min lezen · {n} {"bron" if n == 1 else "bronnen"}</span>'
        f'<span class="gelezen" hidden>{VINK}Gelezen</span></div>'
        f'</article>'
    )


def rij_html(item, ref, basis):
    """Een bericht als rij in de lijst die je na het kiezen van een filter ziet. Ook hier is de hele rij een link."""
    stijl = RUBRIEKEN[item["rubriek"]]
    product = PRODUCT.get(bedrijf_van(item))
    n = aantal_bronnen(item)
    return (
        f'<li class="kaart rij" data-id="{e(item["id"])}" data-rubriek="{stijl["klasse"]}" data-merk="{merk_van(item)}">'
        f'{beeld_html(item)}<div class="rijtekst">'
        f'<div class="boven"><span class="rubriek">{e(stijl["knop"])}</span>'
        f'{f"<span class=product>{e(product)}</span>" if product else ""}'
        f'<span>{e(datumtekst(item, ref))}</span></div>'
        f'<h3><a class="kaartlink" href="{basis}artikel/{e(item["id"])}.html">{e(item["kop"])}</a></h3>'
        f'<p>{e(item["samenvatting"])}</p>'
        f'<div class="onder"><span>{leestijd(item)} min lezen · {n} {"bron" if n == 1 else "bronnen"}</span>'
        f'<span class="gelezen" hidden>{VINK}Gelezen</span></div></div></li>'
    )


def kortrij_html(k, ref):
    """Kort nieuws in dezelfde lijst. Zonder eigen pagina: de link gaat naar de bron, en het pijltje zegt dat."""
    product = PRODUCT.get(bedrijf_van(k))
    return (
        f'<li class="kaart rij kortrij" data-rubriek="kort" data-merk="{merk_van(k)}"><div class="rijtekst">'
        f'<div class="boven"><span class="rubriek">Kort nieuws</span>'
        f'{f"<span class=product>{e(product)}</span>" if product else ""}'
        f'<span>{e(datumregel(k["bronnen"], ref))}</span></div>'
        f'<h3><a class="kaartlink" href="{e(veilig(k["bronnen"][0]["url"]))}">{e(k["kop"])}{EXTERN}</a></h3>'
        f'<p>{e(k["zin"])}</p></div></li>'
    )


def kort_html(k, ref):
    eerste = [b for b in k["bronnen"] if b["datum"]]
    tijd = f"{_datum(min(eerste, key=_datum)).astimezone():%H:%M}" if eerste else "nieuw"
    namen = ", ".join(naam for naam, _ in bronlinks(k["bronnen"]))
    # Kort nieuws heeft geen eigen pagina: de link gaat naar de bron. Het pijltje zegt dat vooraf.
    return (
        f'<li><span class="tijd">{e(tijd)}</span><div>'
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


VERGROOTGLAS = ('<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" '
                'stroke-linecap="round" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5"></circle><path d="M20 20l-4.6-4.6"></path></svg>')
MENUSTREEPJES = ('<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" '
                 'stroke-linecap="round" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16"></path></svg>')


def pagina(titel, basis, actief, inhoud, bovenregel, extra="", deel=None, site_url="", versie="", voorpagina=False,
           vindbaar=False):
    """`versie` is de nieuwste editie toen de site gemaakt werd. site.js vergelijkt die met laatste.json.

    `vindbaar`: Google mag de pagina opnemen (zie VINDBAAR in schrijf_site). Andere pagina's krijgen noindex,
    maar Google mag hun links wel volgen naar de artikelen.
    """
    if vindbaar:
        robots = '<meta name="robots" content="index, follow">'
        if site_url and deel:
            robots += f'<link rel="canonical" href="{e(deel["url"])}">'
        if voorpagina and GOOGLE_VERIFICATIE:
            robots += f'<meta name="google-site-verification" content="{e(GOOGLE_VERIFICATIE)}">'
    else:
        robots = '<meta name="robots" content="noindex, follow">'
    huidig = ' aria-current="page"'
    menu = (("Vandaag", "index.html"), ("De week", "week/index.html"), ("Archief", "archief.html"),
            ("Begrippen en tips", "leren.html"), ("Zoeken", "zoeken.html"))
    links = "".join(f'<a href="{basis}{doel}"{huidig if naam == actief else ""}>{naam}</a>' for naam, doel in menu)
    # Op de telefoon, zoals bij NOS: één regel met de naam, Zoeken en Menu. Menu klapt de pagina's uit.
    menulinks = "".join(f'<a href="{basis}{doel}"{huidig if naam == actief else ""}>{naam}</a>'
                        for naam, doel in menu[:4] + (("Zo maken we dit", "zo-maken-we-dit.html"),))
    snel = (f'<div class="snel"><a class="zoeklink" href="{basis}zoeken.html">{VERGROOTGLAS}<span>Zoeken</span></a>'
            f'<details class="menu"><summary>{MENUSTREEPJES}<span>Menu</span></summary>'
            f'<nav aria-label="Menu">{menulinks}</nav></details></div>')
    kenmerken = (f' data-versie="{e(versie)}"' if versie else "") + (" data-voorpagina" if voorpagina else "")
    return (
        '<!doctype html><html lang="nl"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        # Licht of donker volgens de instelling van de telefoon; de balk van de browser kleurt mee.
        '<meta name="color-scheme" content="light dark">'
        '<meta name="theme-color" content="#ffffff" media="(prefers-color-scheme: light)">'
        '<meta name="theme-color" content="#121211" media="(prefers-color-scheme: dark)">'
        f'{robots}'
        # Beveiliging: alleen scripts van de site zelf, geen formulieren, geen ingesloten pagina's.
        # De enige verbinding naar buiten is de telling van GoatCounter.
        '<meta http-equiv="Content-Security-Policy" content="default-src \'self\'; script-src \'self\'; '
        'style-src \'self\' \'unsafe-inline\' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; '
        f'img-src \'self\' https: data:; connect-src \'self\' {TELLER_SERVER}; object-src \'none\'; base-uri \'none\'; form-action \'none\'">'
        f'<title>{e(titel)}</title>{deel_tags(deel, site_url) if deel else ""}'
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        f'<link rel="stylesheet" href="{e(FONTS)}">'
        f'<link rel="icon" href="{basis}favicon.svg" type="image/svg+xml">'
        # Op het beginscherm van je telefoon: icoon en naam, zodat de site opent als een app.
        f'<link rel="manifest" href="{basis}manifest.webmanifest">'
        f'<link rel="apple-touch-icon" href="{basis}icoon-180.png">'
        f'<link rel="stylesheet" href="{basis}stijl.css">{extra}'
        # Al in de kop, want een beeld kan al mislukken voordat site.js geladen is.
        f'<script src="{basis}vroeg.js"></script></head><body{kenmerken}>'
        # Voor wie met het toetsenbord of een schermlezer werkt: meteen naar de inhoud, langs het menu.
        '<a class="overslaan" href="#inhoud">Naar de inhoud</a>'
        f'<section class="utility" aria-label="Over deze pagina"><div class="binnen">{bovenregel}'
        f'<a class="ailabel" href="{basis}zo-maken-we-dit.html">Geschreven met AI</a></div></section>'
        f'<header class="kop"><div class="binnen"><div><a class="merk" href="{basis}index.html">AI-nieuws</a>'
        '<div class="ondertitel">Het belangrijkste AI-nieuws in gewone taal, twee keer per dag</div></div>'
        f'<nav class="hoofdmenu" aria-label="Hoofdmenu">{links}</nav>{snel}</div></header>'
        f'<main id="inhoud">{inhoud}</main>'
        '<footer class="colofon"><div class="binnen">Geschreven door AI (Claude), niet door een redacteur gecontroleerd. '
        'Dat kan fouten opleveren, dus lees bij twijfel de bron. '
        f'Fout gezien? Mail <a href="mailto:{FOUTEN_ADRES}">{FOUTEN_ADRES}</a>. '
        'De beelden komen van de AI-bedrijven zelf of van GitHub. Wat je gelezen hebt, wordt alleen in je eigen browser bewaard. '
        'Bezoeken tellen we anoniem, zonder cookies. '
        f'<a href="{basis}zo-maken-we-dit.html">Zo maken we dit</a> · <a href="{basis}correcties.html">Correcties</a></div></footer>'
        f'<script data-goatcounter="{TELLER}" async src="{basis}count.js"></script>'
        f'<script src="{basis}site.js"></script></body></html>'
    )


def editietijd(ed):
    """'08:00' of '20:00' als de editie rond de vaste tijd klaarstond, anders bijvoorbeeld 'gemaakt om 08:36'."""
    tijd = datetime.fromisoformat(ed["tijd"])
    vast = tijd.replace(hour=8 if ed["moment"] == "ochtend" else 20, minute=0, second=0, microsecond=0)
    if abs(tijd - vast) <= timedelta(minutes=15):
        return f"{vast:%H:%M}"
    return f"gemaakt om {tijd:%H:%M}"


def bovenregel_editie(ed):
    volgende = "20:00" if ed["moment"] == "ochtend" else "08:00"
    return (f'<span>{e(dagtitel(editiedag(ed)).capitalize())} · {e(ed["moment"].capitalize())}editie · '
            f'{editietijd(ed)}</span><span>Volgende editie om {volgende}</span>')


ALGEMENE_BOVENREGEL = '<span>Elke dag om 08:00 en 20:00 een nieuwe editie</span>'
OMSCHRIJVING = "Het belangrijkste AI-nieuws in gewone taal, elke dag om 08:00 en 20:00."


# ---------------------------------------------------------------- pagina's

def editie_html(ed, begrippen, basis, site_url):
    ref = datetime.fromisoformat(ed["tijd"])
    items = ed["items"]
    if not items and not ed["kort"]:
        return '<div class="binnen"><p class="leeg">In deze editie stond niets dat de moeite waard was.</p></div>'

    # De opening: het belangrijkste grote nieuws, liefst met een beeld. Daarnaast het volgende grote bericht.
    groot = sorted([i for i in items if i["rubriek"] == "Het grote nieuws"], key=lambda i: -i["score"])
    rest = sorted(items, key=lambda i: -i["score"])
    lead = next((i for i in groot if i.get("beeld")), groot[0] if groot else (rest[0] if rest else None))
    tweede = next((i for i in groot + rest if lead is not None and i is not lead), None)
    getoond = {id(lead), id(tweede)}

    # De keuzeknoppen, zoals de ronde knoppen bij NOS: Alles, Claude, ChatGPT en de Quiz. Groot genoeg voor je duim.
    # De onderwerpen zijn tussenkopjes in de lijst. Hoeveel berichten je ziet, staat na het tikken boven de lijst.
    alles_bij_elkaar = items + ed["kort"]
    keuzes = [("alles", "Alles", len(alles_bij_elkaar), "alles", "")]
    for code, naam, uitleg, _ in MERKFILTERS:
        aantal = sum(1 for i in alles_bij_elkaar if merk_van(i) == code)
        if aantal and code != "overig":
            keuzes.append((code, naam, aantal, "merk", uitleg))
    if ed.get("quiz"):
        keuzes.append(("quiz", "Quiz", len(ed["quiz"]), "quiz", ""))
    tabbalk = "".join(
        f'<button type="button" data-filter="{k}" data-soort="{soort}" data-titel="{e(n)}" data-uitleg="{e(u)}" '
        f'data-aantal="{a}" aria-label="{e(n)}, {a} {"vragen" if k == "quiz" else "berichten"}" '
        f'aria-pressed="{"true" if k == "alles" else "false"}">{e(n)}</button>'
        for k, n, a, soort, u in keuzes
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
            secties.append(f'<section class="sectie" id="{stijl["klasse"]}"><div class="kopregel"><h2>{e(naam)}</h2></div>'
                           f'<div class="raster">{kaarten}</div></section>')

    # Na het kiezen van een filter: alles wat erbij past in één lijst, ook Kort nieuws.
    rijen = "".join(rij_html(i, ref, basis) for i in items) + "".join(kortrij_html(k, ref) for k in ed["kort"])
    kort = ""
    if ed["kort"]:
        kort = (f'<section class="sectie kortnieuws" id="kort"><div class="kopregel"><h2>Kort nieuws</h2>'
                f'<span>Kleiner nieuws in één zin</span></div>'
                f'<ul>{"".join(kort_html(k, ref) for k in ed["kort"])}</ul></section>')

    voet =f"Gekozen uit {ed['bekeken']} nieuwe berichten uit {ed['aantal_bronnen']} bronnen."
    if ed.get("fouten"):
        voet += f" Niet bereikbaar: {', '.join(ed['fouten'])}."
    aantal = len(items) + len(ed["kort"])
    return (
        f'<div class="editiekop binnen"><div class="label">{e(ed["moment"].capitalize())}editie</div>'
        f'<h1>{e(dagtitel(editiedag(ed)).capitalize())}</h1><p class="intro">{e(ed["intro"])}</p>'
        f'<p class="teller">{aantal} berichten, gekozen uit {ed["bekeken"]} nieuwe berichten'
        f'<span class="alleenbreed"> en geschreven met AI</span>.</p></div>'
        f'<div class="tabbalk" data-totaal="{len(items)}" data-ids="{e(",".join(i["id"] for i in items))}"><div class="binnen">'
        f'<div class="tabs" role="group" aria-label="Kies wat je wilt zien">{tabbalk}</div>'
        f'<div class="voortgang"><span class="voortgangtekst">0 van {len(items)} gelezen</span>'
        f'<div class="balk" role="progressbar" aria-label="Hoeveel berichten je hebt gelezen" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"><div></div></div></div>'
        f'</div></div>'
        f'<div class="binnen editie">'
        f'<div class="klaar" hidden>{VINK}<span>Je hebt alles van deze editie gelezen. De volgende verschijnt om '
        f'{"20:00" if ed["moment"] == "ochtend" else "08:00"}.</span></div>'
        f'<div id="alles">{opening}{probeer}{"".join(secties)}</div>'
        f'<section id="gefilterd" hidden aria-live="polite"><div class="filterstand"><p>Je ziet: <b class="filternaam"></b>'
        f' · <span class="filteraantal"></span></p>'
        f'<button type="button" class="knop licht" data-kies="alles">✕ Toon alles</button></div>'
        f'<p class="filteruitleg"></p><ol class="lijst">{rijen}</ol></section>'
        f'{kort}{quiz_html(ed.get("quiz"), ed, site_url)}'
        f'<p class="editievoet">{e(voet)}</p></div>'
    )


BYLINE = "Geschreven met AI (Claude) op basis van de bronnen hieronder, niet door een redacteur gecontroleerd"
# Een uitlegstuk gebruikt ook algemene kennis; het nieuws uit de bronnen is het voorbeeld.
BYLINE_UITLEG = ("Uitleg geschreven met AI (Claude), met het nieuws uit de bronnen hieronder als voorbeeld, "
                 "niet door een redacteur gecontroleerd")


def artikel_html(item, ed, alle, basis, site_url):
    stijl = RUBRIEKEN[item["rubriek"]]
    ref = datetime.fromisoformat(ed["tijd"])
    onderwerpen = item.get("onderwerpen", [])
    chips = "".join(f'<a class="chip" href="{basis}onderwerp/{slug(o)}.html">{e(o)}</a>' for o in onderwerpen)

    # Lees ook: 3 tot 5 berichten. Eerst over hetzelfde onderwerp (het nieuwste eerst), dan aangevuld uit deze
    # editie, en is dat nog geen 3, uit de edities ervoor. Lezers die via zo'n link binnenkomen, lezen het langst (Pew 2016).
    verwant, gezien = [], {item["id"]}

    def erbij(ander, ander_ed):
        if ander["id"] not in gezien and len(verwant) < 5:
            verwant.append((ander, ander_ed))
            gezien.add(ander["id"])

    zelfde = [(a, a_ed) for a, a_ed in alle if set(onderwerpen) & set(a.get("onderwerpen", []))]
    for ander, ander_ed in sorted(zelfde, key=lambda paar: paar[1]["tijd"], reverse=True):
        erbij(ander, ander_ed)
    for ander in sorted(ed["items"], key=lambda i: -i["score"]):
        erbij(ander, ed)
    for ander, ander_ed in sorted(alle, key=lambda paar: paar[1]["tijd"], reverse=True):
        if len(verwant) >= 3:
            break
        erbij(ander, ander_ed)
    verwant_html = ""
    if verwant:
        rijen = "".join(
            f'<li data-id="{e(a["id"])}"><a href="{basis}artikel/{e(a["id"])}.html">{beeld_html(a, "16 / 10")}'
            f'<span><span class="meta">{e(dagtitel(editiedag(a_ed)).capitalize())} · {e(RUBRIEKEN[a["rubriek"]]["knop"])}</span>'
            f'<b>{e(a["kop"])}</b></span></a></li>'
            for a, a_ed in verwant
        )
        verwant_html = f'<section class="verwant"><h2>Lees ook</h2><ul>{rijen}</ul></section>'
    waarom = f'<p class="waarom"><b>{stijl["waarom"]}:</b> {e(item["waarom"])}</p>' if item.get("waarom") else ""
    # Het artikel zelf: blokken met een tussenkop. Oudere berichten hebben dat nog niet.
    lijf = "".join(
        (f'<h2>{e(blok["tussenkop"])}</h2>' if blok["tussenkop"] else "") + "".join(f"<p>{e(a)}</p>" for a in blok["alineas"])
        for blok in item.get("artikel", [])
    )
    return (
        f'<div class="artikel binnen" data-artikel="{e(item["id"])}">'
        f'<nav class="kruimel" aria-label="Waar je bent"><a href="{basis}edities/{e(ed["id"])}.html">{e(editietitel(ed))}</a>'
        f' › <a href="{basis}edities/{e(ed["id"])}.html#{stijl["klasse"]}">{e(stijl["knop"])}</a></nav>'
        f'{beeld_html(item, "16 / 9")}'
        f'<div class="boven"><span class="rubriek">{e(stijl["knop"])}</span>'
        f'<span>{e(datumtekst(item, ref))}</span><span>{leestijd(item)} min lezen</span>{impact_html(item)}</div>'
        f'<h1>{e(item["kop"])}</h1>'
        f'<p class="byline">{BYLINE_UITLEG if item["rubriek"] == "Uitleg" else BYLINE} · '
        f'<a href="{basis}zo-maken-we-dit.html">Zo maken we dit</a></p>'
        f'<p class="lede">{e(item["samenvatting"])}</p>'
        f'{waarom}'
        f'<div class="uitlegblok"><div class="label">Even uitgelegd</div><p>{e(item["uitleg"])}</p></div>'
        f'{f"<div class=lijf>{lijf}</div>" if lijf else ""}'
        f'{correcties_html(item)}'
        f'<p class="bronnen">{bronnen_html(item)}</p>'
        f'<p class="acties"><a class="knop" href="{e(veilig(item["bronnen"][0]["url"]))}">Lees de bron{EXTERN}</a>'
        f'<a class="knop licht" href="{e(deel_link(item, site_url))}" target="_blank" rel="noopener">Deel via WhatsApp</a>'
        f'<a class="knop licht" href="{e(fout_link(item, site_url))}">Klopt er iets niet?</a></p>'
        f'{f"<p class=chips>Onderwerpen: {chips}</p>" if chips else ""}'
        f'{verwant_html}'
        f'</div>'
    )


def correctiepagina_html(edities, basis):
    """Alle verbeteringen, de nieuwste eerst. Een artikel linkt naar zijn pagina, een kort bericht naar de bron."""
    lijst = []
    for ed in edities:
        for item in ed["items"]:
            for c in item.get("correcties", []):
                lijst.append((c, item["kop"], f'{basis}artikel/{item["id"]}.html'))
        for kort in ed.get("kort", []):
            for c in kort.get("correcties", []):
                lijst.append((c, kort["kop"], veilig(kort["bronnen"][0]["url"]) if kort.get("bronnen") else "#"))
    lijst.sort(key=lambda rij: rij[0]["datum"], reverse=True)
    rijen = "".join(
        f'<li><span class="meta">{e(dagtitel(date.fromisoformat(c["datum"])).capitalize())}</span>'
        f'<a href="{e(adres)}">{e(kop)}</a><p>{e(c["tekst"])}</p></li>'
        for c, kop, adres in lijst
    )
    return (
        '<div class="editiekop binnen"><div class="label">Correcties</div><h1>Wat we verbeterd hebben</h1>'
        '<p class="intro">AI-nieuws wordt met AI geschreven en niet door een redacteur gecontroleerd. Daardoor kan er '
        'een fout in een bericht staan. Zie je er een? Klik onder het artikel op "Klopt er iets niet?" of mail naar '
        f'<a href="mailto:{FOUTEN_ADRES}">{FOUTEN_ADRES}</a>. Klopt de melding, dan verbeteren we het bericht en zetten '
        'we eronder wat er veranderd is. We halen nooit stilletjes iets weg.</p></div>'
        f'<div class="binnen">{f"<ol class=correctielijst>{rijen}</ol>" if rijen else "<p class=leeg>Er zijn nog geen correcties.</p>"}</div>'
    )


def onderwerp_html(naam, lijst, basis, site_url):
    kaarten = "".join(kaart(item, datetime.fromisoformat(ed["tijd"]), basis, site_url) for item, ed in lijst)
    return (f'<div class="editiekop binnen"><div class="label">Onderwerp</div><h1>{e(naam)}</h1>'
            f'<p class="teller">{len(lijst)} {"bericht" if len(lijst) == 1 else "berichten"}, het nieuwste eerst.</p></div>'
            # Een kop die alleen een schermlezer voorleest, zodat de koppen netjes van h1 naar h3 gaan.
            f'<div class="binnen"><h2 class="sr">Berichten over {e(naam)}</h2><div class="raster">{kaarten}</div></div>')


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
            f'<div class="binnen"><ol class="weeklijst">{"".join(rijen)}</ol></div>')


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
            f'<div class="binnen archief">{weekblok}<section class="sectie"><div class="kopregel"><h2>Edities</h2></div>'
            f'{"".join(dagen) or "<p class=leeg>Nog geen edities.</p>"}</section></div>')


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
        '<div class="binnen leren">'
        f'<section class="sectie"><div class="kopregel"><h2>Begrippen</h2><span>{len(termen)} begrippen</span></div>'
        '<label class="zoekveld">Zoek een begrip <input id="begripzoek" type="search" autocomplete="off"></label>'
        f'<dl class="begrippen">{lijst}</dl></section>'
        f'<section class="sectie"><div class="kopregel"><h2>Probeer dit</h2></div>{"".join(tips) or "<p class=leeg>Nog geen tips.</p>"}</section>'
        '</div>'
    )


def zoeken_html():
    return (
        '<div class="editiekop binnen"><h1>Zoeken</h1><p class="intro">Zoek in alle berichten van alle edities.</p></div>'
        '<div class="binnen zoeken"><label class="zoekveld">Zoekwoorden <input id="zoekveld" type="search" '
        'autocomplete="off" placeholder="Bijvoorbeeld Claude Code of Mistral"></label>'
        '<p id="zoekuitleg" class="teller">Typ minstens twee letters.</p><ol id="zoekresultaten" class="zoekresultaten"></ol></div>'
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
        '<div class="binnen werkwijze">'
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
        '<section class="sectie"><div class="kopregel"><h2>Fouten en correcties</h2></div>'
        '<p>Claude kan fouten maken, en er kijkt geen redacteur mee. Zie je een fout? Klik onder het artikel op '
        f'"Klopt er iets niet?" of mail naar <a href="mailto:{FOUTEN_ADRES}">{FOUTEN_ADRES}</a>. We bekijken elke melding. '
        'Klopt hij, dan verbeteren we het bericht en zetten we eronder wat er veranderd is. Alle verbeteringen staan op '
        '<a href="correcties.html">Correcties</a>. Je mail gebruiken we alleen om de melding te bekijken en je eventueel '
        'te antwoorden.</p></section>'
        '<section class="sectie"><div class="kopregel"><h2>Beelden en privacy</h2></div>'
        '<p>De beelden komen alleen van de AI-bedrijven zelf (het plaatje dat ze opgeven voor als je een link deelt) '
        'of van GitHub (de kaart die GitHub voor elk project maakt). Foto’s van nieuwssites en persbureaus '
        'gebruiken we niet. Heeft een bericht geen beeld, dan staat er een zwart blok met de naam van de bron.</p>'
        '<p>De site zet geen cookies en houdt niet bij wie wat leest. Wat je gelezen hebt en welke AI je kiest, '
        'staat alleen in je eigen browser.</p>'
        '<p>We tellen wel hoe vaak elke pagina bekeken wordt, met GoatCounter. Dat werkt zonder cookies en zonder '
        'bij te houden wie je bent. Zo zien we welke berichten gelezen worden, waar bezoekers vandaan komen '
        '(bijvoorbeeld WhatsApp of Google) en of ze op een telefoon of een computer lezen.</p></section>'
        '</div>'
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
    for bestand in ("site.js", "vroeg.js", "count.js", "favicon.svg"):
        (doel / bestand).write_text((bron / bestand).read_text(encoding="utf-8"), encoding="utf-8")
    for bestand in ("deel.png", "icoon-180.png", "icoon-192.png", "icoon-512.png", "icoon-512-rond.png"):
        (doel / bestand).write_bytes((bron / bestand).read_bytes())
    # Zo kun je de site op het beginscherm van je telefoon zetten, met naam en icoon. Bewust zonder
    # service worker: die bewaart pagina's, en dan zie je mogelijk niet de nieuwste editie.
    (doel / "manifest.webmanifest").write_text(json.dumps({
        "name": "AI-nieuws", "short_name": "AI-nieuws", "description": OMSCHRIJVING, "lang": "nl",
        "start_url": "./", "scope": "./", "display": "standalone",
        "background_color": "#ffffff", "theme_color": "#141414",
        "icons": [{"src": "icoon-192.png", "sizes": "192x192", "type": "image/png"},
                  {"src": "icoon-512.png", "sizes": "512x512", "type": "image/png"},
                  {"src": "icoon-512-rond.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"}],
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    edities = sorted(edities, key=lambda ed: ed["tijd"])
    for ed in edities:
        geef_ids(ed)
    alle = [(item, ed) for ed in edities for item in ed["items"]]
    index = {item["id"]: (item, ed) for item, ed in alle}
    # De servers van GitHub en de browser geven soms nog even een oude kopie, ook na F5. Elke pagina weet daarom
    # welke editie de nieuwste was toen hij gemaakt werd, en laatste.json zegt welke dat nu is (zie site.js).
    versie = edities[-1]["id"] if edities else ""
    (doel / "laatste.json").write_text(
        json.dumps({"id": versie, "titel": editietitel(edities[-1]) if edities else ""}, ensure_ascii=False),
        encoding="utf-8")

    vindbaar = []  # (adres, laatst bijgewerkt) van de pagina's die Google mag opnemen, voor sitemap.xml

    def schrijf(pad, titel, basis, actief, inhoud, bovenregel=ALGEMENE_BOVENREGEL, deel=None, extra="", bijgewerkt=None):
        # Wat een app toont bij een gedeelde link. Zonder eigen tekst of beeld: de omschrijving en het plaatje van de site.
        deel = {"titel": titel, "tekst": OMSCHRIJVING, "soort": "website", **(deel or {}),
                "url": site_url + ("" if pad == "index.html" else pad)}
        # Google mag alleen de voorpagina, de artikelen (ook de uitlegstukken) en Zo maken we dit opnemen.
        # Edities, onderwerpen, weken en het archief herhalen dezelfde berichten in lijstjes; die blijven
        # buiten Google, zodat de site niet lijkt op een stapel automatisch gemaakte pagina's.
        mag = pad in ("index.html", "zo-maken-we-dit.html") or pad.startswith("artikel/")
        if mag and site_url:
            vindbaar.append((deel["url"], bijgewerkt))
        (doel / pad).write_text(pagina(titel, basis, actief, inhoud, bovenregel, extra=extra, deel=deel, site_url=site_url,
                                       versie=versie, voorpagina=pad == "index.html", vindbaar=mag),
                                encoding="utf-8")

    for ed in edities:
        beste = next((i for i in sorted(ed["items"], key=lambda i: -i["score"]) if i.get("beeld")), None)
        schrijf(f"edities/{ed['id']}.html", f"AI-nieuws, {editietitel(ed)}", "../", None,
                editie_html(ed, begrippen, "../", site_url), bovenregel_editie(ed),
                {"tekst": ed.get("intro") or OMSCHRIJVING, "beeld": beste["beeld"] if beste else None})
        tijd = datetime.fromisoformat(ed["tijd"]).astimezone().isoformat()
        for item in ed["items"]:
            schrijf(f"artikel/{item['id']}.html", f"{item['kop']} | AI-nieuws", "../", None,
                    artikel_html(item, ed, alle, "../", site_url), bovenregel_editie(ed),
                    {"titel": item["kop"], "tekst": item["samenvatting"], "beeld": item.get("beeld"),
                     "soort": "article", "tijd": tijd},
                    extra=artikel_gegevens(item, tijd, site_url) if site_url else "", bijgewerkt=tijd)
    if edities:
        laatste = edities[-1]
        schrijf("index.html", "AI-nieuws", "", "Vandaag", editie_html(laatste, begrippen, "", site_url), bovenregel_editie(laatste),
                bijgewerkt=datetime.fromisoformat(laatste["tijd"]).astimezone().isoformat())
    else:
        schrijf("index.html", "AI-nieuws", "", "Vandaag", '<div class="binnen"><p class="leeg">De eerste editie verschijnt om 08:00 of 20:00.</p></div>')

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
    schrijf("correcties.html", "Correcties | AI-nieuws", "", None, correctiepagina_html(edities, ""),
            deel={"tekst": "Wat AI-nieuws verbeterd heeft na een melding van een lezer, en hoe je een fout meldt."})
    schrijf("zo-maken-we-dit.html", "Zo maken we dit | AI-nieuws", "", None, werkwijze_html(bronnen),
            deel={"tekst": "Hoe AI-nieuws met AI het belangrijkste AI-nieuws kiest en schrijft, en waar het nieuws vandaan komt."})
    zoek = [
        {"id": item["id"], "kop": item["kop"], "samenvatting": item["samenvatting"],
         "rubriek": RUBRIEKEN[item["rubriek"]]["knop"], "datum": dagtitel(editiedag(ed)).capitalize(),
         "onderwerpen": item.get("onderwerpen", [])}
        for item, ed in reversed(alle)
    ]
    (doel / "zoek.json").write_text(json.dumps(zoek, ensure_ascii=False), encoding="utf-8")

    # Voor Google: de lijst met vindbare pagina's, en waar die lijst staat.
    if site_url:
        regels = "".join(f"<url><loc>{e(adres)}</loc>{f'<lastmod>{tijd}</lastmod>' if tijd else ''}</url>"
                         for adres, tijd in vindbaar)
        (doel / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n'
                                          f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{regels}</urlset>\n',
                                          encoding="utf-8")
        (doel / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {site_url}sitemap.xml\n", encoding="utf-8")
    return doel / "index.html"
