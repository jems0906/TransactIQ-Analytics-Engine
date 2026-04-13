from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
import random
import uuid

import numpy as np
import pandas as pd


def generate_transactions(n: int = 4000, seed: int = 42) -> pd.DataFrame:
    random.seed(seed)
    np.random.seed(seed)

    start = datetime.now(UTC) - timedelta(days=90)
    merchants = [f"M{str(i).zfill(4)}" for i in range(1, 51)]
    cardholders = [f"C{str(i).zfill(5)}" for i in range(1, 301)]
    categories = ["grocery", "travel", "electronics", "fuel", "dining", "health", "utilities"]
    channels = ["online", "pos", "wallet"]
    countries = ["US", "CA", "GB", "IN", "SG"]

    risky_merchants = {"M0047", "M0048", "M0049"}

    rows = []
    for _ in range(n):
        merchant_id = random.choice(merchants)
        timestamp = start + timedelta(minutes=random.randint(0, 90 * 24 * 60))
        base_amount = np.random.lognormal(mean=3.5, sigma=0.7)

        status = "approved"
        chargeback = 0

        if merchant_id in risky_merchants:
            if random.random() < 0.35:
                status = "declined"
            if random.random() < 0.18:
                chargeback = 1
            amount = base_amount * np.random.uniform(1.3, 2.4)
        else:
            if random.random() < 0.11:
                status = "declined"
            if random.random() < 0.03:
                chargeback = 1
            amount = base_amount

        if random.random() < 0.01:
            amount *= np.random.uniform(4.0, 8.0)

        rows.append(
            {
                "transaction_id": str(uuid.uuid4()),
                "timestamp": timestamp.isoformat(timespec="seconds"),
                "merchant_id": merchant_id,
                "cardholder_id": random.choice(cardholders),
                "amount": round(float(amount), 2),
                "currency": "USD",
                "status": status,
                "merchant_category": random.choice(categories),
                "country": random.choice(countries),
                "channel": random.choice(channels),
                "is_chargeback": int(chargeback),
            }
        )

    return pd.DataFrame(rows)


def main() -> None:
    output_path = Path("data/sample_transactions.csv")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    df = generate_transactions()
    df.to_csv(output_path, index=False)
    print(f"Generated {len(df)} rows -> {output_path}")


if __name__ == "__main__":
    main()
