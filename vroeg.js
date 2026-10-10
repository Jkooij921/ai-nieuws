// Laadt in de kop van elke pagina, vóór de beelden. Werkt een beeld niet (meer),
// dan komt er een zwart blok met de naam van de bron voor in de plaats.
document.addEventListener('error', function (gebeurtenis) {
  var beeld = gebeurtenis.target;
  if (!beeld || beeld.tagName !== 'IMG' || !beeld.hasAttribute('data-groot')) return;
  var tegel = document.createElement('div');
  tegel.className = 'tegel';
  tegel.style.aspectRatio = beeld.style.aspectRatio;
  var groot = document.createElement('span');
  groot.textContent = beeld.getAttribute('data-groot');
  var klein = document.createElement('small');
  klein.textContent = beeld.getAttribute('data-klein') || '';
  tegel.appendChild(groot);
  tegel.appendChild(klein);
  beeld.replaceWith(tegel);
}, true);

// Instellingen voor de teller (count.js van GoatCounter, zonder cookies). Een pagina telt zonder
// ?e= of ?t= in het adres, en index.html telt als de voorpagina. Herlaadt site.js de voorpagina
// voor een nieuwe editie, dan is dat geen nieuw bezoek en telt de nieuwe pagina niet mee.
window.goatcounter = {
  path: function () { return location.pathname.replace(/index\.html$/, '') || '/'; }
};
try {
  if (sessionStorage.getItem('ai-nieuws-niet-tellen')) {
    sessionStorage.removeItem('ai-nieuws-niet-tellen');
    window.goatcounter.no_onload = true;
  }
} catch (fout) { /* privévenster zonder geheugen: dan gewoon tellen */ }
