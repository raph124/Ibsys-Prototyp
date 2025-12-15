import os, random, time, math
from datetime import datetime, timezone
import psycopg
from psycopg import OperationalError

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://sensor:sensorpw@localhost:5432/sensor_db")
INTERVAL = int(os.getenv("WRITE_INTERVAL_SECONDS", "5"))
SENSOR_NAME = os.getenv("SENSOR_NAME", "lackieranlage_1")
PARAMETER = os.getenv("PARAMETER", "kabinentemperatur")
UNIT = os.getenv("UNIT", "C")
MIN_VALUE = float(os.getenv("MIN_VALUE", "18"))
MAX_VALUE = float(os.getenv("MAX_VALUE", "30"))
THRESHOLD_HIGH = float(os.getenv("THRESHOLD_HIGH", "26"))
THRESHOLD_LOW = float(os.getenv("THRESHOLD_LOW", "20"))

# Realistic production simulation parameters
NORMAL_CENTER = (MIN_VALUE + MAX_VALUE) / 2  # Normal operating point
ANOMALY_CYCLE_MINUTES = float(os.getenv("ANOMALY_CYCLE_MINUTES", "15"))  # How often anomalies occur
ANOMALY_DURATION_SECONDS = int(os.getenv("ANOMALY_DURATION_SECONDS", "90"))  # How long threshold violation lasts
BUILDUP_SECONDS = int(os.getenv("BUILDUP_SECONDS", "180"))  # How long it takes to reach threshold
RECOVERY_SECONDS = int(os.getenv("RECOVERY_SECONDS", "120"))  # How long recovery takes after action

print(f"[SENSOR] Starting realistic {PARAMETER} sensor for {SENSOR_NAME}")
print(f"[SENSOR] Normal range: {MIN_VALUE}-{MAX_VALUE}, Thresholds: <{THRESHOLD_LOW} or >{THRESHOLD_HIGH}")
print(f"[SENSOR] Anomaly cycle: every {ANOMALY_CYCLE_MINUTES}min, buildup {BUILDUP_SECONDS}s, sustain {ANOMALY_DURATION_SECONDS}s")

def connect_with_retry(max_attempts: int = 20, wait_seconds: int = 2):
    attempt = 1
    while True:
        try:
            return psycopg.connect(DATABASE_URL)
        except OperationalError as e:
            if attempt >= max_attempts:
                raise
            print(f"[SENSOR] DB not ready (attempt {attempt}/{max_attempts}): {e}. Retrying in {wait_seconds}s...")
            attempt += 1
            time.sleep(wait_seconds)

# State machine for realistic anomaly cycles with action-triggered recovery
class AnomalySimulator:
    def __init__(self, conn):
        self.conn = conn
        self.state = "normal"  # normal, buildup, threshold_violation, recovery
        self.state_start_time = time.time()
        self.current_value = NORMAL_CENTER
        self.target_value = NORMAL_CENTER
        self.anomaly_type = None  # 'high' or 'low'
        self.last_action_check = 0
        self.action_detected = False
        
    def check_for_action(self):
        """Check if an action was triggered for this parameter - OPTIMIZED FOR FAST RESPONSE"""
        now = time.time()
        # Check every 1 second for immediate response
        if now - self.last_action_check < 1:
            return self.action_detected
            
        self.last_action_check = now
        
        try:
            with self.conn.cursor() as cur:
                # Check if action was created in last 2 minutes for this parameter
                # Use pattern that matches both 'duesendruck' and 'Düsendruck'
                search_pattern = PARAMETER.replace('ue', '[uü]').replace('ae', '[aä]').replace('oe', '[oö]')
                cur.execute("""
                    SELECT id, created_at, action FROM alert_actions 
                    WHERE alert_title ~* %s 
                    AND created_at > NOW() - INTERVAL '2 minutes'
                    ORDER BY created_at DESC LIMIT 1
                """, (search_pattern,))
                result = cur.fetchone()
                if result and not self.action_detected:
                    action_id, created_at, action_text = result
                    print(f"[SENSOR] 🎯 ACTION DETECTED (ID: {action_id})! Starting immediate recovery...")
                    print(f"[SENSOR] Action taken: {action_text}")
                    self.action_detected = True
                    return True
        except Exception as e:
            # ALWAYS log errors for debugging
            print(f"[SENSOR] ⚠️ ERROR checking for action: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
        
        return self.action_detected
    
    def check_for_existing_action_on_startup(self):
        """Check if there's a recent action when sensor starts - if so, start in recovery mode"""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT id, created_at, action FROM alert_actions 
                    WHERE alert_title ILIKE %s 
                    AND created_at > NOW() - INTERVAL '5 minutes'
                    ORDER BY created_at DESC LIMIT 1
                """, (f"%{PARAMETER}%",))
                result = cur.fetchone()
                if result:
                    action_id, created_at, action_text = result
                    # Check current sensor value
                    if self.current_value > THRESHOLD_HIGH or self.current_value < THRESHOLD_LOW:
                        print(f"[SENSOR] 🔄 STARTUP: Found recent action (ID: {action_id}) and value still out of range")
                        print(f"[SENSOR] 🔄 Starting directly in RECOVERY mode to normalize values")
                        self.action_detected = True
                        self.state = "recovery"
                        self.state_start_time = time.time()
                        # Determine recovery direction
                        if self.current_value > THRESHOLD_HIGH:
                            self.anomaly_type = "high"
                            self.target_value = NORMAL_CENTER
                        else:
                            self.anomaly_type = "low"
                            self.target_value = NORMAL_CENTER
        except Exception as e:
            print(f"[SENSOR] Warning: Could not check for existing action on startup: {e}")
        
    def get_next_value(self):
        now = time.time()
        elapsed = now - self.state_start_time
        
        if self.state == "normal":
            # Stable operation with small random fluctuations
            self.current_value = NORMAL_CENTER + random.uniform(-1.5, 1.5)
            
            # Randomly trigger anomaly cycle
            if elapsed > ANOMALY_CYCLE_MINUTES * 60:
                self.state = "buildup"
                self.state_start_time = now
                self.action_detected = False  # Reset action flag
                # Decide if anomaly goes high or low
                self.anomaly_type = random.choice(["high", "low"])
                if self.anomaly_type == "high":
                    self.target_value = THRESHOLD_HIGH + random.uniform(1, 3)
                    print(f"[SENSOR] Starting HIGH anomaly buildup to {self.target_value:.1f}")
                else:
                    self.target_value = THRESHOLD_LOW - random.uniform(1, 3)
                    print(f"[SENSOR] Starting LOW anomaly buildup to {self.target_value:.1f}")
        
        elif self.state == "buildup":
            # Gradually approach threshold over BUILDUP_SECONDS
            progress = min(1.0, elapsed / BUILDUP_SECONDS)
            self.current_value = NORMAL_CENTER + (self.target_value - NORMAL_CENTER) * progress
            self.current_value += random.uniform(-0.5, 0.5)  # Small noise
            
            if elapsed > BUILDUP_SECONDS:
                self.state = "threshold_violation"
                self.state_start_time = now
                print(f"[SENSOR] ⚠️  Threshold reached! Waiting for action...")
        
        elif self.state == "threshold_violation":
            # Stay above/below threshold until action is detected
            self.current_value = self.target_value + random.uniform(-0.8, 0.8)
            
            # Check if action was triggered - FAST RESPONSE
            if self.check_for_action():
                self.state = "recovery"
                self.state_start_time = now
                print(f"[SENSOR] 🔧 Recovery initiated by action! Returning to normal...")
            # Wait for action - no automatic timeout
        
        elif self.state == "recovery":
            # Gradually return to normal (simulating corrective action effect)
            progress = min(1.0, elapsed / RECOVERY_SECONDS)
            self.current_value = self.target_value + (NORMAL_CENTER - self.target_value) * progress
            self.current_value += random.uniform(-0.5, 0.5)
            
            if elapsed > RECOVERY_SECONDS:
                self.state = "normal"
                self.state_start_time = now
                self.target_value = NORMAL_CENTER
                print(f"[SENSOR] ✅ Recovered to normal operation")
        
        # Clamp to reasonable bounds (don't allow values below absolute minimum for physical sensors)
        absolute_min = max(0, MIN_VALUE - 5) if UNIT in ['bar', 'W', '%'] else MIN_VALUE - 5
        self.current_value = max(absolute_min, min(MAX_VALUE + 5, self.current_value))
        return round(self.current_value, 2)

with connect_with_retry() as conn:
    print("[SENSOR] DB connection established. Starting simulation...")
    
    # Clean up old data first, before creating simulator
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM sensor_readings WHERE parameter = %s AND sensor_name = %s", (PARAMETER, SENSOR_NAME))
            deleted_count = cur.rowcount
        conn.commit()
        print(f"🧹 CLEANUP: Deleted {deleted_count} old readings for '{PARAMETER}' from '{SENSOR_NAME}'")
    except Exception as e:
        print(f"❌ Error during cleanup: {e}")
        import traceback
        traceback.print_exc()
    
    # Pass connection to simulator
    simulator = AnomalySimulator(conn)
    
    while True:
        value = simulator.get_next_value()
        
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO sensor_readings (sensor_name, parameter, value, unit, recorded_at) VALUES (%s,%s,%s,%s,%s)",
                    (SENSOR_NAME, PARAMETER, value, UNIT, datetime.now(timezone.utc))
                )
            conn.commit()
            
            # Log state changes and threshold crossings
            state_marker = ""
            if simulator.state == "threshold_violation":
                state_marker = " ⚠️  THRESHOLD VIOLATION (waiting for action)"
            elif simulator.state == "buildup":
                state_marker = " ↗️ BUILDING UP"
            elif simulator.state == "recovery":
                state_marker = " ↘️ RECOVERING (action triggered)"
                
            print(f"[SENSOR] {datetime.now().strftime('%H:%M:%S')} | {value}{UNIT}{state_marker}")
            
        except OperationalError as e:
            print(f"[SENSOR] Write failed: {e}. Reconnecting...")
            conn.close()
            conn = connect_with_retry()
        
        time.sleep(INTERVAL)
