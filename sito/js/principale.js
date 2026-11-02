import { tema, rivela, barra, spia, fantavoto } from './effetti.js';
import { installa } from './installa.js';

const calmo = matchMedia('(prefers-reduced-motion: reduce)').matches;

tema();
rivela();
barra();
spia();
fantavoto(calmo);
installa();

// la demo si carica solo quando sta per comparire
const demo = document.getElementById('demo-app');
if (demo) {
  const carica = () => import('./demo.js').then((m) => m.avvia(demo, calmo));
  if ('IntersectionObserver' in window) {
    const io = new IntersectionObserver(
      (e) => {
        if (e.some((x) => x.isIntersecting)) {
          io.disconnect();
          carica();
        }
      },
      { rootMargin: '800px 0px' },
    );
    io.observe(demo);
  } else carica();
}
