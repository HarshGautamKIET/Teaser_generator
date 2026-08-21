const { Card, CardHeader, Button, IconButton, Icon, IconTile, Select, StatusPill, DataTable, SearchField, Badge } = window.OripioDesignSystem_c89f4b;
const more = <IconButton label="More options" variant="ghost" size={26}><Icon name="more-horizontal" size={16} /></IconButton>;

function TransactionsScreen({ transactions }) {
  const [tab, setTab] = React.useState('All');
  const rows = transactions.filter(t => tab === 'All' || (tab === 'Success' && t.status === 'success') || (tab === 'Pending' && t.status === 'pending') || (tab === 'Failed' && t.status === 'failed'));
  return (
    <Card>
      <CardHeader icon={<Icon name="credit-card" size={15} />} title="All Transactions"
        actions={<><SearchField width={170} shortcut={null} placeholder="Search activity" />
          <Select value="This Month" options={['This Month','This Year']} variant="outline" />
          <Button variant="dark" size="sm" icon={<Icon name="download" size={13} />}>Export</Button></>} />
      <div style={{display:'flex', gap:6, marginBottom:12}}>
        {['All','Success','Pending','Failed'].map(t => (
          <Button key={t} size="sm" variant={tab === t ? 'primary' : 'ghost'} onClick={() => setTab(t)}>{t}</Button>
        ))}
      </div>
      <DataTable
        columns={[
          {key:'activity', label:'Activity', width:'1.9fr'},
          {key:'date', label:'Date', muted:true, numeric:true},
          {key:'method', label:'Method', muted:true},
          {key:'price', label:'Price', numeric:true, width:'.8fr'},
          {key:'status', label:'Status', width:'.8fr'},
          {key:'more', label:'', width:'34px', align:'right'}
        ]}
        rows={rows.map(t => ({
          activity:<><IconTile tone="neutral" size={22}><Icon name={t.icon} size={12} /></IconTile>{t.name}</>,
          date:t.date, method:t.method || 'Card ···· 4417', price:t.price,
          status:<StatusPill tone={t.status}>{t.status === 'success' ? 'Success' : t.status === 'pending' ? 'Pending' : 'Failed'}</StatusPill>,
          more:more
        }))} />
    </Card>
  );
}

Object.assign(window, { TransactionsScreen });
