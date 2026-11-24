# Answer capture list

No baseline image is stored. A later capture, after the look review, records one frame for each row. Do not compare pixels in this task.

| Language | Theme | Viewport | Drawer |
|---|---|---|---|
| en | dark | 3840×2160 | closed |
| en | dark | 3840×2160 | open |
| en | light | 3840×2160 | closed |
| en | light | 3840×2160 | open |
| ar | dark | 3840×2160 | closed |
| ar | dark | 3840×2160 | open |
| ar | light | 3840×2160 | closed |
| ar | light | 3840×2160 | open |
| en | dark | 1920×1080 | closed |
| en | dark | 1920×1080 | open |
| en | light | 1920×1080 | closed |
| en | light | 1920×1080 | open |
| ar | dark | 1920×1080 | closed |
| ar | dark | 1920×1080 | open |
| ar | light | 1920×1080 | closed |
| ar | light | 1920×1080 | open |
| en | dark | 1440×900 | closed |
| en | dark | 1440×900 | open |
| en | light | 1440×900 | closed |
| en | light | 1440×900 | open |
| ar | dark | 1440×900 | closed |
| ar | dark | 1440×900 | open |
| ar | light | 1440×900 | closed |
| ar | light | 1440×900 | open |
| en | dark | 1024×768 | closed |
| en | dark | 1024×768 | open |
| en | light | 1024×768 | closed |
| en | light | 1024×768 | open |
| ar | dark | 1024×768 | closed |
| ar | dark | 1024×768 | open |
| ar | light | 1024×768 | closed |
| ar | light | 1024×768 | open |

States, both languages, behind `?scene=states`. No baseline image.

| Language | Theme | Viewport | Scene |
|---|---|---|---|
| en | dark | 1440×900 | states |
| ar | dark | 1440×900 | states |
| en | dark | 1440×900 | open synthetic |
| ar | dark | 1440×900 | open synthetic |
| en | dark | 1440×900 | open simulated |
| ar | dark | 1440×900 | open simulated |
| en | dark | 1440×900 | open suppressed |
| ar | dark | 1440×900 | open suppressed |
| en | dark | 1440×900 | open observed |
| ar | dark | 1440×900 | open observed |
| en | dark | 1440×900 | open inferred |
| ar | dark | 1440×900 | open inferred |
| en | dark | 1440×900 | open still to test |
| ar | dark | 1440×900 | open still to test |

The states page shows a hero chip, a no-data chip, a loading chip, a refused chip, Synthetic, Simulated and Suppressed class chips, an inline composite chip, and a receipt link with an injected address. Class words stay off the default closed page.

The page is `web/tests/visual/index.html` with `lang` and `theme`. The product entry `/` is the empty shell and is not a capture row.

Drawing, both languages, behind `web/tests/visual/draw.html`. No baseline image.

| Language | Theme | Viewport | Scene |
|---|---|---|---|
| en | dark | 1440×900 | polygon drawn |
| ar | dark | 1440×900 | polygon drawn |
| en | dark | 1440×900 | radius chips |
| ar | dark | 1440×900 | radius chips |
| en | dark | 1024×768 | tools idle |
| ar | dark | 1024×768 | tools idle |

Public context cards (S3-T14), both languages, behind `?scene=context` in `web/tests/visual/context-sizes.spec.ts`. No baseline image; each run writes one frame per row under `.overnight/evidence/S3-T14/sizes/` for the owner's review (decision 0049 item 6).

| Language | Theme | Viewport | Scene |
|---|---|---|---|
| en, ar | dark, light | the ten views of decision 0049's eight named sizes (`NAMED_SIZES`) | context, all levels open |
