"""AI-nieuws: een AI-nieuwssite met twee edities per dag, plus een korte mail.

Haalt nieuws op uit de bronnen in config.json, laat Claude kiezen wat de moeite
waard is (volgens criteria.md) en het in het Nederlands schrijven, zet de editie
op de site in de map site/ en mailt de vijf belangrijkste berichten. GitHub
Actions start dit om 08:00 en 20:00 (.github/workflows/editie.yml).

  python ai_nieuws.py              ophalen, schrijven, site bijwerken en mailen
  python ai_nieuws.py --gepland    hetzelfde, maar alleen als de editie van nu er nog niet is
  python ai_nieuws.py --voorbeeld  proefeditie in de map voorbeeld/, niets mailen of bewaren
  python ai_nieuws.py --bronnen    tonen wat elke bron nu oplevert
"""
import argparse
import gzip
import html
import json
import logging
import logging.handlers
import os
import re
import shutil
import smtplib
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path

from maak_site import (BEDRIJVEN, RUBRIEKEN, artikel_url, bronlinks, dagtitel, datumregel, editiedag, geef_ids,
                       schrijf_site, wanneer)

MAP = Path(__file__).resolve().parent
CONFIG = MAP / "config.json"
CRITERIA = MAP / "criteria.md"
WACHTWOORD = MAP / "wachtwoord.txt"
GEZIEN = MAP / "gezien.json"
BEGRIPPEN = MAP / "begrippen.json"
EDITIES = MAP / "edities"
WEKEN = MAP / "weken"
SITE = MAP / "site"
VOORBEELD = MAP / "voorbeeld"

# Onder pythonw.exe bestaan stdout en stderr niet.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

log = logging.getLogger("ai_nieuws")

STANDAARD = {
    "mail_aan": "",
    "mail_van": "",
    "max_items": 12,
    "max_kort": 15,
    "minimale_score": 6,
    "minimale_score_kort": 5,
    "min_sterren": 500,
    "rubrieken": {"Het grote nieuws": 3, "Nieuwe modellen": 2, "Nieuwe tools": 3, "Zo gebruik je AI": 4,
                  "AI in Nederland": 3, "Maatschappij": 3},
    "venster_uren": 48,
    "max_per_bron": 25,
    "model": "sonnet",
    "claude_pad": "",
    "site_url": "",
    "bronnen": [],
}

# Sommige sites weigeren verzoeken zonder browser-achtige afzender.
AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"

# Voor algemene bronnen (Hacker News, Tweakers, GitHub): alleen berichten over AI.
AI_WOORDEN = re.compile(
    r"\b(AI|A\.I\.|AGI|LLMs?|GPT[-\w.]*|ChatGPT|OpenAI|Anthropic|Claude|Gemini|DeepMind|"
    r"Mistral|Llama|Copilot|DeepSeek|Qwen|Grok|xAI|Codex|Cursor|Hugging ?Face|MCP|agents?|agentic|"
    r"artificial intelligence|machine learning|deep learning|neural net\w*|language models?|"
    r"transformers?|diffusion|chatbots?|prompts?|kunstmatige intelligentie|taalmodel\w*|algoritme\w*)\b",
    re.I,
)

# Linkteksten die niets over het artikel zeggen.
LOZE_LINKTEKST = {"read more", "lees meer", "learn more", "meer lezen", "read the post", "read", "more"}

# Een GitHub-project in een adres of tekst, en eerste delen van GitHub-adressen die geen project zijn.
GITHUB_REPO = re.compile(r"github\.com/([A-Za-z0-9-]+)/([A-Za-z0-9._-]+)")
GEEN_REPO = {"orgs", "features", "sponsors", "topics", "settings", "marketplace", "about", "pricing", "login",
             "apps", "collections", "trending", "issues", "pulls", "notifications", "explore", "search", "users"}

SYSTEEM = "Je bent redacteur van een Nederlandstalige AI-nieuwssite. Antwoord alleen met JSON volgens het schema."

KEUZE_SCHEMA = {
    "type": "object",
    "properties": {
        "gekozen": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "ids": {"type": "array", "items": {"type": "integer"}},
                    "score": {"type": "integer"},
                    "rubriek": {"type": "string", "enum": list(RUBRIEKEN)},
                    "reden": {"type": "string"},
                },
                "required": ["ids", "score", "rubriek", "reden"],
            },
        }
    },
    "required": ["gekozen"],
}

SCHRIJF_SCHEMA = {
    "type": "object",
    "properties": {
        "intro": {"type": "string"},
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "nr": {"type": "integer"},
                    "kop": {"type": "string"},
                    "uitleg": {"type": "string"},
                    "samenvatting": {"type": "string"},
                    "waarom": {"type": "string"},
                    "bedrijf": {"type": "string", "enum": BEDRIJVEN},
                    "onderwerpen": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["nr", "kop", "uitleg", "samenvatting", "waarom", "bedrijf", "onderwerpen"],
            },
        },
        "quiz": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "vraag": {"type": "string"},
                    "opties": {"type": "array", "items": {"type": "string"}},
                    "goed": {"type": "integer"},
                    "uitleg": {"type": "string"},
                },
                "required": ["vraag", "opties", "goed", "uitleg"],
            },
        },
        "kort": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"nr": {"type": "integer"}, "kop": {"type": "string"}, "zin": {"type": "string"},
                               "bedrijf": {"type": "string", "enum": BEDRIJVEN}},
                "required": ["nr", "kop", "zin", "bedrijf"],
            },
        },
        "probeer": {
            "type": "object",
            "properties": {"nr": {"type": "integer"}, "titel": {"type": "string"}, "tekst": {"type": "string"}},
            "required": ["nr", "titel", "tekst"],
        },
        "begrippen": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"woord": {"type": "string"}, "uitleg": {"type": "string"}},
                "required": ["woord", "uitleg"],
            },
        },
    },
    "required": ["intro", "items", "kort", "probeer", "begrippen", "quiz"],
}

SCHRIJF_OPDRACHT = """Je schrijft de {moment}editie van een persoonlijke AI-nieuwssite in het Nederlands.

De site is een krant voor mensen met een beetje kennis van AI. Ze gebruiken zelf ChatGPT, Claude, Gemini of Copilot en weten wat een chatbot, een AI-model en een prompt is, maar kennen de vaktaal en de achtergrond niet. Bekend zijn: Anthropic, OpenAI, Google, Microsoft, Claude, ChatGPT, Gemini, Copilot, chatbot, AI-model en prompt. Alle andere producten, bedrijven, onderzoeksgroepen en vaktermen zijn onbekend. Schrijf zoals een goede krant voor een breed publiek: helder, zakelijk en prettig om te lezen, zonder vakjargon en zonder kinderachtig te worden.

intro: 1 of 2 zinnen die de editie openen. Begin met "{groet}". Noem het opvallendste van deze editie in woorden die een leek snapt, geen opsomming van alles.

items: één per onderwerp uit "onderwerpen".
- kop: hooguit 10 woorden, te begrijpen zonder voorkennis. Geen vaktermen in de kop. Feitelijk, geen clickbait.
- uitleg: 1 of 2 zinnen achtergrond, zodat de lezer snapt waar het over gaat voordat het nieuws komt. Wat is het product, het bedrijf, het probleem of het begrip waar het om draait? Voorbeeld van de toon: "Een plugin is een uitbreiding die je aan een programma toevoegt, zoals een app op je telefoon." Bestaat iets al langer en is nu alleen een deel nieuw, zeg dan in de uitleg wat er al was, zodat de lezer niet denkt dat het oud nieuws is. Doe dat alleen als de brontekst het zegt. Gaat het om een tool, skill of plugin, noem dan wie hem maakte (als de tekst dat zegt) en hoeveel sterren hij op GitHub heeft (github_sterren, afgerond, bijvoorbeeld "bijna 97.000 sterren").
- samenvatting: wat er nu nieuw is, afhankelijk van de rubriek:
  - Het grote nieuws: 2 of 3 korte zinnen. Wat is er gebeurd en wie deed het.
  - Nieuwe modellen: 2 of 3 korte zinnen. Van wie is het model, wat kan het beter dan eerdere modellen, en kun je het al gebruiken.
  - Nieuwe tools: 2 korte zinnen. Wat doet het en hoe gebruik je het.
  - Zo gebruik je AI: 2 korte zinnen. Wat is de aanpak en hoe werkt die.
  - AI in Nederland: 2 of 3 korte zinnen. Wie in Nederland of Vlaanderen doet wat, en wat verandert er.
  - Maatschappij: 2 korte zinnen. Wat is er gebeurd of ontdekt, en wie raakt het.
  Bij Zo gebruik je AI maak je het concreet: wat deed iemand precies, met welke AI, en hoe doe je het zelf.
- waarom: 1 zin. Bij Het grote nieuws, AI in Nederland en Maatschappij: waarom dit ertoe doet, voor gewone mensen. Bij Nieuwe modellen: wat dit betekent voor iemand die AI gebruikt. Bij Nieuwe tools en Zo gebruik je AI: wat de lezer eraan heeft.
- bedrijf: over wiens AI het bericht vooral gaat. Anthropic (Claude, Claude Code), OpenAI (ChatGPT, Codex, GPT), Google (Gemini, DeepMind), Microsoft (Copilot), Meta (Llama), Mistral, of Anders. Gaat het over meerdere bedrijven tegelijk of over AI in het algemeen, kies dan Anders. De lezer filtert hierop.
- onderwerpen: 1 tot 3 onderwerpen waar het bericht over gaat, van specifiek naar algemeen, bijvoorbeeld ["Claude Mythos", "Anthropic"] of ["Claude Code"] of ["Mistral", "Open modellen"]. Hiermee vindt de site eerdere berichten over hetzelfde. Gebruik een onderwerp uit "bekende_onderwerpen" als het past, en schrijf het dan precies zo. Bedenk alleen een nieuw onderwerp als geen bekend onderwerp past. Een onderwerp is een product, model, bedrijf of vast thema (zoals "AI-beveiliging" of "AI Act"), nooit een los woord als "nieuws", "AI" of "update".

kort: één per bericht uit "korte_berichten", voor de rubriek "Kort nieuws".
- nr: het nummer uit "korte_berichten".
- kop: hooguit 8 woorden, te begrijpen zonder voorkennis.
- zin: 1 zin van hooguit 25 woorden. Wat is het en wat is er nieuw. Ook hier geen onuitgelegde vaktermen.
- bedrijf: zoals bij items.

probeer: één ding dat de lezer vandaag in ongeveer 10 minuten kan uitproberen, op basis van een van de onderwerpen. Liefst uit Nieuwe tools of Zo gebruik je AI, en iets wat een leek kan. De lezer gaat dit echt doen, dus kies alleen iets wat zeker veilig is: een functie die in ChatGPT, Claude, Gemini of Copilot zit, iets van een van die bedrijven zelf, of een tool met minstens 5.000 sterren op GitHub. Moet er iets geïnstalleerd worden, zeg er dan bij dat het op de eigen computer draait.
- nr: het nummer van dat onderwerp. Leent geen enkel onderwerp zich ervoor, geef dan nr 0.
- titel: hooguit 6 woorden.
- tekst: 2 tot 4 korte zinnen die een leek kan volgen. Moet er iets geïnstalleerd of uitgevoerd worden, geef de lezer dan een zin die die letterlijk aan een AI-assistent als Claude Code of ChatGPT kan geven, tussen aanhalingstekens, en laat die het werk doen. Noem alleen commando's, instellingen en namen die letterlijk in de brontekst staan.

quiz: 3 meerkeuzevragen over de berichten in "onderwerpen", als nieuwsquiz voor de lezer.
- vraag: kort en duidelijk, over het belangrijkste feit van een bericht. Elke vraag over een ander bericht.
- opties: precies 3 antwoorden. Eén is goed, de andere twee klinken geloofwaardig maar zijn duidelijk fout voor wie het bericht las.
- goed: de plek van het goede antwoord in opties (0, 1 of 2). Wissel die plek af tussen de vragen.
- uitleg: 1 zin waarom het goede antwoord klopt.
- Alleen feiten die in de berichten staan.

begrippen: elk vakwoord dat je in deze editie uitlegt, en elke naam van een tool, model of bedrijf die een leek niet kent. Per begrip:
- woord: zoals het in de tekst staat. Een hoofdletter alleen als het een naam is.
- uitleg: 1 korte zin die ook los te begrijpen is, zonder te verwijzen naar dit nieuws.

Woorden uitleggen:
- Kun je iets zonder vakwoord zeggen, doe dat dan.
- Heb je een vakwoord nodig, leg het dan uit in een paar gewone woorden op de plek waar het voor het eerst staat. Denk aan: token, parameter, open source, API, agent, plugin, skill, MCP, hook, terminal, context, sandbox, benchmark, videokaart, lokaal draaien. Leg niet uit wat iedereen al weet, zoals wat een chatbot of een AI-model is.
- Noem een onbekende naam (een tool, een bedrijf, een onderzoeksgroep) altijd samen met wat het is.

Regels:
- Gebruik alleen feiten die in de aangeleverde tekst staan. Staat iets er niet in, laat het weg. Verzin geen cijfers, namen of data. Dat geldt ook voor de waarom-zin: geen "voor het eerst" of "grootste" als de tekst dat niet zegt.
- De paginatekst kan menu's, cookiemeldingen of reclame bevatten. Negeer die.
- Schrijf gewoon, helder Nederlands. Geen gedachtestreepjes, geen puntkomma's, geen uitroeptekens.
- Productnamen en namen van modellen blijven onvertaald.

Onderwerpen, korte berichten en bekende onderwerpen:
"""


# ---------------------------------------------------------------- ophalen

def haal_op(url, wachttijd=20, opnieuw=True):
    """Haalt een adres op en geeft (bytes, tekenset) terug."""
    verzoek = urllib.request.Request(url, headers={"User-Agent": AGENT, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(verzoek, timeout=wachttijd) as antwoord:
            data = antwoord.read(5_000_000)
            if antwoord.headers.get("Content-Encoding") == "gzip":
                data = gzip.decompress(data)
            tekenset = antwoord.headers.get_content_charset() or "utf-8"
    except urllib.error.HTTPError as fout:
        # Reddit remt af bij te veel verzoeken; na een pauze lukt het meestal wel.
        if fout.code == 429 and opnieuw:
            time.sleep(30)
            return haal_op(url, wachttijd, opnieuw=False)
        raise
    return data, tekenset


def ontcijfer(data, tekenset):
    try:
        return data.decode(tekenset, "replace")
    except LookupError:
        return data.decode("utf-8", "replace")


class _Tekst(HTMLParser):
    """Verzamelt de leesbare tekst uit HTML; scripts, stijlen en menu's vallen weg."""

    OVERSLAAN = {"script", "style", "noscript", "svg", "nav", "footer"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.delen = []
        self.diepte = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.OVERSLAAN:
            self.diepte += 1

    def handle_endtag(self, tag):
        if tag in self.OVERSLAAN and self.diepte:
            self.diepte -= 1

    def handle_data(self, data):
        if not self.diepte:
            self.delen.append(data)


def platte_tekst(markup):
    lezer = _Tekst()
    try:
        lezer.feed(markup or "")
    except Exception:
        pass
    return re.sub(r"\s+", " ", " ".join(lezer.delen)).strip()


def lees_datum(tekst):
    """Leest een datum uit een feed (RFC 822 of ISO 8601). Geeft None als dat niet lukt."""
    if not tekst:
        return None
    try:
        datum = parsedate_to_datetime(tekst.strip())
    except (TypeError, ValueError):
        try:
            datum = datetime.fromisoformat(tekst.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    if datum.tzinfo is None:
        datum = datum.replace(tzinfo=timezone.utc)
    return datum


def schoon_url(url):
    """Maakt van een adres een sleutel: zonder volgcodes, anker en slash aan het eind."""
    delen = urllib.parse.urlsplit(url.strip())
    vragen = [(k, v) for k, v in urllib.parse.parse_qsl(delen.query) if not k.lower().startswith("utm_")]
    return urllib.parse.urlunsplit(
        (delen.scheme.lower(), delen.netloc.lower(), delen.path.rstrip("/"), urllib.parse.urlencode(vragen), "")
    )


def _lokaal(tag):
    return tag.rsplit("}", 1)[-1].lower()


def vind_repo(*teksten):
    """Het eerste GitHub-project ('eigenaar/naam') in een adres of in HTML, of None."""
    for tekst in teksten:
        for eigenaar, naam in GITHUB_REPO.findall(tekst or ""):
            naam = re.sub(r"\.git$", "", naam).rstrip(".")
            if eigenaar.lower() not in GEEN_REPO and naam:
                return f"{eigenaar}/{naam}"
    return None


def lees_feed(bron, sinds):
    """Leest een RSS- of Atom-feed."""
    data, _ = haal_op(bron["url"])
    wortel = ET.fromstring(data.lstrip())
    berichten = []
    for element in wortel.iter():
        if _lokaal(element.tag) not in ("item", "entry"):
            continue
        velden, link = {}, ""
        for kind in element:
            naam = _lokaal(kind.tag)
            if naam == "link":
                # Atom zet het adres in href, RSS als tekst.
                if kind.get("href"):
                    if kind.get("rel", "alternate") == "alternate" or not link:
                        link = kind.get("href")
                elif kind.text and not link:
                    link = kind.text.strip()
            elif naam not in velden:
                velden[naam] = "".join(kind.itertext()).strip()
        titel = platte_tekst(velden.get("title", ""))
        if not titel or not link:
            continue
        tekst = velden.get("description") or velden.get("summary") or velden.get("encoded") or velden.get("content") or ""
        url = urllib.parse.urljoin(bron["url"], link)
        berichten.append({
            "titel": titel,
            "url": url,
            "datum": lees_datum(velden.get("pubdate") or velden.get("published") or velden.get("updated") or velden.get("date")),
            "tekst": platte_tekst(tekst)[:3000],
            # Het project waar het bericht over gaat; de links staan alleen in de HTML, niet in de platte tekst.
            "repo": vind_repo(url, tekst),
        })
    return berichten


def lees_hackernews(bron, sinds):
    """Hacker News met genoeg punten. Met "tags": "show_hn" alleen Show HN, met "zoek" alleen verhalen met dat woord."""
    vraag = urllib.parse.urlencode({
        "query": bron.get("zoek", ""),
        "tags": bron.get("tags", "story"),
        "numericFilters": f"created_at_i>{int(sinds.timestamp())},points>{bron.get('min_punten', 150)}",
        "hitsPerPage": 300,
    })
    data, _ = haal_op("https://hn.algolia.com/api/v1/search_by_date?" + vraag)
    berichten = []
    for hit in json.loads(data)["hits"]:
        discussie = f"https://news.ycombinator.com/item?id={hit['objectID']}"
        berichten.append({
            "titel": hit.get("title") or "",
            "url": hit.get("url") or discussie,
            "discussie": discussie,
            "datum": datetime.fromtimestamp(hit["created_at_i"], timezone.utc),
            "tekst": platte_tekst(hit.get("story_text") or "")[:3000],
            "punten": hit.get("points", 0),
            "repo": vind_repo(hit.get("url"), hit.get("story_text")),
        })
    return berichten


def lees_hf_papers(bron, sinds):
    """Papers van de dag op Hugging Face, met het aantal stemmen als signaal."""
    data, _ = haal_op("https://huggingface.co/api/daily_papers?limit=100")
    berichten = []
    for rij in json.loads(data):
        paper = rij.get("paper", {})
        stemmen = paper.get("upvotes", 0)
        if not paper.get("id") or stemmen < bron.get("min_stemmen", 30):
            continue
        berichten.append({
            "titel": rij.get("title") or paper.get("title") or "",
            "url": f"https://huggingface.co/papers/{paper['id']}",
            # De dag dat de paper op Hugging Face kwam; de publicatiedatum is vaak dagen ouder.
            "datum": lees_datum(paper.get("submittedOnDailyAt") or rij.get("publishedAt")),
            "tekst": re.sub(r"\s+", " ", paper.get("summary") or "")[:3000],
            "punten": stemmen,
            # De samenvatting van de paper staat er al in; de pagina ophalen voegt niets toe.
            "volledig": True,
        })
    return berichten


def lees_pagina(bron, sinds):
    """Nieuwspagina zonder feed: alle links die op het patroon passen. Zonder datum."""
    data, tekenset = haal_op(bron["url"])
    gevonden = {}
    for href, binnen in re.findall(r'<a\b[^>]*?href="([^"]+)"[^>]*>(.*?)</a>', ontcijfer(data, tekenset), re.S | re.I):
        if not re.search(bron["patroon"], href):
            continue
        url = urllib.parse.urljoin(bron["url"], html.unescape(href))
        titel = platte_tekst(binnen)
        if titel.lower() in LOZE_LINKTEKST:
            titel = ""
        if len(titel) > len(gevonden.get(url, "")):
            gevonden[url] = titel
        else:
            gevonden.setdefault(url, "")
    return [
        {"titel": titel or url.rstrip("/").rsplit("/", 1)[-1].replace("-", " "), "url": url, "datum": None, "tekst": ""}
        for url, titel in gevonden.items()
    ]


LEZERS = {"rss": lees_feed, "hackernews": lees_hackernews, "hf_papers": lees_hf_papers, "pagina": lees_pagina}


def verzamel(cfg, staat, nu):
    """Haalt alle bronnen op.

    Geeft (nieuwe berichten, aantal per bron, mislukte bronnen, sleutels die
    voortaan als gezien gelden) terug.
    """
    berichten, telling, fouten, basis = [], {}, [], []
    al_gehad = set(staat["urls"])
    for bron in cfg["bronnen"]:
        # Een bron mag een eigen venster hebben: papers verzamelen hun stemmen in dagen.
        sinds = nu - timedelta(hours=bron.get("venster_uren", cfg["venster_uren"]))
        try:
            ruw = LEZERS[bron["soort"]](bron, sinds)
        except Exception as fout:
            log.warning("Bron %s mislukt: %s", bron["naam"], fout)
            fouten.append(bron["naam"])
            continue
        eerste_keer = bron["naam"] not in staat["bronnen"]
        nieuw = []
        for bericht in ruw:
            # Alleen gewone webadressen; een vreemd adres uit een feed komt nooit op de site.
            if not bericht["url"].lower().startswith(("https://", "http://")):
                continue
            sleutel = schoon_url(bericht["url"])
            if sleutel in al_gehad:
                continue
            if bericht["datum"] is None:
                # Een pagina zonder datums: wat er bij de eerste keer al staat is oud nieuws.
                # Bij "basis": false (zoals GitHub trending) is alles wat er staat actueel.
                if eerste_keer and bron.get("basis", True):
                    basis.append(sleutel)
                    continue
            elif bericht["datum"] < sinds:
                continue
            if bron.get("filter") and not AI_WOORDEN.search(f"{bericht['titel']} {bericht['tekst']}"):
                continue
            al_gehad.add(sleutel)
            nieuw.append({**bericht, "bron": bron["naam"], "groep": bron.get("groep", ""), "sleutel": sleutel})
        nieuw.sort(key=lambda b: b["datum"] or sinds, reverse=True)
        nieuw = nieuw[:bron.get("max", cfg["max_per_bron"])]
        telling[bron["naam"]] = len(nieuw)
        berichten.extend(nieuw)
    return berichten, telling, fouten, basis


def tel_sterren(berichten, minimum):
    """Zoekt de GitHub-sterren op van elk project in de berichten.

    Sterren zijn het beste teken dat veel mensen een tool gebruiken en vertrouwen.
    Een project met minder dan `minimum` sterren valt weg, behalve van de labs zelf.
    Lukt het opzoeken niet, dan blijft het bericht staan zonder aantal.
    """
    def ophalen(repo):
        try:
            data, _ = haal_op(f"https://api.github.com/repos/{repo}", wachttijd=10, opnieuw=False)
            return repo, json.loads(data).get("stargazers_count")
        except Exception as fout:
            log.info("Sterren van %s onbekend: %s", repo, fout)
            return repo, None

    # GitHub staat zonder account 60 opvragingen per uur toe.
    repos = list(dict.fromkeys(b["repo"] for b in berichten if b.get("repo")))[:50]
    with ThreadPoolExecutor(max_workers=8) as pool:
        sterren = dict(pool.map(ophalen, repos))
    over = []
    for bericht in berichten:
        bericht["sterren"] = sterren.get(bericht.get("repo"))
        if bericht["sterren"] is not None and bericht["sterren"] < minimum and bericht["groep"] != "lab":
            log.info("Weggelaten, %s sterren op GitHub: %s", bericht["sterren"], bericht["titel"])
            continue
        over.append(bericht)
    return over


def haal_pagina(url):
    """De HTML van een artikel, of niets als ophalen niet lukt."""
    try:
        data, tekenset = haal_op(url, wachttijd=15)
    except Exception as fout:
        log.info("Artikel niet opgehaald (%s): %s", url, fout)
        return ""
    if data[:5] == b"%PDF-":
        return ""
    return ontcijfer(data, tekenset)


def artikeltekst_uit(markup, url):
    """De leesbare tekst van een artikel, of niets bij een cookiemuur of inlogpagina."""
    tekst = platte_tekst(markup)
    if len(tekst) < 500:
        log.info("Artikel te kort, waarschijnlijk een cookiemuur (%s)", url)
        return ""
    return tekst[:5000]


# ---------------------------------------------------------------- beelden

# Deelbeelden die geen nieuwsfoto zijn maar een logo of standaardplaatje van de site.
GENERIEK_BEELD = re.compile(r"logo|favicon|default|placeholder|avatar|/icons?/|redditstatic|apple-touch", re.I)


def beelden_uit(markup, url):
    """Het deelbeeld van een pagina (og:image of twitter:image), zoals sites het voor WhatsApp en sociale media opgeven."""
    kandidaten = []
    for tag in re.findall(r"<meta\b[^>]*>", markup[:300_000], re.I):
        soort = re.search(r"(?:property|name)\s*=\s*[\"']([^\"']+)", tag, re.I)
        inhoud = re.search(r"content\s*=\s*[\"']([^\"']+)", tag, re.I)
        if soort and inhoud and soort.group(1).lower() in (
            "og:image", "og:image:url", "og:image:secure_url", "twitter:image", "twitter:image:src"
        ):
            kandidaten.append(urllib.parse.urljoin(url, html.unescape(inhoud.group(1).strip())))
    return list(dict.fromkeys(kandidaten))


def beeldmaat(data):
    """(breedte, hoogte) van een plaatje, of None als het niet te lezen is."""
    try:
        from PIL import Image
        import io
        return Image.open(io.BytesIO(data)).size
    except Exception:
        return None


def beeld_geschikt(url):
    """Een goed nieuwsbeeld: geen logo, breed genoeg en ongeveer liggend."""
    if GENERIEK_BEELD.search(url):
        return False
    try:
        data, _ = haal_op(url, wachttijd=10, opnieuw=False)
    except Exception:
        return False
    maat = beeldmaat(data)
    if maat is None:
        # Zonder Pillow of bij een onbekend formaat: vertrouw de site.
        return len(data) > 5_000
    breedte, hoogte = maat
    return breedte >= 600 and hoogte > 0 and 1.2 <= breedte / hoogte <= 2.6


def verrijk(berichten):
    """Haalt voor een onderwerp de artikeltekst en het beste beeld op.

    Geeft (plek van de bron met tekst, tekst, beeld-adres) terug. De eerste hand staat
    vooraan, dus het beeld van het lab zelf wint van dat van een nieuwssite.
    """
    plek_tekst, tekst, beeld = -1, "", ""
    for plek, bericht in enumerate(berichten[:3]):
        markup = haal_pagina(bericht["url"])
        if markup and not tekst and not bericht.get("volledig"):
            tekst = artikeltekst_uit(markup, bericht["url"])
            if tekst:
                plek_tekst = plek
        if markup and not beeld:
            beeld = next((b for b in beelden_uit(markup, bericht["url"]) if beeld_geschikt(b)), "")
        if not beeld and bericht.get("repo"):
            # GitHub maakt voor elk project een nette kaart met naam, beschrijving en sterren.
            beeld = f"https://opengraph.githubassets.com/1/{bericht['repo']}"
        if beeld and (tekst or bericht.get("volledig")):
            break
    return plek_tekst, tekst, beeld


# ---------------------------------------------------------------- Claude

def vraag_claude(cfg, bericht, schema):
    """Stelt één vraag aan Claude Code (zonder tools) en geeft het antwoord als dict terug."""
    claude = cfg["claude_pad"] or shutil.which("claude") or str(Path.home() / ".local" / "bin" / "claude.exe")
    # --safe-mode slaat hooks, plugins en MCP-servers over: sneller, en het antwoord
    # hangt dan niet af van wat er toevallig in Claude Code is ingesteld.
    opdracht = [
        claude, "-p", "--safe-mode", "--tools", "", "--model", cfg["model"],
        "--output-format", "json", "--no-session-persistence",
        "--system-prompt", SYSTEEM, "--json-schema", json.dumps(schema),
    ]
    uitkomst = subprocess.run(
        opdracht, input=bericht, capture_output=True, text=True, encoding="utf-8",
        # Op Windows geen zwart venster; in de cloud (Linux) bestaat die vlag niet.
        timeout=900, cwd=MAP, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if uitkomst.returncode != 0:
        raise RuntimeError(f"Claude stopte met fout {uitkomst.returncode}: {(uitkomst.stderr or uitkomst.stdout).strip()[:300]}")
    antwoord = json.loads(uitkomst.stdout)
    if antwoord.get("is_error"):
        raise RuntimeError(f"Claude gaf een fout: {str(antwoord.get('result'))[:300]}")
    # Wat deze vraag kostte. Met een abonnement betaal je dit niet los; het telt mee voor je gebruikslimiet.
    gebruik = antwoord.get("usage") or {}
    tokens_in = sum(gebruik.get(veld, 0) for veld in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
    log.info("Claude: %s tokens in, %s tokens uit, %.0f seconden, $%.2f tegen API-prijs",
             tokens_in, gebruik.get("output_tokens", 0), antwoord.get("duration_ms", 0) / 1000, antwoord.get("total_cost_usd") or 0)
    if isinstance(antwoord.get("structured_output"), dict):
        return antwoord["structured_output"]
    gevonden = re.search(r"\{.*\}", antwoord.get("result") or "", re.S)
    if not gevonden:
        raise RuntimeError("Claude gaf geen JSON terug")
    return json.loads(gevonden.group(0))


GEBRUIKERSPOSTS = ("reddit.com", "news.ycombinator.com")


def bevestigd(bericht):
    """Komt dit bericht van een echte nieuwsbron? Een post op Reddit of een tekstpost op Hacker News niet;
    een Hacker News-link naar een artikel van een nieuwssite of bedrijf wel."""
    if bericht["groep"] != "community":
        return True
    host = urllib.parse.urlsplit(bericht["url"]).netloc.lower()
    return not any(host == d or host.endswith("." + d) for d in GEBRUIKERSPOSTS)


def kies(cfg, berichten, staat):
    """Laat Claude de berichten scoren. Geeft (volledige berichten, korte berichten) terug."""
    nu = datetime.now()
    lijst = []
    for nr, bericht in enumerate(berichten, 1):
        regel = {"id": nr, "bron": bericht["bron"], "soort": bericht["groep"], "datum": wanneer(bericht["datum"], nu),
                 "titel": bericht["titel"], "tekst": bericht["tekst"][:400]}
        if bericht.get("punten"):
            regel["punten"] = bericht["punten"]
        if bericht.get("sterren") is not None:
            regel["github_sterren"] = bericht["sterren"]
        lijst.append(regel)
    eerder = "\n".join(f"- {v['kop']}" for v in staat["verstuurd"]) or "- (nog niets)"
    vraag = (
        f"{CRITERIA.read_text(encoding='utf-8')}\n\n"
        f"## Eerder verschenen\n\nKies deze onderwerpen niet opnieuw, tenzij er een echt nieuw feit bij is gekomen.\n\n{eerder}\n\n"
        f"## Berichten\n\n{json.dumps(lijst, ensure_ascii=False)}"
    )
    onderwerpen = []
    for keuze in vraag_claude(cfg, vraag, KEUZE_SCHEMA)["gekozen"]:
        bij = [berichten[i - 1] for i in dict.fromkeys(keuze["ids"]) if 1 <= i <= len(berichten)]
        if bij:
            # De eerste hand voorop: daar wijst de kop naar en die tekst wordt samengevat.
            bij.sort(key=lambda b: b["groep"] != "lab")
            onderwerpen.append({**keuze, "berichten": bij})
    # Iets wat alleen in een bericht op Reddit of Hacker News staat, is (nog) geen nieuws: een gebruiker
    # kan van alles beweren. Zulke berichten mogen nooit groot nieuws, modelnieuws, Nederlands nieuws of
    # maatschappijnieuws zijn; hooguit Kort nieuws. Ervaringen en tools mogen wel, want daar gaat het juist om gebruikers.
    for o in onderwerpen:
        if (o["rubriek"] in ("Het grote nieuws", "Nieuwe modellen", "AI in Nederland", "Maatschappij")
                and not any(bevestigd(b) for b in o["berichten"])):
            log.info("Niet bevestigd, naar Kort nieuws: %s", o["berichten"][0]["titel"])
            o["score"] = min(o["score"], cfg["minimale_score_kort"])
    onderwerpen.sort(key=lambda o: o["score"], reverse=True)
    for o in onderwerpen:
        log.info("Score %s [%s] %s (%s)", o["score"], o["rubriek"], o["berichten"][0]["titel"], o["reden"])

    # Eerst de beste van elke rubriek, zodat elke rubriek met goed nieuws aan bod komt.
    # Daarna de rest op score, tot het maximum per rubriek en in totaal.
    goed = [o for o in onderwerpen if o["score"] >= cfg["minimale_score"]]
    gekozen, per_rubriek = [], {}
    for o in goed:
        if o["rubriek"] not in per_rubriek and cfg["rubrieken"].get(o["rubriek"], 3) > 0:
            per_rubriek[o["rubriek"]] = 1
            gekozen.append(o)
    for o in goed:
        if len(gekozen) >= cfg["max_items"]:
            break
        if o in gekozen or per_rubriek.get(o["rubriek"], 0) >= cfg["rubrieken"].get(o["rubriek"], 3):
            continue
        per_rubriek[o["rubriek"]] = per_rubriek.get(o["rubriek"], 0) + 1
        gekozen.append(o)
    # Wat geen volledig bericht krijgt maar wel de moeite waard is, komt onder "Snel nog even".
    kort = [o for o in onderwerpen if o not in gekozen and o["score"] >= cfg["minimale_score_kort"]][:cfg["max_kort"]]
    # Op de site staan de rubrieken op vaste volgorde, binnen een rubriek de hoogste score eerst.
    volgorde = list(RUBRIEKEN)
    gekozen.sort(key=lambda o: volgorde.index(o["rubriek"]))
    return gekozen, kort


def schrijf_editie(cfg, gekozen, kort, moment, bekend):
    """Haalt de artikelen en beelden op en laat Claude de editie schrijven. Geeft het antwoord van Claude terug.

    Het gekozen beeld komt in elk onderwerp onder "beeld".
    """
    with ThreadPoolExecutor(max_workers=6) as pool:
        verrijkt = list(pool.map(lambda o: verrijk(o["berichten"]), gekozen))
    # Hetzelfde plaatje bij twee verschillende berichten is het standaardplaatje van een site, geen nieuwsfoto.
    tellingen = {}
    for _, _, beeld in verrijkt:
        if beeld:
            tellingen[beeld] = tellingen.get(beeld, 0) + 1
    for onderwerp, (_, _, beeld) in zip(gekozen, verrijkt):
        onderwerp["beeld"] = beeld if tellingen.get(beeld) == 1 else ""
    log.info("Beelden gevonden voor %s van de %s berichten", sum(1 for o in gekozen if o["beeld"]), len(gekozen))
    teksten = [(plek, tekst) for plek, tekst, _ in verrijkt]
    nu = datetime.now()
    onderwerpen = []
    for nr, (onderwerp, (plek_pagina, pagina)) in enumerate(zip(gekozen, teksten), 1):
        bronnen = []
        for plek, bericht in enumerate(onderwerp["berichten"][:3]):
            tekst = bericht["tekst"]
            if plek == plek_pagina and pagina:
                tekst = f"{tekst}\n\nPAGINATEKST:\n{pagina}".strip()
            bron = {"bron": bericht["bron"], "datum": wanneer(bericht["datum"], nu), "titel": bericht["titel"], "tekst": tekst}
            if bericht.get("sterren") is not None:
                bron["github_sterren"] = bericht["sterren"]
            bronnen.append(bron)
        onderwerpen.append({"nr": nr, "rubriek": onderwerp["rubriek"], "bronnen": bronnen})
    korte = []
    for nr, onderwerp in enumerate(kort, 1):
        eerste = onderwerp["berichten"][0]
        korte.append({"nr": nr, "rubriek": onderwerp["rubriek"], "bron": eerste["bron"],
                      "datum": wanneer(eerste["datum"], nu), "titel": eerste["titel"], "tekst": eerste["tekst"][:600]})

    groet = "Goedemorgen." if moment == "ochtend" else "Goedenavond."
    opdracht = SCHRIJF_OPDRACHT.format(moment=moment, groet=groet)
    inhoud = json.dumps({"onderwerpen": onderwerpen, "korte_berichten": korte, "bekende_onderwerpen": bekend},
                        ensure_ascii=False)
    return vraag_claude(cfg, opdracht + inhoud, SCHRIJF_SCHEMA)


def bekende_onderwerpen(edities, hoeveel=80):
    """De onderwerpen van eerdere berichten, het vaakst gebruikte eerst, zodat Claude ze hergebruikt."""
    teller = {}
    for ed in edities:
        for item in ed["items"]:
            for onderwerp in item.get("onderwerpen", []):
                teller[onderwerp] = teller.get(onderwerp, 0) + 1
    return [o for o, _ in sorted(teller.items(), key=lambda paar: -paar[1])][:hoeveel]


# ---------------------------------------------------------------- editie

def _bronnen(onderwerp):
    """De bronnen van een onderwerp zoals ze in de editie worden bewaard."""
    uit = []
    for bericht in onderwerp["berichten"]:
        rij = {"bron": bericht["bron"], "groep": bericht["groep"], "url": bericht["url"],
               "datum": bericht["datum"].isoformat() if bericht["datum"] else None}
        if bericht.get("discussie"):
            rij.update(discussie=bericht["discussie"], punten=bericht["punten"])
        if bericht.get("sterren") is not None:
            rij["sterren"] = bericht["sterren"]
        uit.append(rij)
    return uit


def stel_samen(tijd, datum, moment, gekozen, kort, antwoord, bekeken, aantal_bronnen, fouten):
    """Zet de keuze en de teksten van Claude samen in één editie, klaar om te bewaren.

    `tijd` is wanneer de editie gemaakt is, `datum` de dag waar hij bij hoort. Die verschillen
    als GitHub de avondeditie pas na middernacht start.
    """
    lang = {i["nr"]: i for i in antwoord.get("items", [])}
    items = [
        {"rubriek": o["rubriek"], "score": o["score"], "kop": lang[nr]["kop"], "uitleg": lang[nr]["uitleg"],
         "samenvatting": lang[nr]["samenvatting"], "waarom": lang[nr]["waarom"], "bronnen": _bronnen(o),
         "beeld": o.get("beeld", ""), "bedrijf": lang[nr].get("bedrijf", "Anders"),
         "onderwerpen": [t.strip() for t in lang[nr].get("onderwerpen", []) if t.strip()][:3]}
        for nr, o in enumerate(gekozen, 1) if nr in lang
    ]
    # Alleen vragen die kloppen: precies drie antwoorden en een goed antwoord dat bestaat.
    quiz = [
        {"vraag": v["vraag"], "opties": v["opties"], "goed": v["goed"], "uitleg": v["uitleg"]}
        for v in antwoord.get("quiz", [])
        if len(v.get("opties", [])) == 3 and v.get("goed") in (0, 1, 2)
    ][:3]
    kortjes = {k["nr"]: k for k in antwoord.get("kort", [])}
    korte = [
        {"rubriek": o["rubriek"], "score": o["score"], "kop": kortjes[nr]["kop"], "zin": kortjes[nr]["zin"],
         "bedrijf": kortjes[nr].get("bedrijf", "Anders"), "bronnen": _bronnen(o)}
        for nr, o in enumerate(kort, 1) if nr in kortjes
    ]
    probeer = antwoord.get("probeer") or {}
    if 1 <= probeer.get("nr", 0) <= len(gekozen):
        probeer = {"titel": probeer["titel"], "tekst": probeer["tekst"], "url": gekozen[probeer["nr"] - 1]["berichten"][0]["url"]}
    else:
        probeer = None
    return {
        "id": None, "tijd": tijd.isoformat(timespec="minutes"), "datum": datum.isoformat(), "moment": moment,
        "intro": antwoord.get("intro", "").strip(), "items": items, "kort": korte, "probeer": probeer, "quiz": quiz,
        "bekeken": bekeken, "aantal_bronnen": aantal_bronnen, "fouten": fouten,
    }


def laatste_moment(lokaal):
    """De laatste vaste editie die al had moeten verschijnen: (dag, 'ochtend' of 'avond')."""
    if lokaal.hour >= 20:
        return lokaal.date(), "avond"
    if lokaal.hour >= 8:
        return lokaal.date(), "ochtend"
    return lokaal.date() - timedelta(days=1), "avond"


def nieuw_id(datum, moment, edities):
    basis = f"{datum:%Y-%m-%d}-{moment}"
    bestaand = {ed["id"] for ed in edities}
    kandidaat, n = basis, 2
    while kandidaat in bestaand:
        kandidaat, n = f"{basis}-{n}", n + 1
    return kandidaat


def laad_edities():
    edities = []
    for pad in EDITIES.glob("*.json"):
        try:
            ed = json.loads(pad.read_text(encoding="utf-8"))
        except ValueError:
            log.warning("Editie %s is onleesbaar en wordt overgeslagen", pad.name)
            continue
        geef_ids(ed)
        edities.append(ed)
    return edities


WEEK_SCHEMA = {"type": "object", "properties": {"intro": {"type": "string"}}, "required": ["intro"]}


def maak_week(cfg, edities, dag):
    """De week in AI: de 10 belangrijkste berichten van maandag tot en met `dag`."""
    maandag = dag - timedelta(days=dag.weekday())
    berichten = [item for ed in edities if maandag <= editiedag(ed) <= dag for item in ed["items"]]
    if not berichten:
        return None
    # Het belangrijkste eerst; bij gelijke score wint wat door meer bronnen gemeld werd.
    berichten.sort(key=lambda i: (i["score"], len(i["bronnen"])), reverse=True)
    top = berichten[:10]
    lijst = [{"kop": i["kop"], "samenvatting": i["samenvatting"]} for i in top]
    vraag = (
        "Schrijf de opening van 'De week in AI', het weekoverzicht van een Nederlandse AI-nieuwssite voor lezers met "
        "een beetje kennis van AI. 2 of 3 zinnen over wat deze week opviel, in helder Nederlands zonder vakjargon. "
        "Gebruik alleen wat in de berichten staat. Geen gedachtestreepjes, geen puntkomma's, geen uitroeptekens.\n\n"
        f"De belangrijkste berichten van deze week:\n{json.dumps(lijst, ensure_ascii=False)}"
    )
    intro = vraag_claude(cfg, vraag, WEEK_SCHEMA).get("intro", "").strip()
    jaar, weeknr, _ = dag.isocalendar()
    return {"id": f"{jaar}-W{weeknr:02d}", "van": maandag.isoformat(), "tot": dag.isoformat(),
            "intro": intro, "items": [i["id"] for i in top]}


def laad_weken():
    weken = []
    for pad in sorted(WEKEN.glob("*.json")):
        try:
            weken.append(json.loads(pad.read_text(encoding="utf-8")))
        except ValueError:
            log.warning("Week %s is onleesbaar en wordt overgeslagen", pad.name)
    return weken


def laad_begrippen():
    try:
        return json.loads(BEGRIPPEN.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return {}


def voeg_begrippen_toe(begrippen, nieuw, editie_id):
    """Nieuwe begrippen erbij. Een begrip dat er al is houdt zijn eerste uitleg."""
    for begrip in nieuw:
        woord, uitleg = begrip["woord"].strip(), begrip["uitleg"].strip()
        if not woord or not uitleg:
            continue
        sleutel = woord.lower()
        if sleutel in begrippen:
            begrippen[sleutel]["keer"] += 1
        else:
            begrippen[sleutel] = {"woord": woord, "uitleg": uitleg, "editie": editie_id, "keer": 1}


def bewaar_json(pad, data):
    tijdelijk = pad.with_suffix(".tmp")
    tijdelijk.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tijdelijk.replace(pad)


# ---------------------------------------------------------------- mail

def bouw_mail(ed, site_url, week=None):
    """Een korte mail in de stijl van de site: de vijf belangrijkste berichten en een link naar de rest.

    Geeft (onderwerp, tekst, html). Met `week` (zondagavond) komt er een verwijzing naar De week in AI bij.
    """
    e = html.escape
    datum, moment = dagtitel(editiedag(ed)), ed["moment"]
    tijd = datetime.fromisoformat(ed["tijd"])
    top = sorted(ed["items"], key=lambda i: i["score"], reverse=True)[:5]
    totaal = len(ed["items"]) + len(ed["kort"])
    if top:
        onderwerp = f"AI-nieuws {moment}: {top[0]['kop']}"
        if totaal > 1:
            onderwerp += f" (+{totaal - 1})"
        intro = ed["intro"]
    else:
        onderwerp = f"AI-nieuws {moment}: rustige editie"
        intro = "Sinds de vorige editie is er niets verschenen dat de moeite waard is."

    rest = totaal - len(top)
    delen = []
    if rest:
        delen.append(f"nog {rest} berichten")
    if ed.get("probeer"):
        delen.append("de tip van vandaag")
    if ed.get("quiz"):
        delen.append("de nieuwsquiz")
    verwijzing = f"Op de site staan {', '.join(delen[:-1]) + ' en ' + delen[-1] if len(delen) > 1 else delen[0]}." if delen else ""

    serif = "Georgia,'Times New Roman',serif"
    plat = [f"AI-nieuws, {datum}, {moment}", "", intro, ""]
    blokken = []
    for nr, item in enumerate(top):
        url = artikel_url(site_url, item) if site_url else item["bronnen"][0]["url"]
        regel = datumregel(item["bronnen"], tijd)
        beeld = ""
        if nr == 0 and item.get("beeld"):
            beeld = (f'<a href="{e(url)}"><img src="{e(item["beeld"])}" alt="" width="560" '
                     'style="display:block;width:100%;height:auto;margin:0 0 12px;border:0"></a>')
        blokken.append(
            f'<div style="margin:0 0 26px">{beeld}'
            f'<div style="font-size:12px;font-weight:bold;letter-spacing:1px;text-transform:uppercase;color:#C4122F">{e(item["rubriek"])}</div>'
            f'<h3 style="font-family:{serif};font-size:21px;line-height:1.25;margin:4px 0 4px"><a href="{e(url)}" style="color:#141414;text-decoration:none">{e(item["kop"])}</a></h3>'
            f'<div style="margin:0 0 8px;font-size:13px;color:#666666">{e(regel)}</div>'
            f'<p style="margin:0;font-size:15px;line-height:1.55;color:#222222">{e(item["samenvatting"])}</p>'
            f'</div>'
        )
        plat += [f"[{item['rubriek']}] {item['kop']}", f"({regel})", item["samenvatting"], url, ""]
    if verwijzing:
        plat.append(f"{verwijzing} {site_url}")
    if week:
        plat.append(f"Ook nieuw: De week in AI, de 10 belangrijkste berichten van deze week. {site_url}week/{week['id']}.html")

    knop = ""
    if verwijzing:
        knop = (
            '<div style="border-top:3px solid #141414;padding:16px 0 0;font-size:15px;line-height:1.5;color:#333333">'
            f'{e(verwijzing)}<br><a href="{e(site_url)}" style="display:inline-block;margin-top:12px;padding:12px 18px;'
            'background:#141414;color:#ffffff;text-decoration:none;font-weight:bold">Lees de hele editie</a></div>'
        )
    if week:
        knop += (
            '<div style="margin-top:22px;background:#F3F3F0;padding:16px 18px;font-size:15px;line-height:1.5">'
            f'<b>Ook nieuw: De week in AI.</b> De 10 belangrijkste berichten van deze week op een rij. '
            f'<a href="{e(site_url)}week/{e(week["id"])}.html" style="color:#C4122F;font-weight:bold">Lees de week</a></div>'
        )
    opmaak = (
        '<!doctype html><html lang="nl"><body style="margin:0;padding:0;background:#f4f4f2">'
        '<div style="max-width:600px;margin:0 auto;padding:26px 22px;background:#ffffff;font-family:Arial,Helvetica,sans-serif;color:#141414">'
        f'<div style="font-size:13px;color:#666666">{e(datum.capitalize())}, {e(moment)}editie</div>'
        f'<h1 style="font-family:{serif};font-size:34px;line-height:1;margin:4px 0 14px">AI-nieuws</h1>'
        f'<p style="font-family:{serif};margin:0 0 26px;font-size:18px;line-height:1.5;color:#333333">{e(intro)}</p>'
        f'{"".join(blokken)}{knop}'
        '</div></body></html>'
    )
    return onderwerp, "\n".join(plat), opmaak


def lees_wachtwoord():
    # In de cloud staat het wachtwoord in de geheime instellingen van GitHub, op de pc in wachtwoord.txt.
    if os.environ.get("GMAIL_APP_WACHTWOORD"):
        return os.environ["GMAIL_APP_WACHTWOORD"].strip().replace(" ", "")
    try:
        return WACHTWOORD.read_text(encoding="utf-8-sig").strip().replace(" ", "")
    except FileNotFoundError:
        return ""


def verstuur(cfg, wachtwoord, onderwerp, plat, opmaak=None):
    bericht = EmailMessage()
    bericht["Subject"] = onderwerp
    bericht["From"] = f"AI-nieuws <{cfg['mail_van']}>"
    bericht["To"] = cfg["mail_aan"]
    bericht.set_content(plat)
    if opmaak:
        bericht.add_alternative(opmaak, subtype="html")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as server:
        server.login(cfg["mail_van"], wachtwoord)
        server.send_message(bericht)


# ---------------------------------------------------------------- staat

def laad_config():
    cfg = dict(STANDAARD)
    cfg.update(json.loads(CONFIG.read_text(encoding="utf-8")))
    # config.json is openbaar op GitHub; het mailadres komt daarom uit een geheime instelling.
    adres = os.environ.get("MAIL_ADRES", "").strip()
    cfg["mail_aan"] = cfg["mail_aan"] or adres
    cfg["mail_van"] = cfg["mail_van"] or adres
    return cfg


def laad_staat():
    """Wat al bekeken en verschenen is. Een kapot of ontbrekend bestand begint leeg."""
    try:
        staat = json.loads(GEZIEN.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        staat = {}
    staat.setdefault("urls", {})
    staat.setdefault("verstuurd", [])
    staat.setdefault("bronnen", [])
    return staat


def bewaar_staat(staat, nu):
    grens_urls = (nu - timedelta(days=30)).isoformat()
    grens_koppen = (nu - timedelta(days=7)).isoformat()
    staat["urls"] = {u: d for u, d in staat["urls"].items() if d > grens_urls}
    staat["verstuurd"] = [v for v in staat["verstuurd"] if v["datum"] > grens_koppen]
    bewaar_json(GEZIEN, staat)


# ---------------------------------------------------------------- hoofdprogramma

def main():
    keuzes = argparse.ArgumentParser(description="AI-nieuws ophalen, schrijven, op de site zetten en mailen.")
    keuzes.add_argument("--voorbeeld", action="store_true", help="proefeditie in de map voorbeeld/, niets mailen of bewaren")
    keuzes.add_argument("--bronnen", action="store_true", help="tonen wat elke bron nu oplevert")
    keuzes.add_argument("--gepland", action="store_true", help="de laatste vaste editie (08:00 of 20:00) maken, als die er nog niet is")
    keuzes.add_argument("--nodig", action="store_true", help="alleen kijken of de laatste vaste editie nog ontbreekt (voor GitHub)")
    keuzes.add_argument("--alles", action="store_true", help="met --voorbeeld: doen alsof er nog niets gezien is, om alles te testen")
    keuzes.add_argument("--week", action="store_true", help="ook De week in AI maken (gebeurt vanzelf op zondagavond)")
    keuzes.add_argument("--alleen-site", action="store_true", help="geen nieuws ophalen, alleen de site opnieuw maken uit de bewaarde edities")
    args = keuzes.parse_args()
    if args.alles and not args.voorbeeld:
        keuzes.error("--alles kan alleen samen met --voorbeeld; anders raakt de lijst met gezien nieuws in de war")

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.handlers.RotatingFileHandler(MAP / "ai_nieuws.log", maxBytes=500_000, backupCount=1, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )

    cfg = laad_config()
    staat = {"urls": {}, "verstuurd": [], "bronnen": []} if args.alles else laad_staat()
    nu = datetime.now(timezone.utc)
    lokaal = datetime.now()
    datum, moment = lokaal.date(), ("ochtend" if lokaal.hour < 14 else "avond")

    if args.alleen_site:
        doel = VOORBEELD if args.voorbeeld else SITE
        voorpagina = schrijf_site(doel, laad_edities(), laad_begrippen(), laad_weken(), cfg["site_url"])
        log.info("Site opnieuw gemaakt: %s", voorpagina)
        return 0

    if args.gepland or args.nodig:
        # GitHub start geplande runs soms uren te laat of slaat ze over. Daarom kijkt het programma
        # welke editie er als laatste had moeten zijn, en maakt die alsnog als hij ontbreekt.
        datum, moment = laatste_moment(lokaal)
        ontbreekt = not any(ed["id"] == f"{datum:%Y-%m-%d}-{moment}" for ed in laad_edities())
        if args.nodig:
            log.info("Editie %s %s %s", f"{datum:%Y-%m-%d}", moment, "ontbreekt" if ontbreekt else "is er al")
            if os.environ.get("GITHUB_OUTPUT"):
                with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as uitvoer:
                    uitvoer.write(f"nodig={'true' if ontbreekt else 'false'}\n")
            return 0
        if not ontbreekt:
            log.info("Geen editie nodig om %s; alleen de site wordt opnieuw gemaakt.", f"{lokaal:%H:%M}")
            schrijf_site(SITE, laad_edities(), laad_begrippen(), laad_weken(), cfg["site_url"])
            return 0

    # Net na het aanzetten van de pc is er soms nog geen internet.
    for poging in range(4):
        berichten, telling, fouten, basis = verzamel(cfg, staat, nu)
        if telling or args.bronnen:
            break
        log.warning("Geen enkele bron bereikbaar (poging %s van 4)", poging + 1)
        time.sleep(60)
    else:
        log.error("Gestopt: geen internet")
        return 1

    if args.bronnen:
        for bron in cfg["bronnen"]:
            naam = bron["naam"]
            if naam in fouten:
                print(f"{naam:<28} MISLUKT")
                continue
            eerste = next((b["titel"] for b in berichten if b["bron"] == naam), "")
            print(f"{naam:<28} {telling[naam]:>3}  {eerste[:70]}")
        print(f"\nTotaal {len(berichten)} nieuwe berichten, {len(basis)} oude links overgeslagen.")
        return 0

    berichten = tel_sterren(berichten, cfg["min_sterren"])
    log.info("%s nieuwe berichten uit %s bronnen, mislukt: %s", len(berichten), len(telling), ", ".join(fouten) or "geen")
    wachtwoord = lees_wachtwoord()
    try:
        gekozen, kort = kies(cfg, berichten, staat) if berichten else ([], [])
        bekend = bekende_onderwerpen(laad_edities())
        antwoord = schrijf_editie(cfg, gekozen, kort, moment, bekend) if gekozen or kort else {}
    except Exception as fout:
        log.exception("Kiezen of schrijven mislukt")
        if wachtwoord and cfg["mail_aan"] and not args.voorbeeld:
            verstuur(cfg, wachtwoord, f"AI-nieuws {moment}: schrijven mislukt",
                     f"Het maken van de editie is mislukt.\n\nOorzaak: {fout}\n\n"
                     "Meer staat in het logboek van de laatste run op GitHub (tabblad Actions).\n"
                     "De berichten van nu komen in de volgende editie.")
        return 1

    edities = laad_edities()
    begrippen = laad_begrippen()
    ed = stel_samen(lokaal, datum, moment, gekozen, kort, antwoord, len(berichten), len(telling), fouten)
    ed["id"] = nieuw_id(datum, moment, edities)
    geef_ids(ed)
    leeg = not ed["items"] and not ed["kort"]
    if not leeg:
        edities.append(ed)
        voeg_begrippen_toe(begrippen, antwoord.get("begrippen", []), ed["id"])

    # Zondagavond komt er De week in AI bij: de 10 belangrijkste berichten van maandag tot en met vandaag.
    weken = laad_weken()
    week = None
    if args.week or (moment == "avond" and datum.weekday() == 6):
        try:
            week = maak_week(cfg, edities, datum)
        except Exception:
            log.exception("De week in AI is mislukt; de editie gaat gewoon door")
        if week:
            weken = [w for w in weken if w["id"] != week["id"]] + [week]
    onderwerp, plat, opmaak = bouw_mail(ed, cfg["site_url"], week)

    if args.voorbeeld:
        voorpagina = schrijf_site(VOORBEELD, edities, begrippen, weken, cfg["site_url"])
        (VOORBEELD / "mail.html").write_text(opmaak, encoding="utf-8")
        log.info("Proefeditie geschreven: %s (%s)", voorpagina, onderwerp)
        return 0

    # Eerst de site en het geheugen bijwerken; de mail is alleen een seintje dat er een editie is.
    if not leeg:
        EDITIES.mkdir(exist_ok=True)
        bewaar_json(EDITIES / f"{ed['id']}.json", ed)
        bewaar_json(BEGRIPPEN, begrippen)
    if week:
        WEKEN.mkdir(exist_ok=True)
        bewaar_json(WEKEN / f"{week['id']}.json", week)
    schrijf_site(SITE, edities, begrippen, weken, cfg["site_url"])
    stempel = nu.isoformat()
    for sleutel in basis + [b["sleutel"] for b in berichten]:
        staat["urls"][sleutel] = stempel
    staat["verstuurd"] += [{"kop": i["kop"], "datum": stempel} for i in ed["items"] + ed["kort"]]
    staat["bronnen"] = sorted(set(staat["bronnen"]) | set(telling))
    bewaar_staat(staat, nu)
    log.info("Editie %s op de site gezet: %s berichten, %s kort", ed["id"], len(ed["items"]), len(ed["kort"]))

    if not wachtwoord or not cfg["mail_aan"]:
        log.error("Niet gemaild: geen Gmail-wachtwoord of mailadres ingesteld. De editie staat wel op de site.")
        return 1
    try:
        verstuur(cfg, wachtwoord, onderwerp, plat, opmaak)
    except smtplib.SMTPAuthenticationError:
        log.error("Niet gemaild: Gmail weigert het app-wachtwoord. De editie staat wel op de site.")
        return 1
    log.info("Gemaild: %s", onderwerp)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        log.exception("AI-nieuws is gestopt door een fout")
        sys.exit(1)
