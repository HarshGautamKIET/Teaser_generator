/* @ds-bundle: {"format":4,"namespace":"OripioDesignSystem_c89f4b","components":[{"name":"Avatar","sourcePath":"components/core/Avatar.jsx"},{"name":"Badge","sourcePath":"components/core/Badge.jsx"},{"name":"Button","sourcePath":"components/core/Button.jsx"},{"name":"Card","sourcePath":"components/core/Card.jsx"},{"name":"CardHeader","sourcePath":"components/core/Card.jsx"},{"name":"Icon","sourcePath":"components/core/Icon.jsx"},{"name":"IconButton","sourcePath":"components/core/IconButton.jsx"},{"name":"IconTile","sourcePath":"components/core/IconTile.jsx"},{"name":"SearchField","sourcePath":"components/core/SearchField.jsx"},{"name":"Select","sourcePath":"components/core/Select.jsx"},{"name":"StatusPill","sourcePath":"components/core/StatusPill.jsx"},{"name":"BarChart","sourcePath":"components/data/BarChart.jsx"},{"name":"DataTable","sourcePath":"components/data/DataTable.jsx"},{"name":"GoalRow","sourcePath":"components/data/GoalRow.jsx"},{"name":"StatCard","sourcePath":"components/data/StatCard.jsx"},{"name":"WalletTile","sourcePath":"components/data/WalletTile.jsx"},{"name":"PromoCard","sourcePath":"components/navigation/PromoCard.jsx"},{"name":"SidebarSectionLabel","sourcePath":"components/navigation/SidebarNav.jsx"},{"name":"SidebarItem","sourcePath":"components/navigation/SidebarNav.jsx"},{"name":"SidebarNav","sourcePath":"components/navigation/SidebarNav.jsx"},{"name":"TopBar","sourcePath":"components/navigation/TopBar.jsx"},{"name":"BrandLockup","sourcePath":"components/navigation/TopBar.jsx"}],"sourceHashes":{"components/core/Avatar.jsx":"e3b8677401c4","components/core/Badge.jsx":"4c74459c8042","components/core/Button.jsx":"075a29cb875c","components/core/Card.jsx":"8624cdf9838d","components/core/Icon.jsx":"613c09ab428b","components/core/IconButton.jsx":"67e75849177b","components/core/IconTile.jsx":"8608652cd36e","components/core/SearchField.jsx":"7116b062acae","components/core/Select.jsx":"3da7b1c60ad3","components/core/StatusPill.jsx":"75439aa88406","components/data/BarChart.jsx":"a00d97bf6b4c","components/data/DataTable.jsx":"6906f5272afc","components/data/GoalRow.jsx":"780368b7a080","components/data/StatCard.jsx":"b1c5edff106c","components/data/WalletTile.jsx":"f7a07bb681b5","components/navigation/PromoCard.jsx":"2fb0643d60a2","components/navigation/SidebarNav.jsx":"163022eab97d","components/navigation/TopBar.jsx":"1df7689c8c95","ui_kits/dashboard/AppShell.jsx":"9b3182405296","ui_kits/dashboard/DashboardScreen.jsx":"3eba0caee6ff","ui_kits/dashboard/SendMoneySheet.jsx":"f613a28d5e5e","ui_kits/dashboard/TransactionsScreen.jsx":"6e5321a5107c"},"inlinedExternals":[],"unexposedExports":[]} */

(() => {

const __ds_ns = (window.OripioDesignSystem_c89f4b = window.OripioDesignSystem_c89f4b || {});

const __ds_scope = {};

(__ds_ns.__errors = __ds_ns.__errors || []);

// components/core/Avatar.jsx
try { (() => {
function Avatar({
  src,
  name = '',
  size = 30,
  ring = true,
  style
}) {
  const initials = name.split(' ').map(w => w[0]).slice(0, 2).join('').toUpperCase();
  return /*#__PURE__*/React.createElement("span", {
    style: {
      width: size,
      height: size,
      borderRadius: 'var(--radius-pill)',
      overflow: 'hidden',
      display: 'inline-flex',
      alignItems: 'center',
      justifyContent: 'center',
      flex: '0 0 auto',
      background: 'var(--green-50)',
      color: 'var(--green-700)',
      fontSize: Math.round(size * 0.36),
      fontWeight: 'var(--weight-bold)',
      boxShadow: ring ? '0 0 0 2px var(--white)' : 'none',
      ...style
    }
  }, src ? /*#__PURE__*/React.createElement("img", {
    src: src,
    alt: name,
    style: {
      width: '100%',
      height: '100%',
      objectFit: 'cover'
    }
  }) : initials);
}
Object.assign(__ds_scope, { Avatar });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Avatar.jsx", error: String((e && e.message) || e) }); }

// components/core/Badge.jsx
try { (() => {
const badgeTones = {
  positive: {
    background: 'var(--success-50)',
    color: 'var(--success-600)'
  },
  negative: {
    background: 'var(--danger-50)',
    color: 'var(--danger-600)'
  },
  warning: {
    background: 'var(--amber-50)',
    color: 'var(--amber-600)'
  },
  neutral: {
    background: 'var(--ink-100)',
    color: 'var(--ink-500)'
  },
  brand: {
    background: 'var(--green-50)',
    color: 'var(--green-600)'
  }
};
function Badge({
  tone = 'positive',
  arrow,
  children,
  style
}) {
  return /*#__PURE__*/React.createElement("span", {
    className: "o-num",
    style: {
      display: 'inline-flex',
      alignItems: 'center',
      gap: 3,
      height: 20,
      padding: '0 7px',
      borderRadius: 'var(--radius-pill)',
      fontSize: 'var(--text-2xs)',
      fontWeight: 'var(--weight-semibold)',
      letterSpacing: '-0.01em',
      ...badgeTones[tone],
      ...style
    }
  }, children, arrow ? /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 9,
      lineHeight: 1
    }
  }, arrow === 'up' ? '↑' : '↓') : null);
}
Object.assign(__ds_scope, { Badge });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Badge.jsx", error: String((e && e.message) || e) }); }

// components/core/Button.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const btnBase = {
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  gap: 8,
  fontFamily: 'var(--font-sans)',
  fontWeight: 'var(--weight-semibold)',
  letterSpacing: '-0.01em',
  borderRadius: 'var(--radius-pill)',
  border: '1px solid transparent',
  cursor: 'pointer',
  whiteSpace: 'nowrap',
  transition: 'var(--transition-control)',
  textDecoration: 'none'
};
const btnSizes = {
  sm: {
    height: 'var(--control-h-sm)',
    padding: '0 14px',
    fontSize: 'var(--text-xs)'
  },
  md: {
    height: 'var(--control-h-md)',
    padding: '0 16px',
    fontSize: 'var(--text-sm)'
  },
  lg: {
    height: 'var(--control-h-lg)',
    padding: '0 20px',
    fontSize: 'var(--text-md)'
  }
};
const btnVariants = {
  primary: {
    background: 'var(--surface-brand)',
    color: 'var(--text-on-brand)'
  },
  secondary: {
    background: 'var(--ink-100)',
    color: 'var(--text-strong)'
  },
  dark: {
    background: 'var(--surface-dark)',
    color: 'var(--text-on-brand)'
  },
  outline: {
    background: 'var(--white)',
    color: 'var(--text-strong)',
    borderColor: 'var(--border-hairline)'
  },
  ghost: {
    background: 'transparent',
    color: 'var(--text-body)'
  },
  onBrand: {
    background: 'var(--white)',
    color: 'var(--green-700)'
  }
};
const btnHovers = {
  primary: {
    background: 'var(--green-700)'
  },
  secondary: {
    background: 'var(--ink-200)'
  },
  dark: {
    background: 'var(--ink-700)'
  },
  outline: {
    background: 'var(--ink-50)'
  },
  ghost: {
    background: 'var(--ink-100)',
    color: 'var(--text-strong)'
  },
  onBrand: {
    background: 'var(--green-25)'
  }
};
function Button({
  variant = 'primary',
  size = 'md',
  icon,
  iconRight,
  fullWidth = false,
  disabled = false,
  as = 'button',
  children,
  style,
  ...rest
}) {
  const [hover, setHover] = React.useState(false);
  const [down, setDown] = React.useState(false);
  const Tag = as;
  return /*#__PURE__*/React.createElement(Tag, _extends({
    disabled: Tag === 'button' ? disabled : undefined,
    onMouseEnter: () => setHover(true),
    onMouseLeave: () => {
      setHover(false);
      setDown(false);
    },
    onMouseDown: () => setDown(true),
    onMouseUp: () => setDown(false),
    style: {
      ...btnBase,
      ...btnSizes[size],
      ...btnVariants[variant],
      ...(hover && !disabled ? btnHovers[variant] : null),
      width: fullWidth ? '100%' : undefined,
      transform: down && !disabled ? 'scale(.985)' : 'scale(1)',
      opacity: disabled ? 0.45 : 1,
      cursor: disabled ? 'not-allowed' : 'pointer',
      ...style
    }
  }, rest), icon ? /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'flex',
      fontSize: 0
    }
  }, icon) : null, children, iconRight ? /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'flex',
      fontSize: 0
    }
  }, iconRight) : null);
}
Object.assign(__ds_scope, { Button });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Button.jsx", error: String((e && e.message) || e) }); }

// components/core/Icon.jsx
try { (() => {
/* Oripio uses Lucide (2px round-cap outline) as its icon set — see
   readme.md → ICONOGRAPHY. The CDN UMD build must be on the page:
   <script src="https://unpkg.com/lucide@0.474.0/dist/umd/lucide.js"></script> */
function Icon({
  name,
  size = 16,
  strokeWidth = 2,
  color = 'currentColor',
  style
}) {
  const ref = React.useRef(null);
  React.useEffect(() => {
    const el = ref.current;
    if (!el || !window.lucide) return;
    el.innerHTML = '';
    const i = document.createElement('i');
    i.setAttribute('data-lucide', name);
    el.appendChild(i);
    window.lucide.createIcons({
      nameAttr: 'data-lucide',
      attrs: {
        width: size,
        height: size,
        stroke: color,
        'stroke-width': strokeWidth
      },
      root: el
    });
  }, [name, size, strokeWidth, color]);
  return /*#__PURE__*/React.createElement("span", {
    ref: ref,
    "aria-hidden": "true",
    style: {
      display: 'inline-flex',
      width: size,
      height: size,
      flex: '0 0 auto',
      color,
      ...style
    }
  });
}
Object.assign(__ds_scope, { Icon });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Icon.jsx", error: String((e && e.message) || e) }); }

// components/core/IconButton.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const iconBtnShapes = {
  circle: {
    borderRadius: 'var(--radius-pill)'
  },
  square: {
    borderRadius: 'var(--radius-sm)'
  }
};
function IconButton({
  children,
  label,
  variant = 'outline',
  shape = 'circle',
  size = 34,
  style,
  ...rest
}) {
  const [hover, setHover] = React.useState(false);
  const fills = {
    outline: {
      background: 'var(--white)',
      border: '1px solid var(--border-hairline)',
      color: 'var(--ink-700)'
    },
    ghost: {
      background: 'transparent',
      border: '1px solid transparent',
      color: 'var(--text-muted)'
    },
    sunken: {
      background: 'var(--surface-sunken)',
      border: '1px solid transparent',
      color: 'var(--ink-700)'
    }
  };
  return /*#__PURE__*/React.createElement("button", _extends({
    "aria-label": label,
    onMouseEnter: () => setHover(true),
    onMouseLeave: () => setHover(false),
    style: {
      width: size,
      height: size,
      display: 'inline-flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: 0,
      cursor: 'pointer',
      transition: 'var(--transition-control)',
      ...iconBtnShapes[shape],
      ...fills[variant],
      ...(hover ? {
        background: 'var(--ink-50)',
        color: 'var(--text-strong)'
      } : null),
      ...style
    }
  }, rest), children);
}
Object.assign(__ds_scope, { IconButton });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/IconButton.jsx", error: String((e && e.message) || e) }); }

// components/core/IconTile.jsx
try { (() => {
function IconTile({
  children,
  tone = 'brand',
  size = 28,
  style
}) {
  const tones = {
    brand: {
      background: 'var(--green-50)',
      color: 'var(--green-600)'
    },
    neutral: {
      background: 'var(--ink-50)',
      color: 'var(--ink-500)'
    },
    amber: {
      background: 'var(--amber-50)',
      color: 'var(--amber-600)'
    },
    white: {
      background: 'var(--white)',
      color: 'var(--green-600)'
    }
  };
  return /*#__PURE__*/React.createElement("span", {
    style: {
      width: size,
      height: size,
      flex: '0 0 auto',
      borderRadius: 'var(--radius-sm)',
      display: 'inline-flex',
      alignItems: 'center',
      justifyContent: 'center',
      ...tones[tone],
      ...style
    }
  }, children);
}
Object.assign(__ds_scope, { IconTile });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/IconTile.jsx", error: String((e && e.message) || e) }); }

// components/core/Card.jsx
try { (() => {
function Card({
  children,
  pad = true,
  style
}) {
  return /*#__PURE__*/React.createElement("section", {
    style: {
      background: 'var(--surface-card)',
      borderRadius: 'var(--radius-lg)',
      padding: pad ? 'var(--card-pad)' : 0,
      boxShadow: 'var(--shadow-card)',
      ...style
    }
  }, children);
}
function CardHeader({
  icon,
  title,
  actions,
  style
}) {
  return /*#__PURE__*/React.createElement("header", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 10,
      marginBottom: 14,
      ...style
    }
  }, icon ? /*#__PURE__*/React.createElement(__ds_scope.IconTile, null, icon) : null, /*#__PURE__*/React.createElement("h3", {
    style: {
      fontSize: 'var(--text-lg)',
      fontWeight: 'var(--weight-bold)',
      color: 'var(--text-heading)',
      letterSpacing: 'var(--tracking-tight)'
    }
  }, title), /*#__PURE__*/React.createElement("div", {
    style: {
      marginLeft: 'auto',
      display: 'flex',
      alignItems: 'center',
      gap: 8
    }
  }, actions));
}
Object.assign(__ds_scope, { Card, CardHeader });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Card.jsx", error: String((e && e.message) || e) }); }

// components/core/SearchField.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
function SearchField({
  placeholder = 'Search',
  shortcut = '⌘ K',
  width = 180,
  style,
  ...rest
}) {
  const [focus, setFocus] = React.useState(false);
  return /*#__PURE__*/React.createElement("label", {
    style: {
      display: 'inline-flex',
      alignItems: 'center',
      gap: 8,
      height: 'var(--control-h-sm)',
      padding: '0 6px 0 12px',
      borderRadius: 'var(--radius-pill)',
      background: 'var(--surface-sunken)',
      boxShadow: focus ? '0 0 0 3px var(--focus-ring)' : 'none',
      transition: 'var(--transition-control)',
      width,
      ...style
    }
  }, /*#__PURE__*/React.createElement("svg", {
    width: "14",
    height: "14",
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "var(--text-muted)",
    strokeWidth: "2.2",
    strokeLinecap: "round"
  }, /*#__PURE__*/React.createElement("circle", {
    cx: "11",
    cy: "11",
    r: "7"
  }), /*#__PURE__*/React.createElement("path", {
    d: "m20 20-3.5-3.5"
  })), /*#__PURE__*/React.createElement("input", _extends({
    placeholder: placeholder,
    onFocus: () => setFocus(true),
    onBlur: () => setFocus(false),
    style: {
      flex: 1,
      minWidth: 0,
      border: 'none',
      outline: 'none',
      background: 'transparent',
      fontFamily: 'var(--font-sans)',
      fontSize: 'var(--text-sm)',
      color: 'var(--text-strong)'
    }
  }, rest)), shortcut ? /*#__PURE__*/React.createElement("kbd", {
    style: {
      fontFamily: 'var(--font-sans)',
      fontSize: 'var(--text-2xs)',
      fontWeight: 'var(--weight-semibold)',
      color: 'var(--text-muted)',
      background: 'var(--white)',
      borderRadius: 'var(--radius-xs)',
      padding: '3px 6px'
    }
  }, shortcut) : null);
}
Object.assign(__ds_scope, { SearchField });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/SearchField.jsx", error: String((e && e.message) || e) }); }

// components/core/Select.jsx
try { (() => {
function Select({
  value,
  options = [],
  onChange,
  leading,
  variant = 'ghost',
  size = 'sm',
  style
}) {
  const [open, setOpen] = React.useState(false);
  const pad = size === 'sm' ? '0 8px' : '0 12px';
  const fills = {
    ghost: {
      background: 'transparent',
      border: '1px solid transparent'
    },
    outline: {
      background: 'var(--white)',
      border: '1px solid var(--border-hairline)'
    },
    sunken: {
      background: 'var(--surface-sunken)',
      border: '1px solid transparent'
    }
  };
  return /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'relative',
      ...style
    }
  }, /*#__PURE__*/React.createElement("button", {
    onClick: () => setOpen(o => !o),
    style: {
      display: 'inline-flex',
      alignItems: 'center',
      gap: 6,
      cursor: 'pointer',
      height: size === 'sm' ? 28 : 'var(--control-h-sm)',
      padding: pad,
      borderRadius: 'var(--radius-pill)',
      fontFamily: 'var(--font-sans)',
      fontSize: 'var(--text-xs)',
      fontWeight: 'var(--weight-semibold)',
      color: 'var(--text-heading)',
      whiteSpace: 'nowrap',
      transition: 'var(--transition-control)',
      ...fills[variant]
    }
  }, leading, value, /*#__PURE__*/React.createElement("svg", {
    width: "12",
    height: "12",
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "2.4",
    strokeLinecap: "round",
    style: {
      opacity: .5,
      transform: open ? 'rotate(180deg)' : 'none',
      transition: 'transform var(--duration-fast) var(--ease-standard)'
    }
  }, /*#__PURE__*/React.createElement("path", {
    d: "m6 9 6 6 6-6"
  }))), open ? /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'absolute',
      top: 'calc(100% + 6px)',
      right: 0,
      zIndex: 20,
      minWidth: 130,
      background: 'var(--white)',
      borderRadius: 'var(--radius-md)',
      boxShadow: 'var(--shadow-overlay)',
      padding: 6
    }
  }, options.map(o => /*#__PURE__*/React.createElement("button", {
    key: o,
    onClick: () => {
      onChange && onChange(o);
      setOpen(false);
    },
    style: {
      display: 'block',
      width: '100%',
      textAlign: 'left',
      border: 'none',
      cursor: 'pointer',
      padding: '7px 9px',
      borderRadius: 'var(--radius-xs)',
      background: o === value ? 'var(--green-50)' : 'transparent',
      color: o === value ? 'var(--green-600)' : 'var(--text-body)',
      fontSize: 'var(--text-xs)',
      fontWeight: 'var(--weight-semibold)'
    }
  }, o))) : null);
}
Object.assign(__ds_scope, { Select });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Select.jsx", error: String((e && e.message) || e) }); }

// components/core/StatusPill.jsx
try { (() => {
const statusTones = {
  success: {
    color: 'var(--success-600)',
    dot: 'var(--success-500)'
  },
  pending: {
    color: 'var(--amber-600)',
    dot: 'var(--amber-600)'
  },
  failed: {
    color: 'var(--danger-600)',
    dot: 'var(--danger-600)'
  },
  inactive: {
    color: 'var(--amber-600)',
    dot: 'var(--amber-600)'
  },
  active: {
    color: 'var(--success-600)',
    dot: 'var(--success-600)'
  }
};
function StatusPill({
  tone = 'success',
  dot = true,
  children,
  style
}) {
  const t = statusTones[tone];
  return /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'inline-flex',
      alignItems: 'center',
      gap: 5,
      fontSize: 'var(--text-xs)',
      fontWeight: 'var(--weight-semibold)',
      color: t.color,
      ...style
    }
  }, dot ? /*#__PURE__*/React.createElement("span", {
    style: {
      width: 12,
      height: 12,
      borderRadius: 'var(--radius-pill)',
      background: t.dot,
      display: 'inline-flex',
      alignItems: 'center',
      justifyContent: 'center',
      color: 'var(--white)',
      fontSize: 8,
      fontWeight: 'var(--weight-bold)',
      lineHeight: 1
    }
  }, tone === 'success' || tone === 'active' ? '✓' : '') : null, children);
}
Object.assign(__ds_scope, { StatusPill });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/StatusPill.jsx", error: String((e && e.message) || e) }); }

// components/data/BarChart.jsx
try { (() => {
function BarChart({
  data = [],
  activeIndex = -1,
  height = 190,
  ticks = ['$40k', '$30k', '$20k', '$10k', '$0k'],
  tooltip,
  onHover,
  style
}) {
  const max = Math.max(...data.map(d => d.value), 1);
  const [hover, setHover] = React.useState(activeIndex);
  const active = hover;
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 10,
      ...style
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      justifyContent: 'space-between',
      height,
      paddingBottom: 20,
      fontSize: 'var(--text-2xs)',
      color: 'var(--text-muted)',
      textAlign: 'right'
    },
    className: "o-num"
  }, ticks.map(t => /*#__PURE__*/React.createElement("span", {
    key: t
  }, t))), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      position: 'relative'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'absolute',
      inset: '0 0 20px 0',
      display: 'flex',
      flexDirection: 'column',
      justifyContent: 'space-between'
    }
  }, ticks.map((t, i) => /*#__PURE__*/React.createElement("div", {
    key: t,
    style: {
      height: 1,
      background: i === ticks.length - 1 ? 'var(--chart-grid)' : 'var(--ink-100)'
    }
  }))), /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'relative',
      height,
      display: 'flex',
      alignItems: 'flex-end',
      gap: '2.2%'
    }
  }, data.map((d, i) => {
    const isActive = i === active;
    const h = Math.max(6, d.value / max * (height - 26));
    return /*#__PURE__*/React.createElement("div", {
      key: d.label,
      onMouseEnter: () => {
        setHover(i);
        onHover && onHover(i);
      },
      style: {
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 7,
        cursor: 'default'
      }
    }, /*#__PURE__*/React.createElement("div", {
      style: {
        position: 'relative',
        width: '100%',
        display: 'flex',
        justifyContent: 'center'
      }
    }, isActive ? /*#__PURE__*/React.createElement("span", {
      style: {
        position: 'absolute',
        top: -13,
        width: 11,
        height: 11,
        borderRadius: 'var(--radius-pill)',
        background: 'var(--green-600)',
        boxShadow: '0 0 0 3px var(--white)'
      }
    }) : null, /*#__PURE__*/React.createElement("div", {
      style: {
        width: '62%',
        height: h,
        borderRadius: 'var(--radius-pill)',
        background: isActive ? 'linear-gradient(180deg,var(--green-600) 0%,var(--green-500) 55%,rgba(255,255,255,0) 100%)' : 'linear-gradient(180deg,var(--green-100) 0%,rgba(227,244,236,0) 100%)',
        transition: 'height var(--duration-slow) var(--ease-out), background var(--duration-fast) var(--ease-standard)'
      }
    })), /*#__PURE__*/React.createElement("span", {
      style: {
        fontSize: 'var(--text-2xs)',
        fontWeight: isActive ? 'var(--weight-bold)' : 'var(--weight-medium)',
        color: isActive ? 'var(--text-heading)' : 'var(--text-muted)'
      }
    }, d.label));
  })), tooltip && active > -1 ? /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'absolute',
      left: `${(active + 0.5) / data.length * 100}%`,
      top: 4,
      transform: 'translateX(-40%)',
      background: 'var(--white)',
      borderRadius: 'var(--radius-md)',
      boxShadow: 'var(--shadow-overlay)',
      padding: '7px 11px',
      pointerEvents: 'none'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 'var(--text-2xs)',
      color: 'var(--text-muted)'
    }
  }, tooltip.label), /*#__PURE__*/React.createElement("div", {
    className: "o-num",
    style: {
      fontSize: 'var(--text-md)',
      fontWeight: 'var(--weight-bold)',
      color: 'var(--text-heading)',
      letterSpacing: 'var(--tracking-tight)'
    }
  }, tooltip.value)) : null));
}
Object.assign(__ds_scope, { BarChart });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/data/BarChart.jsx", error: String((e && e.message) || e) }); }

// components/data/DataTable.jsx
try { (() => {
function DataTable({
  columns = [],
  rows = [],
  style
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      ...style
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: columns.map(c => c.width || '1fr').join(' '),
      gap: 10,
      padding: '9px 12px',
      borderRadius: 'var(--radius-sm)',
      background: 'var(--surface-sunken)',
      fontSize: 'var(--text-xs)',
      fontWeight: 'var(--weight-semibold)',
      color: 'var(--text-body)'
    }
  }, columns.map(c => /*#__PURE__*/React.createElement("span", {
    key: c.key,
    style: {
      textAlign: c.align || 'left'
    }
  }, c.label))), rows.map((r, i) => /*#__PURE__*/React.createElement("div", {
    key: i,
    style: {
      display: 'grid',
      gridTemplateColumns: columns.map(c => c.width || '1fr').join(' '),
      gap: 10,
      padding: '11px 12px',
      alignItems: 'center',
      borderBottom: i === rows.length - 1 ? 'none' : '1px solid var(--border-hairline)',
      fontSize: 'var(--text-sm)',
      color: 'var(--text-heading)',
      fontWeight: 'var(--weight-medium)'
    }
  }, columns.map(c => /*#__PURE__*/React.createElement("span", {
    key: c.key,
    className: c.numeric ? 'o-num' : undefined,
    style: {
      textAlign: c.align || 'left',
      display: 'flex',
      alignItems: 'center',
      gap: 9,
      justifyContent: c.align === 'right' ? 'flex-end' : 'flex-start',
      color: c.muted ? 'var(--text-body)' : undefined
    }
  }, r[c.key])))));
}
Object.assign(__ds_scope, { DataTable });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/data/DataTable.jsx", error: String((e && e.message) || e) }); }

// components/data/GoalRow.jsx
try { (() => {
function GoalRow({
  icon,
  title,
  current,
  target,
  percent,
  tone = 'brand',
  style
}) {
  const accent = tone === 'amber' ? 'var(--amber-600)' : 'var(--green-600)';
  return /*#__PURE__*/React.createElement("div", {
    style: {
      background: 'var(--surface-tile)',
      borderRadius: 'var(--radius-md)',
      padding: '12px 14px',
      ...style
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 9
    }
  }, /*#__PURE__*/React.createElement(__ds_scope.IconTile, {
    tone: tone,
    size: 26,
    style: {
      background: 'var(--white)'
    }
  }, icon), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 'var(--text-md)',
      fontWeight: 'var(--weight-semibold)',
      color: 'var(--text-heading)'
    }
  }, title)), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'baseline',
      gap: 8,
      marginTop: 10
    }
  }, /*#__PURE__*/React.createElement("span", {
    className: "o-num",
    style: {
      fontSize: 'var(--text-sm)',
      color: 'var(--text-body)'
    }
  }, /*#__PURE__*/React.createElement("strong", {
    style: {
      color: 'var(--text-heading)',
      fontWeight: 'var(--weight-bold)'
    }
  }, current), "/", target), /*#__PURE__*/React.createElement("span", {
    className: "o-num",
    style: {
      marginLeft: 'auto',
      fontSize: 'var(--text-sm)',
      fontWeight: 'var(--weight-bold)',
      color: accent
    }
  }, percent, "%")), /*#__PURE__*/React.createElement("div", {
    style: {
      marginTop: 8,
      height: 5,
      borderRadius: 'var(--radius-pill)',
      background: 'var(--white)',
      overflow: 'hidden'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: `${percent}%`,
      height: '100%',
      borderRadius: 'var(--radius-pill)',
      background: accent,
      transition: 'width var(--duration-slow) var(--ease-out)'
    }
  })));
}
Object.assign(__ds_scope, { GoalRow });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/data/GoalRow.jsx", error: String((e && e.message) || e) }); }

// components/data/StatCard.jsx
try { (() => {
function StatCard({
  icon,
  title,
  value,
  delta,
  deltaTone = 'positive',
  deltaArrow = 'up',
  caption = 'from last month',
  actions,
  children,
  style
}) {
  return /*#__PURE__*/React.createElement(__ds_scope.Card, {
    style: style
  }, /*#__PURE__*/React.createElement(__ds_scope.CardHeader, {
    icon: icon,
    title: title,
    actions: actions
  }), /*#__PURE__*/React.createElement("div", {
    className: "o-num",
    style: {
      fontSize: 'var(--text-2xl)',
      fontWeight: 'var(--weight-extrabold)',
      letterSpacing: 'var(--tracking-tight)',
      color: 'var(--text-heading)',
      lineHeight: 1.1
    }
  }, value), delta != null ? /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 8,
      marginTop: 10
    }
  }, /*#__PURE__*/React.createElement(__ds_scope.Badge, {
    tone: deltaTone,
    arrow: deltaArrow
  }, delta), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 'var(--text-xs)',
      color: 'var(--text-body)'
    }
  }, caption)) : null, children);
}
Object.assign(__ds_scope, { StatCard });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/data/StatCard.jsx", error: String((e && e.message) || e) }); }

// components/data/WalletTile.jsx
try { (() => {
function WalletTile({
  flag,
  code,
  amount,
  status = 'active',
  onMore,
  style
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      background: 'var(--surface-tile)',
      borderRadius: 'var(--radius-md)',
      padding: '10px 12px',
      ...style
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 7
    }
  }, flag, /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 'var(--text-xs)',
      fontWeight: 'var(--weight-semibold)',
      color: 'var(--text-body)'
    }
  }, code), /*#__PURE__*/React.createElement("button", {
    onClick: onMore,
    "aria-label": `${code} options`,
    style: {
      marginLeft: 'auto',
      border: 'none',
      background: 'transparent',
      cursor: 'pointer',
      color: 'var(--text-muted)',
      padding: 0,
      lineHeight: 1,
      fontSize: 14
    }
  }, "\u22EE")), /*#__PURE__*/React.createElement("div", {
    className: "o-num",
    style: {
      marginTop: 6,
      fontSize: 'var(--text-lg)',
      fontWeight: 'var(--weight-bold)',
      letterSpacing: 'var(--tracking-tight)',
      color: 'var(--text-heading)'
    }
  }, amount), /*#__PURE__*/React.createElement(__ds_scope.StatusPill, {
    tone: status,
    dot: false,
    style: {
      marginTop: 4,
      fontSize: 'var(--text-2xs)'
    }
  }, status === 'active' ? 'Active' : 'Inactive'));
}
Object.assign(__ds_scope, { WalletTile });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/data/WalletTile.jsx", error: String((e && e.message) || e) }); }

// components/navigation/PromoCard.jsx
try { (() => {
function PromoCard({
  title,
  body,
  action,
  style
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      background: 'linear-gradient(180deg,var(--green-600) 0%,var(--green-800) 100%)',
      borderRadius: 'var(--radius-lg)',
      padding: '18px 14px',
      textAlign: 'center',
      color: 'var(--text-on-brand)',
      ...style
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 'var(--text-md)',
      fontWeight: 'var(--weight-bold)',
      letterSpacing: 'var(--tracking-tight)'
    }
  }, title), /*#__PURE__*/React.createElement("p", {
    style: {
      margin: '6px 0 14px',
      fontSize: 'var(--text-xs)',
      lineHeight: 'var(--leading-normal)',
      color: 'rgba(255,255,255,.78)'
    }
  }, body), action);
}
Object.assign(__ds_scope, { PromoCard });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/navigation/PromoCard.jsx", error: String((e && e.message) || e) }); }

// components/navigation/SidebarNav.jsx
try { (() => {
function SidebarSectionLabel({
  children,
  style
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '0 10px',
      marginBottom: 8,
      fontSize: 'var(--text-2xs)',
      fontWeight: 'var(--weight-bold)',
      letterSpacing: 'var(--tracking-label)',
      textTransform: 'uppercase',
      color: 'var(--text-muted)',
      ...style
    }
  }, children);
}
function SidebarItem({
  icon,
  label,
  count,
  active = false,
  onClick,
  style
}) {
  const [hover, setHover] = React.useState(false);
  return /*#__PURE__*/React.createElement("button", {
    onClick: onClick,
    onMouseEnter: () => setHover(true),
    onMouseLeave: () => setHover(false),
    style: {
      position: 'relative',
      display: 'flex',
      alignItems: 'center',
      gap: 10,
      width: '100%',
      height: 38,
      padding: '0 12px',
      border: 'none',
      cursor: 'pointer',
      textAlign: 'left',
      borderRadius: 'var(--radius-md)',
      transition: 'var(--transition-control)',
      background: active ? 'var(--nav-item-active-bg)' : hover ? 'var(--ink-50)' : 'transparent',
      color: active ? 'var(--nav-item-active-text)' : 'var(--nav-item-rest-text)',
      fontFamily: 'var(--font-sans)',
      fontSize: 'var(--text-md)',
      fontWeight: active ? 'var(--weight-semibold)' : 'var(--weight-medium)',
      ...style
    }
  }, active ? /*#__PURE__*/React.createElement("span", {
    style: {
      position: 'absolute',
      left: 2,
      top: '50%',
      transform: 'translateY(-50%)',
      width: 3,
      height: 14,
      borderRadius: 'var(--radius-pill)',
      background: 'var(--green-600)'
    }
  }) : null, icon, /*#__PURE__*/React.createElement("span", {
    style: {
      flex: 1,
      minWidth: 0,
      overflow: 'hidden',
      textOverflow: 'ellipsis',
      whiteSpace: 'nowrap'
    }
  }, label), count != null ? /*#__PURE__*/React.createElement("span", {
    className: "o-num",
    style: {
      fontSize: 'var(--text-xs)',
      fontWeight: 'var(--weight-semibold)',
      color: 'var(--text-muted)'
    }
  }, count) : null);
}
function SidebarNav({
  children,
  style
}) {
  return /*#__PURE__*/React.createElement("nav", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 2,
      ...style
    }
  }, children);
}
Object.assign(__ds_scope, { SidebarSectionLabel, SidebarItem, SidebarNav });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/navigation/SidebarNav.jsx", error: String((e && e.message) || e) }); }

// components/navigation/TopBar.jsx
try { (() => {
function TopBar({
  left,
  children,
  style
}) {
  return /*#__PURE__*/React.createElement("header", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 10,
      height: 56,
      padding: '0 18px 0 14px',
      ...style
    }
  }, left, /*#__PURE__*/React.createElement("div", {
    style: {
      marginLeft: 'auto',
      display: 'flex',
      alignItems: 'center',
      gap: 8
    }
  }, children));
}
function BrandLockup({
  src = 'assets/logo-mark.png',
  name = 'Oripio',
  size = 30,
  style
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 9,
      ...style
    }
  }, /*#__PURE__*/React.createElement("img", {
    src: src,
    width: size,
    height: size,
    alt: "",
    style: {
      borderRadius: 'var(--radius-sm)',
      display: 'block'
    }
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 'var(--text-xl)',
      fontWeight: 'var(--weight-bold)',
      letterSpacing: 'var(--tracking-tight)',
      color: 'var(--text-strong)'
    }
  }, name));
}
Object.assign(__ds_scope, { TopBar, BrandLockup });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/navigation/TopBar.jsx", error: String((e && e.message) || e) }); }

// ui_kits/dashboard/AppShell.jsx
try { (() => {
const {
  SidebarNav,
  SidebarItem,
  SidebarSectionLabel,
  PromoCard,
  BrandLockup,
  TopBar,
  Button,
  IconButton,
  SearchField,
  Avatar,
  Icon
} = window.OripioDesignSystem_c89f4b;
const NAV = [{
  label: 'Main Menu',
  items: [{
    id: 'dashboard',
    label: 'Dashboard',
    icon: 'layout-grid'
  }, {
    id: 'analytics',
    label: 'Analytics',
    icon: 'chart-pie',
    count: 20
  }, {
    id: 'transactions',
    label: 'Transactions',
    icon: 'credit-card'
  }, {
    id: 'invoices',
    label: 'Invoices',
    icon: 'file-text'
  }]
}, {
  label: 'Features',
  items: [{
    id: 'recurring',
    label: 'Recurring',
    icon: 'layers',
    count: 16
  }, {
    id: 'subscriptions',
    label: 'Subscriptions',
    icon: 'badge-dollar-sign'
  }, {
    id: 'feedback',
    label: 'Feedback',
    icon: 'users'
  }]
}, {
  label: 'General',
  items: [{
    id: 'settings',
    label: 'Settings',
    icon: 'settings'
  }, {
    id: 'help',
    label: 'Help Desk',
    icon: 'circle-help'
  }, {
    id: 'logout',
    label: 'Log out',
    icon: 'log-out'
  }]
}];
function AppShell({
  route,
  onRoute,
  children
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      height: '100%',
      background: 'var(--surface-shell)',
      borderRadius: 'var(--radius-xl)',
      boxShadow: 'var(--shadow-shell)',
      overflow: 'hidden'
    }
  }, /*#__PURE__*/React.createElement("aside", {
    style: {
      width: 'var(--sidebar-width)',
      flex: '0 0 var(--sidebar-width)',
      display: 'flex',
      flexDirection: 'column',
      padding: '14px 12px 14px 14px'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 8,
      height: 34,
      marginBottom: 18
    }
  }, /*#__PURE__*/React.createElement(BrandLockup, {
    src: "../../assets/logo-mark.png",
    size: 28,
    style: {
      flex: 1
    }
  }), /*#__PURE__*/React.createElement(IconButton, {
    label: "Collapse sidebar",
    variant: "ghost",
    size: 22
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "chevrons-left",
    size: 14
  }))), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      display: 'flex',
      flexDirection: 'column',
      gap: 16,
      overflow: 'hidden'
    }
  }, NAV.map(group => /*#__PURE__*/React.createElement("div", {
    key: group.label
  }, /*#__PURE__*/React.createElement(SidebarSectionLabel, null, group.label), /*#__PURE__*/React.createElement(SidebarNav, null, group.items.map(it => /*#__PURE__*/React.createElement(SidebarItem, {
    key: it.id,
    label: it.label,
    count: it.count,
    icon: /*#__PURE__*/React.createElement(Icon, {
      name: it.icon,
      size: 17
    }),
    active: route === it.id,
    onClick: () => onRoute(it.id)
  })))))), /*#__PURE__*/React.createElement(PromoCard, {
    title: /*#__PURE__*/React.createElement("span", null, "Upgrade Pro! \uD83C\uDFC6"),
    body: "Higher productivity with better organization",
    action: /*#__PURE__*/React.createElement(Button, {
      variant: "onBrand",
      size: "md",
      fullWidth: true,
      icon: /*#__PURE__*/React.createElement(Icon, {
        name: "crown",
        size: 14
      })
    }, "Upgrade")
  })), /*#__PURE__*/React.createElement("main", {
    style: {
      flex: 1,
      minWidth: 0,
      margin: '8px 8px 8px 0',
      padding: '0 0 0 0',
      background: 'var(--surface-page)',
      borderRadius: 'var(--radius-lg)',
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden'
    }
  }, /*#__PURE__*/React.createElement(TopBar, {
    left: /*#__PURE__*/React.createElement(SearchField, {
      width: 190
    }),
    style: {
      background: 'var(--surface-page)'
    }
  }, /*#__PURE__*/React.createElement(IconButton, {
    label: "Help"
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "circle-help",
    size: 16
  })), /*#__PURE__*/React.createElement(IconButton, {
    label: "Messages"
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "mail",
    size: 16
  })), /*#__PURE__*/React.createElement(IconButton, {
    label: "Notifications"
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "bell",
    size: 16
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 4,
      marginLeft: 4
    }
  }, /*#__PURE__*/React.createElement(Avatar, {
    src: "../../assets/avatar-user.png",
    name: "Sajibur Rahman"
  }), /*#__PURE__*/React.createElement(Icon, {
    name: "chevrons-up-down",
    size: 14,
    color: "var(--text-muted)"
  }))), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      overflowY: 'auto',
      padding: '6px 18px 18px'
    }
  }, children)));
}
function PageHead({
  title,
  subtitle,
  actions
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'flex-start',
      gap: 16,
      marginBottom: 16
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      minWidth: 0
    }
  }, /*#__PURE__*/React.createElement("h1", {
    style: {
      fontSize: 'var(--text-3xl)',
      fontWeight: 'var(--weight-extrabold)'
    }
  }, title), /*#__PURE__*/React.createElement("p", {
    style: {
      marginTop: 6,
      fontSize: 'var(--text-sm)',
      color: 'var(--text-body)'
    }
  }, subtitle)), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 10
    }
  }, actions));
}
Object.assign(window, {
  AppShell,
  PageHead,
  ORIPIO_NAV: NAV
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/dashboard/AppShell.jsx", error: String((e && e.message) || e) }); }

// ui_kits/dashboard/DashboardScreen.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const {
  Card,
  CardHeader,
  StatCard,
  Button,
  IconButton,
  Icon,
  IconTile,
  Select,
  Badge,
  StatusPill,
  WalletTile,
  GoalRow,
  BarChart,
  DataTable
} = window.OripioDesignSystem_c89f4b;
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const SERIES = [19, 27, 31, 22, 29, 11, 13, 40, 24, 19, 10, 23];
const EARNINGS = ['$21,410.02', '$38,204.15', '$46,900.77', '$28,140.60', '$41,006.31', '$12,880.44', '$15,220.10', '$84,849.93', '$33,470.28', '$22,905.66', '$11,340.19', '$29,776.05'];
const more = /*#__PURE__*/React.createElement(IconButton, {
  label: "More options",
  variant: "ghost",
  size: 26
}, /*#__PURE__*/React.createElement(Icon, {
  name: "more-horizontal",
  size: 16
}));
function DashboardScreen({
  onSend,
  onRequest,
  wallets,
  goals,
  transactions
}) {
  const [currency, setCurrency] = React.useState('USD');
  const [period, setPeriod] = React.useState('This Year');
  const [active, setActive] = React.useState(7);
  return /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: '1.02fr 1.98fr',
      gap: 'var(--card-gap)',
      alignItems: 'start'
    }
  }, /*#__PURE__*/React.createElement(Card, null, /*#__PURE__*/React.createElement(CardHeader, {
    icon: /*#__PURE__*/React.createElement(Icon, {
      name: "wallet",
      size: 15
    }),
    title: "Account Balance",
    actions: /*#__PURE__*/React.createElement(Select, {
      value: currency,
      options: ['USD', 'EUR', 'GBP', 'BDT'],
      onChange: setCurrency,
      leading: /*#__PURE__*/React.createElement("img", {
        src: `../../assets/flag-${currency.toLowerCase()}.png`,
        width: "17",
        alt: "",
        style: {
          borderRadius: 2
        }
      })
    })
  }), /*#__PURE__*/React.createElement("div", {
    className: "o-num",
    style: {
      fontSize: 34,
      fontWeight: 'var(--weight-extrabold)',
      letterSpacing: '-0.03em',
      color: 'var(--text-heading)',
      lineHeight: 1.05
    }
  }, "$35,340.89"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 8,
      marginTop: 10
    }
  }, /*#__PURE__*/React.createElement(Badge, {
    tone: "positive",
    arrow: "up"
  }, "+3.2%"), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 'var(--text-xs)',
      color: 'var(--text-body)'
    }
  }, "from last month")), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 10,
      marginTop: 16
    }
  }, /*#__PURE__*/React.createElement(Button, {
    variant: "primary",
    size: "lg",
    onClick: onSend,
    icon: /*#__PURE__*/React.createElement(Icon, {
      name: "upload",
      size: 15
    }),
    style: {
      flex: 1
    }
  }, "Send Money"), /*#__PURE__*/React.createElement(Button, {
    variant: "secondary",
    size: "lg",
    onClick: onRequest,
    icon: /*#__PURE__*/React.createElement(Icon, {
      name: "download",
      size: 15
    }),
    style: {
      flex: 1
    }
  }, "Request Money")), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      marginTop: 20,
      marginBottom: 10
    }
  }, /*#__PURE__*/React.createElement("h3", {
    style: {
      fontSize: 'var(--text-md)',
      fontWeight: 'var(--weight-bold)'
    }
  }, "My Wallet"), /*#__PURE__*/React.createElement(Button, {
    variant: "secondary",
    size: "sm",
    icon: /*#__PURE__*/React.createElement(Icon, {
      name: "plus",
      size: 13
    }),
    style: {
      marginLeft: 'auto'
    }
  }, "Add New")), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: '1fr 1fr',
      gap: 10
    }
  }, wallets.map(w => /*#__PURE__*/React.createElement(WalletTile, {
    key: w.code,
    code: w.code,
    amount: w.amount,
    status: w.status,
    flag: /*#__PURE__*/React.createElement("img", {
      src: `../../assets/flag-${w.code.toLowerCase()}.png`,
      width: "16",
      alt: "",
      style: {
        borderRadius: 2
      }
    })
  })))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 'var(--card-gap)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: '1fr 1fr',
      gap: 'var(--card-gap)'
    }
  }, /*#__PURE__*/React.createElement(StatCard, {
    icon: /*#__PURE__*/React.createElement(Icon, {
      name: "banknote",
      size: 15
    }),
    title: "Total Expenses",
    value: "$9,845.20",
    delta: "-2.1%",
    deltaTone: "negative",
    deltaArrow: "down",
    actions: more
  }), /*#__PURE__*/React.createElement(StatCard, {
    icon: /*#__PURE__*/React.createElement(Icon, {
      name: "piggy-bank",
      size: 15
    }),
    title: "Total Savings",
    value: "$18,420.75",
    delta: "+4.5%",
    actions: more
  })), /*#__PURE__*/React.createElement(Card, null, /*#__PURE__*/React.createElement(CardHeader, {
    icon: /*#__PURE__*/React.createElement(Icon, {
      name: "chart-no-axes-column",
      size: 15
    }),
    title: "Overview",
    actions: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("span", {
      style: {
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        fontSize: 'var(--text-xs)',
        fontWeight: 'var(--weight-semibold)',
        color: 'var(--text-heading)'
      }
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        width: 5,
        height: 12,
        borderRadius: 99,
        background: 'var(--green-600)'
      }
    }), "Earnings"), /*#__PURE__*/React.createElement(Select, {
      value: period,
      options: ['This Year', 'This Month', 'This Week'],
      onChange: setPeriod,
      variant: "outline"
    }), more)
  }), /*#__PURE__*/React.createElement(BarChart, {
    data: MONTHS.map((m, i) => ({
      label: m,
      value: SERIES[i]
    })),
    activeIndex: 7,
    onHover: setActive,
    height: 200,
    tooltip: {
      label: 'Earnings',
      value: EARNINGS[active] || EARNINGS[7]
    }
  })))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: '1.02fr 1.98fr',
      gap: 'var(--card-gap)',
      marginTop: 'var(--card-gap)',
      alignItems: 'start'
    }
  }, /*#__PURE__*/React.createElement(Card, null, /*#__PURE__*/React.createElement(CardHeader, {
    icon: /*#__PURE__*/React.createElement(Icon, {
      name: "lightbulb",
      size: 15
    }),
    title: "My Savings Plan",
    actions: more
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 10
    }
  }, goals.map(g => /*#__PURE__*/React.createElement(GoalRow, _extends({
    key: g.title
  }, g, {
    icon: /*#__PURE__*/React.createElement(Icon, {
      name: g.icon,
      size: 14
    })
  }))))), /*#__PURE__*/React.createElement(Card, null, /*#__PURE__*/React.createElement(CardHeader, {
    icon: /*#__PURE__*/React.createElement(Icon, {
      name: "arrow-up-down",
      size: 15
    }),
    title: "Recent Transaction",
    actions: /*#__PURE__*/React.createElement(Button, {
      variant: "outline",
      size: "sm",
      iconRight: /*#__PURE__*/React.createElement(Icon, {
        name: "list-filter",
        size: 13
      })
    }, "Filter")
  }), /*#__PURE__*/React.createElement(DataTable, {
    columns: [{
      key: 'activity',
      label: 'Activity',
      width: '1.9fr'
    }, {
      key: 'date',
      label: 'Date',
      muted: true,
      numeric: true
    }, {
      key: 'price',
      label: 'Price',
      numeric: true,
      width: '.7fr'
    }, {
      key: 'status',
      label: 'Status',
      width: '.8fr'
    }, {
      key: 'more',
      label: '',
      width: '34px',
      align: 'right'
    }],
    rows: transactions.map(t => ({
      activity: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(IconTile, {
        tone: "neutral",
        size: 22
      }, /*#__PURE__*/React.createElement(Icon, {
        name: t.icon,
        size: 12
      })), t.name),
      date: t.date,
      price: t.price,
      status: /*#__PURE__*/React.createElement(StatusPill, {
        tone: t.status
      }, t.status === 'success' ? 'Success' : t.status === 'pending' ? 'Pending' : 'Failed'),
      more: more
    }))
  }))));
}
Object.assign(window, {
  DashboardScreen
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/dashboard/DashboardScreen.jsx", error: String((e && e.message) || e) }); }

// ui_kits/dashboard/SendMoneySheet.jsx
try { (() => {
const {
  Button,
  Icon,
  IconTile,
  Select,
  StatusPill,
  Avatar
} = window.OripioDesignSystem_c89f4b;
function SendMoneySheet({
  open,
  onClose,
  onSent,
  wallets
}) {
  const [amount, setAmount] = React.useState('250.00');
  const [from, setFrom] = React.useState('USD');
  if (!open) return null;
  return /*#__PURE__*/React.createElement("div", {
    onClick: onClose,
    style: {
      position: 'absolute',
      inset: 0,
      background: 'rgba(21,22,27,.28)',
      backdropFilter: 'blur(2px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 50,
      borderRadius: 'var(--radius-xl)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    onClick: e => e.stopPropagation(),
    style: {
      width: 380,
      background: 'var(--surface-card)',
      borderRadius: 'var(--radius-lg)',
      boxShadow: 'var(--shadow-overlay)',
      padding: 'var(--card-pad)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 10,
      marginBottom: 16
    }
  }, /*#__PURE__*/React.createElement(IconTile, null, /*#__PURE__*/React.createElement(Icon, {
    name: "upload",
    size: 15
  })), /*#__PURE__*/React.createElement("h3", {
    style: {
      fontSize: 'var(--text-lg)'
    }
  }, "Send Money"), /*#__PURE__*/React.createElement("button", {
    onClick: onClose,
    "aria-label": "Close",
    style: {
      marginLeft: 'auto',
      border: 'none',
      background: 'transparent',
      cursor: 'pointer',
      color: 'var(--text-muted)',
      display: 'flex'
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "x",
    size: 17
  }))), /*#__PURE__*/React.createElement("div", {
    style: {
      background: 'var(--surface-tile)',
      borderRadius: 'var(--radius-md)',
      padding: '12px 14px',
      display: 'flex',
      alignItems: 'center',
      gap: 10
    }
  }, /*#__PURE__*/React.createElement(Avatar, {
    name: "Rafiul Karim",
    size: 34,
    ring: false
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 'var(--text-sm)',
      fontWeight: 'var(--weight-semibold)',
      color: 'var(--text-heading)'
    }
  }, "Rafiul Karim"), /*#__PURE__*/React.createElement("div", {
    className: "o-num",
    style: {
      fontSize: 'var(--text-xs)',
      color: 'var(--text-body)'
    }
  }, "\xB7\xB7\xB7\xB7  8842 \xB7 Oripio")), /*#__PURE__*/React.createElement(Icon, {
    name: "chevron-right",
    size: 16,
    color: "var(--text-muted)"
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      marginTop: 14,
      marginBottom: 6,
      fontSize: 'var(--text-2xs)',
      fontWeight: 'var(--weight-bold)',
      letterSpacing: 'var(--tracking-label)',
      textTransform: 'uppercase',
      color: 'var(--text-muted)'
    }
  }, "Amount"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 10,
      background: 'var(--surface-sunken)',
      borderRadius: 'var(--radius-md)',
      padding: '10px 12px'
    }
  }, /*#__PURE__*/React.createElement("span", {
    className: "o-num",
    style: {
      fontSize: 'var(--text-2xl)',
      fontWeight: 'var(--weight-extrabold)',
      color: 'var(--text-heading)'
    }
  }, "$"), /*#__PURE__*/React.createElement("input", {
    value: amount,
    onChange: e => setAmount(e.target.value),
    className: "o-num",
    style: {
      flex: 1,
      minWidth: 0,
      border: 'none',
      background: 'transparent',
      outline: 'none',
      fontFamily: 'var(--font-sans)',
      fontSize: 'var(--text-2xl)',
      fontWeight: 'var(--weight-extrabold)',
      letterSpacing: 'var(--tracking-tight)',
      color: 'var(--text-heading)'
    }
  }), /*#__PURE__*/React.createElement(Select, {
    value: from,
    options: wallets.map(w => w.code),
    onChange: setFrom,
    variant: "outline",
    leading: /*#__PURE__*/React.createElement("img", {
      src: `../../assets/flag-${from.toLowerCase()}.png`,
      width: "16",
      alt: "",
      style: {
        borderRadius: 2
      }
    })
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 8,
      marginTop: 12,
      fontSize: 'var(--text-xs)',
      color: 'var(--text-body)'
    }
  }, /*#__PURE__*/React.createElement(StatusPill, {
    tone: "success"
  }, "No fee"), /*#__PURE__*/React.createElement("span", null, "Arrives instantly on Oripio")), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 10,
      marginTop: 18
    }
  }, /*#__PURE__*/React.createElement(Button, {
    variant: "secondary",
    size: "lg",
    style: {
      flex: 1
    },
    onClick: onClose
  }, "Cancel"), /*#__PURE__*/React.createElement(Button, {
    variant: "primary",
    size: "lg",
    style: {
      flex: 1.3
    },
    onClick: () => onSent(amount, from),
    icon: /*#__PURE__*/React.createElement(Icon, {
      name: "upload",
      size: 15
    })
  }, 'Send $' + amount))));
}
Object.assign(window, {
  SendMoneySheet
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/dashboard/SendMoneySheet.jsx", error: String((e && e.message) || e) }); }

// ui_kits/dashboard/TransactionsScreen.jsx
try { (() => {
const {
  Card,
  CardHeader,
  Button,
  IconButton,
  Icon,
  IconTile,
  Select,
  StatusPill,
  DataTable,
  SearchField,
  Badge
} = window.OripioDesignSystem_c89f4b;
const more = /*#__PURE__*/React.createElement(IconButton, {
  label: "More options",
  variant: "ghost",
  size: 26
}, /*#__PURE__*/React.createElement(Icon, {
  name: "more-horizontal",
  size: 16
}));
function TransactionsScreen({
  transactions
}) {
  const [tab, setTab] = React.useState('All');
  const rows = transactions.filter(t => tab === 'All' || tab === 'Success' && t.status === 'success' || tab === 'Pending' && t.status === 'pending' || tab === 'Failed' && t.status === 'failed');
  return /*#__PURE__*/React.createElement(Card, null, /*#__PURE__*/React.createElement(CardHeader, {
    icon: /*#__PURE__*/React.createElement(Icon, {
      name: "credit-card",
      size: 15
    }),
    title: "All Transactions",
    actions: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(SearchField, {
      width: 170,
      shortcut: null,
      placeholder: "Search activity"
    }), /*#__PURE__*/React.createElement(Select, {
      value: "This Month",
      options: ['This Month', 'This Year'],
      variant: "outline"
    }), /*#__PURE__*/React.createElement(Button, {
      variant: "dark",
      size: "sm",
      icon: /*#__PURE__*/React.createElement(Icon, {
        name: "download",
        size: 13
      })
    }, "Export"))
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 6,
      marginBottom: 12
    }
  }, ['All', 'Success', 'Pending', 'Failed'].map(t => /*#__PURE__*/React.createElement(Button, {
    key: t,
    size: "sm",
    variant: tab === t ? 'primary' : 'ghost',
    onClick: () => setTab(t)
  }, t))), /*#__PURE__*/React.createElement(DataTable, {
    columns: [{
      key: 'activity',
      label: 'Activity',
      width: '1.9fr'
    }, {
      key: 'date',
      label: 'Date',
      muted: true,
      numeric: true
    }, {
      key: 'method',
      label: 'Method',
      muted: true
    }, {
      key: 'price',
      label: 'Price',
      numeric: true,
      width: '.8fr'
    }, {
      key: 'status',
      label: 'Status',
      width: '.8fr'
    }, {
      key: 'more',
      label: '',
      width: '34px',
      align: 'right'
    }],
    rows: rows.map(t => ({
      activity: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(IconTile, {
        tone: "neutral",
        size: 22
      }, /*#__PURE__*/React.createElement(Icon, {
        name: t.icon,
        size: 12
      })), t.name),
      date: t.date,
      method: t.method || 'Card ···· 4417',
      price: t.price,
      status: /*#__PURE__*/React.createElement(StatusPill, {
        tone: t.status
      }, t.status === 'success' ? 'Success' : t.status === 'pending' ? 'Pending' : 'Failed'),
      more: more
    }))
  }));
}
Object.assign(window, {
  TransactionsScreen
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/dashboard/TransactionsScreen.jsx", error: String((e && e.message) || e) }); }

__ds_ns.Avatar = __ds_scope.Avatar;

__ds_ns.Badge = __ds_scope.Badge;

__ds_ns.Button = __ds_scope.Button;

__ds_ns.Card = __ds_scope.Card;

__ds_ns.CardHeader = __ds_scope.CardHeader;

__ds_ns.Icon = __ds_scope.Icon;

__ds_ns.IconButton = __ds_scope.IconButton;

__ds_ns.IconTile = __ds_scope.IconTile;

__ds_ns.SearchField = __ds_scope.SearchField;

__ds_ns.Select = __ds_scope.Select;

__ds_ns.StatusPill = __ds_scope.StatusPill;

__ds_ns.BarChart = __ds_scope.BarChart;

__ds_ns.DataTable = __ds_scope.DataTable;

__ds_ns.GoalRow = __ds_scope.GoalRow;

__ds_ns.StatCard = __ds_scope.StatCard;

__ds_ns.WalletTile = __ds_scope.WalletTile;

__ds_ns.PromoCard = __ds_scope.PromoCard;

__ds_ns.SidebarSectionLabel = __ds_scope.SidebarSectionLabel;

__ds_ns.SidebarItem = __ds_scope.SidebarItem;

__ds_ns.SidebarNav = __ds_scope.SidebarNav;

__ds_ns.TopBar = __ds_scope.TopBar;

__ds_ns.BrandLockup = __ds_scope.BrandLockup;

})();
