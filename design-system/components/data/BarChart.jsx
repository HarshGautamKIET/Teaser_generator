import React from 'react';

export function BarChart({ data = [], activeIndex = -1, height = 190, ticks = ['$40k','$30k','$20k','$10k','$0k'],
  tooltip, onHover, style }) {
  const max = Math.max(...data.map(d => d.value), 1);
  const [hover, setHover] = React.useState(activeIndex);
  const active = hover;
  return (
    <div style={{display:'flex', gap:10, ...style}}>
      <div style={{
        display:'flex', flexDirection:'column', justifyContent:'space-between',
        height, paddingBottom:20, fontSize:'var(--text-2xs)', color:'var(--text-muted)', textAlign:'right'
      }} className="o-num">
        {ticks.map(t => <span key={t}>{t}</span>)}
      </div>
      <div style={{flex:1, position:'relative'}}>
        <div style={{position:'absolute', inset:'0 0 20px 0', display:'flex', flexDirection:'column', justifyContent:'space-between'}}>
          {ticks.map((t,i) => <div key={t} style={{height:1, background: i === ticks.length-1 ? 'var(--chart-grid)' : 'var(--ink-100)'}} />)}
        </div>
        <div style={{position:'relative', height, display:'flex', alignItems:'flex-end', gap:'2.2%'}}>
          {data.map((d, i) => {
            const isActive = i === active;
            const h = Math.max(6, (d.value / max) * (height - 26));
            return (
              <div key={d.label} onMouseEnter={() => { setHover(i); onHover && onHover(i); }}
                style={{flex:1, display:'flex', flexDirection:'column', alignItems:'center', gap:7, cursor:'default'}}>
                <div style={{position:'relative', width:'100%', display:'flex', justifyContent:'center'}}>
                  {isActive ? <span style={{
                    position:'absolute', top:-13, width:11, height:11, borderRadius:'var(--radius-pill)',
                    background:'var(--green-600)', boxShadow:'0 0 0 3px var(--white)'
                  }} /> : null}
                  <div style={{
                    width:'62%', height:h, borderRadius:'var(--radius-pill)',
                    background: isActive
                      ? 'linear-gradient(180deg,var(--green-600) 0%,var(--green-500) 55%,rgba(255,255,255,0) 100%)'
                      : 'linear-gradient(180deg,var(--green-100) 0%,rgba(227,244,236,0) 100%)',
                    transition:'height var(--duration-slow) var(--ease-out), background var(--duration-fast) var(--ease-standard)'
                  }} />
                </div>
                <span style={{
                  fontSize:'var(--text-2xs)',
                  fontWeight: isActive ? 'var(--weight-bold)' : 'var(--weight-medium)',
                  color: isActive ? 'var(--text-heading)' : 'var(--text-muted)'
                }}>{d.label}</span>
              </div>
            );
          })}
        </div>
        {tooltip && active > -1 ? (
          <div style={{
            position:'absolute', left:`${((active + 0.5) / data.length) * 100}%`, top:4,
            transform:'translateX(-40%)', background:'var(--white)', borderRadius:'var(--radius-md)',
            boxShadow:'var(--shadow-overlay)', padding:'7px 11px', pointerEvents:'none'
          }}>
            <div style={{fontSize:'var(--text-2xs)', color:'var(--text-muted)'}}>{tooltip.label}</div>
            <div className="o-num" style={{
              fontSize:'var(--text-md)', fontWeight:'var(--weight-bold)', color:'var(--text-heading)',
              letterSpacing:'var(--tracking-tight)'
            }}>{tooltip.value}</div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
