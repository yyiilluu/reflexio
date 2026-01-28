/**
 * Reflexio Documentation - Custom JavaScript
 * Adds enhanced functionality and user experience improvements
 */

// Wait for DOM to be fully loaded
document.addEventListener('DOMContentLoaded', function() {

  // ==================== External Link Handler ====================
  // Add external link indicators and open in new tab
  const links = document.querySelectorAll('a[href^="http"]');
  links.forEach(link => {
    // Skip if it's linking to the same domain
    if (!link.href.includes(window.location.hostname)) {
      link.setAttribute('target', '_blank');
      link.setAttribute('rel', 'noopener noreferrer');

      // Add external link icon (optional)
      if (!link.querySelector('.external-icon')) {
        const icon = document.createElement('span');
        icon.className = 'external-icon';
        icon.innerHTML = ' ↗';
        icon.style.fontSize = '0.8em';
        icon.style.opacity = '0.6';
        link.appendChild(icon);
      }
    }
  });

  // ==================== Code Block Enhancements ====================
  // Add language labels to code blocks
  const codeBlocks = document.querySelectorAll('pre > code[class*="language-"]');
  codeBlocks.forEach(block => {
    const pre = block.parentElement;
    const language = block.className.match(/language-(\w+)/);

    if (language && !pre.querySelector('.code-label')) {
      const label = document.createElement('div');
      label.className = 'code-label';
      label.textContent = language[1].toUpperCase();
      label.style.cssText = `
        position: absolute;
        top: 0;
        right: 0;
        background: rgba(69, 123, 157, 0.9);
        color: white;
        padding: 0.25rem 0.75rem;
        font-size: 0.75rem;
        font-weight: 600;
        border-bottom-left-radius: 4px;
        z-index: 1;
      `;

      pre.style.position = 'relative';
      pre.insertBefore(label, pre.firstChild);
    }
  });

  // ==================== Smooth Scroll for Anchor Links ====================
  const anchorLinks = document.querySelectorAll('a[href^="#"]');
  anchorLinks.forEach(link => {
    link.addEventListener('click', function(e) {
      const targetId = this.getAttribute('href');
      if (targetId === '#') return;

      const targetElement = document.querySelector(targetId);
      if (targetElement) {
        e.preventDefault();
        targetElement.scrollIntoView({
          behavior: 'smooth',
          block: 'start'
        });

        // Update URL without jumping
        history.pushState(null, null, targetId);
      }
    });
  });

  // ==================== Copy Code Button Enhancement ====================
  // Add success feedback when copying code
  const copyButtons = document.querySelectorAll('.md-clipboard');
  copyButtons.forEach(button => {
    button.addEventListener('click', function() {
      // Create temporary success message
      const originalTitle = button.getAttribute('title');
      button.setAttribute('title', 'Copied!');

      // Reset after 2 seconds
      setTimeout(() => {
        button.setAttribute('title', originalTitle);
      }, 2000);
    });
  });

  // ==================== Table of Contents Highlighting ====================
  // Highlight current section in TOC based on scroll position
  const observerOptions = {
    rootMargin: '-20% 0px -80% 0px',
    threshold: 0
  };

  const headings = document.querySelectorAll('h2[id], h3[id]');
  const tocLinks = document.querySelectorAll('.md-nav__link[href^="#"]');

  if (headings.length > 0 && tocLinks.length > 0) {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const id = entry.target.getAttribute('id');

          // Remove active class from all TOC links
          tocLinks.forEach(link => {
            link.classList.remove('md-nav__link--active');
          });

          // Add active class to current section
          const activeLink = document.querySelector(`.md-nav__link[href="#${id}"]`);
          if (activeLink) {
            activeLink.classList.add('md-nav__link--active');
          }
        }
      });
    }, observerOptions);

    headings.forEach(heading => observer.observe(heading));
  }

  // ==================== Keyboard Shortcuts ====================
  document.addEventListener('keydown', function(e) {
    // Ctrl/Cmd + K to focus search
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
      e.preventDefault();
      const searchInput = document.querySelector('.md-search__input');
      if (searchInput) {
        searchInput.focus();
      }
    }

    // Esc to close search
    if (e.key === 'Escape') {
      const searchInput = document.querySelector('.md-search__input');
      if (searchInput && document.activeElement === searchInput) {
        searchInput.blur();
      }
    }
  });

  // ==================== Reading Progress Indicator ====================
  // Add a reading progress bar at the top
  const progressBar = document.createElement('div');
  progressBar.id = 'reading-progress';
  progressBar.style.cssText = `
    position: fixed;
    top: 0;
    left: 0;
    height: 3px;
    background: linear-gradient(90deg, #e63946, #457b9d);
    width: 0%;
    z-index: 9999;
    transition: width 0.1s ease;
  `;
  document.body.appendChild(progressBar);

  window.addEventListener('scroll', function() {
    const windowHeight = window.innerHeight;
    const documentHeight = document.documentElement.scrollHeight - windowHeight;
    const scrolled = window.scrollY;
    const progress = (scrolled / documentHeight) * 100;
    progressBar.style.width = progress + '%';
  });

  // ==================== Dark Mode Persistence ====================
  // Remember user's theme preference
  const themeToggle = document.querySelector('[data-md-component="palette"]');
  if (themeToggle) {
    themeToggle.addEventListener('change', function() {
      const isDark = document.querySelector('[data-md-color-scheme="slate"]');
      localStorage.setItem('theme', isDark ? 'dark' : 'light');
    });
  }

  // ==================== Copy Heading Link ====================
  // Allow clicking on heading to copy anchor link
  const articleHeadings = document.querySelectorAll('.md-content h2[id], .md-content h3[id]');
  articleHeadings.forEach(heading => {
    heading.style.cursor = 'pointer';
    heading.title = 'Click to copy link';

    heading.addEventListener('click', function() {
      const id = this.getAttribute('id');
      const url = window.location.origin + window.location.pathname + '#' + id;

      navigator.clipboard.writeText(url).then(() => {
        // Show temporary success message
        const message = document.createElement('span');
        message.textContent = ' Link copied!';
        message.style.cssText = `
          color: #588157;
          font-size: 0.85em;
          margin-left: 0.5rem;
          font-weight: normal;
        `;
        this.appendChild(message);

        setTimeout(() => {
          message.remove();
        }, 2000);
      });
    });
  });

  // ==================== Table Responsiveness ====================
  // Wrap tables in scrollable containers for mobile
  const tables = document.querySelectorAll('.md-typeset table:not([class])');
  tables.forEach(table => {
    if (!table.parentElement.classList.contains('table-wrapper')) {
      const wrapper = document.createElement('div');
      wrapper.className = 'table-wrapper';
      wrapper.style.cssText = `
        overflow-x: auto;
        margin: 1rem 0;
        border-radius: 6px;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
      `;
      table.parentNode.insertBefore(wrapper, table);
      wrapper.appendChild(table);
    }
  });

  // ==================== Back to Top Enhancement ====================
  // Show back to top button only when scrolled down
  const backToTop = document.querySelector('.md-top');
  if (backToTop) {
    window.addEventListener('scroll', function() {
      if (window.scrollY > 300) {
        backToTop.style.opacity = '1';
      } else {
        backToTop.style.opacity = '0.3';
      }
    });
  }

  // ==================== Print Optimization ====================
  // Expand all collapsed sections before printing
  window.addEventListener('beforeprint', function() {
    const details = document.querySelectorAll('details');
    details.forEach(detail => {
      detail.setAttribute('open', '');
    });
  });

  // ==================== Console Welcome Message ====================
  console.log('%c Reflexio Documentation ', 'background: #1d3557; color: #f1faee; font-size: 16px; font-weight: bold; padding: 10px;');
  console.log('%c Welcome! We\'re glad you\'re here. ', 'color: #457b9d; font-size: 12px;');

});

// ==================== Analytics Helper (if needed) ====================
// Generic function to track events
window.trackEvent = function(category, action, label) {
  if (typeof gtag !== 'undefined') {
    gtag('event', action, {
      'event_category': category,
      'event_label': label
    });
  }
  console.log('Event tracked:', category, action, label);
};

// ==================== Service Worker Registration (if needed) ====================
// Uncomment to enable offline support
/*
if ('serviceWorker' in navigator) {
  window.addEventListener('load', function() {
    navigator.serviceWorker.register('/sw.js').then(function(registration) {
      console.log('ServiceWorker registered:', registration.scope);
    }, function(err) {
      console.log('ServiceWorker registration failed:', err);
    });
  });
}
*/
