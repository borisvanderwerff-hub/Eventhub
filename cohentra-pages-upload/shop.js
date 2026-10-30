// Shop op cohentra.digital: haalt de gepubliceerde catalogus op bij de shop-API (alleen lezen, geen persoonsgegevens).
// Bestellen gebeurt in het klantenportaal; prijzen en rechten worden daar aan de serverzijde opnieuw bepaald.

const meta = (name, fallback) => document.querySelector(`meta[name="${name}"]`)?.content || fallback;
const SHOP_API = meta('shop-api', 'https://shop-api.cohentra.digital').replace(/\/+$/, '');
const PORTAL = meta('customer-portal', 'https://customer.cohentra.digital').replace(/\/+$/, '');

const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
const money = (amount, currency) => {
  try { return new Intl.NumberFormat('nl-NL', { style: 'currency', currency: String(currency).toUpperCase() }).format(amount / 100); }
  catch { return `${(amount / 100).toFixed(2)} ${String(currency).toUpperCase()}`; }
};
const INTERVALS = { day: ['dag', 'dagen'], week: ['week', 'weken'], month: ['maand', 'maanden'], year: ['jaar', 'jaar'] };
const period = (price) => {
  if (!price.interval) return 'eenmalig';
  const [one, many] = INTERVALS[price.interval] || [price.interval, price.interval];
  return price.interval_count > 1 ? `per ${price.interval_count} ${many}` : `per ${one}`;
};
const taxNote = (price) => (price.tax_behavior === 'inclusive' ? 'incl. btw' : price.tax_behavior === 'exclusive' ? 'excl. btw' : '');
const periodKey = (price) => (price.interval ? `${price.interval}:${price.interval_count}` : 'once');
const PERIOD_LABELS = { 'month:1': 'Maandelijks', 'year:1': 'Jaarlijks', once: 'Eenmalig' };

async function getJson(path) {
  const response = await fetch(SHOP_API + path, { headers: { Accept: 'application/json' } });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) { const error = new Error(data.error || 'De shop is tijdelijk niet bereikbaar.'); error.status = response.status; throw error; }
  return data;
}

function stateMessage(title, text, action = '') {
  return `<div class="shop-state"><h2>${escapeHtml(title)}</h2><p>${escapeHtml(text)}</p>${action}</div>`;
}

async function renderShopList() {
  const grid = document.getElementById('shopGrid');
  try {
    const { products } = await getJson('/api/public/shop/products');
    grid.innerHTML = products.length ? products.map((p) => `
      <article class="shop-card">
        <a class="shop-card-link" href="/product?p=${encodeURIComponent(p.slug)}">
          <div class="shop-card-media">${p.images[0] ? `<img src="${escapeHtml(p.images[0].url)}" alt="${escapeHtml(p.images[0].alt || p.name)}" loading="lazy">` : `<span aria-hidden="true">${escapeHtml(p.name.slice(0, 1))}</span>`}</div>
          <div class="shop-card-body">
            <h2>${escapeHtml(p.name)}</h2>
            <p>${escapeHtml(p.tagline || '')}</p>
            <div class="shop-card-foot">${p.from_price ? `<span><small>vanaf</small> <strong>${escapeHtml(money(p.from_price.unit_amount, p.from_price.currency))}</strong> <small>${escapeHtml(period(p.from_price))}</small></span>` : '<span></span>'}<span class="shop-card-cta">Bekijken <span aria-hidden="true">→</span></span></div>
          </div>
        </a>
      </article>`).join('') : stateMessage('Binnenkort beschikbaar', 'Er staan nog geen producten in de shop. Neem gerust contact op als je nu al interesse hebt.', '<a class="button button-primary" href="mailto:info@cohentra.digital?subject=Interesse%20in%20producten">Mail ons <span aria-hidden="true">↗</span></a>');
  } catch (error) {
    grid.innerHTML = stateMessage('De shop is even niet bereikbaar', 'Probeer het over een paar minuten opnieuw.', '<button type="button" class="button button-primary" onclick="location.reload()">Opnieuw laden</button>');
  } finally { grid.setAttribute('aria-busy', 'false'); }
}

function featureValue(plan, feature) {
  const value = plan.features[feature.key];
  if (feature.kind === 'flag') return value === true ? '<span class="shop-yes" aria-label="Inbegrepen">✓</span>' : '<span class="shop-no" aria-label="Niet inbegrepen">—</span>';
  if (value === undefined || value === null) return '<span class="shop-no" aria-label="Niet inbegrepen">—</span>';
  return escapeHtml(value === 'unlimited' ? 'Onbeperkt' : value);
}

function renderProduct(product, checkoutAvailable) {
  document.title = `${product.name} — Cohentra Digital`;
  const periods = [...new Set(product.plans.flatMap((plan) => plan.prices.map(periodKey)))];
  const recurring = periods.filter((p) => p !== 'once');
  let active = recurring.includes('month:1') ? 'month:1' : recurring[0] || 'once';
  const paragraphs = String(product.description || '').split(/\n\s*\n/).filter(Boolean).map((p) => `<p>${escapeHtml(p)}</p>`).join('');
  const gallery = product.images.length ? `<div class="shop-gallery"><figure class="shop-gallery-main"><img id="galleryMain" src="${escapeHtml(product.images[0].url)}" alt="${escapeHtml(product.images[0].alt || product.name)}"></figure>${product.images.length > 1 ? `<div class="shop-gallery-thumbs">${product.images.map((img, i) => `<button type="button" data-gallery="${i}" aria-label="Afbeelding ${i + 1} tonen"${i === 0 ? ' aria-current="true"' : ''}><img src="${escapeHtml(img.url)}" alt=""></button>`).join('')}</div>` : ''}</div>` : '';
  const limitRows = [
    ['Gebruikers', (plan) => (plan.max_users ? escapeHtml(plan.max_users) : 'Onbeperkt')],
    ['Apparaten / activaties', (plan) => (plan.max_activations !== null && plan.max_activations !== undefined ? escapeHtml(plan.max_activations) : 'Onbeperkt')],
    ['Proefperiode', (plan) => (plan.trial_days ? `${escapeHtml(plan.trial_days)} dagen` : '<span class="shop-no">—</span>')]
  ];
  const main = document.getElementById('productMain');
  main.innerHTML = `
    <section class="shop-hero shop-product-hero">
      <a class="text-link shop-back" href="/shop"><span aria-hidden="true">←</span> Alle producten</a>
      <div class="shop-product-head">
        <div><p class="eyebrow"><span class="eyebrow-dot"></span> Cohentra Digital</p><h1>${escapeHtml(product.name)}</h1><p class="hero-intro">${escapeHtml(product.tagline || '')}</p>${product.latest_release ? `<p class="shop-release">Nieuwste versie <strong>${escapeHtml(product.latest_release.version)}</strong>${product.latest_release.platform ? ` · ${escapeHtml(product.latest_release.platform)}` : ''}</p>` : ''}</div>
        ${gallery}
      </div>
    </section>
    ${paragraphs ? `<section class="shop-section section shop-about"><div class="section-kicker"><span>01</span><i></i><span>Over ${escapeHtml(product.name)}</span></div><div class="shop-description">${paragraphs}</div></section>` : ''}
    <section class="shop-section section" id="abonnementen" aria-labelledby="plansTitle">
      <div class="section-kicker"><span>${paragraphs ? '02' : '01'}</span><i></i><span id="plansTitle">Abonnementen</span></div>
      ${periods.length > 1 ? `<div class="shop-toggle" role="radiogroup" aria-label="Betaalperiode">${periods.map((p) => `<button type="button" role="radio" data-period="${p}">${escapeHtml(PERIOD_LABELS[p] || p.replace(':1', ''))}</button>`).join('')}</div>` : ''}
      ${checkoutAvailable ? '' : '<p class="shop-notice">Online bestellen is nog niet geopend. Neem contact op voor een offerte; we helpen je graag verder.</p>'}
      <div class="shop-plans" id="shopPlans"></div>
      ${product.features.length ? `<div class="shop-compare-wrap"><h2 class="shop-compare-title">Vergelijk de abonnementen</h2><div class="shop-compare-scroll"><table class="shop-compare"><thead><tr><th scope="col">Functie</th>${product.plans.map((plan) => `<th scope="col">${escapeHtml(plan.name)}</th>`).join('')}</tr></thead><tbody>${product.features.map((f) => `<tr><th scope="row">${escapeHtml(f.name)}${f.description ? `<small>${escapeHtml(f.description)}</small>` : ''}</th>${product.plans.map((plan) => `<td>${featureValue(plan, f)}</td>`).join('')}</tr>`).join('')}${limitRows.map(([label, fn]) => `<tr><th scope="row">${label}</th>${product.plans.map((plan) => `<td>${fn(plan)}</td>`).join('')}</tr>`).join('')}</tbody></table></div></div>` : ''}
      <p class="shop-fineprint">Abonnementen lopen door tot je opzegt; opzeggen kan in het klantenportaal en gaat in aan het einde van de lopende betaalperiode. Betalen gaat veilig via Stripe. Heb je vragen? Mail <a href="mailto:info@cohentra.digital">info@cohentra.digital</a>.</p>
    </section>`;

  const renderPlans = () => {
    document.querySelectorAll('[data-period]').forEach((b) => b.setAttribute('aria-checked', String(b.dataset.period === active)));
    const cards = product.plans.map((plan) => {
      const price = plan.prices.find((p) => periodKey(p) === active) || (active !== 'once' ? null : plan.prices[0]);
      if (!price) return '';
      const included = product.features.filter((f) => plan.features[f.key] !== undefined).map((f) => `<li>${escapeHtml(f.name)}${f.kind === 'limit' ? `: ${escapeHtml(plan.features[f.key] === 'unlimited' ? 'onbeperkt' : plan.features[f.key])}` : ''}</li>`).join('');
      const buy = checkoutAvailable
        ? `<a class="button button-primary" href="${PORTAL}/?buy=${encodeURIComponent(price.id)}">Kies ${escapeHtml(plan.name)} <span aria-hidden="true">→</span></a>`
        : `<a class="button button-primary" href="mailto:info@cohentra.digital?subject=${encodeURIComponent(`Offerte ${product.name} ${plan.name}`)}">Offerte aanvragen <span aria-hidden="true">↗</span></a>`;
      return `<article class="shop-plan"><h3>${escapeHtml(plan.name)}</h3><p class="shop-plan-desc">${escapeHtml(plan.description || '')}</p><p class="shop-price"><strong>${escapeHtml(money(price.unit_amount, price.currency))}</strong> <span>${escapeHtml(period(price))}${taxNote(price) ? `, ${taxNote(price)}` : ''}</span></p>${plan.trial_days ? `<p class="shop-trial">${escapeHtml(plan.trial_days)} dagen gratis proberen</p>` : ''}${included ? `<ul class="shop-plan-features">${included}</ul>` : ''}${buy}</article>`;
    }).filter(Boolean);
    document.getElementById('shopPlans').innerHTML = cards.length ? cards.join('') : stateMessage('Geen abonnement voor deze periode', 'Kies een andere betaalperiode.');
  };
  main.addEventListener('click', (event) => {
    const toggle = event.target.closest('[data-period]');
    if (toggle) { active = toggle.dataset.period; renderPlans(); return; }
    const thumb = event.target.closest('[data-gallery]');
    if (thumb) {
      const image = product.images[Number(thumb.dataset.gallery)];
      const big = document.getElementById('galleryMain');
      big.src = image.url; big.alt = image.alt || product.name;
      document.querySelectorAll('[data-gallery]').forEach((b) => b.toggleAttribute('aria-current', b === thumb));
    }
  });
  renderPlans();
}

async function renderProductPage() {
  const main = document.getElementById('productMain');
  const slug = new URLSearchParams(location.search).get('p') || '';
  try {
    if (!/^[a-z0-9-]{1,60}$/.test(slug)) throw Object.assign(new Error('Onbekend product'), { status: 404 });
    const { product, checkout_available: checkoutAvailable } = await getJson(`/api/public/shop/products/${slug}`);
    renderProduct(product, checkoutAvailable);
  } catch (error) {
    main.innerHTML = `<section class="shop-hero shop-product-hero"><a class="text-link shop-back" href="/shop"><span aria-hidden="true">←</span> Alle producten</a>${error.status === 404 ? stateMessage('Product niet gevonden', 'Dit product bestaat niet of is niet meer te koop.', '<a class="button button-primary" href="/shop">Naar de shop</a>') : stateMessage('De shop is even niet bereikbaar', 'Probeer het over een paar minuten opnieuw.', '<button type="button" class="button button-primary" onclick="location.reload()">Opnieuw laden</button>')}</section>`;
  } finally { main.setAttribute('aria-busy', 'false'); }
}

if (document.getElementById('shopGrid')) renderShopList();
if (document.getElementById('productMain')) renderProductPage();
