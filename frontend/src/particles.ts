export const particlesInit = () => {
  // Check if element exists
  const element = document.getElementById('particles-js');
  if (!element) {
    console.warn('particles-js element not found');
    return;
  }

  // Dynamically import and initialize particles.js
  import('particles.js').then((particlesModule) => {
    const particlesJS = (particlesModule as any).default || particlesModule;

    if (typeof particlesJS === 'function') {
      particlesJS('particles-js', {
        particles: {
          number: { value: 50, density: { enable: true, value_area: 800 } },
          color: { value: '#00ffff' },
          shape: { type: 'circle' },
          opacity: { value: 0.3, random: true, anim: { enable: true, speed: 1, opacity_min: 0.1 } },
          size: { value: 1, random: true, anim: { enable: true, speed: 1, size_min: 0.1 } },
          line_linked: { enable: false },
          move: { enable: true, speed: 0.5, direction: 'none', random: true, straight: false, out_mode: 'out', bounce: false },
        },
        interactivity: { detect_on: 'canvas', events: { onhover: { enable: false }, onclick: { enable: false } } },
        retina_detect: true,
      });
    }
  }).catch((error) => {
    console.error('Failed to load particles.js:', error);
  });
};
