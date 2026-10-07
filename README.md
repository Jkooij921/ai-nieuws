# AI-nieuws

Een AI-nieuwssite met elke dag om 08:00 en 20:00 een nieuwe editie: wat er sinds de vorige editie in AI is gebeurd, vooral rond Claude. Per editie ongeveer 12 berichten met uitleg voor leken en 10 tot 15 korte berichten. Je krijgt een mail met de 5 belangrijkste en een link naar de rest.

Alles draait in de cloud bij GitHub. Je laptop mag uit. Claude schrijft de berichten via je eigen abonnement.

## De site

- **Vandaag:** de nieuwste editie, in rubrieken: Het grote nieuws, Nieuwe modellen, Nieuwe tools, Zo gebruik je AI, Onderzoek en regels, en Snel nog even. Met elke editie één tip onder "Probeer dit vandaag".
- **Archief:** alle eerdere edities.
- **Leren:** alle woorden die ooit zijn uitgelegd, met een zoekvak, en alle tips.

Iedereen met de link kan de site lezen. Zoekmachines nemen hem niet op.

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
| `bronnen` | De lijst met bronnen. `"filter": true` laat alleen berichten met een AI-woord door. |

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
- `python ai_nieuws.py --bronnen`: per bron hoeveel nieuwe berichten er zijn.

## Als het niet werkt

- **Geen nieuwe editie of geen mail:** kijk op GitHub onder Actions. Een rood kruis is een mislukte run; klik erop voor het logboek. GitHub mailt je ook bij een mislukte run.
- **Mail met `schrijven mislukt`:** Claude gaf een fout. Vaak is de sleutel verlopen of je limiet op. Maak een nieuwe sleutel met `claude setup-token` en zet die bij `CLAUDE_CODE_OAUTH_TOKEN`.
- **`Niet bereikbaar` onderaan een editie:** die bron deed het even niet. Gebeurt het elke keer, haal de bron dan uit `config.json`.
