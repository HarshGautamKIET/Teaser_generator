import React from 'react';

export function IconTile({ children, tone = 'brand', size = 28, style }) {
  const tones = {
    brand:{background:'var(--green-50)', color:'var(--green-600)'},
    neutral:{background:'var(--ink-50)', color:'var(--ink-500)'},
    amber:{background:'var(--amber-50)', color:'var(--amber-600)'},
    white:{background:'var(--white)', color:'var(--green-600)'}
  };
  return (
    <span style={{
      width:size, height:size, flex:'0 0 auto', borderRadius:'var(--radius-sm)',
      display:'inline-flex', alignItems:'center', justifyContent:'center',
      ...tones[tone], ...style
    }}>{children}</span>
  );
}
