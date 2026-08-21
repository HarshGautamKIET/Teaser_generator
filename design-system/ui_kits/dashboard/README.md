# Oripio Dashboard — UI kit

Faithful recreation of the one product view present in the source material:
the personal-finance dashboard in `uploads/ec5fe68b55cbefac884d2fa29ac65fe2.jpg`.

## Files
| File | What it is |
| --- | --- |
| `index.html` | Interactive click-through. Sidebar routing, currency switch, chart hover, Send Money sheet → new transaction row + toast. |
| `AppShell.jsx` | Rounded white shell: sidebar (brand lockup, grouped nav, upgrade promo) + top bar + scrolling content area. Also exports `PageHead`. |
| `DashboardScreen.jsx` | The reference screen: Account Balance + My Wallet, Total Expenses / Total Savings, Overview bar chart, My Savings Plan, Recent Transaction. |
| `TransactionsScreen.jsx` | Full transaction list, composed only from patterns visible in the source (card header, tab-like pill buttons, DataTable, StatusPill). |
| `SendMoneySheet.jsx` | Modal for the Send Money / Request Money buttons. Extrapolated — see caveat. |

## Fidelity notes
- Layout, colour, radii, type sizes and spacing come from measuring the source render.
- **Extrapolated, not observed:** the Send Money sheet, the Transactions list and the toast. Nothing in the source shows these; they reuse observed patterns only and add no new visual language.
- Every other sidebar destination renders an explicit "intentionally blank" placeholder rather than an invented screen.
- Transaction row glyphs in the source are third-party brand marks (App Store, Adobe, Walmart). Those are not redistributed here — neutral Lucide glyphs in an `IconTile` stand in.
