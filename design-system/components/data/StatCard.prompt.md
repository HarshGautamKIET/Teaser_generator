The dashboard's KPI card. Value is always tabular and currency-prefixed; the delta is green up / red down.

```jsx
<StatCard icon={<Icon name="wallet" size={15} />} title="Total Expenses" value="$9,845.20"
  delta="-2.1%" deltaTone="negative" deltaArrow="down"
  actions={<IconButton label="More" variant="ghost" size={26}><Icon name="more-horizontal" size={16} /></IconButton>} />
```
