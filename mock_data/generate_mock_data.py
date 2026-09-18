import os
import csv
import random
import datetime
import json

# Output directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = SCRIPT_DIR

# Seed for reproducibility
random.seed(42)

FIRST_NAMES = [
    "James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael", "Linda",
    "David", "Elizabeth", "William", "Barbara", "Richard", "Susan", "Joseph", "Jessica",
    "Thomas", "Sarah", "Charles", "Karen", "Christopher", "Nancy", "Daniel", "Lisa",
    "Matthew", "Betty", "Anthony", "Margaret", "Mark", "Sandra", "Donald", "Ashley",
    "Steven", "Kimberly", "Paul", "Emily", "Andrew", "Donna", "Joshua", "Michelle",
    "Kenneth", "Carol", "Kevin", "Amanda", "Brian", "Melissa", "George", "Deborah"
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
    "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson",
    "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson", "Walker"
]

TIERS = ["STANDARD", "PREMIUM", "ENTERPRISE", "PRIVATE_BANKING"]
CUSTOMER_STATUSES = ["ACTIVE", "ACTIVE", "ACTIVE", "ACTIVE", "PENDING", "SUSPENDED"]
ACCOUNT_TYPES = ["CHECKING", "SAVINGS", "ESCROW", "TREASURY_RESERVE", "MONEY_MARKET"]
ACCOUNT_STATUSES = ["ACTIVE", "ACTIVE", "ACTIVE", "ACTIVE", "DORMANT", "FROZEN"]

ORDER_TYPES = [
    "WIRE_TRANSFER", "ACH_CREDIT", "ACH_DEBIT", "MERCHANT_SETTLEMENT", 
    "FX_CONVERSION", "INTERNAL_BOOK_TRANSFER", "CARD_AUTH"
]
ORDER_STATUSES = ["COMPLETED", "COMPLETED", "COMPLETED", "PENDING", "PROCESSING", "ON_HOLD", "FAILED"]
MERCHANTS = [
    "Amazon AWS Services", "Stripe Clearing Inc", "JPMorgan Settlement Corp", 
    "Target Retail Network", "Microsoft Azure Cloud", "Walmart Global Vendor", 
    "Fedwire Interbank Net", "Apple Services US", "Oracle Cloud Infra", "Visa Direct Global"
]

ACTIONS = [
    "ORDER_UPDATE", "ORDER_CREATE", "ACCOUNT_AUTH", "TRANSFER_INITIATE", 
    "KYC_VERIFY", "BALANCE_INQUIRY", "POLICY_EVAL", "RISK_FLAG_OVERRIDE"
]
ENTITY_TYPES = ["ORDER", "ACCOUNT", "CUSTOMER", "AUTH_SESSION", "WIRE_BATCH"]

RECON_STATUSES = ["MATCHED", "MATCHED", "MATCHED", "MATCHED", "UNMATCHED", "DISCREPANCY"]
SYSTEM_NAMES = ["FED_ACH_CLEARING", "SWIFT_FIN", "INTERNAL_LEDGER", "CARD_PAYMENT_GATEWAY"]

def random_date(days_back=90):
    start = datetime.datetime.now() - datetime.timedelta(days=days_back)
    random_seconds = random.randint(0, days_back * 86400)
    dt = start + datetime.timedelta(seconds=random_seconds)
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def generate_customers(count=500):
    filepath = os.path.join(OUTPUT_DIR, "customers.csv")
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["customer_id", "first_name", "last_name", "email", "phone", "tier", "status", "created_at"])
        for i in range(1, count + 1):
            fname = random.choice(FIRST_NAMES)
            lname = random.choice(LAST_NAMES)
            email = f"{fname.lower()}.{lname.lower()}{i}@example-corp.com"
            phone = f"+1-800-{random.randint(100, 999)}-{random.randint(1000, 9999)}"
            tier = random.choice(TIERS)
            status = random.choice(CUSTOMER_STATUSES)
            created_at = random_date(365)
            writer.writerow([i, fname, lname, email, phone, tier, status, created_at])
    print(f"Generated {count} customers -> {filepath}")

def generate_accounts(count=1000, customer_count=500):
    filepath = os.path.join(OUTPUT_DIR, "accounts.csv")
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["account_id", "customer_id", "account_number", "account_type", "balance", "currency", "status", "created_at"])
        for i in range(1, count + 1):
            account_id = 5000 + i
            cust_id = random.randint(1, customer_count)
            acct_num = f"PNC-{random.randint(10000000, 99999999)}"
            acct_type = random.choice(ACCOUNT_TYPES)
            balance = round(random.uniform(1500.0, 450000.0), 2)
            currency = "USD"
            status = random.choice(ACCOUNT_STATUSES)
            created_at = random_date(180)
            writer.writerow([account_id, cust_id, acct_num, acct_type, balance, currency, status, created_at])
    print(f"Generated {count} accounts -> {filepath}")

def generate_orders(count=5000, account_count=1000, customer_count=500):
    filepath = os.path.join(OUTPUT_DIR, "orders.csv")
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["order_id", "account_id", "customer_id", "order_type", "amount", "currency", "status", "merchant_name", "created_at", "updated_at"])
        for i in range(1, count + 1):
            order_id = 10000 + i
            acct_id = 5000 + random.randint(1, account_count)
            cust_id = random.randint(1, customer_count)
            order_type = random.choice(ORDER_TYPES)
            amount = round(random.uniform(25.50, 150000.0), 2)
            currency = "USD"
            status = random.choice(ORDER_STATUSES)
            merchant = random.choice(MERCHANTS)
            created_at = random_date(60)
            # updated_at slightly after created_at
            created_dt = datetime.datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S")
            updated_dt = created_dt + datetime.timedelta(seconds=random.randint(5, 7200))
            updated_at = updated_dt.strftime("%Y-%m-%d %H:%M:%S")
            writer.writerow([order_id, acct_id, cust_id, order_type, amount, currency, status, merchant, created_at, updated_at])
    print(f"Generated {count} orders -> {filepath}")

def generate_audit_logs(count=10000):
    filepath = os.path.join(OUTPUT_DIR, "audit_logs.csv")
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["log_id", "user_id", "action", "entity_type", "entity_id", "payload", "ip_address", "status_code", "created_at"])
        for i in range(1, count + 1):
            log_id = i
            user_id = f"USR_{random.randint(1001, 1099)}"
            action = random.choice(ACTIONS)
            entity_type = random.choice(ENTITY_TYPES)
            entity_id = random.randint(10001, 15000)
            
            # Payload with realistic JSON content
            batch_code = f"BATCH_{random.randint(100, 999)}"
            risk_score = round(random.uniform(0.01, 0.99), 3)
            is_flagged = risk_score > 0.85
            payload_dict = {
                "batch": batch_code,
                "risk_score": risk_score,
                "flagged": is_flagged,
                "auth_method": random.choice(["OAUTH2_BEARER", "MTLS_CERT", "API_KEY"]),
                "note": f"Transaction validation for entity {entity_id}"
            }
            if is_flagged:
                payload_dict["review_required"] = True
                payload_dict["reason"] = "Elevated risk threshold exceeded"

            payload_str = json.dumps(payload_dict)
            ip = f"10.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 254)}"
            status_code = random.choice([200, 200, 200, 200, 201, 400, 403, 500])
            created_at = random_date(30)
            writer.writerow([log_id, user_id, action, entity_type, entity_id, payload_str, ip, status_code, created_at])
    print(f"Generated {count} audit logs -> {filepath}")

def generate_recon_records(count=2500):
    filepath = os.path.join(OUTPUT_DIR, "recon_records.csv")
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["recon_id", "source_system", "external_ref", "internal_order_id", "amount", "currency", "status", "discrepancy_reason", "reconciled_at"])
        for i in range(1, count + 1):
            recon_id = 80000 + i
            source = random.choice(SYSTEM_NAMES)
            ext_ref = f"EXT-{random.randint(1000000, 9999999)}"
            order_id = 10000 + random.randint(1, 5000)
            amount = round(random.uniform(50.0, 85000.0), 2)
            currency = "USD"
            status = random.choice(RECON_STATUSES)
            reason = ""
            if status == "DISCREPANCY":
                reason = random.choice(["AMOUNT_MISMATCH", "FEE_DEDUCTION_VARIANCE", "TIMESTAMP_SLIPPAGE"])
            elif status == "UNMATCHED":
                reason = "PENDING_SETTLEMENT_FILE"
            reconciled_at = random_date(14)
            writer.writerow([recon_id, source, ext_ref, order_id, amount, currency, status, reason, reconciled_at])
    print(f"Generated {count} recon records -> {filepath}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate realistic PostgreSQL mockup CSV datasets for dbpulse.")
    parser.add_argument("--customers", type=int, default=500, help="Number of customer rows (default: 500)")
    parser.add_argument("--accounts", type=int, default=1000, help="Number of account rows (default: 1000)")
    parser.add_argument("--orders", type=int, default=5000, help="Number of order rows (default: 5000)")
    parser.add_argument("--audit-logs", type=int, default=10000, help="Number of audit_log rows (default: 10000)")
    parser.add_argument("--recon", type=int, default=2500, help="Number of recon rows (default: 2500)")
    args = parser.parse_args()

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    generate_customers(args.customers)
    generate_accounts(args.accounts, args.customers)
    generate_orders(args.orders, args.accounts, args.customers)
    generate_audit_logs(args.audit_logs)
    generate_recon_records(args.recon)
    print("All mock CSV files generated successfully!")
