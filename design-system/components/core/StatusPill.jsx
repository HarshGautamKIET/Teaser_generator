import React from 'react';

const statusTones = {
  success:{color:'var(--success-600)', dot:'var(--success-500)'},
  pending:{color:'var(--amber-600)', dot:'var(--amber-600)'},
  failed:{color:'var(--danger-600)', dot:'var(--danger-600)'},
  inactive:{color:'var(--amber-600)', dot:'var(--amber-600)'},
  active:{color:'var(--success-600)', dot:'var(--success-600)'}
};

export function StatusPill({ tone = 'success', dot = true, children, style }) {
  const t = statusTones[tone];
  return (
    <span style={{
      display:'inline-flex', alignItems:'center', gap:5,
      fontSize:'var(--text-xs)', fontWeight:'var(--weight-semibold)',
      color:t.color, ...style
    }}>
      {dot ? <span style={{
        width:12, height:12, borderRadius:'var(--radius-pill)',
        background:t.dot, display:'inline-flex', alignItems:'center', justifyContent:'center',
        color:'var(--white)', fontSize:8, fontWeight:'var(--weight-bold)', lineHeight:1
      }}>{tone === 'success' || tone === 'active' ? '✓' : ''}</span> : null}
      {children}
    </span>
  );
}
