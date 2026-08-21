const { Card, CardHeader, StatCard, Button, IconButton, Icon, IconTile, Select, Badge, StatusPill, WalletTile, GoalRow, BarChart, DataTable } = window.OripioDesignSystem_c89f4b;

const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
const SERIES = [19,27,31,22,29,11,13,40,24,19,10,23];
const EARNINGS = ['$21,410.02','$38,204.15','$46,900.77','$28,140.60','$41,006.31','$12,880.44','$15,220.10','$84,849.93','$33,470.28','$22,905.66','$11,340.19','$29,776.05'];

const more = <IconButton label="More options" variant="ghost" size={26}><Icon name="more-horizontal" size={16} /></IconButton>;

function DashboardScreen({ onSend, onRequest, wallets, goals, transactions }) {
  const [currency, setCurrency] = React.useState('USD');
  const [period, setPeriod] = React.useState('This Year');
  const [active, setActive] = React.useState(7);
  return (
    <div>
      <div style={{display:'grid', gridTemplateColumns:'1.02fr 1.98fr', gap:'var(--card-gap)', alignItems:'start'}}>
        {/* Account balance + wallet column */}
        <Card>
          <CardHeader icon={<Icon name="wallet" size={15} />} title="Account Balance"
            actions={<Select value={currency} options={['USD','EUR','GBP','BDT']} onChange={setCurrency}
              leading={<img src={`../../assets/flag-${currency.toLowerCase()}.png`} width="17" alt="" style={{borderRadius:2}} />} />} />
          <div className="o-num" style={{fontSize:34, fontWeight:'var(--weight-extrabold)', letterSpacing:'-0.03em', color:'var(--text-heading)', lineHeight:1.05}}>$35,340.89</div>
          <div style={{display:'flex', alignItems:'center', gap:8, marginTop:10}}>
            <Badge tone="positive" arrow="up">+3.2%</Badge>
            <span style={{fontSize:'var(--text-xs)', color:'var(--text-body)'}}>from last month</span>
          </div>
          <div style={{display:'flex', gap:10, marginTop:16}}>
            <Button variant="primary" size="lg" onClick={onSend} icon={<Icon name="upload" size={15} />} style={{flex:1}}>Send Money</Button>
            <Button variant="secondary" size="lg" onClick={onRequest} icon={<Icon name="download" size={15} />} style={{flex:1}}>Request Money</Button>
          </div>
          <div style={{display:'flex', alignItems:'center', marginTop:20, marginBottom:10}}>
            <h3 style={{fontSize:'var(--text-md)', fontWeight:'var(--weight-bold)'}}>My Wallet</h3>
            <Button variant="secondary" size="sm" icon={<Icon name="plus" size={13} />} style={{marginLeft:'auto'}}>Add New</Button>
          </div>
          <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:10}}>
            {wallets.map(w => (
              <WalletTile key={w.code} code={w.code} amount={w.amount} status={w.status}
                flag={<img src={`../../assets/flag-${w.code.toLowerCase()}.png`} width="16" alt="" style={{borderRadius:2}} />} />
            ))}
          </div>
        </Card>

        {/* Right column */}
        <div style={{display:'flex', flexDirection:'column', gap:'var(--card-gap)'}}>
          <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:'var(--card-gap)'}}>
            <StatCard icon={<Icon name="banknote" size={15} />} title="Total Expenses" value="$9,845.20"
              delta="-2.1%" deltaTone="negative" deltaArrow="down" actions={more} />
            <StatCard icon={<Icon name="piggy-bank" size={15} />} title="Total Savings" value="$18,420.75"
              delta="+4.5%" actions={more} />
          </div>
          <Card>
            <CardHeader icon={<Icon name="chart-no-axes-column" size={15} />} title="Overview"
              actions={<>
                <span style={{display:'inline-flex', alignItems:'center', gap:6, fontSize:'var(--text-xs)', fontWeight:'var(--weight-semibold)', color:'var(--text-heading)'}}>
                  <span style={{width:5, height:12, borderRadius:99, background:'var(--green-600)'}} />Earnings
                </span>
                <Select value={period} options={['This Year','This Month','This Week']} onChange={setPeriod} variant="outline" />
                {more}
              </>} />
            <BarChart data={MONTHS.map((m,i) => ({label:m, value:SERIES[i]}))} activeIndex={7}
              onHover={setActive} height={200}
              tooltip={{label:'Earnings', value:EARNINGS[active] || EARNINGS[7]}} />
          </Card>
        </div>
      </div>

      <div style={{display:'grid', gridTemplateColumns:'1.02fr 1.98fr', gap:'var(--card-gap)', marginTop:'var(--card-gap)', alignItems:'start'}}>
        <Card>
          <CardHeader icon={<Icon name="lightbulb" size={15} />} title="My Savings Plan" actions={more} />
          <div style={{display:'flex', flexDirection:'column', gap:10}}>
            {goals.map(g => <GoalRow key={g.title} {...g} icon={<Icon name={g.icon} size={14} />} />)}
          </div>
        </Card>
        <Card>
          <CardHeader icon={<Icon name="arrow-up-down" size={15} />} title="Recent Transaction"
            actions={<Button variant="outline" size="sm" iconRight={<Icon name="list-filter" size={13} />}>Filter</Button>} />
          <DataTable
            columns={[
              {key:'activity', label:'Activity', width:'1.9fr'},
              {key:'date', label:'Date', muted:true, numeric:true},
              {key:'price', label:'Price', numeric:true, width:'.7fr'},
              {key:'status', label:'Status', width:'.8fr'},
              {key:'more', label:'', width:'34px', align:'right'}
            ]}
            rows={transactions.map(t => ({
              activity:<><IconTile tone="neutral" size={22}><Icon name={t.icon} size={12} /></IconTile>{t.name}</>,
              date:t.date, price:t.price,
              status:<StatusPill tone={t.status}>{t.status === 'success' ? 'Success' : t.status === 'pending' ? 'Pending' : 'Failed'}</StatusPill>,
              more:more
            }))} />
        </Card>
      </div>
    </div>
  );
}

Object.assign(window, { DashboardScreen });
