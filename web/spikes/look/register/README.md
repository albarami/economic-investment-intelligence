# Invented establishment stand-in

Every value in `establishments.csv` is invented for this page. It is not a collected register, and none of the names is a real business. The page reads this file when `EII_REGISTER_FILE` is unset. Tests and the hosted job use only this file. A real register file is never copied here.

| | |
|---|---|
| Date written | 2026-11-13 |
| How it was made | A fixed generator, `web/spikes/look/tools/build_standin.mjs`, placed 800 invented rows around twelve invented centres of activity on land in Greater Doha and Lusail (a fixed seed, spreads cut at one and a half times their value, and a hand-drawn line inland of the coast per centre); every row also carries an invented `employees` count |
| Rows | 800 |
| SHA-256 | `017b4bcaa1b31b08b42f670c669f83bb14d7e9dc198e645924398b283b74aadb` |

Columns are the published fields in `.overnight/IN/register-table-shape.md`, plus `employees` (the owner's decision of 2026-11-13: the company card shows the number of employees; no wage or other labour field). Empty optional fields are blank. No registration number, licence number or person's name is present.
