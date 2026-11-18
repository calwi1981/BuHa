# BUHA - Installationsanleitung

## Voraussetzungen

- Linux-Server mit Docker Engine und Docker Compose
- Git
- Ausreichend Speicherplatz fuer PostgreSQL und Rechnungsdaten
- Optional: HTTPS-Reverse-Proxy und eigene Domain

## 1. Repository herunterladen

    git clone https://github.com/calwi1981/BUHA.git
    cd BUHA

## 2. Konfiguration erstellen

    cp .env.example .env
    chmod 600 .env

Die Datei .env mit einem Texteditor bearbeiten.

Wichtige Einstellungen:

- POSTGRES_DB: Datenbankname
- POSTGRES_USER: Datenbankbenutzer
- POSTGRES_PASSWORD: Starkes Datenbankpasswort
- DATABASE_URL: Verbindung zur PostgreSQL-Datenbank
- SECRET_KEY: Sicherer zufaelliger Anwendungsschluessel
- INITIAL_ADMIN_USERNAME: Benutzername des Administrators
- INITIAL_ADMIN_EMAIL: E-Mail-Adresse des Administrators
- INITIAL_ADMIN_PASSWORD: Passwort mit mindestens 12 Zeichen

DATABASE_URL muss auf den Docker-Dienst db verweisen.

Beispiel:

    postgresql+psycopg://BENUTZER:PASSWORT@db:5432/DATENBANK

Sonderzeichen in Zugangsdaten muessen URL-kodiert werden.
Die Datei .env darf niemals auf GitHub veroeffentlicht werden.

## 3. Datenbank starten

    docker compose -f compose.public.yaml build app
    docker compose -f compose.public.yaml up -d db
    docker compose -f compose.public.yaml ps

Vor der Initialisierung muss PostgreSQL healthy sein.

## 4. Ersteinrichtung

    docker compose -f compose.public.yaml run --rm app python -m app.bootstrap

Der Befehl fuehrt Datenbankmigrationen aus und legt den
ersten Administrator an, sofern noch kein Benutzer existiert.

Nach der Ersteinrichtung sollten die initialen
Administrator-Zugangsdaten aus .env entfernt werden.

## 5. Anwendung starten

    docker compose -f compose.public.yaml up -d app
    docker compose -f compose.public.yaml ps

BUHA ist lokal auf dem Server unter folgender Adresse erreichbar:

    http://127.0.0.1:8000

Der Port ist nur an die lokale Schnittstelle gebunden.
Fuer entfernten Zugriff SSH-Tunnel oder HTTPS-Proxy verwenden.

## 6. HTTPS

Fuer Internetzugriff einen HTTPS-Reverse-Proxy einrichten.
Dieser leitet Anfragen an 127.0.0.1:8000 weiter.

APP_DOMAIN und APP_URL muessen angepasst werden.
Bei HTTPS muss SESSION_COOKIE_SECURE=true gesetzt sein.
Die PostgreSQL-Datenbank darf nicht oeffentlich erreichbar sein.

## 7. E-Mail-Versand

BUHA unterstuetzt SMTP. Erforderliche Einstellungen koennen sein:

- SMTP_HOST
- SMTP_PORT
- SMTP_USER
- SMTP_PASSWORD
- SMTP_FROM
- SMTP_STARTTLS

Fuer verschluesselt gespeicherte SMTP-Zugangsdaten in der
BUHA-Administration wird BUHA_SMTP_ENCRYPTION_KEY benoetigt.
Der Schluessel muss sicher gespeichert und gesichert werden.

## 8. XRechnung

Fuer die externe XRechnung-Validierung wird ein separater
Validator-Dienst benoetigt. Dieser ist nicht im Repository enthalten.

Die Verbindung wird ueber BUHA_XRECHNUNG_VALIDATOR_URL festgelegt.
Ohne Validator sind abhaengige Validierungsfunktionen nicht verfuegbar.

## 9. Aktualisierung

Vor jedem Update Datenbank und Konfiguration sichern.
Anschliessend Quellcode aktualisieren und Image neu bauen.

    docker compose -f compose.public.yaml build app
    docker compose -f compose.public.yaml run --rm app alembic -c /app/alembic.ini upgrade head
    docker compose -f compose.public.yaml up -d app

## 10. Datensicherung

PostgreSQL und Konfigurationsdateien regelmaessig sichern.
Sicherungen vor unbefugtem Zugriff schuetzen.
Die Wiederherstellung regelmaessig testen.

## 11. Lizenz

BUHA steht unter der BUHA Community License 1.0.
Private und interne Unternehmensnutzung sind kostenlos erlaubt.
Aenderungen und kostenlose Weitergabe sind gemaess Lizenz erlaubt.
Kommerzielle Verwertung der Software erfordert eine
vorherige schriftliche Genehmigung.

Vollstaendige Bedingungen: LICENSE.md


## Hinweise zur Aktualisierung auf v1.2.0

Version 1.2.0 fuehrt eine mandantenbezogene Datenstruktur
und neue Buchhaltungsfunktionen ein.

Vor der Aktualisierung:

1. Vollstaendige PostgreSQL-Datensicherung erstellen.
2. Bestehende Konfiguration und Dateispeicher sichern.
3. Anwendungsversion und Datenbank-Migrationsstand pruefen.
4. Sicherstellen, dass die Migrationen vollstaendig vorliegen.

Die neuen Migrationen reichen von 0020 bis 0026.
Sie muessen in der vorgesehenen Reihenfolge angewendet werden.

Fuer die oeffentliche Installation gelten die oben
beschriebenen Docker-Compose-Befehle.

Bestehende individuell konfigurierte Serverinstallationen
muessen anhand ihrer tatsaechlichen Compose-Konfiguration
aktualisiert werden.

Nach der Aktualisierung pruefen:

- Anwendung startet fehlerfrei.
- Anmeldung und Mandantenauswahl funktionieren.
- Mandantenbezogene Daten sind korrekt getrennt.
- Zahlungskonten und Anfangssalden werden korrekt angezeigt.
- Buchungen und Umbuchungen funktionieren.
- Rechnungsstellung und PDF-Erzeugung funktionieren.
- Nebenkostenabrechnung und EÜR sind verfuegbar.
- XRechnung-Funktionen arbeiten mit dem konfigurierten Validator.

Die Datenbank darf nicht durch eine Neuinitialisierung
bestehender produktiver Daten ersetzt werden.
