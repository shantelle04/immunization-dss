"""FHIR R4 export of a child record (FR-34, NFR-09): a collection Bundle of one Patient and its Immunizations.

Vaccine codes use this system's own antigen codes under a local code system; mapping them to an international
vaccine code system is left to the receiving system.
"""

from __future__ import annotations

from datetime import datetime

from .models import Child

IDENTIFIER_SYSTEM = "urn:immdss:child-system-id"
ANTIGEN_SYSTEM = "urn:immdss:antigen"
GENDER = {"F": "female", "M": "male"}


def _patient(child: Child) -> dict:
    return {
        "resourceType": "Patient",
        "id": str(child.pk),
        "identifier": [{"system": IDENTIFIER_SYSTEM, "value": child.system_id}],
        "name": [{"use": "official", "family": child.family_name, "given": [child.given_name]}],
        "gender": GENDER[child.sex],
        "birthDate": child.date_of_birth.isoformat(),
        "contact": [
            {
                "relationship": [
                    {
                        "coding": [
                            {
                                "system": "http://terminology.hl7.org/CodeSystem/v2-0131",
                                "code": "N",
                                "display": "Next-of-Kin",
                            }
                        ]
                    }
                ],
                "name": {"text": child.caregiver_name},
            }
        ],
        "managingOrganization": {"display": child.registration_facility.name},
    }


def _immunization(event, patient_ref: str) -> dict:
    dose = event.schedule_dose
    protocol = {"series": dose.antigen.name}
    # FHIR positiveInt starts at 1; a birth dose numbered 0 is carried as text.
    if dose.dose_number >= 1:
        protocol["doseNumberPositiveInt"] = dose.dose_number
    else:
        protocol["doseNumberString"] = str(dose.dose_number)
    resource = {
        "resourceType": "Immunization",
        "id": f"imm-{event.pk}",
        "status": "completed",
        "vaccineCode": {
            "coding": [{"system": ANTIGEN_SYSTEM, "code": dose.antigen.code, "display": dose.antigen.name}],
            "text": dose.dose_code,
        },
        "patient": {"reference": patient_ref},
        "occurrenceDateTime": event.given_on.isoformat(),
        "primarySource": True,
        "location": {"display": event.facility.name},
        "protocolApplied": [protocol],
    }
    if event.lot_id:
        resource["lotNumber"] = event.lot.lot_number
    return resource


def bundle(child: Child, generated_at: datetime) -> dict:
    patient_ref = f"urn:uuid:{child.pk}"
    events = child.events.select_related("schedule_dose__antigen", "facility", "lot").order_by(
        "given_on", "pk"
    )
    entries = [{"fullUrl": patient_ref, "resource": _patient(child)}]
    entries += [
        {"fullUrl": f"urn:immdss:immunization:{e.pk}", "resource": _immunization(e, patient_ref)}
        for e in events
    ]
    return {
        "resourceType": "Bundle",
        "type": "collection",
        "timestamp": generated_at.isoformat(timespec="seconds"),
        "entry": entries,
    }
