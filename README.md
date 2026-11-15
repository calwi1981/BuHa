# BUHA

BUHA ist eine webbasierte Anwendung zur Rechnungsstellung und
Buchhaltungsverwaltung. Sie kann auf einem eigenen Server mit
Docker und PostgreSQL betrieben werden.

## Funktionen

- Kunden- und Lieferantenverwaltung
- Artikel- und Leistungsverwaltung
- Erstellung und Verwaltung von Rechnungen
- PDF-Rechnungen und Rechnungsanhänge
- Versand von Rechnungen per E-Mail
- Wiederkehrende Rechnungen
- XRechnung-Unterstützung
- Import und Verarbeitung eingehender XRechnungen
- Buchhaltungsfunktionen und Kontenverwaltung
- Dashboard mit Umsatzübersichten
- Benutzerverwaltung und Administration
- Mehrsprachige Grundeinstellungen

Einzelne Funktionen können zusätzliche Konfigurationen oder
externe Dienste benötigen.

## Technische Grundlage

- Python 3.12
- FastAPI
- PostgreSQL 16
- SQLAlchemy und Alembic
- HTML, CSS und JavaScript
- Docker Compose

## Installation

Für eine eigenständige Installation ist die Datei
`compose.public.yaml` vorgesehen.

Die vollständige Installationsanleitung befindet sich in
[INSTALL.md](INSTALL.md).

Die produktive Bereitstellung sollte ausschließlich über
HTTPS erfolgen.

## XRechnung

BUHA unterstützt die Verarbeitung elektronischer Rechnungen.

Für die externe XRechnung-Validierung wird ein gesonderter
Validator-Dienst benötigt. Dieser ist nicht Bestandteil des
veröffentlichten BUHA-Quellcodes.

## Lizenz

BUHA wird unter der **BUHA Community License 1.0**
bereitgestellt.

Erlaubt sind insbesondere:

- kostenlose private Nutzung,
- kostenlose interne Nutzung in Unternehmen,
- Anpassungen und Erweiterungen des Quellcodes,
- kostenlose Weitergabe unveränderter und veränderter Versionen
  unter Einhaltung der Lizenzbedingungen.

Die kommerzielle Verwertung der BUHA-Software selbst,
insbesondere Verkauf, kostenpflichtiger Weitervertrieb
oder kostenpflichtige Bereitstellung als SaaS-Dienst,
bedarf der vorherigen schriftlichen Genehmigung des
Rechteinhabers.

Die interne Nutzung durch ein Unternehmen ist ausdrücklich
erlaubt und gilt nicht allein deshalb als untersagte
kommerzielle Verwertung.

BUHA ist damit öffentlich einsehbare Software
(Source-Available), jedoch keine Open-Source-Software
im Sinne der Open Source Initiative (OSI).

Die vollständigen Bedingungen stehen in
[LICENSE.md](LICENSE.md).

## Urheberrecht

Copyright (c) 2026 calwi.de - Markus A. Bross.

## Haftung

BUHA wird ohne Zusicherung einer bestimmten Eignung
bereitgestellt. Die gesetzlichen Haftungsbestimmungen
und die Regelungen der BUHA Community License gelten.

## Projektstatus

BUHA wird aktiv entwickelt. Vor einem produktiven Einsatz
sind die Konfiguration, Datensicherung und gesetzlichen
Anforderungen eigenverantwortlich zu prüfen.
