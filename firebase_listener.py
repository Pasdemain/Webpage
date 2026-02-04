"""
Firebase Listener - Ecoute les commandes depuis la page web et execute l'automatisation
"""

import time
import os
import subprocess
import threading
import requests
import json
from datetime import datetime

# ============== CONFIGURATION ==============
# URL de ta base Firebase (sans le .json a la fin)
FIREBASE_URL = "https://webpage-659e4-default-rtdb.firebaseio.com"

# Chemin vers le script d'automatisation
SCRIPT_PATH = os.path.join(os.path.dirname(__file__), 'automation.py')

# Intervalle du heartbeat (en secondes)
HEARTBEAT_INTERVAL = 10

# ============================================

log_order = 0

def get_timestamp():
    """Retourne le timestamp actuel formate"""
    return datetime.now().strftime("%H:%M:%S")

def firebase_get(path):
    """Recupere des donnees depuis Firebase"""
    try:
        response = requests.get(f"{FIREBASE_URL}/{path}.json", timeout=10)
        return response.json()
    except Exception as e:
        print(f"[ERREUR] Firebase GET: {e}")
        return None

def firebase_set(path, data):
    """Ecrit des donnees dans Firebase"""
    try:
        response = requests.put(f"{FIREBASE_URL}/{path}.json", json=data, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"[ERREUR] Firebase SET: {e}")
        return False

def firebase_push(path, data):
    """Ajoute des donnees dans Firebase (push)"""
    try:
        response = requests.post(f"{FIREBASE_URL}/{path}.json", json=data, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"[ERREUR] Firebase PUSH: {e}")
        return False

def firebase_delete(path):
    """Supprime des donnees dans Firebase"""
    try:
        response = requests.delete(f"{FIREBASE_URL}/{path}.json", timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"[ERREUR] Firebase DELETE: {e}")
        return False

def send_log(log_type, message):
    """Envoie un log a Firebase"""
    global log_order
    log_order += 1

    log_data = {
        "type": log_type,
        "message": message,
        "timestamp": get_timestamp(),
        "order": log_order
    }

    firebase_push("logs", log_data)
    print(f"[{get_timestamp()}] [{log_type.upper()}] {message}")

def send_heartbeat():
    """Envoie un heartbeat pour indiquer que le PC est en ligne"""
    while True:
        firebase_set("pc_status", {
            "online": True,
            "timestamp": int(time.time() * 1000)
        })
        time.sleep(HEARTBEAT_INTERVAL)

def run_automation():
    """Lance le script d'automatisation et capture les logs en temps reel"""
    send_log("info", "Demarrage de l'automatisation...")

    try:
        # Lancer le processus avec -u pour desactiver le buffering
        env = os.environ.copy()
        env['PYTHONUNBUFFERED'] = '1'

        process = subprocess.Popen(
            ['python', '-u', SCRIPT_PATH],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env
        )

        # Lire les logs en temps reel
        for line in iter(process.stdout.readline, ''):
            line = line.strip()
            if line:
                # Determiner le type de log selon le contenu
                if "erreur" in line.lower() or "error" in line.lower():
                    send_log("error", line)
                elif "warning" in line.lower() or "attention" in line.lower():
                    send_log("warning", line)
                elif "succes" in line.lower() or "success" in line.lower() or "reussi" in line.lower():
                    send_log("success", line)
                else:
                    send_log("info", line)

        process.wait()

        if process.returncode == 0:
            send_log("success", "Automatisation terminee avec succes!")
            return True
        else:
            send_log("error", f"Automatisation echouee (code: {process.returncode})")
            return False

    except FileNotFoundError:
        send_log("error", f"Script non trouve: {SCRIPT_PATH}")
        return False
    except Exception as e:
        send_log("error", f"Erreur: {str(e)}")
        return False

def check_commands():
    """Verifie s'il y a une commande en attente"""
    command = firebase_get("command")

    if command and command.get("status") == "pending" and command.get("action") == "run":
        # Marquer comme en cours
        firebase_set("command", {
            "action": "run",
            "status": "running",
            "timestamp": int(time.time() * 1000)
        })

        # Executer l'automatisation
        success = run_automation()

        # Marquer comme termine
        firebase_set("command", {
            "action": "run",
            "status": "completed" if success else "failed",
            "timestamp": int(time.time() * 1000)
        })

def main():
    global log_order

    print("=" * 60)
    print("   FIREBASE LISTENER - AUTOMATISATION A DISTANCE")
    print("=" * 60)
    print(f"Firebase URL: {FIREBASE_URL}")
    print(f"Script: {SCRIPT_PATH}")
    print("En attente de commandes...\n")

    # Recuperer l'ordre actuel des logs
    logs = firebase_get("logs")
    if logs:
        log_order = max([l.get("order", 0) for l in logs.values()])

    # Demarrer le heartbeat en arriere-plan
    heartbeat_thread = threading.Thread(target=send_heartbeat, daemon=True)
    heartbeat_thread.start()

    # Envoyer un log de demarrage
    send_log("info", "PC connecte - En attente de commandes")

    # Boucle principale
    while True:
        try:
            check_commands()
        except Exception as e:
            print(f"[ERREUR] {e}")

        time.sleep(2)  # Verifier toutes les 2 secondes

if __name__ == '__main__':
    main()
