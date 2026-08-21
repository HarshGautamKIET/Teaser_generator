import React from 'react';

const btnBase = {
  display:'inline-flex', alignItems:'center', justifyContent:'center', gap:8,
  fontFamily:'var(--font-sans)', fontWeight:'var(--weight-semibold)',
  letterSpacing:'-0.01em', borderRadius:'var(--radius-pill)',
  border:'1px solid transparent', cursor:'pointer', whiteSpace:'nowrap',
  transition:'var(--transition-control)', textDecoration:'none'
};

const btnSizes = {
  sm:{height:'var(--control-h-sm)', padding:'0 14px', fontSize:'var(--text-xs)'},
  md:{height:'var(--control-h-md)', padding:'0 16px', fontSize:'var(--text-sm)'},
  lg:{height:'var(--control-h-lg)', padding:'0 20px', fontSize:'var(--text-md)'}
};

const btnVariants = {
  primary:{background:'var(--surface-brand)', color:'var(--text-on-brand)'},
  secondary:{background:'var(--ink-100)', color:'var(--text-strong)'},
  dark:{background:'var(--surface-dark)', color:'var(--text-on-brand)'},
  outline:{background:'var(--white)', color:'var(--text-strong)', borderColor:'var(--border-hairline)'},
  ghost:{background:'transparent', color:'var(--text-body)'},
  onBrand:{background:'var(--white)', color:'var(--green-700)'}
};

const btnHovers = {
  primary:{background:'var(--green-700)'},
  secondary:{background:'var(--ink-200)'},
  dark:{background:'var(--ink-700)'},
  outline:{background:'var(--ink-50)'},
  ghost:{background:'var(--ink-100)', color:'var(--text-strong)'},
  onBrand:{background:'var(--green-25)'}
};

export function Button({
  variant = 'primary', size = 'md', icon, iconRight, fullWidth = false,
  disabled = false, as = 'button', children, style, ...rest
}) {
  const [hover, setHover] = React.useState(false);
  const [down, setDown] = React.useState(false);
  const Tag = as;
  return (
    <Tag
      disabled={Tag === 'button' ? disabled : undefined}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => { setHover(false); setDown(false); }}
      onMouseDown={() => setDown(true)}
      onMouseUp={() => setDown(false)}
      style={{
        ...btnBase, ...btnSizes[size], ...btnVariants[variant],
        ...(hover && !disabled ? btnHovers[variant] : null),
        width: fullWidth ? '100%' : undefined,
        transform: down && !disabled ? 'scale(.985)' : 'scale(1)',
        opacity: disabled ? 0.45 : 1,
        cursor: disabled ? 'not-allowed' : 'pointer',
        ...style
      }}
      {...rest}
    >
      {icon ? <span style={{display:'flex', fontSize:0}}>{icon}</span> : null}
      {children}
      {iconRight ? <span style={{display:'flex', fontSize:0}}>{iconRight}</span> : null}
    </Tag>
  );
}
