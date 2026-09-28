"""Import files with planted defects, for testing the system's CSV import validation.

Each defect has a code; `import_dirty_truth.csv` lists the row and defect so the import report can
be scored for recall and false rejections.
"""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

IMMUNIZATION_DEFECTS = [
    "DUPLICATE_ROW",
    "DATE_BEFORE_BIRTH",
    "FUTURE_DATE",
    "UNKNOWN_DOSE",
    "MISSING_CHILD_ID",
    "MALFORMED_DATE",
    "UNKNOWN_FACILITY",
]
STOCK_DEFECTS = ["NEGATIVE_RECEIPT", "UNKNOWN_ANTIGEN", "MALFORMED_DATE", "NON_NUMERIC_QUANTITY"]


def _pick(rng: np.random.Generator, n_rows: int, share: float) -> np.ndarray:
    k = max(1, int(round(n_rows * share)))
    return np.sort(rng.choice(n_rows, size=k, replace=False))


def build_dirty_imports(
    tables: dict[str, pd.DataFrame], rows: int, share: float, as_of: dt.date, rng: np.random.Generator
) -> dict[str, pd.DataFrame]:
    children = tables["children"].set_index("child_id")
    events = tables["immunization_events"]
    sample = events.sample(n=min(rows, len(events)), random_state=int(rng.integers(2**31))).reset_index(
        drop=True
    )
    imm = pd.DataFrame(
        {
            "child_system_id": children.loc[sample.child_id, "system_id"].to_numpy(),
            "date_of_birth": children.loc[sample.child_id, "date_of_birth"].to_numpy(),
            "dose_code": sample.dose_code,
            "given_on": sample.given_on,
            "facility_code": sample.facility_code,
            "lot_number": sample.lot_number,
        }
    ).astype(str)
    truth = []
    extra = []
    for row in _pick(rng, len(imm), share):
        defect = str(rng.choice(IMMUNIZATION_DEFECTS))
        if defect == "DUPLICATE_ROW":
            extra.append(imm.loc[row].copy())
            truth.append(("immunizations", len(imm) + len(extra) - 1, defect))
            continue
        if defect == "DATE_BEFORE_BIRTH":
            dob = dt.date.fromisoformat(imm.at[row, "date_of_birth"])
            imm.at[row, "given_on"] = (dob - dt.timedelta(days=int(rng.integers(1, 60)))).isoformat()
        elif defect == "FUTURE_DATE":
            imm.at[row, "given_on"] = (as_of + dt.timedelta(days=int(rng.integers(30, 400)))).isoformat()
        elif defect == "UNKNOWN_DOSE":
            imm.at[row, "dose_code"] = str(rng.choice(["PENTA-4", "BCG-2", "HPV-1", "OPV3", "penta 1"]))
        elif defect == "MISSING_CHILD_ID":
            imm.at[row, "child_system_id"] = ""
        elif defect == "MALFORMED_DATE":
            d = dt.date.fromisoformat(imm.at[row, "given_on"])
            imm.at[row, "given_on"] = str(
                rng.choice([d.strftime("%d/%m/%Y"), d.strftime("%Y-%d-%m"), "unknown"])
            )
        elif defect == "UNKNOWN_FACILITY":
            imm.at[row, "facility_code"] = "SYN-X99"
        truth.append(("immunizations", int(row), defect))
    if extra:
        imm = pd.concat([imm, pd.DataFrame(extra)], ignore_index=True)

    tx = tables["stock_transactions"]
    receipts = tx[tx.kind == "receipt"]
    s = receipts.sample(n=min(rows // 3, len(receipts)), random_state=int(rng.integers(2**31))).reset_index(
        drop=True
    )
    stock = pd.DataFrame(
        {
            "date": s.date,
            "facility_code": s.facility_code,
            "antigen_code": s.antigen_code,
            "lot_number": s.lot_number,
            "kind": s.kind,
            "quantity_doses": s.quantity_doses,
        }
    ).astype(str)
    for row in _pick(rng, len(stock), share):
        defect = str(rng.choice(STOCK_DEFECTS))
        if defect == "NEGATIVE_RECEIPT":
            stock.at[row, "quantity_doses"] = str(-abs(int(stock.at[row, "quantity_doses"])))
        elif defect == "UNKNOWN_ANTIGEN":
            stock.at[row, "antigen_code"] = str(rng.choice(["YF", "HPV", "Penta", "MMR"]))
        elif defect == "MALFORMED_DATE":
            stock.at[row, "date"] = str(rng.choice(["2023-13-01", "31/02/2024", ""]))
        elif defect == "NON_NUMERIC_QUANTITY":
            stock.at[row, "quantity_doses"] = str(rng.choice(["ten", "1,000", "n/a"]))
        truth.append(("stock", int(row), defect))

    truth_frame = pd.DataFrame(truth, columns=["file", "row_index", "defect"]).sort_values(
        ["file", "row_index"]
    )
    return {"import_immunizations_dirty": imm, "import_stock_dirty": stock, "import_dirty_truth": truth_frame}
