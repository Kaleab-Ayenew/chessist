(function () {
  'use strict';

  // Video fallback: show placeholder when hero video is missing or fails to load
  var heroVideo = document.getElementById('hero-video');
  var heroPlaceholder = document.getElementById('hero-placeholder');

  if (heroVideo && heroPlaceholder) {
    function showPlaceholder() {
      heroPlaceholder.classList.remove('hidden');
    }

    function hidePlaceholder() {
      heroPlaceholder.classList.add('hidden');
    }

    // No source or invalid source
    var source = heroVideo.querySelector('source');
    if (!source || !source.getAttribute('src')) {
      showPlaceholder();
    } else {
      heroPlaceholder.classList.add('hidden');
      heroVideo.addEventListener('error', function () {
        showPlaceholder();
      });
      heroVideo.addEventListener('loadeddata', function () {
        hidePlaceholder();
      });
      // If video never loads (e.g. 404), error will fire
      heroVideo.load();
    }
  }

  // Mobile nav toggle
  var navToggle = document.querySelector('.nav-toggle');
  var navLinks = document.querySelector('.nav-links');
  var nav = document.querySelector('.nav') || (navToggle && navToggle.parentElement);

  if (navToggle && navLinks) {
    navToggle.addEventListener('click', function () {
      navLinks.classList.toggle('is-open');
    });

    if (nav) {
      document.addEventListener('click', function (e) {
        if (navLinks.classList.contains('is-open') && !nav.contains(e.target)) {
          navLinks.classList.remove('is-open');
        }
      });
    }
  }
})();
