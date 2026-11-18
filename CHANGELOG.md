# BUHA – Änderungsverlauf

## v1.2.0 – 18.11.2026

### Mandanten und Administration

- Mandantenverwaltung eingeführt.
- Mandantenbezogene Zugriffskontrolle ergänzt.
- Globale Systemadministration erweitert.
- Benutzer- und Mandantenzuordnungen ergänzt.
- Mandantenbezogene Einstellungen eingeführt.

### Zahlungskonten und Buchhaltung

- Verwaltung mehrerer Zahlungskonten ergänzt.
- Anfangssaldo und Anfangsdatum je Konto eingeführt.
- Nachträgliche Bearbeitung der Anfangswerte ermöglicht.
- Umbuchungen zwischen Zahlungskonten ergänzt.
- Manuelle Einnahmen- und Ausgabenbuchungen eingeführt.
- Kontostandsberechnung erweitert.
- Einnahmenüberschussrechnung (EÜR) ergänzt.

### Rechnungen und Nebenkosten

- Rechnungsverwaltung mandantenbezogen erweitert.
- Nebenkostenabrechnung ergänzt.
- Eigene Nummernkreise für Nebenkostenabrechnungen eingeführt.
- Rechnungs- und PDF-Erzeugung erweitert.
- Darstellung und Zahlungsinformationen in PDFs überarbeitet.

### Korrekturen

- NK-Stellenzahl von 1 bis 8 ermöglicht.
- Speicherung der NK-Abrechnungseinstellungen korrigiert.
- Bearbeitung von Anfangssalden und Anfangsdaten korrigiert.
- Deutsche Dezimalschreibweise bei Anfangssalden berücksichtigt.
- Frontend-Validierung für Beträge und Datumswerte korrigiert.

### Technische Änderungen

- Datenbankmigrationen 0020 bis 0026.
- Neue API-Module für Mandanten, Systemadministration,
  Zahlungskonten, Umbuchungen und manuelle Buchungen.
- Erweiterungen der Datenmodelle und Buchhaltungsservices.
- Anwendungsversion auf 1.2.0 aktualisiert.

### Hinweise zur Aktualisierung

Vor dem Update sind Datenbank und Konfiguration zu sichern.
Bestehende Installationen müssen die Datenbankmigrationen
vollständig anwenden.

Der externe XRechnung-Validator ist nicht Bestandteil
des veröffentlichten BUHA-Repositorys.

## v1.0.1

- Versionsinformation unterhalb der Abmeldung platziert.

## v1.0.0

- Erste öffentliche Veröffentlichung von BUHA.
