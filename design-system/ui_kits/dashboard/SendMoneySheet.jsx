const { Button, Icon, IconTile, Select, StatusPill, Avatar } = window.OripioDesignSystem_c89f4b;

function SendMoneySheet({ open, onClose, onSent, wallets }) {
  const [amount, setAmount] = React.useState('250.00');
  const [from, setFrom] = React.useState('USD');
  if (!open) return null;
  return (
    <div onClick={onClose} style={{
      position:'absolute', inset:0, background:'rgba(21,22,27,.28)', backdropFilter:'blur(2px)',
      display:'flex', alignItems:'center', justifyContent:'center', zIndex:50,
      borderRadius:'var(--radius-xl)'
    }}>
      <div onClick={e => e.stopPropagation()} style={{
        width:380, background:'var(--surface-card)', borderRadius:'var(--radius-lg)',
        boxShadow:'var(--shadow-overlay)', padding:'var(--card-pad)'
      }}>
        <div style={{display:'flex', alignItems:'center', gap:10, marginBottom:16}}>
          <IconTile><Icon name="upload" size={15} /></IconTile>
          <h3 style={{fontSize:'var(--text-lg)'}}>Send Money</h3>
          <button onClick={onClose} aria-label="Close" style={{marginLeft:'auto', border:'none', background:'transparent', cursor:'pointer', color:'var(--text-muted)', display:'flex'}}>
            <Icon name="x" size={17} />
          </button>
        </div>
        <div style={{background:'var(--surface-tile)', borderRadius:'var(--radius-md)', padding:'12px 14px', display:'flex', alignItems:'center', gap:10}}>
          <Avatar name="Rafiul Karim" size={34} ring={false} />
          <div style={{flex:1}}>
            <div style={{fontSize:'var(--text-sm)', fontWeight:'var(--weight-semibold)', color:'var(--text-heading)'}}>Rafiul Karim</div>
            <div className="o-num" style={{fontSize:'var(--text-xs)', color:'var(--text-body)'}}>····  8842 · Oripio</div>
          </div>
          <Icon name="chevron-right" size={16} color="var(--text-muted)" />
        </div>
        <div style={{marginTop:14, marginBottom:6, fontSize:'var(--text-2xs)', fontWeight:'var(--weight-bold)', letterSpacing:'var(--tracking-label)', textTransform:'uppercase', color:'var(--text-muted)'}}>Amount</div>
        <div style={{display:'flex', alignItems:'center', gap:10, background:'var(--surface-sunken)', borderRadius:'var(--radius-md)', padding:'10px 12px'}}>
          <span className="o-num" style={{fontSize:'var(--text-2xl)', fontWeight:'var(--weight-extrabold)', color:'var(--text-heading)'}}>$</span>
          <input value={amount} onChange={e => setAmount(e.target.value)} className="o-num" style={{
            flex:1, minWidth:0, border:'none', background:'transparent', outline:'none',
            fontFamily:'var(--font-sans)', fontSize:'var(--text-2xl)', fontWeight:'var(--weight-extrabold)',
            letterSpacing:'var(--tracking-tight)', color:'var(--text-heading)'
          }} />
          <Select value={from} options={wallets.map(w => w.code)} onChange={setFrom} variant="outline"
            leading={<img src={`../../assets/flag-${from.toLowerCase()}.png`} width="16" alt="" style={{borderRadius:2}} />} />
        </div>
        <div style={{display:'flex', alignItems:'center', gap:8, marginTop:12, fontSize:'var(--text-xs)', color:'var(--text-body)'}}>
          <StatusPill tone="success">No fee</StatusPill>
          <span>Arrives instantly on Oripio</span>
        </div>
        <div style={{display:'flex', gap:10, marginTop:18}}>
          <Button variant="secondary" size="lg" style={{flex:1}} onClick={onClose}>Cancel</Button>
          <Button variant="primary" size="lg" style={{flex:1.3}} onClick={() => onSent(amount, from)} icon={<Icon name="upload" size={15} />}>{'Send $' + amount}</Button>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { SendMoneySheet });
