import React from 'react';
import { StatusPill } from '../core/StatusPill.jsx';

export function WalletTile({ flag, code, amount, status = 'active', onMore, style }) {
  return (
    <div style={{
      background:'var(--surface-tile)', borderRadius:'var(--radius-md)', padding:'10px 12px', ...style
    }}>
      <div style={{display:'flex', alignItems:'center', gap:7}}>
        {flag}
        <span style={{fontSize:'var(--text-xs)', fontWeight:'var(--weight-semibold)', color:'var(--text-body)'}}>{code}</span>
        <button onClick={onMore} aria-label={`${code} options`} style={{
          marginLeft:'auto', border:'none', background:'transparent', cursor:'pointer',
          color:'var(--text-muted)', padding:0, lineHeight:1, fontSize:14
        }}>⋮</button>
      </div>
      <div className="o-num" style={{
        marginTop:6, fontSize:'var(--text-lg)', fontWeight:'var(--weight-bold)',
        letterSpacing:'var(--tracking-tight)', color:'var(--text-heading)'
      }}>{amount}</div>
      <StatusPill tone={status} dot={false} style={{marginTop:4, fontSize:'var(--text-2xs)'}}>
        {status === 'active' ? 'Active' : 'Inactive'}
      </StatusPill>
    </div>
  );
}
