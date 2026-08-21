import React from 'react';
import { IconTile } from './IconTile.jsx';

export function Card({ children, pad = true, style }) {
  return (
    <section style={{
      background:'var(--surface-card)', borderRadius:'var(--radius-lg)',
      padding: pad ? 'var(--card-pad)' : 0, boxShadow:'var(--shadow-card)',
      ...style
    }}>{children}</section>
  );
}

export function CardHeader({ icon, title, actions, style }) {
  return (
    <header style={{
      display:'flex', alignItems:'center', gap:10, marginBottom:14, ...style
    }}>
      {icon ? <IconTile>{icon}</IconTile> : null}
      <h3 style={{
        fontSize:'var(--text-lg)', fontWeight:'var(--weight-bold)',
        color:'var(--text-heading)', letterSpacing:'var(--tracking-tight)'
      }}>{title}</h3>
      <div style={{marginLeft:'auto', display:'flex', alignItems:'center', gap:8}}>{actions}</div>
    </header>
  );
}
