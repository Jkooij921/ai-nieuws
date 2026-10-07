// AI-nieuws: filters, Lees meer, gelezen-vinkjes, nieuwsquiz en zoeken.
// Wat je gelezen hebt, staat alleen in de localStorage van je eigen browser.
(function () {
  var SLEUTEL = 'ai-nieuws-gelezen';

  function leesGelezen() {
    try { return JSON.parse(localStorage.getItem(SLEUTEL) || '{}'); } catch (fout) { return {}; }
  }

  function markeer(id) {
    var gelezen = leesGelezen();
    if (!gelezen[id]) {
      gelezen[id] = Date.now();
      try { localStorage.setItem(SLEUTEL, JSON.stringify(gelezen)); } catch (fout) { /* privévenster: dan maar niet onthouden */ }
    }
    toonGelezen();
  }

  function toonGelezen() {
    var gelezen = leesGelezen();
    document.querySelectorAll('[data-id]').forEach(function (el) {
      var vink = el.querySelector('.gelezen');
      if (vink) vink.hidden = !gelezen[el.getAttribute('data-id')];
    });
    var balk = document.querySelector('.tabbalk');
    if (!balk) return;
    var ids = (balk.getAttribute('data-ids') || '').split(',').filter(Boolean);
    var aantal = ids.filter(function (id) { return gelezen[id]; }).length;
    var procent = ids.length ? Math.round((aantal / ids.length) * 100) : 0;
    balk.querySelector('.voortgangtekst').textContent = aantal + ' van ' + ids.length + ' gelezen';
    var staaf = balk.querySelector('.balk');
    staaf.setAttribute('aria-valuenow', procent);
    staaf.firstElementChild.style.width = procent + '%';
    var klaar = document.querySelector('.klaar');
    if (klaar) klaar.hidden = !(ids.length && aantal === ids.length);
  }

  // Lees meer: klapt de uitleg open en telt het bericht als gelezen.
  document.addEventListener('click', function (gebeurtenis) {
    var knop = gebeurtenis.target.closest('.leesmeer');
    if (!knop) return;
    var kaart = knop.closest('.kaart');
    var open = knop.getAttribute('aria-expanded') !== 'true';
    kaart.querySelector('.meer').hidden = !open;
    knop.setAttribute('aria-expanded', open ? 'true' : 'false');
    knop.textContent = open ? 'Minder tonen' : 'Lees meer';
    if (open) markeer(kaart.getAttribute('data-id'));
  });

  // Filters op onderwerp. Het gekozen filter komt in het adres, zodat je het kunt delen.
  var tabs = document.querySelectorAll('.tabs button');
  function kies(filter, scrollen) {
    var knop = document.querySelector('.tabs button[data-filter="' + filter + '"]');
    if (!knop) { filter = 'alles'; knop = document.querySelector('.tabs button[data-filter="alles"]'); }
    if (!knop) return;
    tabs.forEach(function (t) { t.setAttribute('aria-pressed', t === knop ? 'true' : 'false'); });
    var rubriek = ['alles', 'kort', 'quiz'].indexOf(filter) < 0;
    var alles = document.getElementById('alles');
    var gefilterd = document.getElementById('gefilterd');
    var kort = document.getElementById('kort');
    var quiz = document.getElementById('quiz');
    if (alles) alles.hidden = filter !== 'alles';
    if (kort) kort.hidden = !(filter === 'alles' || filter === 'kort');
    if (quiz) quiz.hidden = !(filter === 'alles' || filter === 'quiz');
    if (gefilterd) {
      gefilterd.hidden = !rubriek;
      if (rubriek) {
        gefilterd.querySelector('h2').textContent = knop.getAttribute('data-titel');
        gefilterd.querySelector('.filteruitleg').textContent = knop.getAttribute('data-uitleg');
        gefilterd.querySelectorAll('.kaart').forEach(function (k) { k.hidden = k.getAttribute('data-rubriek') !== filter; });
      }
    }
    if (history.replaceState) history.replaceState(null, '', filter === 'alles' ? location.pathname : '#' + filter);
    if (scrollen) {
      var balk = document.querySelector('.tabbalk');
      if (balk && window.scrollY > balk.offsetTop) window.scrollTo({ top: balk.offsetTop, behavior: 'smooth' });
    }
  }
  tabs.forEach(function (t) { t.addEventListener('click', function () { kies(t.getAttribute('data-filter'), true); }); });
  document.querySelectorAll('[data-kies]').forEach(function (k) {
    k.addEventListener('click', function () { kies(k.getAttribute('data-kies'), true); });
  });
  if (tabs.length && location.hash) kies(location.hash.slice(1), false);

  // Een artikelpagina openen telt als gelezen.
  var artikel = document.querySelector('[data-artikel]');
  if (artikel) markeer(artikel.getAttribute('data-artikel'));

  // Nieuwsquiz
  document.querySelectorAll('.quiz').forEach(function (quiz) {
    var aantal = +quiz.getAttribute('data-aantal');
    var beantwoord = 0;
    var goed = 0;
    quiz.querySelectorAll('.vraag').forEach(function (vraag) {
      var juist = +vraag.getAttribute('data-goed');
      var knoppen = vraag.querySelectorAll('.opties button');
      knoppen.forEach(function (knop) {
        knop.addEventListener('click', function () {
          var keuze = +knop.getAttribute('data-i');
          knoppen.forEach(function (b) { b.disabled = true; });
          knoppen[juist].classList.add('goed');
          var antwoord = vraag.querySelector('.antwoord');
          if (keuze === juist) {
            goed++;
            antwoord.textContent = 'Goed.';
          } else {
            knop.classList.add('fout');
            antwoord.textContent = 'Helaas. Het goede antwoord staat in het groen.';
          }
          antwoord.hidden = false;
          vraag.querySelector('.toelichting').hidden = false;
          beantwoord++;
          if (beantwoord === aantal) {
            var score = quiz.querySelector('.score');
            score.textContent = 'Je score: ' + goed + ' van de ' + aantal + ' goed.';
            score.hidden = false;
          }
        });
      });
    });
  });

  // Begrippen doorzoeken
  var begripzoek = document.getElementById('begripzoek');
  if (begripzoek) {
    begripzoek.addEventListener('input', function () {
      var vraag = begripzoek.value.toLowerCase();
      document.querySelectorAll('.begrip').forEach(function (b) {
        b.hidden = vraag && b.textContent.toLowerCase().indexOf(vraag) < 0;
      });
    });
  }

  // Zoeken in alle berichten
  var zoekveld = document.getElementById('zoekveld');
  if (zoekveld) {
    var index = null;
    var uitleg = document.getElementById('zoekuitleg');
    var lijst = document.getElementById('zoekresultaten');
    var zoek = function () {
      lijst.textContent = '';
      if (!index) return;
      var woorden = zoekveld.value.toLowerCase().split(/\s+/).filter(function (w) { return w.length > 1; });
      if (!woorden.length) { uitleg.textContent = 'Typ minstens twee letters.'; return; }
      var gevonden = index.filter(function (item) {
        var tekst = (item.kop + ' ' + item.samenvatting + ' ' + item.onderwerpen.join(' ')).toLowerCase();
        return woorden.every(function (w) { return tekst.indexOf(w) >= 0; });
      });
      uitleg.textContent = gevonden.length + (gevonden.length === 1 ? ' bericht gevonden' : ' berichten gevonden');
      gevonden.slice(0, 50).forEach(function (item) {
        var rij = document.createElement('li');
        var meta = document.createElement('div');
        var link = document.createElement('a');
        var tekst = document.createElement('p');
        meta.className = 'meta';
        meta.textContent = item.datum + ' · ' + item.rubriek;
        link.href = 'artikel/' + item.id + '.html';
        link.textContent = item.kop;
        tekst.textContent = item.samenvatting;
        rij.appendChild(meta);
        rij.appendChild(link);
        rij.appendChild(tekst);
        lijst.appendChild(rij);
      });
    };
    var vraag = new URLSearchParams(location.search).get('q');
    if (vraag) zoekveld.value = vraag;
    zoekveld.addEventListener('input', zoek);
    fetch('zoek.json')
      .then(function (r) { return r.json(); })
      .then(function (data) { index = data; zoek(); })
      .catch(function () { uitleg.textContent = 'Zoeken lukt nu niet. Probeer het later opnieuw.'; });
  }

  toonGelezen();
})();
