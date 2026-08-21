import React from 'react';

export function PromoCard({ title, body, action, style }) {
  return (
    <div style={{
      background:'linear-gradient(180deg,var(--green-600) 0%,var(--green-800) 100%)',
      borderRadius:'var(--radius-lg)', padding:'18px 14px', textAlign:'center',
      color:'var(--text-on-brand)', ...style
    }}>
      <div style={{fontSize:'var(--text-md)', fontWeight:'var(--weight-bold)', letterSpacing:'var(--tracking-tight)'}}>{title}</div>
      <p style={{
        margin:'6px 0 14px', fontSize:'var(--text-xs)', lineHeight:'var(--leading-normal)',
        color:'rgba(255,255,255,.78)'
      }}>{body}</p>
      {action}
    </div>
  );
}
