import React from 'react';

export function DataTable({ columns = [], rows = [], style }) {
  return (
    <div style={{...style}}>
      <div style={{
        display:'grid', gridTemplateColumns:columns.map(c => c.width || '1fr').join(' '),
        gap:10, padding:'9px 12px', borderRadius:'var(--radius-sm)',
        background:'var(--surface-sunken)', fontSize:'var(--text-xs)',
        fontWeight:'var(--weight-semibold)', color:'var(--text-body)'
      }}>
        {columns.map(c => <span key={c.key} style={{textAlign:c.align || 'left'}}>{c.label}</span>)}
      </div>
      {rows.map((r, i) => (
        <div key={i} style={{
          display:'grid', gridTemplateColumns:columns.map(c => c.width || '1fr').join(' '),
          gap:10, padding:'11px 12px', alignItems:'center',
          borderBottom: i === rows.length - 1 ? 'none' : '1px solid var(--border-hairline)',
          fontSize:'var(--text-sm)', color:'var(--text-heading)',
          fontWeight:'var(--weight-medium)'
        }}>
          {columns.map(c => (
            <span key={c.key} className={c.numeric ? 'o-num' : undefined}
              style={{
                textAlign:c.align || 'left', display:'flex', alignItems:'center', gap:9,
                justifyContent: c.align === 'right' ? 'flex-end' : 'flex-start',
                color: c.muted ? 'var(--text-body)' : undefined
              }}>{r[c.key]}</span>
          ))}
        </div>
      ))}
    </div>
  );
}
