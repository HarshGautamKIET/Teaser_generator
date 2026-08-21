import React from 'react';

const badgeTones = {
  positive:{background:'var(--success-50)', color:'var(--success-600)'},
  negative:{background:'var(--danger-50)', color:'var(--danger-600)'},
  warning:{background:'var(--amber-50)', color:'var(--amber-600)'},
  neutral:{background:'var(--ink-100)', color:'var(--ink-500)'},
  brand:{background:'var(--green-50)', color:'var(--green-600)'}
};

export function Badge({ tone = 'positive', arrow, children, style }) {
  return (
    <span
      className="o-num"
      style={{
        display:'inline-flex', alignItems:'center', gap:3,
        height:20, padding:'0 7px', borderRadius:'var(--radius-pill)',
        fontSize:'var(--text-2xs)', fontWeight:'var(--weight-semibold)',
        letterSpacing:'-0.01em', ...badgeTones[tone], ...style
      }}
    >
      {children}
      {arrow ? <span style={{fontSize:9, lineHeight:1}}>{arrow === 'up' ? '↑' : '↓'}</span> : null}
    </span>
  );
}
