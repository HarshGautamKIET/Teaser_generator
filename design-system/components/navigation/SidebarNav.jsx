import React from 'react';

export function SidebarSectionLabel({ children, style }) {
  return (
    <div style={{
      padding:'0 10px', marginBottom:8, fontSize:'var(--text-2xs)',
      fontWeight:'var(--weight-bold)', letterSpacing:'var(--tracking-label)',
      textTransform:'uppercase', color:'var(--text-muted)', ...style
    }}>{children}</div>
  );
}

export function SidebarItem({ icon, label, count, active = false, onClick, style }) {
  const [hover, setHover] = React.useState(false);
  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}
      style={{
        position:'relative', display:'flex', alignItems:'center', gap:10, width:'100%',
        height:38, padding:'0 12px', border:'none', cursor:'pointer', textAlign:'left',
        borderRadius:'var(--radius-md)', transition:'var(--transition-control)',
        background: active ? 'var(--nav-item-active-bg)' : hover ? 'var(--ink-50)' : 'transparent',
        color: active ? 'var(--nav-item-active-text)' : 'var(--nav-item-rest-text)',
        fontFamily:'var(--font-sans)', fontSize:'var(--text-md)',
        fontWeight: active ? 'var(--weight-semibold)' : 'var(--weight-medium)', ...style
      }}
    >
      {active ? <span style={{
        position:'absolute', left:2, top:'50%', transform:'translateY(-50%)',
        width:3, height:14, borderRadius:'var(--radius-pill)', background:'var(--green-600)'
      }} /> : null}
      {icon}
      <span style={{flex:1, minWidth:0, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap'}}>{label}</span>
      {count != null ? <span className="o-num" style={{
        fontSize:'var(--text-xs)', fontWeight:'var(--weight-semibold)', color:'var(--text-muted)'
      }}>{count}</span> : null}
    </button>
  );
}

export function SidebarNav({ children, style }) {
  return <nav style={{display:'flex', flexDirection:'column', gap:2, ...style}}>{children}</nav>;
}
