import React from 'react';

/* Oripio uses Lucide (2px round-cap outline) as its icon set — see
   readme.md → ICONOGRAPHY. The CDN UMD build must be on the page:
   <script src="https://unpkg.com/lucide@0.474.0/dist/umd/lucide.js"></script> */
export function Icon({ name, size = 16, strokeWidth = 2, color = 'currentColor', style }) {
  const ref = React.useRef(null);
  React.useEffect(() => {
    const el = ref.current;
    if (!el || !window.lucide) return;
    el.innerHTML = '';
    const i = document.createElement('i');
    i.setAttribute('data-lucide', name);
    el.appendChild(i);
    window.lucide.createIcons({
      nameAttr:'data-lucide',
      attrs:{ width:size, height:size, stroke:color, 'stroke-width':strokeWidth },
      root: el
    });
  }, [name, size, strokeWidth, color]);
  return <span ref={ref} aria-hidden="true" style={{display:'inline-flex', width:size, height:size, flex:'0 0 auto', color, ...style}} />;
}
