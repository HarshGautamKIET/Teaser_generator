import React from 'react';

const iconBtnShapes = {
  circle:{borderRadius:'var(--radius-pill)'},
  square:{borderRadius:'var(--radius-sm)'}
};

export function IconButton({
  children, label, variant = 'outline', shape = 'circle', size = 34, style, ...rest
}) {
  const [hover, setHover] = React.useState(false);
  const fills = {
    outline:{background:'var(--white)', border:'1px solid var(--border-hairline)', color:'var(--ink-700)'},
    ghost:{background:'transparent', border:'1px solid transparent', color:'var(--text-muted)'},
    sunken:{background:'var(--surface-sunken)', border:'1px solid transparent', color:'var(--ink-700)'}
  };
  return (
    <button
      aria-label={label}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        width:size, height:size, display:'inline-flex', alignItems:'center', justifyContent:'center',
        padding:0, cursor:'pointer', transition:'var(--transition-control)',
        ...iconBtnShapes[shape], ...fills[variant],
        ...(hover ? {background:'var(--ink-50)', color:'var(--text-strong)'} : null),
        ...style
      }}
      {...rest}
    >
      {children}
    </button>
  );
}
