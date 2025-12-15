import os, json
from flask import Flask, request, jsonify
import psycopg
from datetime import datetime, timezone
from alert_logic import AlertDurationManager

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://sensor:sensorpw@postgres:5432/sensor_db")
DURATION = int(os.getenv("ALERT_DURATION_SECONDS", "20"))

manager = AlertDurationManager(DURATION)
app = Flask(__name__)

@app.route('/health')
def health():
    return {'status': 'ok', 'duration_requirement': DURATION}

@app.route('/grafana/webhook', methods=['POST'])
def grafana_webhook():
    payload = request.json
    # Debug: Log entire payload to see what Grafana sends
    print(f"[DEBUG] Received webhook payload: {json.dumps(payload, indent=2)}")
    # Grafana Unified Alerting webhook structure
    alerts = payload.get('alerts', [])
    actions_taken = []
    with psycopg.connect(DATABASE_URL) as conn:
        for alert in alerts:
            labels = alert.get('labels', {})
            uid = alert.get('fingerprint', 'unknown')
            title = alert.get('annotations', {}).get('summary') or labels.get('alertname', 'Alert')
            status = alert.get('status', 'firing')
            # Try to get value & threshold from multiple possible locations
            value = None
            threshold = None
            try:
                # Priority 1: Check 'values' dict directly (most reliable)
                if 'values' in alert:
                    values_dict = alert['values']
                    # Try B first (that's where the reduced AVG result is)
                    if 'B' in values_dict and values_dict['B'] is not None:
                        value = float(values_dict['B'])
                    elif 'A' in values_dict and values_dict['A'] is not None:
                        value = float(values_dict['A'])
                
                # Priority 2: Try valueString with regex parsing for array format
                if value is None and 'valueString' in alert:
                    value_str = str(alert['valueString'])
                    # Parse "[ var='B' labels={} value=30.03 ]" format
                    import re
                    match = re.search(r"var='B'[^}]*value=([\d.]+)", value_str)
                    if match:
                        value = float(match.group(1))
                    else:
                        # Try direct float conversion as fallback
                        try:
                            value = float(value_str)
                        except:
                            pass
                
                # Priority 3: Fallback to values dict if still None
                if value is None and 'values' in alert:
                    values_dict = alert['values']
                    # Try B first (that's where the reduced AVG result is)
                    if 'B' in values_dict and values_dict['B'] is not None:
                        value = float(values_dict['B'])
                    elif 'A' in values_dict and values_dict['A'] is not None:
                        value = float(values_dict['A'])
                
                # Get threshold from annotations
                if 'threshold' in alert.get('annotations', {}):
                    threshold = float(alert['annotations']['threshold'])
                elif '__threshold__' in alert.get('annotations', {}):
                    threshold = float(alert['annotations']['__threshold__'])
                elif 'threshold' in labels:
                    threshold = float(labels['threshold'])
            except (ValueError, KeyError, TypeError, AttributeError) as e:
                print(f"[WARN] Could not parse value/threshold: {e}")
            
            print(f"[DEBUG] Alert '{title}': status={status}, value={value}, threshold={threshold}")
            should_act = manager.process(str(uid), title, threshold, value, status)
            print(f"[DEBUG] Alert '{title}' (UID: {uid}): should_act={should_act}")
            if should_act:
                # Check if action already exists for this ONGOING alert to avoid duplicates
                # Only skip if action was created recently AND alert manager shows it's still the same alert instance
                alert_state = manager.get_alert_state(str(uid))
                if alert_state and alert_state.action_written:
                    print(f"[INFO] Action already written for this alert instance (UID: {uid}) - skipping duplicate")
                    continue
                
                # Mark that we're writing an action for this alert
                manager.mark_action_written(str(uid))
                
                # Map alert titles to specific actions based on requirements table
                action_map = {
                    "Luftfeuchtigkeit zu hoch": "ENTSCHEIDUNG: Entfeuchtungsanlage aktiviert | FOLGESCHRITTE: Aktuelle Werkstücke fertiglackieren, neue Aufträge pausieren, Klimaanlage auf Stufe 3, nach 5min Messwert prüfen, bei >60% Produktion fortsetzen",
                    "Luftfeuchtigkeit zu niedrig": "ENTSCHEIDUNG: Befeuchtungssystem aktiviert | FOLGESCHRITTE: Wassernebel-Düsen gestartet, Lackierroboter verlangsamen (80% Geschwindigkeit), Schichtdicke um 10% erhöhen, QS-Kontrolle nach 10 Werkstücken",
                    "Kabinentemperatur zu niedrig": "ENTSCHEIDUNG: Prozessgeschwindigkeit reduziert | FOLGESCHRITTE: IR-Heizstrahler auf Maximum, Vorheizzeit von 3min auf 8min erhöht, Werkstücke in Warteposition, Schichtleiter benachrichtigt, Produktion bei 20°C freigegeben",
                    "Kabinentemperatur zu hoch": "ENTSCHEIDUNG: Kühlprotokoll aktiviert | FOLGESCHRITTE: Abluftventilatoren 100%, Frischluftzufuhr maximiert, Trocknungszeit um 30% verlängert, Temperaturlog alle 30s, nächste 5 Teile Sonderprüfung",
                    "Energieverbrauch zu hoch": "ENTSCHEIDUNG: Energieoptimierung aktiviert | FOLGESCHRITTE: Kompressor-Druck von 6bar auf 5bar reduziert, Hallenbeleuchtung auf 70%, parallele Trocknungsprozesse gestaffelt (Verzögerung 2min), Wartungsteam für Leistungscheck eingeplant",
                    "Energieverbrauch zu niedrig": "ENTSCHEIDUNG: Energiemonitoring-Alarm | FOLGESCHRITTE: Roboter in Sicherheitsposition gefahren, Lackpumpen abgeschaltet, Instandhaltung alarmiert, Fehlerdiagnose gestartet, Schichtleiter informiert, Neustart nur nach Freigabe",
                    "Düsendruck zu hoch": "ENTSCHEIDUNG: Sprühparameter angepasst | FOLGESCHRITTE: Druckregler auf 2.8bar reduziert, nächste 3 Werkstücke Sprühbild-Kontrolle, Overspray-Messung durchgeführt, bei Abweichung >15% Filter wechseln, Roboterpfad unverändert",
                    "Düsendruck zu niedrig": "ENTSCHEIDUNG: Wartungsprotokoll aktiviert | FOLGESCHRITTE: Roboter in Wartungsposition, Lackpumpe auf Kavitation geprüft, Düsen demontiert und gereinigt, Zuleitungen auf Verstopfung untersucht, Testlackierung vor Freigabe, Ausfallzeit dokumentiert"
                }
                action_text = action_map.get(title, f"Alarm: {title}")
                with conn.cursor() as cur:
                    cur.execute("INSERT INTO alert_actions (alert_uid, alert_title, state, threshold, current_value, started_at, sustained_seconds, action) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                                (str(uid), title, status, threshold, value, datetime.now(timezone.utc), DURATION, action_text))
                    conn.commit()
                actions_taken.append(action_text)
        return jsonify({'received': len(alerts), 'actions_taken': actions_taken})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
