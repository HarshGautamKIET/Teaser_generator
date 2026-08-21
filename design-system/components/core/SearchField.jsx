import React from 'react';

export function SearchField({ placeholder = 'Search', shortcut = '⌘ K', width = 180, style, ...rest }) {
  const [focus, setFocus] = React.useState(false);
  return (
    <label style={{
      display:'inline-flex', alignItems:'center', gap:8, height:'var(--control-h-sm)',
      padding:'0 6px 0 12px', borderRadius:'var(--radius-pill)',
      background:'var(--surface-sunken)',
      boxShadow: focus ? '0 0 0 3px var(--focus-ring)' : 'none',
      transition:'var(--transition-control)', width, ...style
    }}>
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" strokeWidth="2.2" strokeLinecap="round"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>
      <input
        placeholder={placeholder}
        onFocus={() => setFocus(true)} onBlur={() => setFocus(false)}
        style={{
          flex:1, minWidth:0, border:'none', outline:'none', background:'transparent',
          fontFamily:'var(--font-sans)', fontSize:'var(--text-sm)', color:'var(--text-strong)'
        }}
        {...rest}
      />
      {shortcut ? <kbd style={{
        fontFamily:'var(--font-sans)', fontSize:'var(--text-2xs)', fontWeight:'var(--weight-semibold)',
        color:'var(--text-muted)', background:'var(--white)', borderRadius:'var(--radius-xs)',
        padding:'3px 6px'
      }}>{shortcut}</kbd> : null}
    </label>
  );
}
