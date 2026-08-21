Flat table with a sunken header strip. Keep it to 4–5 columns and put a <StatusPill> in the last data column.

```jsx
<DataTable
  columns={[{key:'activity',label:'Activity',width:'1.7fr'},{key:'date',label:'Date',muted:true,numeric:true},
            {key:'price',label:'Price',numeric:true},{key:'status',label:'Status'},{key:'more',label:'',width:'32px',align:'right'}]}
  rows={[{activity:'Mobile App Purchase', date:'Wed, 12 Jun 2026', price:'$806.50', status:<StatusPill>Success</StatusPill>}]} />
```
