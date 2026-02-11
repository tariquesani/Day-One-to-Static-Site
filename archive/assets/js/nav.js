/* Navigation + lightbox JS.
 *
 * Lightbox behaviour:
 * - Enhances entry pages only (inline photos).
 * - Clicking a photo opens a modal overlay instead of navigating directly
 *   to the image file, when the global photo index is available.
 * - Prev/Next traverse all photos in journal order (oldest-first index).
 * - Closing navigates to the entry of the currently visible photo, anchored
 *   to that photo's id (Entry.html#photo-id).
 *
 * Without JS or if anything fails, the underlying links still work:
 * - Entry photos open the raw image file.
 * - Media grid links go to Entry.html#photo-id.
 */

(function () {
  var body = document.body;
  if (!body) return;

  body.classList.add('js-enabled');

  var photoIndexUrl = body.getAttribute('data-photo-index-url') || '';
  // Lightbox requires fetch(); only enable when served over http(s) to avoid CORS on file://
  if (location.protocol !== 'http:' && location.protocol !== 'https:') {
    photoIndexUrl = '';
  }
  var archiveRoot = (function () {
    var root = body.getAttribute('data-archive-root');
    if (root == null || root === '') root = './';
    try {
      return new URL(root, location.href).href;
    } catch (e) {
      return location.href.replace(/[^/]+$/, '');
    }
  })();
  var photoIndex = null;
  var photoIndexById = null;
  var lightboxEl = null;
  var lightboxImg = null;
  var lightboxMeta = null;
  var btnClose = null;
  var btnPrev = null;
  var btnNext = null;
  var currentIndex = -1;
  var lastFocused = null;

  function loadPhotoIndex() {
    if (!photoIndexUrl || photoIndex) {
      return Promise.resolve(photoIndex || []);
    }
    return fetch(photoIndexUrl, { credentials: 'same-origin' })
      .then(function (res) {
        if (!res.ok) throw new Error('Failed to load photo index');
        return res.json();
      })
      .then(function (data) {
        if (!Array.isArray(data)) data = [];
        photoIndex = data;
        photoIndexById = {};
        data.forEach(function (p, idx) {
          if (p && p.id) {
            photoIndexById[p.id] = idx;
          }
        });
        return photoIndex;
      })
      .catch(function () {
        // On failure, keep photoIndex null so default navigation still works.
        photoIndex = null;
        photoIndexById = null;
        return [];
      });
  }

  function ensureLightbox() {
    if (lightboxEl) return;

    lightboxEl = document.createElement('div');
    lightboxEl.className = 'photo-lightbox';
    lightboxEl.setAttribute('role', 'dialog');
    lightboxEl.setAttribute('aria-modal', 'true');

    var dialog = document.createElement('div');
    dialog.className = 'photo-lightbox-dialog';

    btnClose = document.createElement('button');
    btnClose.type = 'button';
    btnClose.className = 'photo-lightbox-close';
    btnClose.setAttribute('aria-label', 'Close');
    btnClose.textContent = '×';

    btnPrev = document.createElement('button');
    btnPrev.type = 'button';
    btnPrev.className = 'photo-lightbox-prev';
    btnPrev.setAttribute('aria-label', 'Previous photo');
    btnPrev.textContent = 'Prev';

    btnNext = document.createElement('button');
    btnNext.type = 'button';
    btnNext.className = 'photo-lightbox-next';
    btnNext.setAttribute('aria-label', 'Next photo');
    btnNext.textContent = 'Next';

    var imgWrap = document.createElement('div');
    imgWrap.className = 'photo-lightbox-img-wrap';

    lightboxImg = document.createElement('img');
    lightboxImg.className = 'photo-lightbox-img';
    lightboxImg.alt = '';

    imgWrap.appendChild(lightboxImg);

    var navWrap = document.createElement('div');
    navWrap.className = 'photo-lightbox-nav';
    navWrap.appendChild(btnPrev);
    navWrap.appendChild(btnNext);
    imgWrap.appendChild(navWrap);
    imgWrap.appendChild(btnClose);

    lightboxMeta = document.createElement('div');
    lightboxMeta.className = 'photo-lightbox-meta';

    dialog.appendChild(imgWrap);
    dialog.appendChild(lightboxMeta);

    lightboxEl.appendChild(dialog);
    document.body.appendChild(lightboxEl);

    btnClose.addEventListener('click', closeLightbox);
    btnPrev.addEventListener('click', function () {
      showRelative(-1);
    });
    btnNext.addEventListener('click', function () {
      showRelative(1);
    });

    lightboxEl.addEventListener('click', function (e) {
      if (e.target === lightboxEl) {
        closeLightbox();
      }
    });

    document.addEventListener('keydown', function (e) {
      if (!lightboxEl || !lightboxEl.classList.contains('is-open')) return;
      if (e.key === 'Escape') {
        e.preventDefault();
        closeLightbox();
      } else if (e.key === 'ArrowLeft') {
        e.preventDefault();
        showRelative(-1);
      } else if (e.key === 'ArrowRight') {
        e.preventDefault();
        showRelative(1);
      }
    });
  }

  function openLightboxForId(photoId, triggerEl) {
    if (!photoId || !photoIndexUrl) return;
    loadPhotoIndex().then(function (list) {
      if (!list || !photoIndexById || !(photoId in photoIndexById)) {
        // Fallback: simulate click to keep default navigation.
        if (triggerEl && typeof triggerEl.click === 'function') {
          triggerEl.click();
        }
        return;
      }
      ensureLightbox();
      lastFocused = document.activeElement;
      currentIndex = photoIndexById[photoId];
      showCurrent();
      lightboxEl.classList.add('is-open');
      btnClose.focus();
    });
  }

  function showCurrent() {
    if (!photoIndex || currentIndex < 0 || currentIndex >= photoIndex.length) return;
    var p = photoIndex[currentIndex];
    try {
      lightboxImg.src = new URL(p.image_url, archiveRoot).href;
    } catch (e) {
      lightboxImg.src = p.image_url;
    }
    var metaParts = [];
    if (p.date_iso) metaParts.push(p.date_iso);
    if (p.month_year) metaParts.push(p.month_year);
    lightboxMeta.textContent = metaParts.join(' · ');
  }

  function showRelative(delta) {
    if (!photoIndex || !photoIndex.length) return;
    if (currentIndex < 0) return;
    var nextIndex = currentIndex + delta;
    if (nextIndex < 0 || nextIndex >= photoIndex.length) return;
    currentIndex = nextIndex;
    showCurrent();
  }

  function closeLightbox() {
    if (!photoIndex || currentIndex < 0 || currentIndex >= photoIndex.length) {
      if (lightboxEl) {
        lightboxEl.classList.remove('is-open');
      }
      if (lastFocused && typeof lastFocused.focus === 'function') {
        lastFocused.focus();
      }
      return;
    }

    var p = photoIndex[currentIndex];
    var entryHref = p.entry_href || '';
    if (!entryHref) {
      if (lightboxEl) {
        lightboxEl.classList.remove('is-open');
      }
      if (lastFocused && typeof lastFocused.focus === 'function') {
        lastFocused.focus();
      }
      return;
    }

    var resolvedEntryUrl;
    try {
      resolvedEntryUrl = new URL(entryHref, archiveRoot).href;
    } catch (e) {
      resolvedEntryUrl = entryHref;
    }

    // If we're already on that entry page, just update the hash and hide.
    try {
      var targetPath = new URL(resolvedEntryUrl).pathname;
      var currentPath = window.location.pathname || '';
      if (targetPath && currentPath === targetPath) {
        var hashPart = new URL(resolvedEntryUrl).hash;
        if (hashPart) {
          window.location.hash = hashPart;
        }
        if (lightboxEl) {
          lightboxEl.classList.remove('is-open');
        }
        if (lastFocused && typeof lastFocused.focus === 'function') {
          lastFocused.focus();
        }
        return;
      }
    } catch (e) {}

    // Otherwise, navigate to that entry (real navigation).
    window.location.href = resolvedEntryUrl;
  }

  // Enhance entry pages: intercept clicks on inline photos.
  function enhanceEntryPhotos() {
    var figures = document.querySelectorAll('.entry-photo a');
    if (!figures.length) return;

    figures.forEach(function (linkEl) {
      linkEl.addEventListener('click', function (e) {
        var fig = linkEl.closest('.entry-photo');
        if (!fig) return;
        var photoId = fig.getAttribute('data-photo-id') || fig.id;
        if (!photoId || !photoIndexUrl) return;
        e.preventDefault();
        openLightboxForId(photoId, linkEl);
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', enhanceEntryPhotos);
  } else {
    enhanceEntryPhotos();
  }
})();
