#!/usr/bin/env python3
"""
Grafana Alert Rules Setup via API
Automatically configures 8 alert rules for IBSYS project
"""
import requests
import json
import time
import sys
import os

GRAFANA_URL = os.getenv("GRAFANA_URL", "http://localhost:3000")
AUTH = ("admin", "admin")

# Alert rule definitions
ALERT_RULES = [
    {
        "title": "Kabinentemperatur zu hoch",
        "parameter": "kabinentemperatur",
        "threshold": 28,
        "operator": "gt",
        "description": "SOFORTMASSNAHME: Kühlsystem auf Maximum | Laufende Teile: Trocknungszeit +30% verlängern | QUALITÄT: Sonderprüfung aller Teile (Oberflächenstruktur) | VERANTWORTLICH: Schichtleiter + QS-Labor | EMAIL: qm-team@lackierwerk.de | DOKUMENTATION: Incident-Nr. in SAP",
        "group": "Temperature Alerts"
    },
    {
        "title": "Kabinentemperatur zu niedrig",
        "parameter": "kabinentemperatur",
        "threshold": 18,
        "operator": "lt",
        "description": "SOFORTMASSNAHME: Heizregister auf 100%, Umluftventilatoren Maximum | PRODUKTIONSANPASSUNG: Taktzeit +15% verlängern (langsamere Durchlaufgeschwindigkeit) | QUALITÄT: Letzte 3 Teile zur Nachtrocknung (60min bei 80°C) | ÜBERWACHUNG: Temperatur alle 2min kontrollieren bis >20°C | VERANTWORTLICH: Schichtleiter | MELDUNG: Produktionsleiter telefonisch | EMAIL: produktion@lackierwerk.de, wartung@lackierwerk.de",
        "group": "Temperature Alerts"
    },
    {
        "title": "Luftfeuchtigkeit zu hoch",
        "parameter": "luftfeuchtigkeit",
        "threshold": 65,
        "operator": "gt",
        "description": "ENTFEUCHTUNG: Trockner-Aggregat auf Stufe 3 aktiviert | PRODUKTIONSANPASSUNG: Aktuelle Charge normal beenden, dann 15min Produktionspause für Klimastabilisierung | NEUE AUFTRÄGE: Auf Warteposition, Start nach Freigabe durch Schichtleiter | KONTROLLE: Nach 5min Messung wiederholen, bei <60% Freigabe | RISIKO: Lackläufer, Orangenhaut | VERANTWORTLICH: Anlagenfahrer | EMAIL: schichtfuehrer@lackierwerk.de",
        "group": "Humidity Alerts"
    },
    {
        "title": "Luftfeuchtigkeit zu niedrig",
        "parameter": "luftfeuchtigkeit",
        "threshold": 30,
        "operator": "lt",
        "description": "BEFEUCHTUNG: Dampfgenerator starten (Sollwert 45%) | ROBOTER: Geschwindigkeit auf 80% reduzieren (Staubbildung) | QS-KONTROLLE: Nächste 5 Teile 100%-Prüfung auf Einschlüsse | VERANTWORTLICH: Anlagenfahrer + QS-Prüfer | Bei <25%: Produktionsstopp | EMAIL: produktion@lackierwerk.de, qs@lackierwerk.de",
        "group": "Humidity Alerts"
    },
    {
        "title": "Düsendruck zu hoch",
        "parameter": "duesendruck",
        "threshold": 3.2,
        "operator": "gt",
        "description": "SPRÜHPARAMETER: Druck manuell auf 2.8bar reduzieren | PRÜFUNG: Sprühbild-Test an Probeplatte | DOKUMENTATION: Overspray-Messung (Zerstäuber-Wirkungsgrad) | RISIKO: Übermäßiger Lackverbrauch, Nebel-Bildung | VERANTWORTLICH: Lackierer + Schichtleiter | Bei >3.5bar: Anlage stoppen, Instandhaltung | EMAIL: lackmeister@lackierwerk.de",
        "group": "Pressure Alerts"
    },
    {
        "title": "Düsendruck zu niedrig",
        "parameter": "duesendruck",
        "threshold": 1.8,
        "operator": "lt",
        "description": "WARTUNG ERFORDERLICH | SOFORT: Düsensatz prüfen (Verstopfung/Verschleiß) | REINIGUNG: Düsen mit Lösemittel spülen, Filter wechseln | TESTLAUF: Probeplatte lackieren, Schichtdicke messen | DOKUMENTATION: Wartungsprotokoll SAP-PM | VERANTWORTLICH: Instandhaltung + Schichtleiter | Bei <1.5bar: Produktionsstopp | EMAIL: wartung@lackierwerk.de, produktion@lackierwerk.de",
        "group": "Pressure Alerts"
    },
    {
        "title": "Energieverbrauch zu hoch",
        "parameter": "energieverbrauch",
        "threshold": 28,
        "operator": "gt",
        "description": "ENERGIEOPTIMIERUNG | KOMPRESSOR: Druck auf 5.5bar reduzieren (von 6.5bar) | PROZESSE: Heizung/Trocknung zeitlich staffeln | PRÜFUNG: Lastspitzen-Analyse, ggf. Wartung Motoren | KOSTEN: Überschreitung Energiebudget dokumentieren | VERANTWORTLICH: Schichtleiter + Facility Management | EMAIL: energie@lackierwerk.de, produktion@lackierwerk.de",
        "group": "Energy Alerts"
    },
    {
        "title": "Energieverbrauch zu niedrig",
        "parameter": "energieverbrauch",
        "threshold": 12,
        "operator": "lt",
        "description": "⚠️ TEILAUSFALL ERKANNT | DIAGNOSE: Welche Komponente ausgefallen? (Roboter/Trockner/Kompressor/Absaugung) | MASSNAHME: Fehlerhafte Komponente identifizieren (Sicherungen, Motorschutzschalter, Schütze prüfen) | PRODUKTION: Auf Handbetrieb umstellen falls möglich, sonst Charge unterbrechen | INSTANDHALTUNG: Notdienst Tel. 555-1234 | VERANTWORTLICH: Schichtleiter + Elektriker vor Ort | EMAIL: notfall@lackierwerk.de, produktion@lackierwerk.de | DOKUMENTATION: Ausfallzeit für Kapazitätsplanung",
        "group": "Energy Alerts"
    }
]

def wait_for_grafana():
    """Wait for Grafana to be ready"""
    print("[SETUP] Waiting for Grafana to be ready...")
    for i in range(60):  # 120 seconds total
        try:
            response = requests.get(f"{GRAFANA_URL}/api/health", timeout=3)
            if response.status_code == 200:
                print("[OK] Grafana is ready!")
                return True
        except requests.exceptions.RequestException:
            pass
        if i % 5 == 0:
            print(f"[SETUP] Still waiting... ({i*2}s elapsed)")
        time.sleep(2)
    print("[ERROR] Grafana not ready after 120 seconds")
    return False

def get_datasource_uid():
    """Get the PostgreSQL datasource UID"""
    try:
        response = requests.get(f"{GRAFANA_URL}/api/datasources", auth=AUTH)
        datasources = response.json()
        for ds in datasources:
            if ds.get("type") == "postgres":
                print(f"[OK] Found datasource: {ds['name']} (UID: {ds['uid']})")
                return ds["uid"]
        print("[ERROR] PostgreSQL datasource not found!")
        print(f"[DEBUG] Available datasources: {[d.get('name') for d in datasources]}")
        return None
    except Exception as e:
        print(f"[ERROR] Failed to get datasource: {e}")
        return None

def create_folder():
    """Create IBSYS folder if not exists"""
    try:
        # Check if folder exists
        response = requests.get(f"{GRAFANA_URL}/api/folders", auth=AUTH)
        folders = response.json()
        for folder in folders:
            if folder.get("title") == "IBSYS":
                print(f"[OK] Folder IBSYS exists (UID: {folder['uid']})")
                return folder["uid"]
        
        # Create folder
        payload = {"title": "IBSYS"}
        response = requests.post(f"{GRAFANA_URL}/api/folders", auth=AUTH, json=payload)
        if response.status_code in [200, 409]:
            folder = response.json()
            print(f"[OK] Created folder IBSYS (UID: {folder.get('uid', 'general')})")
            return folder.get("uid", "general")
        else:
            print(f"[WARN] Could not create folder: {response.text}")
            return "general"
    except Exception as e:
        print(f"[ERROR] Failed to create folder: {e}")
        return "general"

def get_contact_point():
    """Check if worker-webhook contact point exists"""
    try:
        response = requests.get(f"{GRAFANA_URL}/api/v1/provisioning/contact-points", auth=AUTH)
        if response.status_code == 200:
            contact_points = response.json()
            for cp in contact_points:
                if cp.get("name") == "worker-webhook":
                    print(f"[OK] Contact point 'worker-webhook' exists")
                    return True
        return False
    except Exception as e:
        print(f"[WARN] Could not verify contact point: {e}")
        return False

def create_alert_rule(rule_def, datasource_uid, folder_uid):
    """Create a single alert rule via API"""
    # Map operators to math symbols
    operator_symbol = {"gt": ">", "lt": "<"}
    symbol = operator_symbol[rule_def["operator"]]
    
    # Generate UID from title
    rule_uid = rule_def["title"].lower().replace(" ", "_").replace("ü", "ue").replace("ö", "oe")
    
    # Build rule payload for Grafana Unified Alerting with Math Expression
    payload = {
        "uid": rule_uid,
        "title": rule_def["title"],
        "condition": "C",
        "data": [
            {
                "refId": "A",
                "queryType": "",
                "relativeTimeRange": {"from": 60, "to": 0},
                "datasourceUid": datasource_uid,
                "model": {
                    "editorMode": "code",
                    "format": "table",
                    "rawQuery": True,
                    "rawSql": f"SELECT NOW() as time, value FROM sensor_readings WHERE parameter='{rule_def['parameter']}' ORDER BY recorded_at DESC LIMIT 1",
                    "refId": "A",
                    "sql": {
                        "columns": [{"parameters": [], "type": "function"}],
                        "groupBy": [{"property": {"type": "string"}, "type": "groupBy"}],
                        "limit": 50
                    }
                }
            },
            {
                "refId": "B",
                "queryType": "",
                "relativeTimeRange": {"from": 60, "to": 0},
                "datasourceUid": "__expr__",
                "model": {
                    "datasource": {"type": "__expr__", "uid": "__expr__"},
                    "expression": "A",
                    "reducer": "last",
                    "settings": {"mode": ""},
                    "type": "reduce",
                    "refId": "B"
                }
            },
            {
                "refId": "C",
                "queryType": "",
                "relativeTimeRange": {"from": 60, "to": 0},
                "datasourceUid": "__expr__",
                "model": {
                    "datasource": {"type": "__expr__", "uid": "__expr__"},
                    "expression": f"$B {symbol} {rule_def['threshold']}",
                    "type": "math",
                    "refId": "C"
                }
            }
        ],
        "noDataState": "OK",
        "execErrState": "OK",
        "for": "20s",
        "annotations": {
            "summary": rule_def["title"],
            "description": rule_def["description"],
            "threshold": str(rule_def["threshold"]),
            "__value__": "{{ $values.B.Value }}",
            "__threshold__": str(rule_def["threshold"])
        },
        "labels": {},
        "folderUID": folder_uid,
        "ruleGroup": rule_def["group"],
        "intervalSeconds": 10,
        "evaluationIntervalSeconds": 10
    }
    
    try:
        # Try to create the rule
        response = requests.post(
            f"{GRAFANA_URL}/api/v1/provisioning/alert-rules",
            auth=AUTH,
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code in [201, 202]:
            print(f"[OK] Created alert: {rule_def['title']}")
            return True
        elif response.status_code == 400 and "conflicting" in response.text:
            # Rule exists, delete and recreate
            try:
                response = requests.delete(
                    f"{GRAFANA_URL}/api/v1/provisioning/alert-rules/{rule_uid}",
                    auth=AUTH
                )
                time.sleep(0.5)
                # Now create again
                response = requests.post(
                    f"{GRAFANA_URL}/api/v1/provisioning/alert-rules",
                    auth=AUTH,
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                if response.status_code in [201, 202]:
                    print(f"[OK] Recreated alert: {rule_def['title']}")
                    return True
            except Exception as e:
                print(f"[ERROR] Failed to recreate {rule_def['title']}: {e}")
                return False
        
        print(f"[ERROR] Failed to create {rule_def['title']}: {response.status_code} - {response.text[:200]}")
        return False
        
    except Exception as e:
        print(f"[ERROR] Exception creating {rule_def['title']}: {e}")
        return False

def main():
    print("=" * 70)
    print("IBSYS II - Grafana Alert Rules Setup")
    print("=" * 70)
    
    # Wait for Grafana
    if not wait_for_grafana():
        sys.exit(1)
    
    time.sleep(5)  # Give Grafana more time to fully initialize datasources
    
    # Get datasource UID
    datasource_uid = get_datasource_uid()
    if not datasource_uid:
        print("[ERROR] Cannot proceed without datasource UID")
        sys.exit(1)
    
    # Create folder
    folder_uid = create_folder()
    
    # Check contact point
    get_contact_point()
    
    # Create all alert rules
    print(f"\n[SETUP] Creating {len(ALERT_RULES)} alert rules...")
    success_count = 0
    for rule in ALERT_RULES:
        if create_alert_rule(rule, datasource_uid, folder_uid):
            success_count += 1
        time.sleep(1)  # Rate limiting
    
    # Update all rule groups to use 10-second intervals
    print(f"\n[SETUP] Updating rule group intervals to 10 seconds...")
    try:
        response = requests.get(f"{GRAFANA_URL}/api/ruler/grafana/api/v1/rules", auth=AUTH)
        if response.status_code == 200:
            rules_data = response.json()
            if "IBSYS" in rules_data:
                for group in rules_data["IBSYS"]:
                    # Update the interval
                    group["interval"] = "10s"
                    # Post back the updated group
                    group_name = group["name"]
                    response = requests.post(
                        f"{GRAFANA_URL}/api/ruler/grafana/api/v1/rules/IBSYS/{group_name}",
                        auth=AUTH,
                        json=group,
                        headers={"Content-Type": "application/json"}
                    )
                    if response.status_code in [200, 201, 202]:
                        print(f"[OK] Updated {group_name} interval to 10s")
                    else:
                        print(f"[WARN] Failed to update {group_name}: {response.status_code}")
    except Exception as e:
        print(f"[WARN] Could not update rule group intervals: {e}")
    
    print("\n" + "=" * 70)
    print(f"[DONE] Successfully created/updated {success_count}/{len(ALERT_RULES)} alert rules")
    print("=" * 70)
    print(f"\nView alerts: {GRAFANA_URL}/alerting/list")
    print(f"Dashboard: {GRAFANA_URL}/d/sensor_dashboard")
    print("\nAlerts will start firing within 2-3 minutes when sensors reach thresholds!")

if __name__ == "__main__":
    main()
