<div align="center">

# SysMonitor

**Lekki, nowoczesny monitor zasobów systemowych dla Linuksa**

Aplikacja desktopowa GTK3 do monitorowania RAM, SWAP i CPU w czasie rzeczywistym.
Ostrzega gdy kończy się pamięć i pozwala ubijać procesy bezpośrednio z GUI.

![Python](https://img.shields.io/badge/Python-3.8+-3776ab?style=for-the-badge&logo=python&logoColor=white)
![GTK](https://img.shields.io/badge/GTK-3.0-4a86cf?style=for-the-badge&logo=gnome&logoColor=white)
![Linux](https://img.shields.io/badge/Linux-FCC624?style=for-the-badge&logo=linux&logoColor=black)
![License](https://img.shields.io/badge/Licencja-MIT-green?style=for-the-badge)

![SysMonitor](sys_monitor.png)

[English (EN)](README.md)

</div>

---

## Funkcje

<table>
<tr>
<td width="50%">

### Monitoring w czasie rzeczywistym
- Kolorowe paski postępu RAM, SWAP, CPU
- Zielony = OK, Żółty = ostrzeżenie, Czerwony = alarm
- Konfigurowalne progi alarmowe

</td>
<td width="50%">

### Wskaźniki gauge
- Łukowe wskaźniki procentowe w każdej karcie
- Kolorowanie wg progów: zielony → żółty → czerwony
- Aktualizacja w czasie rzeczywistym

</td>
</tr>
<tr>
<td>

### Lista procesów
- Top 20 procesów wg zużycia RAM
- Sortowalne kolumny: PID, Nazwa, RAM (MB), CPU%, Czas, User, Status
- Grupy procesów (np. *"chrome: 12 proc., 3200 MB"*)

</td>
<td>

### Powiadomienia i akcje
- Powiadomienia desktopowe (`notify-send`)
- Ubijanie pojedynczych procesów lub całych grup
- Czyszczenie cache systemu plików (sudo)
- Cooldown 5 min między powiadomieniami

</td>
</tr>
</table>

---

## Wymagania

| Zależność | Opis | Wymagana? |
|-----------|------|:---------:|
| Python 3.8+ | Interpreter | Tak |
| GTK 3.0 + PyGObject | Interfejs graficzny | Tak |
| `python3-gi-cairo` | Rysowanie wykresów (Cairo) | Tak |
| `psutil` | Odczyt metryk systemowych | Tak |
| `notify-send` | Powiadomienia desktopowe | Opcjonalnie |

---

## Instalacja

<details>
<summary><b>Debian / Ubuntu</b></summary>

```bash
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-pango-1.0 libnotify-bin
pip install -r requirements.txt
```
</details>

<details>
<summary><b>Fedora</b></summary>

```bash
sudo dnf install python3-gobject gtk3 libnotify
pip install -r requirements.txt
```
</details>

<details>
<summary><b>Arch Linux</b></summary>

```bash
sudo pacman -S python-gobject gtk3 libnotify
pip install -r requirements.txt
```
</details>

---

## Uruchamianie

```bash
python3 sysmonitor.py
```

---

## Interfejs

```
┌──────────────────────────────────────────────────────┐
│  SYSMONITOR                           ● Status: OK   │
├──────────────────────────────────────────────────────┤
│  ┌──────────┐  ┌──────────┐  ┌──────────┐           │
│  │ RAM      │  │ SWAP     │  │ CPU      │           │
│  │ ██████░░ │  │ ███░░░░░ │  │ █████░░░ │           │
│  │ 62.3%    │  │ 34.1%    │  │ 47.8%    │           │
│  └──────────┘  └──────────┘  └──────────┘           │
├──────────────────────────────────────────────────────┤
│  PID   Nazwa         RAM(MB)  CPU%  Czas   User     │
│  1234  firefox        1200    3.2   01:23  user     │
│  5678  chrome          890    1.8   00:45  user     │
│  ...                                                 │
├──────────────────────────────────────────────────────┤
│  [Wyczyść cache]  [Ubij grupę]  [Ubij]  [Odśwież]  │
├──────────────────────────────────────────────────────┤
│  LOG: 12:30 RAM 82% — ostrzeżenie wysłane           │
└──────────────────────────────────────────────────────┘
```

---

## Konfiguracja

Edytuj stałe na górze pliku `sysmonitor.py`:

```python
RAM_WARNING    = 80    # % — żółte ostrzeżenie
RAM_CRITICAL   = 90    # % — czerwony alarm
SWAP_WARNING   = 70    # % — ostrzeżenie SWAP
CHECK_INTERVAL = 30    # sekundy między odświeżeniami
NOTIFY_COOLDOWN = 300  # sekundy między powiadomieniami
```

---

## Zabezpieczenia

- Nie ubija procesów systemowych (PID < 1000), procesów roota ani siebie
- Dialog potwierdzenia przed każdym ubiciem
- Łagodne zamykanie: `SIGTERM` → 5s oczekiwania → `SIGKILL`

---

<details>
<summary><b>Autostart (systemd)</b></summary>

```bash
mkdir -p ~/.config/systemd/user

cat > ~/.config/systemd/user/sysmonitor.service << 'EOF'
[Unit]
Description=System Resource Monitor

[Service]
Type=simple
ExecStart=/usr/bin/python3 /sciezka/do/sysmonitor.py
Restart=on-failure
RestartSec=10
Environment=DISPLAY=:0

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now sysmonitor.service
```
</details>

---

## Współpraca

Zapraszam do współtworzenia! Otwórz issue lub wyślij pull request.

## Licencja

Projekt na licencji MIT — szczegóły w pliku [LICENSE](LICENSE).
