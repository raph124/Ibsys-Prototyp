# IBSYS II - Sensorbasierte Entscheidungsfindung für Lackieranlage

## 🎯 Übersicht

Vollständig funktionsfähiger Prototyp einer sensorbasierten Überwachungs- und Steuerungslösung für eine industrielle Lackierkabine. Das System überwacht kontinuierlich 4 kritische Parameter, erkennt Schwellenwertüberschreitungen und löst automatisch Korrekturmaßnahmen aus.

### Kernfunktionalität

**Ablauf (präzises Timing):**
1. **Sensoren** erfassen kontinuierlich Daten (Luftfeuchtigkeit, Temperatur, Düsendruck, Energieverbrauch)
2. **Anomalie-Erkennung**: Werte übersteigen Schwellenwerte
3. **20-Sekunden-Regel**: Alert wird erst nach 20 Sekunden anhaltender Überschreitung ausgelöst
4. **Automatische Aktion**: Worker führt vordefinierte Maßnahme aus (z.B. "Lüftung hochfahren")
5. **Sofortige Recovery**: Sensor erkennt Aktion innerhalb von 1 Sekunde und normalisiert Werte
6. **Dashboard-Visualisierung**: Echtzeit-Graphen zeigen die gesamte Ereigniskette

---

## 📊 Überwachte Parameter & Produktionsentscheidungen

| Parameter | Einheit | Normal-Bereich | Schwellenwerte | Produktionsentscheidung & Nachfolgeschritte |
|-----------|---------|----------------|----------------|---------------------------------------------|
| **Luftfeuchtigkeit** | % | 30-65 | < 30 oder > 65 | Entfeuchtung/Befeuchtung aktiviert, Robotergeschwindigkeit angepasst, QS-Kontrolle aktiviert |
| **Kabinentemperatur** | °C | 18-28 | < 18 oder > 28 | Produktion pausiert/Kühlprotokoll, Vorheizzeit/Trocknungszeit angepasst, Sonderprüfung |
| **Düsendruck** | bar | 1.8-3.2 | < 1.8 oder > 3.2 | Wartungsprotokoll/Druckanpassung, Sprühbild-Kontrolle, Testlackierung vor Freigabe |
| **Energieverbrauch** | W | 450-750 | < 450 oder > 750 | Energieoptimierung/NOTFALL-Stopp, Prozesse gestaffelt, Instandhaltung alarmiert |

---

## 🏗️ System-Architektur

```
┌─────────────────────────────────────────────────────────────┐
│                    GRAFANA DASHBOARD                         │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌────────┐│
│  │Luftfeuchtig.│ │ Temperatur  │ │ Düsendruck  │ │ Energie││
│  └─────────────┘ └─────────────┘ └─────────────┘ └────────┘│
│  ┌──────────────────────────────────────────────────────────┤
│  │ Aktionen-Log: "20s Überschreitung → Lüftung hochfahren" ││
│  └──────────────────────────────────────────────────────────┤
└───────────────────────┬─────────────────────────────────────┘
                        │ Alerts (20s Schwellenwert)
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                    WORKER (Alert Logic)                      │
│  • Empfängt Alerts von Grafana via Webhook                   │
│  • Prüft 20-Sekunden-Bedingung                               │
│  • Triggert Aktion → Schreibt in alert_actions Tabelle      │
└───────────────────────┬─────────────────────────────────────┘
                        │ Aktionen-Trigger
                        ▼
┌─────────────────────────────────────────────────────────────┐
│              POSTGRESQL DATENBANK                            │
│  • sensor_readings: Alle Messwerte mit Timestamps           │
│  • alert_actions: Log aller ausgeführten Korrekturmaßnahmen │
└──────────┬──────────────────────────────┬───────────────────┘
           │                              │
           ▼                              ▼
┌──────────────────┐         ┌────────────────────────────────┐
│  SENSOR 1-4      │         │  Sensor reagiert auf Aktion:   │
│  • Luftfeuchte   │◄────────┤  • Prüft alert_actions (1s)    │
│  • Temperatur    │         │  • Startet Recovery-Phase      │
│  • Düsendruck    │         │  • Normalisiert Werte          │
│  • Energie       │         └────────────────────────────────┘
└──────────────────┘
```

---

## 🚀 Setup und Installation

### Voraussetzungen

- Docker & Docker Compose
- Port 3000 (Grafana), 5433 (PostgreSQL), 5001 (Worker) verfügbar

### Installation

```powershell
# 1. Repository klonen oder ins Verzeichnis wechseln
cd c:\IBSYS

# 2. Alle Container starten
docker-compose up -d

# 3. Logs verfolgen (optional)
docker-compose logs -f
```

### Erste Schritte

1. **Grafana Dashboard öffnen:**
   - URL: http://localhost:3000
   - Login: `admin` / `admin`
   - Dashboard: **"Sensor Overview"** (automatisch provisioniert)

2. **Alert-Regeln werden automatisch erstellt:**
   - Der `alert_setup` Container konfiguriert 8 Alert-Regeln
   - Check: http://localhost:3000/alerting/list

3. **System-Überwachung:**
   - Sensoren starten Anomalie-Zyklen automatisch
   - Alerts werden nach 20s ausgelöst
   - Aktionen werden in der Tabelle unten angezeigt

---

## 📈 Erwartetes Verhalten

### Normalbetrieb
- Alle 4 Graphen zeigen stabile Werte im grünen Bereich
- Kleine natürliche Schwankungen (±1-2 Einheiten)

### Anomalie-Zyklus (ca. alle 30-60 Sekunden)

| Zeit | Status | Sensor-Verhalten | Dashboard |
|------|--------|------------------|-----------|
| **T+0s** | ↗️ Buildup | Wert steigt langsam Richtung Schwellenwert | Graph steigt |
| **T+12s** | ⚠️ Threshold | Schwellenwert erreicht (z.B. 65% Luftfeuchtigkeit) | Rote Linie überschritten |
| **T+20s** | 🔔 Alert | Grafana triggert Alert → Worker empfängt | Alert feuert |
| **T+21s** | 🎯 Action | Worker schreibt Aktion in DB (z.B. "Lüftung hochfahren") | Neue Zeile in Aktionen-Tabelle |
| **T+22s** | 🔧 Recovery | Sensor erkennt Aktion → startet Recovery | Graph beginnt zu fallen |
| **T+37s** | ✅ Normal | Wert zurück im Normalbereich | Grüner Bereich erreicht |

---

## 🔍 Troubleshooting

### Problem: Keine Alerts werden ausgelöst

```powershell
# Prüfen ob Alert-Setup erfolgreich war
docker logs ibsys_alert_setup

# Alert-Regeln manuell prüfen
# → Grafana öffnen → Alerting → Alert Rules
```

### Problem: Sensoren reagieren nicht auf Aktionen

```powershell
# Sensor-Logs prüfen
docker logs ibsys_sensor -f
docker logs ibsys_sensor_humidity -f

# Erwartete Ausgabe nach Action:
# [SENSOR] 🎯 ACTION DETECTED (ID: 123)! Starting immediate recovery...
```

### Problem: Worker empfängt keine Webhooks

```powershell
# Worker-Logs prüfen
docker logs ibsys_worker -f

# Contact Point in Grafana prüfen:
# → Alerting → Contact Points → "worker-webhook"
# URL sollte sein: http://worker:5000/grafana/webhook
```

### Datenbank direkt prüfen

```powershell
# PostgreSQL Container betreten
docker exec -it ibsys_postgres psql -U sensor -d sensor_db

# Letzte Sensor-Werte anzeigen
SELECT * FROM sensor_readings ORDER BY recorded_at DESC LIMIT 20;

# Alle ausgeführten Aktionen anzeigen
SELECT * FROM alert_actions ORDER BY created_at DESC;
```

---

## 🔧 Konfiguration

### Schwellenwerte anpassen

Bearbeiten Sie `docker-compose.yml`:

```yaml
sensor_humidity:
  environment:
    THRESHOLD_HIGH: '70'  # Ändern Sie hier
    THRESHOLD_LOW: '25'
```

Dann neu starten:
```powershell
docker-compose restart sensor_humidity
```

### Alert-Dauer ändern (Standard: 20 Sekunden)

```yaml
worker:
  environment:
    ALERT_DURATION_SECONDS: '30'  # Auf 30s erhöhen
```

```powershell
docker-compose restart worker
```

---

## 📁 Projekt-Struktur

```
IBSYS/
├── docker-compose.yml          # Haupt-Orchestrierung
├── README.md                   # Diese Datei
├── provisioning/
│   ├── init.sql               # DB-Schema (sensor_readings, alert_actions)
│   ├── datasources/           # Grafana PostgreSQL Verbindung
│   ├── dashboards/            # Dashboard-Definitionen
│   └── alerting/              # Webhook-Konfiguration
├── sensor/
│   ├── Dockerfile
│   ├── sensor_realistic.py    # Realistische Sensor-Simulation
│   └── requirements.txt
├── worker/
│   ├── Dockerfile
│   ├── worker.py              # Flask Webhook-Empfänger
│   ├── alert_logic.py         # 20s-Schwellenwert-Logik
│   └── requirements.txt
└── setup/
    ├── Dockerfile
    └── setup_alerts_api.py    # Automatische Alert-Regel-Erstellung
```

---

## 🎓 Technologie-Stack

| Komponente | Technologie | Version |
|------------|-------------|---------|
| **Datenbank** | PostgreSQL | 15-alpine |
| **Visualisierung** | Grafana OSS | 10.2.2 |
| **Sensoren** | Python | 3.11-slim |
| **Worker** | Flask + Python | 3.11-slim |
| **Orchestrierung** | Docker Compose | v2.x |

---

## 📊 Performance-Metriken

- **Sensor-Schreibfrequenz**: 4-8 Sekunden pro Parameter
- **Alert-Latenz**: ~20 Sekunden (konfigurierbar)
- **Action-Erkennungszeit**: 1 Sekunde
- **Recovery-Dauer**: 15-20 Sekunden
- **Dashboard-Refresh**: 5 Sekunden

---

## 🔐 Sicherheitshinweise

⚠️ **Nur für Prototyping/Demo-Zwecke!**

- Standard-Passwörter werden verwendet (admin/admin, sensor/sensorpw)
- Keine SSL/TLS-Verschlüsselung
- Keine Authentifizierung für Worker-Endpoint

Für Produktionsumgebungen:
- Starke Passwörter verwenden
- SSL-Zertifikate einrichten
- Webhook-Authentifizierung implementieren
- Netzwerk-Segmentierung vornehmen

---

## 🎯 Testfälle

### Manueller Test: Luftfeuchtigkeit

1. Dashboard öffnen
2. Graph "Luftfeuchtigkeit" beobachten
3. Warten bis Wert über 65% steigt
4. Nach 20s sollte Alert ausgelöst werden
5. In Aktionen-Tabelle erscheint: "Lüftung hochfahren"
6. Graph sollte innerhalb von 15-20s unter 65% fallen

### Verifizierung der Timing-Präzision

```powershell
# Worker-Logs mit Timestamps
docker logs ibsys_worker -f --timestamps

# Erwartete Ausgabe:
# 2025-11-15T10:30:00.123Z [DEBUG] Alert 'Luftfeuchtigkeit zu hoch': status=firing
# 2025-11-15T10:30:20.456Z [INFO] Action triggered after 20.333s
```

---

## 🤝 Entwickler-Hinweise

### Eigene Sensoren hinzufügen

1. In `docker-compose.yml` neuen Service definieren:
```yaml
sensor_custom:
  build: ./sensor
  environment:
    PARAMETER: meinparameter
    THRESHOLD_HIGH: '100'
```

2. Alert-Regel in `setup/setup_alerts_api.py` hinzufügen

3. Dashboard in `provisioning/dashboards/json/sensor_dashboard.json` erweitern

### Debugging-Modus

```powershell
# Alle Logs gleichzeitig
docker-compose logs -f sensor worker grafana

# Nur Fehler anzeigen
docker-compose logs | Select-String "ERROR|WARN"
```

---

## 📝 Lizenz

Dieses Projekt ist für Bildungs- und Demonstrationszwecke erstellt.

---

## ✅ Checkliste: System läuft korrekt

- [ ] Alle 6 Container sind gestartet (`docker ps` zeigt 6 Container)
- [ ] Grafana Dashboard ist erreichbar (http://localhost:3000)
- [ ] 4 Sensor-Graphen zeigen aktive Daten
- [ ] Alert-Regeln sind konfiguriert (8 Regeln unter Alerting → Alert Rules)
- [ ] Aktionen-Tabelle zeigt Einträge nach ca. 2-3 Minuten
- [ ] Sensoren zeigen Recovery-Verhalten nach Aktionen

---

**Version:** 1.0 | **Erstellt:** November 2025 | **Status:** Production-Ready Prototype

