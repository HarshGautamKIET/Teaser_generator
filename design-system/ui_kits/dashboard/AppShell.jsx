const { SidebarNav, SidebarItem, SidebarSectionLabel, PromoCard, BrandLockup, TopBar, Button, IconButton, SearchField, Avatar, Icon } = window.OripioDesignSystem_c89f4b;

const NAV = [
  { label:'Main Menu', items:[
    { id:'dashboard', label:'Dashboard', icon:'layout-grid' },
    { id:'analytics', label:'Analytics', icon:'chart-pie', count:20 },
    { id:'transactions', label:'Transactions', icon:'credit-card' },
    { id:'invoices', label:'Invoices', icon:'file-text' }
  ]},
  { label:'Features', items:[
    { id:'recurring', label:'Recurring', icon:'layers', count:16 },
    { id:'subscriptions', label:'Subscriptions', icon:'badge-dollar-sign' },
    { id:'feedback', label:'Feedback', icon:'users' }
  ]},
  { label:'General', items:[
    { id:'settings', label:'Settings', icon:'settings' },
    { id:'help', label:'Help Desk', icon:'circle-help' },
    { id:'logout', label:'Log out', icon:'log-out' }
  ]}
];

function AppShell({ route, onRoute, children }) {
  return (
    <div style={{
      display:'flex', height:'100%', background:'var(--surface-shell)',
      borderRadius:'var(--radius-xl)', boxShadow:'var(--shadow-shell)', overflow:'hidden'
    }}>
      <aside style={{
        width:'var(--sidebar-width)', flex:'0 0 var(--sidebar-width)',
        display:'flex', flexDirection:'column', padding:'14px 12px 14px 14px'
      }}>
        <div style={{display:'flex', alignItems:'center', gap:8, height:34, marginBottom:18}}>
          <BrandLockup src="../../assets/logo-mark.png" size={28} style={{flex:1}} />
          <IconButton label="Collapse sidebar" variant="ghost" size={22}><Icon name="chevrons-left" size={14} /></IconButton>
        </div>
        <div style={{flex:1, display:'flex', flexDirection:'column', gap:16, overflow:'hidden'}}>
          {NAV.map(group => (
            <div key={group.label}>
              <SidebarSectionLabel>{group.label}</SidebarSectionLabel>
              <SidebarNav>
                {group.items.map(it => (
                  <SidebarItem key={it.id} label={it.label} count={it.count}
                    icon={<Icon name={it.icon} size={17} />}
                    active={route === it.id}
                    onClick={() => onRoute(it.id)} />
                ))}
              </SidebarNav>
            </div>
          ))}
        </div>
        <PromoCard title={<span>Upgrade Pro! 🏆</span>}
          body="Higher productivity with better organization"
          action={<Button variant="onBrand" size="md" fullWidth icon={<Icon name="crown" size={14} />}>Upgrade</Button>} />
      </aside>
      <main style={{
        flex:1, minWidth:0, margin:'8px 8px 8px 0', padding:'0 0 0 0',
        background:'var(--surface-page)', borderRadius:'var(--radius-lg)',
        display:'flex', flexDirection:'column', overflow:'hidden'
      }}>
        <TopBar left={<SearchField width={190} />} style={{background:'var(--surface-page)'}}>
          <IconButton label="Help"><Icon name="circle-help" size={16} /></IconButton>
          <IconButton label="Messages"><Icon name="mail" size={16} /></IconButton>
          <IconButton label="Notifications"><Icon name="bell" size={16} /></IconButton>
          <div style={{display:'flex', alignItems:'center', gap:4, marginLeft:4}}>
            <Avatar src="../../assets/avatar-user.png" name="Sajibur Rahman" />
            <Icon name="chevrons-up-down" size={14} color="var(--text-muted)" />
          </div>
        </TopBar>
        <div style={{flex:1, overflowY:'auto', padding:'6px 18px 18px'}}>{children}</div>
      </main>
    </div>
  );
}

function PageHead({ title, subtitle, actions }) {
  return (
    <div style={{display:'flex', alignItems:'flex-start', gap:16, marginBottom:16}}>
      <div style={{flex:1, minWidth:0}}>
        <h1 style={{fontSize:'var(--text-3xl)', fontWeight:'var(--weight-extrabold)'}}>{title}</h1>
        <p style={{marginTop:6, fontSize:'var(--text-sm)', color:'var(--text-body)'}}>{subtitle}</p>
      </div>
      <div style={{display:'flex', alignItems:'center', gap:10}}>{actions}</div>
    </div>
  );
}

Object.assign(window, { AppShell, PageHead, ORIPIO_NAV: NAV });
