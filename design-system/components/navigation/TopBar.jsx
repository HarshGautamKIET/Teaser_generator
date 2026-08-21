import React from 'react';

export function TopBar({ left, children, style }) {
  return (
    <header style={{
      display:'flex', alignItems:'center', gap:10, height:56,
      padding:'0 18px 0 14px', ...style
    }}>
      {left}
      <div style={{marginLeft:'auto', display:'flex', alignItems:'center', gap:8}}>{children}</div>
    </header>
  );
}

export function BrandLockup({ src = 'assets/logo-mark.png', name = 'Oripio', size = 30, style }) {
  return (
    <div style={{display:'flex', alignItems:'center', gap:9, ...style}}>
      <img src={src} width={size} height={size} alt="" style={{borderRadius:'var(--radius-sm)', display:'block'}} />
      <span style={{
        fontSize:'var(--text-xl)', fontWeight:'var(--weight-bold)',
        letterSpacing:'var(--tracking-tight)', color:'var(--text-strong)'
      }}>{name}</span>
    </div>
  );
}
