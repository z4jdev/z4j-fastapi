# Changelog

## 1.9.0 (2026-08-25)

* Raise the uncapped FastAPI dependency floor to 0.109.1. FastAPI 0.100
  remains the first Pydantic 2-compatible release, but 0.109.1 is the
  first release that also closes CVE-2024-24762.
* TaskIQ discovery now attaches z4j's middleware so TaskIQ startup can bind
  broker operations to the broker's actual owner loop. It does not assume
  that an ambient FastAPI loop owns the supplied broker.

## 1.8.0 (2026-07-23)

* Part of the coordinated 1.8.0 fleet release (unified fleet version, green lint/format/import-boundary gate).

## 1.7.0 (2026-07-07)

* README corrected to the real `z4j_lifespan(...)` passed to `FastAPI(lifespan=...)` API and env-var names.
* Python 3.11 is now the minimum supported version (3.10 dropped).
* Part of the coordinated 1.7.0 fleet release (unified fleet version, green lint/format/import-boundary gate).

## 1.4.0 (2026-05-02)

Initial 1.4.0 release: FastAPI adapter. `add_z4j(app)` call after constructing the FastAPI app.
