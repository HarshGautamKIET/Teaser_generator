import React from 'react';
import { IconTile } from '../core/IconTile.jsx';

export function GoalRow({ icon, title, current, target, percent, tone = 'brand', style }) {
  const accent = tone === 'amber' ? 'var(--amber-600)' : 'var(--green-600)';
  return (
    <div style={{
      background:'var(--surface-tile)', borderRadius:'var(--radius-md)', padding:'12px 14px', ...style
    }}>
      <div style={{display:'flex', alignItems:'center', gap:9}}>
        <IconTile tone={tone} size={26} style={{background:'var(--white)'}}>{icon}</IconTile>
        <span style={{fontSize:'var(--text-md)', fontWeight:'var(--weight-semibold)', color:'var(--text-heading)'}}>{title}</span>
      </div>
      <div style={{display:'flex', alignItems:'baseline', gap:8, marginTop:10}}>
        <span className="o-num" style={{fontSize:'var(--text-sm)', color:'var(--text-body)'}}>
          <strong style={{color:'var(--text-heading)', fontWeight:'var(--weight-bold)'}}>{current}</strong>/{target}
        </span>
        <span className="o-num" style={{
          marginLeft:'auto', fontSize:'var(--text-sm)', fontWeight:'var(--weight-bold)', color:accent
        }}>{percent}%</span>
      </div>
      <div style={{marginTop:8, height:5, borderRadius:'var(--radius-pill)', background:'var(--white)', overflow:'hidden'}}>
        <div style={{
          width:`${percent}%`, height:'100%', borderRadius:'var(--radius-pill)', background:accent,
          transition:'width var(--duration-slow) var(--ease-out)'
        }} />
      </div>
    </div>
  );
}
