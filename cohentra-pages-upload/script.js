const items = document.querySelectorAll('.reveal');
if ('IntersectionObserver' in window) {
  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add('is-visible');
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.13, rootMargin: '0px 0px -35px 0px' });
  items.forEach((item) => observer.observe(item));
} else {
  items.forEach((item) => item.classList.add('is-visible'));
}

if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
  document.documentElement.style.scrollBehavior = 'auto';
  items.forEach((item) => item.classList.add('is-visible'));
}

// Pin one real EventHub screen while the product story advances through its chapters.
const storyChapters = document.querySelectorAll('.eventhub-chapter[data-stage]');
const storyScreens = document.querySelectorAll('.sticky-screen[data-screen]');
if (storyChapters.length && storyScreens.length && 'IntersectionObserver' in window) {
  const labels = { planning: 'Evenementen', control: 'Event Control', checkin: 'Check-in', dashboard: 'Live dashboard' };
  const numbers = { planning: '01', control: '02', checkin: '03', dashboard: '04' };
  const progress = { planning: '25%', control: '50%', checkin: '75%', dashboard: '100%' };
  const stageCount = document.querySelector('.sticky-stage-count b');
  const currentLabel = document.querySelector('.sticky-current-label');
  const progressFill = document.querySelector('.sticky-progress i');
  const stageObserver = new IntersectionObserver((entries) => {
    const current = entries.filter((entry) => entry.isIntersecting).sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
    if (!current) return;
    const stage = current.target.dataset.stage;
    storyChapters.forEach((chapter) => chapter.classList.toggle('is-active', chapter === current.target));
    storyScreens.forEach((screen) => screen.classList.toggle('is-active', screen.dataset.screen === stage));
    if (stageCount) stageCount.textContent = numbers[stage];
    if (currentLabel) currentLabel.textContent = labels[stage];
    if (progressFill) progressFill.style.width = progress[stage];
  }, { threshold: [0.18, 0.4, 0.62], rootMargin: '-30% 0px -30% 0px' });
  storyChapters.forEach((chapter) => stageObserver.observe(chapter));
}

// Keep the Cohentra home chapter rail in step with the section passing the viewport.
const homeRail = document.querySelector('.home-rail');
if (homeRail) {
  const railLinks = [...homeRail.querySelectorAll('[data-rail-section]')];
  const railSections = railLinks.map((link) => document.getElementById(link.dataset.railSection)).filter(Boolean);
  const setActiveRail = (id) => railLinks.forEach((link) => link.classList.toggle('is-active', link.dataset.railSection === id));
  const updateRailProgress = () => {
    const guideY = window.innerHeight * 0.48;
    const current = railSections.find((section) => {
      const rect = section.getBoundingClientRect();
      return rect.top <= guideY && rect.bottom > guideY;
    }) || railSections.reduce((closest, section) => {
      const distance = Math.abs(section.getBoundingClientRect().top - guideY);
      return !closest || distance < closest.distance ? { section, distance } : closest;
    }, null)?.section;
    if (current) setActiveRail(current.id);
    const max = document.documentElement.scrollHeight - window.innerHeight;
    const percent = max > 0 ? Math.min(100, Math.max(0, window.scrollY / max * 100)) : 0;
    homeRail.style.setProperty('--rail-progress', `${percent}%`);
    const active = Math.max(0, railLinks.findIndex((link) => link.classList.contains('is-active')));
    homeRail.style.setProperty('--rail-marker', `${active / Math.max(1, railLinks.length - 1) * 100}%`);
  };
  window.addEventListener('scroll', updateRailProgress, { passive: true });
  window.addEventListener('resize', updateRailProgress);
  updateRailProgress();
}

// Keep the gentle down-arrow in the first viewport, then clear it once scrolling begins.
const scrollHints = document.querySelectorAll('.scroll-cue');
if (scrollHints.length) {
  const updateScrollHints = () => scrollHints.forEach((hint) => hint.classList.toggle('is-dismissed', window.scrollY > 90));
  window.addEventListener('scroll', updateScrollHints, { passive: true });
  updateScrollHints();
}

const updateScrolledState = () => document.body.classList.toggle('has-scrolled', window.scrollY > 150);
window.addEventListener('scroll', updateScrolledState, { passive: true });
updateScrolledState();

const contactDialog = document.querySelector('#contactDialog');
const contactForm = document.querySelector('#contactForm');
if (contactDialog && contactForm) {
  const contactStatus = document.querySelector('#contactStatus');
  const contactSubmit = document.querySelector('#contactSubmit');
  const requestTypeField = contactForm.querySelector('[name="request_type"]');
  const openContactDialog = (requestType = '') => {
    requestTypeField.value = requestType || '';
    contactStatus.textContent = '';
    contactStatus.classList.remove('is-error', 'is-success');
    if (!contactDialog.open) contactDialog.showModal();
    contactForm.querySelector('[name="name"]').focus({ preventScroll: true });
  };

  document.querySelectorAll('[data-contact-open]').forEach((trigger) => {
    trigger.addEventListener('click', (event) => {
      event.preventDefault();
      openContactDialog(trigger.dataset.contactType || '');
    });
  });
  document.querySelector('#contactDialogClose').addEventListener('click', () => contactDialog.close());
  contactDialog.addEventListener('click', (event) => {
    if (event.target === contactDialog) contactDialog.close();
  });

  contactForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    contactStatus.textContent = '';
    contactStatus.classList.remove('is-error', 'is-success');
    contactSubmit.disabled = true;
    contactSubmit.dataset.originalLabel = contactSubmit.innerHTML;
    contactSubmit.textContent = 'Aanvraag versturen…';

    try {
      const response = await fetch(contactForm.action, {
        method: 'POST',
        mode: 'cors',
        credentials: 'omit',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(Object.fromEntries(new FormData(contactForm).entries()))
      });
      let result = {};
      try { result = await response.json(); } catch {}
      if (!response.ok) throw new Error(result.error || 'Je aanvraag kon niet worden verstuurd.');
      contactForm.reset();
      contactStatus.textContent = `Bedankt. Je aanvraag ${result.reference} staat als Websiteformulier-ticket bij Cohentra Support. We reageren via e-mail.`;
      contactStatus.classList.add('is-success');
    } catch (error) {
      contactStatus.textContent = error.message || 'Versturen lukt nu niet. Mail ons op info@cohentra.digital.';
      contactStatus.classList.add('is-error');
    } finally {
      contactSubmit.disabled = false;
      contactSubmit.innerHTML = contactSubmit.dataset.originalLabel;
      delete contactSubmit.dataset.originalLabel;
    }
  });

  if (window.location.hash === '#contact') openContactDialog();
}
