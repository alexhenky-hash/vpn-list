# Единый список ресурсов для VPN

Правится **только `vpn.txt`**. После каждого сохранения GitHub Actions
сам собирает файлы в папке `dist/`:

| Файл | Для чего |
|---|---|
| `dist/awg.txt` | роутер Keenetic, AWG-Manager → правило → «Подписки» |
| `dist/geosite.dat`, `dist/geoip.dat` | Happ и INCY (категории `geosite:personal`, `geoip:personal`) |
| `dist/happ-deeplink.txt` | ссылка `happ://routing/onadd/...` — открыть на устройстве с Happ |
| `dist/incy-deeplink.txt` | ссылка `incy://routing/onadd/...` — открыть на устройстве с INCY |
| `dist/domains.txt`, `dist/cidr.txt` | отдельно домены и подсети |

Ссылки для подключения :

- Роутер: `https://cdn.jsdelivr.net/gh/alexhenky-hash/vpn-list@main/dist/awg.txt`
- Happ: содержимое `https://cdn.jsdelivr.net/gh/alexhenky-hash/vpn-list@main/dist/happ-deeplink.txt`
- INCY: содержимое `https://cdn.jsdelivr.net/gh/alexhenky-hash/vpn-list@main/dist/incy-deeplink.txt`

## Формат vpn.txt

```
# комментарий
example.com            # домен и все поддомены
full:api.example.com   # только точный адрес (Happ/INCY; роутер берёт как обычный домен)
1.2.3.0/24             # подсеть
```

## Профиль Happ / INCY

Через VPN идут только адреса из списка, всё остальное напрямую.
DNS для адресов из списка — 8.8.8.8 через VPN, для остальных — 77.88.8.8.

## Как обновляется

- **Роутер** — сам, AWG-Manager периодически скачивает `awg.txt`.
- **INCY** — сам при обновлении geo-файлов (сверяет `*.dat.sha256`).
- **Happ** — после правки заново открыть ссылку из `happ-deeplink.txt`
  (профиль с тем же именем перезаписывается).
