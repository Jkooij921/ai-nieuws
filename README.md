# AI-nieuws

Een AI-nieuwssite met elke dag om 08:00 en 20:00 een nieuwe editie: wat er sinds de vorige editie in AI is gebeurd, vooral rond Claude. Per editie ongeveer 12 berichten met uitleg voor leken en 10 tot 15 korte berichten. Je krijgt een mail met de 5 belangrijkste en een link naar de rest.

Alles draait in de cloud bij GitHub. Je laptop mag uit. Claude schrijft de berichten via je eigen abonnement.

## De site

- **Vandaag:** de nieuwste editie. Bovenaan een keuze welke AI je wilt zien (Alle AI, Claude, ChatGPT, Overig; onthouden op je apparaat) en filters per onderwerp: Groot nieuws, Modellen, Tools, Zo gebruik je AI, Nederland, Maatschappij, Kort nieuws en de Quiz. Elk bericht heeft een beeld van de bron, een impact-label en het aantal bronnen. Tik of klik ergens op een bericht en je gaat naar de hele uitleg, zoals bij andere nieuwssites. Kort nieuws heeft geen eigen pagina: een pijltje (↗) laat zien dat die link naar de bron gaat. Met elke editie één tip onder "Probeer dit vandaag" en een nieuwsquiz van 3 vragen. Na de quiz kun je je score delen via WhatsApp, met een link naar dezelfde quiz.
- **Een pagina per bericht** (`artikel/`): de hele uitleg, alle bronnen, een knop om te delen via WhatsApp, en onderaan "Eerder over …" met eerdere berichten over hetzelfde onderwerp.
- **Geschreven met AI:** bovenaan elke pagina en onder elke kop staat dat de berichten met AI geschreven zijn (dat moet sinds 2 augustus 2026 volgens de Europese AI-verordening, artikel 50). Het label linkt naar **Zo maken we dit** (`zo-maken-we-dit.html`): hoe we kiezen, wat er niet in komt en welke bronnen, automatisch uit `config.json`.
- **Delen:** elke pagina geeft WhatsApp en andere apps een kop, een korte tekst en een beeld voor de voorvertoning. Zonder bruikbaar beeld komt `deel.png`, het plaatje met de naam van de site.
- **Onderwerpen** (`onderwerp/`): alle berichten over bijvoorbeeld Claude Code of Mistral bij elkaar. Claude geeft elk bericht 1 tot 3 onderwerpen en hergebruikt bestaande namen.
- **De week:** elke zondagavond de 10 belangrijkste berichten van de week.
- **Archief, Begrippen en tips, Zoeken:** alle edities, alle uitgelegde woorden, en zoeken in alle berichten.

Iedereen met de link kan de site lezen. Zoekmachines nemen hem niet op. Wat iemand gelezen heeft, staat alleen in de eigen browser.

## Beelden

Net als nieuwsaggregators gebruikt de site het deelbeeld dat de bron zelf opgeeft (og:image, het plaatje dat je ook ziet als je een link in WhatsApp deelt). Een beeld valt weg als het een logo is, smaller dan 600 pixels, niet ongeveer liggend, of hetzelfde als bij een ander bericht (dan is het het standaardplaatje van een site). Heeft een bericht geen goed beeld maar wel een GitHub-project, dan komt de GitHub-kaart van dat project. Anders een zwart blok met de naam van de bron. Werkt een beeld later niet meer, dan verschijnt dat blok vanzelf.

## Hoe het werkt

1. GitHub start `.github/workflows/editie.yml` twee keer per uur in de uren na 08:00 en 20:00. Elke run kijkt eerst welke editie er als laatste had moeten zijn (08:00 of 20:00). Bestaat die al, dan stopt de run na een paar seconden.
2. Ontbreekt de editie, dan haalt `ai_nieuws.py` het nieuws op, laat Claude kiezen en schrijven, maakt de site en mailt.
3. De editie, de begrippen en de lijst met gezien nieuws worden bewaard in deze repository. De site gaat naar GitHub Pages.

GitHub start geplande runs soms te laat of slaat er een over. Daarom wordt er vaak gekeken: een gemiste editie komt bij de volgende run alsnog, meestal binnen een half uur na 08:00 of 20:00.

## Wat erin komt

- `criteria.md`: voor wie de site is, wat er in elke rubriek hoort, wat er niet in komt (geen reclame, geen onbekende tools) en hoe de score werkt.
- `SCHRIJF_OPDRACHT` bovenin `ai_nieuws.py`: hoe de berichten geschreven worden.
- `config.json`: de bronnen en de aantallen.

Pas een van deze bestanden aan, zet de wijziging op GitHub, en de volgende editie volgt de nieuwe regels.

## Instellingen in config.json

| Instelling | Betekenis |
|---|---|
| `site_url` | Het adres van de site, voor de knop in de mail. |
| `max_items` | Hoogste aantal berichten met uitleg per editie. Standaard `12`. |
| `max_kort` | Hoogste aantal korte berichten onder "Snel nog even". Standaard `15`. |
| `minimale_score`, `minimale_score_kort` | Vanaf welke score een bericht uitleg krijgt (`6`) of kort genoemd wordt (`5`). |
| `min_sterren` | Een GitHub-project met minder sterren valt weg. Standaard `500`. Projecten van de labs zelf blijven altijd. |
| `rubrieken` | Hoogste aantal berichten met uitleg per rubriek. `0` zet een rubriek uit. |
| `venster_uren` | Hoe ver terug er wordt gekeken. Standaard `48`. Niets komt twee keer. |
| `model` | Het Claude-model: `sonnet`, `opus` of `haiku`. |
| `bronnen` | De lijst met bronnen. `"filter": true` laat alleen berichten met een AI-woord door, `"zonder"` slaat titels over (zoals proefversies). Soort `wijzigingen` is voor release notes zonder losse links: het programma onthoudt de pagina in `gezien.json` en geeft alleen door wat er sinds de vorige keer bij kwam. |

## Geheime instellingen

Deze staan bij GitHub onder Settings, Secrets and variables, Actions. Ze zijn nergens openbaar te zien.

| Naam | Wat |
|---|---|
| `CLAUDE_CODE_OAUTH_TOKEN` | Sleutel voor je Claude-abonnement. Nieuw maken: `claude setup-token`. |
| `GMAIL_APP_WACHTWOORD` | App-wachtwoord van Google (https://myaccount.google.com/apppasswords). |
| `MAIL_ADRES` | Je Gmail-adres: de mail gaat van en naar dit adres. |

## Handmatig starten

Op GitHub: tabblad **Actions**, **Editie maken**, **Run workflow**.

- Zonder vinkjes: de site opnieuw zetten (en een editie maken als die van nu er nog niet is).
- **Nu een editie maken:** meteen een editie, ook buiten de vaste tijden.
- **Alleen testen of de Claude-sleutel werkt:** antwoordt met "werkt" als alles goed is.

Op de pc:

- `python ai_nieuws.py --voorbeeld`: proefeditie in `voorbeeld\index.html`, niets wordt bewaard of gemaild.
- `python ai_nieuws.py --alleen-site --voorbeeld`: de site opnieuw maken uit de bewaarde edities, in `voorbeeld\`. Handig na een wijziging in `maak_site.py`, `stijl.css` of `site.js`.
- `python ai_nieuws.py --bronnen`: per bron hoeveel nieuwe berichten er zijn.

## Als het niet werkt

- **Geen nieuwe editie of geen mail:** kijk op GitHub onder Actions. Een rood kruis is een mislukte run; klik erop voor het logboek. GitHub mailt je ook bij een mislukte run.
- **Mail met `schrijven mislukt`:** Claude gaf een fout. Vaak is de sleutel verlopen of je limiet op. Maak een nieuwe sleutel met `claude setup-token` en zet die bij `CLAUDE_CODE_OAUTH_TOKEN`.
- **`Niet bereikbaar` onderaan een editie:** die bron deed het even niet. Gebeurt het elke keer, haal de bron dan uit `config.json`.
