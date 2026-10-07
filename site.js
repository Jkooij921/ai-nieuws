// AI-nieuws: filters, gelezen-vinkjes, nieuwsquiz en zoeken.
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

  // Terug van een bericht: de browser toont de editie soms uit zijn geheugen, zonder dit script opnieuw te draaien.
  // Dan alsnog de vinkjes en de voortgang bijwerken.
  window.addEventListener('pageshow', function (gebeurtenis) { if (gebeurtenis.persisted) toonGelezen(); });

  // Twee filters die samenwerken: een onderwerp (de filterbalk) en een AI (de knoppen bovenaan).
  // Het onderwerp komt in het adres, zodat je het kunt delen; de gekozen AI wordt op dit apparaat onthouden.
  var MERKSLEUTEL = 'ai-nieuws-merk';
  var tabs = document.querySelectorAll('.tabs button');
  var merkknoppen = document.querySelectorAll('.merkknoppen button');
  var filter = 'alles';
  var merk = 'alle';
  try { merk = localStorage.getItem(MERKSLEUTEL) || 'alle'; } catch (fout) { /* privévenster */ }
  if (!document.querySelector('.merkknoppen button[data-merk="' + merk + '"]')) merk = 'alle';

  function past(el) { return merk === 'alle' || el.getAttribute('data-merk') === merk; }

  function toon(scrollen) {
    var tab = document.querySelector('.tabs button[data-filter="' + filter + '"]') ||
      document.querySelector('.tabs button[data-filter="alles"]');
    if (!tab) return;
    filter = tab.getAttribute('data-filter');
    var merkknop = document.querySelector('.merkknoppen button[data-merk="' + merk + '"]');
    tabs.forEach(function (t) { t.setAttribute('aria-pressed', t === tab ? 'true' : 'false'); });
    merkknoppen.forEach(function (k) { k.setAttribute('aria-pressed', k === merkknop ? 'true' : 'false'); });

    var rubriek = ['alles', 'kort', 'quiz'].indexOf(filter) < 0;
    var metMerk = merk !== 'alle';
    var alles = document.getElementById('alles');
    var gefilterd = document.getElementById('gefilterd');
    var kort = document.getElementById('kort');
    var quiz = document.getElementById('quiz');
    if (alles) alles.hidden = !(filter === 'alles' && !metMerk);
    if (quiz) quiz.hidden = !((filter === 'alles' && !metMerk) || filter === 'quiz');
    if (kort) {
      kort.hidden = !(filter === 'alles' || filter === 'kort');
      var korteZichtbaar = 0;
      kort.querySelectorAll('li').forEach(function (li) { li.hidden = !past(li); if (!li.hidden) korteZichtbaar++; });
      kort.querySelector('.geenkort').hidden = korteZichtbaar > 0;
    }
    if (gefilterd) {
      var toonGefilterd = rubriek || (filter === 'alles' && metMerk);
      gefilterd.hidden = !toonGefilterd;
      if (toonGefilterd) {
        var aantal = 0;
        gefilterd.querySelectorAll('.kaart').forEach(function (k) {
          var zichtbaar = (!rubriek || k.getAttribute('data-rubriek') === filter) && past(k);
          k.hidden = !zichtbaar;
          if (zichtbaar) aantal++;
        });
        var titel = [];
        var uitleg = '';
        if (metMerk) { titel.push(merkknop.getAttribute('data-naam')); uitleg = merkknop.getAttribute('data-uitleg'); }
        if (rubriek) {
          titel.push(tab.getAttribute('data-titel'));
          uitleg = tab.getAttribute('data-uitleg') + (metMerk ? ' Alleen over ' + merkknop.getAttribute('data-naam') + '.' : '');
        }
        gefilterd.querySelector('h2').textContent = titel.join(' · ');
        gefilterd.querySelector('.filteruitleg').textContent = uitleg;
        gefilterd.querySelector('.geenresultaat').hidden = aantal > 0;
      }
    }

    // De aantallen op de filterbalk tellen alleen wat bij de gekozen AI past.
    var kaarten = gefilterd ? gefilterd.querySelectorAll('.kaart') : [];
    var korte = kort ? kort.querySelectorAll('li') : [];
    tabs.forEach(function (t) {
      var f = t.getAttribute('data-filter');
      var getal = t.querySelector('span');
      if (!getal || f === 'quiz') return;
      var n = 0;
      if (f === 'alles' || f === 'kort') korte.forEach(function (li) { if (past(li)) n++; });
      if (f !== 'kort') kaarten.forEach(function (k) { if ((f === 'alles' || k.getAttribute('data-rubriek') === f) && past(k)) n++; });
      getal.textContent = n;
    });

    if (history.replaceState) history.replaceState(null, '', filter === 'alles' ? location.pathname : '#' + filter);
    if (scrollen) {
      var balk = document.querySelector('.tabbalk');
      if (balk && window.scrollY > balk.offsetTop) window.scrollTo({ top: balk.offsetTop, behavior: 'smooth' });
    }
  }

  tabs.forEach(function (t) {
    t.addEventListener('click', function () { filter = t.getAttribute('data-filter'); toon(true); });
  });
  document.querySelectorAll('[data-kies]').forEach(function (k) {
    k.addEventListener('click', function () { filter = k.getAttribute('data-kies'); toon(true); });
  });
  merkknoppen.forEach(function (k) {
    k.addEventListener('click', function () {
      merk = k.getAttribute('data-merk');
      try { localStorage.setItem(MERKSLEUTEL, merk); } catch (fout) { /* privévenster: dan niet onthouden */ }
      toon(false);
    });
  });
  if (tabs.length) {
    if (location.hash) filter = location.hash.slice(1);
    toon(false);
  }

  // Past de filterbalk niet op het scherm, dan vervaagt de rechterkant: een teken dat je kunt schuiven.
  var tabrij = document.querySelector('.tabs');
  if (tabrij) {
    var meer = function () {
      tabrij.toggleAttribute('data-meer', tabrij.scrollLeft + tabrij.clientWidth < tabrij.scrollWidth - 4);
    };
    tabrij.addEventListener('scroll', meer, { passive: true });
    window.addEventListener('resize', meer);
    meer();
  }

  // Een artikelpagina openen telt als gelezen.
  var artikel = document.querySelector('[data-artikel]');
  if (artikel) markeer(artikel.getAttribute('data-artikel'));

  // Nieuwsquiz. Na de laatste vraag: je score, en een knop om die te delen via WhatsApp,
  // met per vraag een groen of rood blokje zoals bij Wordle en een link naar dezelfde quiz.
  document.querySelectorAll('.quiz').forEach(function (quiz) {
    var aantal = +quiz.getAttribute('data-aantal');
    var beantwoord = 0;
    var goed = 0;
    var uitslag = [];
    quiz.querySelectorAll('.vraag').forEach(function (vraag, nummer) {
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
          uitslag[nummer] = keuze === juist;
          beantwoord++;
          if (beantwoord === aantal) {
            var score = quiz.querySelector('.score');
            score.textContent = 'Je score: ' + goed + ' van de ' + aantal + ' goed.';
            score.hidden = false;
            var blokjes = uitslag.map(function (g) { return g ? '🟩' : '🟥'; }).join('');
            var tekst = quiz.getAttribute('data-titel') + '\n' + blokjes + ' ' + goed + ' van de ' + aantal + ' goed\n' +
              'Kun jij het beter? ' + quiz.getAttribute('data-url');
            var deel = quiz.querySelector('.quizdeel');
            deel.querySelector('a').href = 'https://wa.me/?text=' + encodeURIComponent(tekst);
            deel.hidden = false;
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
