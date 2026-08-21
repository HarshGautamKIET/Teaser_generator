import React from 'react';
import { Card, CardHeader } from '../core/Card.jsx';
import { Badge } from '../core/Badge.jsx';

export function StatCard({ icon, title, value, delta, deltaTone = 'positive', deltaArrow = 'up',
  caption = 'from last month', actions, children, style }) {
  return (
    <Card style={style}>
      <CardHeader icon={icon} title={title} actions={actions} />
      <div className="o-num" style={{
        fontSize:'var(--text-2xl)', fontWeight:'var(--weight-extrabold)',
        letterSpacing:'var(--tracking-tight)', color:'var(--text-heading)', lineHeight:1.1
      }}>{value}</div>
      {delta != null ? (
        <div style={{display:'flex', alignItems:'center', gap:8, marginTop:10}}>
          <Badge tone={deltaTone} arrow={deltaArrow}>{delta}</Badge>
          <span style={{fontSize:'var(--text-xs)', color:'var(--text-body)'}}>{caption}</span>
        </div>
      ) : null}
      {children}
    </Card>
  );
}
