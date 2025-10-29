/**
 * OUBON SHOP - Premium Theme JavaScript
 * Handles interactions, animations, and dynamic features
 */

(function() {
  'use strict';

  // ════════════════════════════════════════════════════════════
  // UTILITY FUNCTIONS
  // ════════════════════════════════════════════════════════════

  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => document.querySelectorAll(selector);

  const debounce = (func, wait) => {
    let timeout;
    return function executedFunction(...args) {
      const later = () => {
        clearTimeout(timeout);
        func(...args);
      };
      clearTimeout(timeout);
      timeout = setTimeout(later, wait);
    };
  };

  // ════════════════════════════════════════════════════════════
  // HEADER SCROLL EFFECT
  // ════════════════════════════════════════════════════════════

  const initHeaderScroll = () => {
    const header = $('.site-header');
    if (!header) return;

    let lastScroll = 0;

    const handleScroll = () => {
      const currentScroll = window.pageYOffset;

      if (currentScroll > 100) {
        header.classList.add('scrolled');
      } else {
        header.classList.remove('scrolled');
      }

      lastScroll = currentScroll;
    };

    window.addEventListener('scroll', debounce(handleScroll, 10));
  };

  // ════════════════════════════════════════════════════════════
  // MOBILE MENU
  // ════════════════════════════════════════════════════════════

  const initMobileMenu = () => {
    const menuToggle = $('.mobile-menu-toggle');
    const nav = $('.site-nav');

    if (!menuToggle || !nav) return;

    menuToggle.addEventListener('click', () => {
      nav.classList.toggle('active');
      menuToggle.classList.toggle('active');
      document.body.classList.toggle('menu-open');
    });

    // Close menu when clicking nav links
    const navLinks = $$('.nav-link');
    navLinks.forEach(link => {
      link.addEventListener('click', () => {
        nav.classList.remove('active');
        menuToggle.classList.remove('active');
        document.body.classList.remove('menu-open');
      });
    });

    // Close menu on escape key
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && nav.classList.contains('active')) {
        nav.classList.remove('active');
        menuToggle.classList.remove('active');
        document.body.classList.remove('menu-open');
      }
    });
  };

  // ════════════════════════════════════════════════════════════
  // SCROLL REVEAL ANIMATIONS
  // ════════════════════════════════════════════════════════════

  const initScrollReveal = () => {
    const reveals = $$('.scroll-reveal');
    if (reveals.length === 0) return;

    const revealObserver = new IntersectionObserver(
      (entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            entry.target.classList.add('revealed');
            revealObserver.unobserve(entry.target);
          }
        });
      },
      {
        threshold: 0.2,
        rootMargin: '0px 0px -50px 0px'
      }
    );

    reveals.forEach(el => revealObserver.observe(el));
  };

  // ════════════════════════════════════════════════════════════
  // PRODUCT QUANTITY CONTROLS
  // ════════════════════════════════════════════════════════════

  const initQuantityControls = () => {
    const quantityInputs = $$('.quantity-input');

    quantityInputs.forEach(container => {
      const decreaseBtn = container.querySelector('[data-action="decrease"]');
      const increaseBtn = container.querySelector('[data-action="increase"]');
      const input = container.querySelector('.quantity-value');

      if (!decreaseBtn || !increaseBtn || !input) return;

      decreaseBtn.addEventListener('click', () => {
        const currentValue = parseInt(input.value) || 1;
        if (currentValue > 1) {
          input.value = currentValue - 1;
          input.dispatchEvent(new Event('change', { bubbles: true }));
        }
      });

      increaseBtn.addEventListener('click', () => {
        const currentValue = parseInt(input.value) || 1;
        const max = parseInt(input.max) || 999;
        if (currentValue < max) {
          input.value = currentValue + 1;
          input.dispatchEvent(new Event('change', { bubbles: true }));
        }
      });

      input.addEventListener('change', () => {
        const value = parseInt(input.value) || 1;
        const min = parseInt(input.min) || 1;
        const max = parseInt(input.max) || 999;

        if (value < min) input.value = min;
        if (value > max) input.value = max;
      });
    });
  };

  // ════════════════════════════════════════════════════════════
  // ADD TO CART
  // ════════════════════════════════════════════════════════════

  const initAddToCart = () => {
    const addToCartForms = $$('form[action="/cart/add"]');

    addToCartForms.forEach(form => {
      form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const submitBtn = form.querySelector('[type="submit"]');
        const originalText = submitBtn.textContent;

        // Show loading state
        submitBtn.disabled = true;
        submitBtn.textContent = 'Adding...';

        try {
          const formData = new FormData(form);

          const response = await fetch('/cart/add.js', {
            method: 'POST',
            body: formData
          });

          if (!response.ok) throw new Error('Failed to add to cart');

          const data = await response.json();

          // Success state
          submitBtn.textContent = 'Added! ✓';
          submitBtn.classList.add('success');

          // Update cart count
          updateCartCount();

          // Show cart drawer/notification (optional)
          showCartNotification(data);

          // Reset button after 2 seconds
          setTimeout(() => {
            submitBtn.disabled = false;
            submitBtn.textContent = originalText;
            submitBtn.classList.remove('success');
          }, 2000);

        } catch (error) {
          console.error('Add to cart error:', error);

          // Error state
          submitBtn.textContent = 'Error - Try Again';
          submitBtn.classList.add('error');

          setTimeout(() => {
            submitBtn.disabled = false;
            submitBtn.textContent = originalText;
            submitBtn.classList.remove('error');
          }, 2000);
        }
      });
    });
  };

  // ════════════════════════════════════════════════════════════
  // UPDATE CART COUNT
  // ════════════════════════════════════════════════════════════

  const updateCartCount = async () => {
    try {
      const response = await fetch('/cart.js');
      const cart = await response.json();

      const cartCount = $('.cart-count');
      if (cartCount) {
        cartCount.setAttribute('data-count', cart.item_count);

        // Bounce animation
        cartCount.style.animation = 'none';
        setTimeout(() => {
          cartCount.style.animation = 'bounce 0.5s ease';
        }, 10);
      }
    } catch (error) {
      console.error('Failed to update cart count:', error);
    }
  };

  // ════════════════════════════════════════════════════════════
  // CART NOTIFICATION
  // ════════════════════════════════════════════════════════════

  const showCartNotification = (item) => {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = 'cart-notification fade-in';
    notification.innerHTML = `
      <div class="cart-notification-content">
        <p><strong>${item.product_title}</strong> added to cart</p>
        <a href="/cart" class="btn btn-primary btn-small">View Cart</a>
      </div>
    `;

    document.body.appendChild(notification);

    // Remove after 4 seconds
    setTimeout(() => {
      notification.style.animation = 'fadeOut 0.3s ease';
      setTimeout(() => notification.remove(), 300);
    }, 4000);
  };

  // ════════════════════════════════════════════════════════════
  // LAZY LOADING IMAGES
  // ════════════════════════════════════════════════════════════

  const initLazyLoading = () => {
    const images = $$('img[loading="lazy"]');

    if ('loading' in HTMLImageElement.prototype) {
      // Native lazy loading supported
      return;
    }

    // Fallback for browsers that don't support native lazy loading
    const imageObserver = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const img = entry.target;
          if (img.dataset.src) {
            img.src = img.dataset.src;
            img.removeAttribute('data-src');
          }
          imageObserver.unobserve(img);
        }
      });
    });

    images.forEach(img => imageObserver.observe(img));
  };

  // ════════════════════════════════════════════════════════════
  // SEARCH FUNCTIONALITY
  // ════════════════════════════════════════════════════════════

  const initSearch = () => {
    const searchToggle = $('.search-toggle');
    const searchModal = $('.search-modal');
    const searchInput = $('.search-input');
    const searchClose = $('.search-close');

    if (!searchToggle || !searchModal) return;

    searchToggle.addEventListener('click', () => {
      searchModal.classList.add('active');
      searchInput?.focus();
    });

    searchClose?.addEventListener('click', () => {
      searchModal.classList.remove('active');
    });

    // Close on escape
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && searchModal.classList.contains('active')) {
        searchModal.classList.remove('active');
      }
    });

    // Close on backdrop click
    searchModal?.addEventListener('click', (e) => {
      if (e.target === searchModal) {
        searchModal.classList.remove('active');
      }
    });

    // Live search (debounced)
    if (searchInput) {
      const performSearch = debounce(async (query) => {
        if (query.length < 2) return;

        try {
          const response = await fetch(`/search/suggest.json?q=${encodeURIComponent(query)}&resources[type]=product`);
          const data = await response.json();
          displaySearchResults(data);
        } catch (error) {
          console.error('Search error:', error);
        }
      }, 300);

      searchInput.addEventListener('input', (e) => {
        performSearch(e.target.value);
      });
    }
  };

  const displaySearchResults = (data) => {
    const resultsContainer = $('.search-results');
    if (!resultsContainer) return;

    if (!data.resources || !data.resources.results || !data.resources.results.products) {
      resultsContainer.innerHTML = '<p>No results found</p>';
      return;
    }

    const products = data.resources.results.products;

    resultsContainer.innerHTML = products.map(product => `
      <a href="${product.url}" class="search-result-item">
        ${product.featured_image ? `<img src="${product.featured_image.url}" alt="${product.title}">` : ''}
        <div>
          <h4>${product.title}</h4>
          <p>${product.price ? `$${(product.price / 100).toFixed(2)}` : ''}</p>
        </div>
      </a>
    `).join('');
  };

  // ════════════════════════════════════════════════════════════
  // NEWSLETTER SIGNUP
  // ════════════════════════════════════════════════════════════

  const initNewsletter = () => {
    const forms = $$('.newsletter-form');

    forms.forEach(form => {
      form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const emailInput = form.querySelector('input[type="email"]');
        const submitBtn = form.querySelector('[type="submit"]');
        const email = emailInput.value;

        if (!email) return;

        // Show loading
        submitBtn.disabled = true;
        submitBtn.textContent = 'Subscribing...';

        try {
          // Replace with your newsletter service endpoint
          // This is a placeholder - integrate with Klaviyo, Mailchimp, etc.
          const response = await fetch('/contact', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, form_type: 'newsletter' })
          });

          if (response.ok) {
            // Success
            form.innerHTML = '<p class="success-message">✓ Thanks for subscribing!</p>';
          } else {
            throw new Error('Subscription failed');
          }
        } catch (error) {
          console.error('Newsletter error:', error);
          submitBtn.textContent = 'Try Again';
          submitBtn.disabled = false;
        }
      });
    });
  };

  // ════════════════════════════════════════════════════════════
  // SMOOTH SCROLL
  // ════════════════════════════════════════════════════════════

  const initSmoothScroll = () => {
    const links = $$('a[href^="#"]');

    links.forEach(link => {
      link.addEventListener('click', (e) => {
        const href = link.getAttribute('href');
        if (href === '#') return;

        const target = $(href);
        if (!target) return;

        e.preventDefault();

        const headerHeight = $('.site-header')?.offsetHeight || 0;
        const targetPosition = target.offsetTop - headerHeight - 20;

        window.scrollTo({
          top: targetPosition,
          behavior: 'smooth'
        });
      });
    });
  };

  // ════════════════════════════════════════════════════════════
  // PERFORMANCE OPTIMIZATIONS
  // ════════════════════════════════════════════════════════════

  // Prefetch hover links
  const initPrefetch = () => {
    const links = $$('a[href^="/"]');

    links.forEach(link => {
      link.addEventListener('mouseenter', () => {
        const url = link.href;
        const prefetchLink = document.createElement('link');
        prefetchLink.rel = 'prefetch';
        prefetchLink.href = url;
        document.head.appendChild(prefetchLink);
      }, { once: true });
    });
  };

  // ════════════════════════════════════════════════════════════
  // ACCESSIBILITY
  // ════════════════════════════════════════════════════════════

  const initAccessibility = () => {
    // Skip to main content link
    const skipLink = $('#skip-to-main');
    if (skipLink) {
      skipLink.addEventListener('click', (e) => {
        e.preventDefault();
        const main = $('#main-content');
        if (main) {
          main.setAttribute('tabindex', '-1');
          main.focus();
        }
      });
    }

    // Keyboard navigation for dropdowns
    const dropdowns = $$('[data-dropdown]');
    dropdowns.forEach(dropdown => {
      const trigger = dropdown.querySelector('[data-dropdown-trigger]');
      const menu = dropdown.querySelector('[data-dropdown-menu]');

      if (!trigger || !menu) return;

      trigger.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          menu.classList.toggle('active');
        }
        if (e.key === 'Escape') {
          menu.classList.remove('active');
        }
      });
    });
  };

  // ════════════════════════════════════════════════════════════
  // INIT ON DOM READY
  // ════════════════════════════════════════════════════════════

  const init = () => {
    initHeaderScroll();
    initMobileMenu();
    initScrollReveal();
    initQuantityControls();
    initAddToCart();
    initLazyLoading();
    initSearch();
    initNewsletter();
    initSmoothScroll();
    initPrefetch();
    initAccessibility();

    // Initial cart count
    updateCartCount();

    // Announce to assistive tech that page is ready
    console.log('Oubon Shop theme loaded successfully');
  };

  // Initialize when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // Expose utilities to window for theme customization
  window.OubonTheme = {
    updateCartCount,
    showCartNotification
  };

})();
