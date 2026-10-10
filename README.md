# AI-nieuws

Een AI-nieuwssite met elke dag om 08:00 en 20:00 een nieuwe editie: wat er sinds de vorige editie in AI is gebeurd, vooral rond Claude. Per editie 5 tot 8 artikelen voor leken, één uitlegstuk en tot 15 korte berichten. Je krijgt een mail met de 5 belangrijkste en een link naar de rest.

Alles draait in de cloud bij GitHub. Je laptop mag uit. Claude schrijft de berichten via je eigen abonnement.

De site staat op https://ainieuwsvandaag.nl. Het domein is geregistreerd bij Mijndomein; daar wijzen de DNS-regels naar GitHub Pages (vier A-regels en vier AAAA-regels naar de adressen van GitHub, `www` naar `deepworkstudio.github.io`, en een TXT-regel waarmee GitHub weet dat het domein van ons is). In GitHub staat het domein onder Settings, Pages, Custom domain, met https verplicht. Het oude adres deepworkstudio.github.io/ai-nieuws stuurt vanzelf door.

## De site

- **Vandaag:** de nieuwste editie, opgezet zoals NOS en nu.nl. Vier ronde knoppen, groot genoeg voor je duim: Alles, Claude, ChatGPT en Quiz. Daarna een lange lijst met de onderwerpen (Groot nieuws, Uitleg, Modellen, Tools, Zo gebruik je AI, Nederland, Maatschappij, Kort nieuws) als tussenkopjes: per bericht een foto en de kop, de samenvatting staat in het artikel. Tik of klik ergens op een bericht en je gaat naar het hele artikel. Na het kiezen van Claude of ChatGPT staat boven de lijst hoeveel berichten je ziet. Op de telefoon blijft bovenaan één regel staan met Zoeken en Menu; alles wat je aantikt is minstens 48 pixels hoog (NN/g: minstens 1 bij 1 cm). Kort nieuws heeft geen eigen pagina: een pijltje (↗) laat zien dat die link naar de bron gaat. Met elke editie één tip onder "Probeer dit vandaag" en een nieuwsquiz van 3 vragen. Na de quiz kun je je score delen via WhatsApp, met een link naar dezelfde quiz.
- **Uitleg:** elke editie één uitlegstuk. Dat is geen nieuws, maar achtergrond bij een van de berichten, bijvoorbeeld wat een AI-agent is. Het is stap voor stap opgebouwd, want zo begrijpen leken ingewikkeld technieknieuws beter (Yaros 2006). Claude kiest een onderwerp dat nog niet eerder aan bod kwam.
- **Een pagina per bericht** (`artikel/`): een artikel van 2 tot 3 minuten lezen, met tussenkopjes, alle bronnen, een knop om te delen via WhatsApp, en onderaan "Lees ook": 3 tot 5 berichten, eerst over hetzelfde onderwerp en dan uit dezelfde editie. Het programma haalt de tekst van maximaal 3 bronnen op. Is er te weinig brontekst voor een echt artikel (minder dan 1.500 tekens, bijvoorbeeld door een betaalmuur), dan wordt het Kort nieuws in plaats van een opgevuld artikel.
- **Geschreven met AI:** bovenaan elke pagina en onder elke kop staat dat de berichten met AI geschreven zijn (dat moet sinds 2 augustus 2026 volgens de Europese AI-verordening, artikel 50). Het label linkt naar **Zo maken we dit** (`zo-maken-we-dit.html`): hoe we kiezen, wat er niet in komt en welke bronnen, automatisch uit `config.json`.
- **Delen:** elke pagina geeft WhatsApp en andere apps een kop, een korte tekst en een beeld voor de voorvertoning. Zonder bruikbaar beeld komt `deel.png`, het plaatje met de naam van de site.
- **Onderwerpen** (`onderwerp/`): alle berichten over bijvoorbeeld Claude Code of Mistral bij elkaar. Claude geeft elk bericht 1 tot 3 onderwerpen en hergebruikt bestaande namen.
- **De week:** elke zondagavond de 10 belangrijkste berichten van de week.
- **Archief, Begrippen en tips, Zoeken:** alle edities, alle uitgelegde woorden, en zoeken in alle berichten.

- **Altijd de nieuwste editie:** de servers van GitHub en je browser geven soms nog een tijdje een oude kopie, ook na F5. Daarom vraagt de site zelf `laatste.json` op, via een adres dat nog nooit gebruikt is. Dat gebeurt bij openen, bij terugkomen na slaapstand of vanuit een ander tabblad, en elke 5 minuten. Is er een nieuwere editie, dan laadt de voorpagina die vanzelf. Op andere pagina's, of als je ver naar beneden gescrold bent, komt onderaan een balk met de knop "Bekijk de nieuwe editie". De knop in de mail opent ook altijd die editie (`?e=` met de naam van de editie).

- **Licht en donker:** de site volgt de instelling van je telefoon of computer. Alle kleuren staan als namen bovenaan `stijl.css`; de donkere versie staat onderaan.
- **Als app:** via "Zet op beginscherm" opent de site met eigen naam en icoon (`manifest.webmanifest`, `icoon-*.png`). Er is bewust geen offline-opslag, zodat je altijd de nieuwste editie ziet.
- **Toegankelijk:** getest met axe (de meetlat voor de WCAG-richtlijn) op 8 pagina's, licht en donker, telefoon en laptop: geen fouten. Met Tab verschijnt eerst "Naar de inhoud".

Iedereen kan de site lezen. Wat iemand gelezen heeft, staat alleen in de eigen browser.

Vindbaar in Google: alleen de voorpagina, de artikelen (ook de uitlegstukken) en Zo maken we dit. Edities, onderwerpen, De week, het archief, Begrippen en tips en Zoeken herhalen dezelfde berichten in lijstjes; die krijgen `noindex`, zodat de site niet lijkt op een stapel automatisch gemaakte pagina's. Google mag hun links wel volgen. De vindbare pagina's hebben een vast adres (canonical) en staan in sitemap.xml; robots.txt wijst daarheen. Elk artikel vertelt Google in schema.org wat het is: NewsArticle, of Article voor een uitlegstuk, met AI-nieuws als schrijver. De code van Google Search Console staat in GOOGLE_VERIFICATIE in maak_site.py.

Statistieken: GoatCounter telt hoe vaak elke pagina bekeken wordt, zonder cookies en zonder bij te houden wie iemand is. Je ziet het op https://ainieuwsvandaag.goatcounter.com (inloggen met het Proton-adres). De teller (count.js) staat op de site zelf; vroeg.js zorgt dat een pagina telt zonder ?e= of ?t=, en dat het vanzelf herladen voor een nieuwe editie niet als tweede bezoek telt. Je eigen bezoeken tel je niet mee door op elk apparaat één keer https://ainieuwsvandaag.nl/#toggle-goatcounter te openen; je krijgt dan een melding. Nog een keer openen zet het tellen weer aan. Dat regelt vroeg.js, want site.js haalt het #-stuk weg voordat count.js het ziet.

## Beelden

Op foto's van nieuwssites en persbureaus rusten rechten, en daar kan een claim van komen. Daarom gebruikt de site alleen:

- het deelbeeld van een AI-bedrijf zelf (og:image, het plaatje dat je ook ziet als je een link in WhatsApp deelt), bijvoorbeeld van anthropic.com of openai.com;
- de kaart die GitHub voor elk project maakt.

Welke adressen meetellen, staat in `EIGEN_BEELDEN` in `maak_site.py`. Een beeld valt ook weg als het een logo is, smaller dan 600 pixels, niet ongeveer liggend, of hetzelfde als bij een ander bericht (dan is het het standaardplaatje van een site). Anders komt er een zwart blok met de naam van de bron. Oudere edities volgen dezelfde regel: hun beelden van nieuwssites verdwijnen bij de volgende keer dat de site gemaakt wordt. Werkt een beeld later niet meer, dan verschijnt het zwarte blok vanzelf.

## Hoe het werkt

1. De wekker op cron-job.org start `.github/workflows/editie.yml` om 07:55 en 19:55. Het maken duurt ongeveer 3 minuten, dus om 08:00 en 20:00 staat de editie klaar. Een run vanaf 10 minuten voor de vaste tijd hoort al bij de nieuwe editie. Om 08:35 en 20:35 komt een reservestart, en GitHub start zelf ook nog een paar keer per uur. Elke run haalt eerst de nieuwste versie op en kijkt welke editie er nu aan de beurt is. Bestaat die al, dan maakt de run alleen de site opnieuw. Zo komt er nooit een tweede editie of een tweede mail, ook niet als er twee startsignalen vlak na elkaar komen.
2. Ontbreekt de editie, dan haalt `ai_nieuws.py` het nieuws op, laat Claude kiezen en schrijven, maakt de site en mailt. Claude schrijft eerst de editie (koppen, samenvattingen, kort nieuws, quiz) en daarna elk artikel apart, vier tegelijk. Zo krijgt elk artikel zijn volle aandacht.
3. De editie, de begrippen en de lijst met gezien nieuws worden bewaard in deze repository. De site gaat naar GitHub Pages.

Mist de wekker een keer, dan komt de editie bij de reservestart om 08:35 of 20:35. Bovenaan de site staat dan "gemaakt om 08:36" in plaats van "08:00".

## Wat erin komt

- `criteria.md`: voor wie de site is, wat er in elke rubriek hoort, wat er niet in komt (geen reclame, geen onbekende tools) en de vier vaste vragen. Claude geeft zelf geen cijfer, maar beantwoordt per onderwerp vier vragen:
  - **nut:** wat heeft de lezer eraan? (0 tot 3)
  - **bereik:** hoeveel lezers raakt het? (0 tot 3)
  - **nieuw:** is het echt nieuw? (0 tot 2, met in één zin wat er nieuw is)
  - **bevestiging:** wie zegt het? (0 tot 2)

  Het programma telt de antwoorden op tot een score van 0 tot 10: 6 of hoger is een artikel, 5 is Kort nieuws. Het logboek van elke run laat per onderwerp de vier antwoorden zien, en de editie bewaart ze onder `keuze`.
- Bovenin `ai_nieuws.py`: hoe de berichten geschreven worden. `SCHRIJFREGELS` geldt voor alles (het belangrijkste eerst, stap voor stap uitleggen, beloningen onderweg, tussenkopjes als vraag, eindigen met iets wat je kunt doen). `SCHRIJF_OPDRACHT` is voor de editie, met de regels voor koppen: een bewering in plaats van een vraag, iets concreets, een sterk werkwoord en korte woorden (Kuiken e.a. 2017, Lagerwerf & Govaert 2021). `ARTIKEL_OPDRACHT` is voor het verhaal van elk artikel en `UITLEG_OPDRACHT` voor het uitlegstuk.
- `config.json`: de bronnen en de aantallen.

Pas een van deze bestanden aan, zet de wijziging op GitHub, en de volgende editie volgt de nieuwe regels.

## Instellingen in config.json

| Instelling | Betekenis |
|---|---|
| `site_url` | Het adres van de site, voor de knop in de mail. |
| `min_items`, `max_items` | Minste en hoogste aantal artikelen per editie, zonder het uitlegstuk. Standaard `5` en `8`. Zijn er te weinig artikelen, dan schuiven de beste korte berichten met genoeg brontekst door. |
| `max_kort` | Hoogste aantal korte berichten in Kort nieuws. Standaard `15`. |
| `minimale_score`, `minimale_score_kort` | Vanaf welke score een bericht een artikel wordt (`6`) of kort genoemd wordt (`5`). |
| `min_sterren` | Een tool (rubriek Nieuwe tools) met een GitHub-project met minder sterren valt weg. Standaard `500`. Tools van de AI-bedrijven zelf blijven altijd. Een verhaal of onderzoek met een link naar een klein project mag wel. |
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
