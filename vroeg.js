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
