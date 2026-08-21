import React from 'react';

export function Select({ value, options = [], onChange, leading, variant = 'ghost', size = 'sm', style }) {
  const [open, setOpen] = React.useState(false);
  const pad = size === 'sm' ? '0 8px' : '0 12px';
  const fills = {
    ghost:{background:'transparent', border:'1px solid transparent'},
    outline:{background:'var(--white)', border:'1px solid var(--border-hairline)'},
    sunken:{background:'var(--surface-sunken)', border:'1px solid transparent'}
  };
  return (
    <div style={{position:'relative', ...style}}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          display:'inline-flex', alignItems:'center', gap:6, cursor:'pointer',
          height: size === 'sm' ? 28 : 'var(--control-h-sm)', padding:pad,
          borderRadius:'var(--radius-pill)', fontFamily:'var(--font-sans)',
          fontSize:'var(--text-xs)', fontWeight:'var(--weight-semibold)',
          color:'var(--text-heading)', whiteSpace:'nowrap', transition:'var(--transition-control)', ...fills[variant]
        }}
      >
        {leading}
        {value}
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" style={{opacity:.5, transform:open ? 'rotate(180deg)' : 'none', transition:'transform var(--duration-fast) var(--ease-standard)'}}><path d="m6 9 6 6 6-6"/></svg>
      </button>
      {open ? (
        <div style={{
          position:'absolute', top:'calc(100% + 6px)', right:0, zIndex:20, minWidth:130,
          background:'var(--white)', borderRadius:'var(--radius-md)',
          boxShadow:'var(--shadow-overlay)', padding:6
        }}>
          {options.map(o => (
            <button key={o} onClick={() => { onChange && onChange(o); setOpen(false); }}
              style={{
                display:'block', width:'100%', textAlign:'left', border:'none', cursor:'pointer',
                padding:'7px 9px', borderRadius:'var(--radius-xs)',
                background: o === value ? 'var(--green-50)' : 'transparent',
                color: o === value ? 'var(--green-600)' : 'var(--text-body)',
                fontSize:'var(--text-xs)', fontWeight:'var(--weight-semibold)'
              }}>{o}</button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
