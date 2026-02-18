"""Generate a realistic churn dataset.

Run once:  python generate_data.py
"""

from __future__ import annotations

import csv
import random


def generate() -> None:
    random.seed(42)
    fieldnames = [
        "customer_id",
        "tenure_months",
        "monthly_charges",
        "total_charges",
        "contract_type",
        "num_support_tickets",
        "has_partner",
        "has_dependents",
        "online_security",
        "tech_support",
        "payment_method",
        "churned",
    ]

    contracts = ["month-to-month", "one-year", "two-year"]
    payments = ["credit_card", "bank_transfer", "electronic_check", "mailed_check"]

    with open("churn.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for i in range(1, 5001):
            tenure = random.randint(1, 72)
            monthly = round(random.uniform(18.0, 118.0), 2)
            contract = random.choice(contracts)
            tickets = random.randint(0, 9)
            partner = random.choice([0, 1])
            dependents = random.choice([0, 1])
            security = random.choice([0, 1])
            tech = random.choice([0, 1])
            payment = random.choice(payments)

            # Churn probability influenced by features
            churn_score = 0.0
            if contract == "month-to-month":
                churn_score += 0.35
            elif contract == "one-year":
                churn_score += 0.10
            if tenure < 12:
                churn_score += 0.25
            if monthly > 80:
                churn_score += 0.15
            if tickets > 4:
                churn_score += 0.20
            if payment == "electronic_check":
                churn_score += 0.10
            if security == 0 and tech == 0:
                churn_score += 0.10

            churn_score += random.gauss(0, 0.12)
            churned = 1 if churn_score > 0.5 else 0

            writer.writerow({
                "customer_id": i,
                "tenure_months": tenure,
                "monthly_charges": monthly,
                "total_charges": round(monthly * tenure + random.uniform(-50, 50), 2),
                "contract_type": contract,
                "num_support_tickets": tickets,
                "has_partner": partner,
                "has_dependents": dependents,
                "online_security": security,
                "tech_support": tech,
                "payment_method": payment,
                "churned": churned,
            })

    print("✅  Generated churn.csv (5,000 rows)")


if __name__ == "__main__":
    generate()
