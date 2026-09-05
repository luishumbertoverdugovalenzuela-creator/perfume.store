(function () {
  function initReveal() {
    var els = document.querySelectorAll('.ps-reveal');
    if (!els.length) return;
    if (!('IntersectionObserver' in window)) {
      els.forEach(function (el) { el.classList.add('ps-visible'); });
      return;
    }
    var io = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            var delay = entry.target.getAttribute('data-ps-delay') || 0;
            setTimeout(function () { entry.target.classList.add('ps-visible'); }, Number(delay));
            io.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.14, rootMargin: '0px 0px -60px 0px' }
    );
    els.forEach(function (el) { io.observe(el); });
  }

  function initMarquee() {
    document.querySelectorAll('[data-ps-marquee]').forEach(function (track) {
      if (track.dataset.psMarqueeInit) return;
      track.dataset.psMarqueeInit = '1';
      track.innerHTML += track.innerHTML;
      var speed = Number(track.getAttribute('data-ps-speed') || 32);
      track.style.animationDuration = speed + 's';
    });
  }

  function initFaq() {
    document.querySelectorAll('[data-ps-faq-item]').forEach(function (item) {
      var trigger = item.querySelector('[data-ps-faq-trigger]');
      if (!trigger || trigger.dataset.psBound) return;
      trigger.dataset.psBound = '1';
      trigger.addEventListener('click', function () {
        var isOpen = item.getAttribute('data-open') === 'true';
        item.closest('[data-ps-faq]').querySelectorAll('[data-ps-faq-item]').forEach(function (other) {
          other.setAttribute('data-open', 'false');
        });
        item.setAttribute('data-open', isOpen ? 'false' : 'true');
      });
    });
  }

  function initProductGallery() {
    document.querySelectorAll('[data-ps-gallery]').forEach(function (gallery) {
      if (gallery.dataset.psBound) return;
      gallery.dataset.psBound = '1';
      var main = gallery.querySelector('[data-ps-gallery-main]');
      gallery.querySelectorAll('[data-ps-gallery-thumb]').forEach(function (thumb) {
        thumb.addEventListener('click', function () {
          var full = thumb.getAttribute('data-full');
          if (main && full) {
            main.style.transition = 'opacity 0.22s ease, transform 0.22s ease';
            main.style.opacity = '0';
            main.style.transform = 'scale(0.97)';
            setTimeout(function () {
              main.src = full;
              main.style.opacity = '1';
              main.style.transform = 'scale(1)';
            }, 180);
          }
          gallery.querySelectorAll('[data-ps-gallery-thumb]').forEach(function (t) { t.classList.remove('is-active'); });
          thumb.classList.add('is-active');
        });
      });
    });
  }

  function initTilt() {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    if (window.matchMedia('(hover: none)').matches) return;
    document.querySelectorAll('[data-ps-tilt]').forEach(function (card) {
      if (card.dataset.psTiltBound) return;
      card.dataset.psTiltBound = '1';
      var media = card.querySelector('[data-ps-tilt-target]') || card;
      card.addEventListener('mousemove', function (e) {
        var rect = card.getBoundingClientRect();
        var px = (e.clientX - rect.left) / rect.width - 0.5;
        var py = (e.clientY - rect.top) / rect.height - 0.5;
        media.style.transform = 'perspective(700px) rotateX(' + (py * -10).toFixed(2) + 'deg) rotateY(' + (px * 10).toFixed(2) + 'deg) scale(1.04)';
      });
      card.addEventListener('mouseleave', function () {
        media.style.transform = '';
      });
    });
  }

  function initVariantPicker() {
    document.querySelectorAll('[data-ps-product]').forEach(function (root) {
      if (root.dataset.psBound) return;
      root.dataset.psBound = '1';
      var dataEl = root.querySelector('[data-ps-variants]');
      if (!dataEl) return;
      var variants;
      try { variants = JSON.parse(dataEl.textContent); } catch (e) { return; }

      var idInput = root.querySelector('[data-ps-variant-id]');
      var priceEl = root.querySelector('[data-ps-price]');
      var comparePriceEl = root.querySelector('[data-ps-compare-price]');
      var submitBtn = root.querySelector('[data-ps-submit]');
      var submitText = root.querySelector('[data-ps-submit-text]');
      var selects = root.querySelectorAll('[data-ps-option-select]');

      function money(cents) {
        return (cents / 100).toLocaleString(document.documentElement.lang || 'es-MX', {
          style: 'currency',
          currency: (window.Shopify && Shopify.currency && Shopify.currency.active) || 'MXN'
        });
      }

      function findVariant() {
        var values = Array.prototype.map.call(selects, function (s) { return s.value; });
        return variants.find(function (v) {
          return v.options.every(function (opt, i) { return opt === values[i]; });
        });
      }

      function update() {
        var variant = findVariant();
        if (!variant) {
          if (submitBtn) submitBtn.disabled = true;
          if (submitText) submitText.textContent = submitText.getAttribute('data-unavailable-text') || submitText.textContent;
          return;
        }
        if (idInput) idInput.value = variant.id;
        if (priceEl) priceEl.textContent = money(variant.price);
        if (comparePriceEl) {
          if (variant.compare_at_price && variant.compare_at_price > variant.price) {
            comparePriceEl.textContent = money(variant.compare_at_price);
            comparePriceEl.hidden = false;
          } else {
            comparePriceEl.hidden = true;
          }
        }
        if (submitBtn) {
          submitBtn.disabled = !variant.available;
        }
        if (submitText) {
          submitText.textContent = variant.available
            ? submitText.getAttribute('data-add-text')
            : submitText.getAttribute('data-unavailable-text');
        }
      }

      selects.forEach(function (select) { select.addEventListener('change', update); });
      update();
    });
  }

  function initAddToCartPulse() {
    document.querySelectorAll('[data-ps-submit]').forEach(function (btn) {
      if (btn.dataset.psPulseBound) return;
      btn.dataset.psPulseBound = '1';
      btn.addEventListener('click', function () {
        btn.classList.remove('ps-pulse');
        void btn.offsetWidth;
        btn.classList.add('ps-pulse');
      });
    });
  }

  function initAll() {
    initReveal();
    initMarquee();
    initFaq();
    initProductGallery();
    initVariantPicker();
    initTilt();
    initAddToCartPulse();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAll);
  } else {
    initAll();
  }
})();
