import React from 'react';

export function Avatar({ src, name = '', size = 30, ring = true, style }) {
  const initials = name.split(' ').map(w => w[0]).slice(0,2).join('').toUpperCase();
  return (
    <span style={{
      width:size, height:size, borderRadius:'var(--radius-pill)', overflow:'hidden',
      display:'inline-flex', alignItems:'center', justifyContent:'center', flex:'0 0 auto',
      background:'var(--green-50)', color:'var(--green-700)',
      fontSize: Math.round(size * 0.36), fontWeight:'var(--weight-bold)',
      boxShadow: ring ? '0 0 0 2px var(--white)' : 'none', ...style
    }}>
      {src ? <img src={src} alt={name} style={{width:'100%', height:'100%', objectFit:'cover'}} /> : initials}
    </span>
  );
}
