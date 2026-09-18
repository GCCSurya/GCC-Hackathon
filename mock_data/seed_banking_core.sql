\set ON_ERROR_STOP on
BEGIN;

CREATE TABLE public.customers (
    customer_id INT PRIMARY KEY, first_name VARCHAR(64) NOT NULL, last_name VARCHAR(64) NOT NULL,
    email VARCHAR(128) UNIQUE NOT NULL, phone VARCHAR(32), tier VARCHAR(32), status VARCHAR(32), created_at TIMESTAMP
);
CREATE TABLE public.accounts (
    account_id INT PRIMARY KEY, customer_id INT NOT NULL REFERENCES public.customers(customer_id),
    account_number VARCHAR(32) UNIQUE NOT NULL, account_type VARCHAR(32), balance NUMERIC(15,2),
    currency VARCHAR(3), status VARCHAR(32), created_at TIMESTAMP
);
CREATE TABLE public.orders (
    order_id INT PRIMARY KEY, account_id INT NOT NULL REFERENCES public.accounts(account_id), customer_id INT NOT NULL,
    order_type VARCHAR(64), amount NUMERIC(15,2), currency VARCHAR(3), status VARCHAR(32),
    merchant_name VARCHAR(128), created_at TIMESTAMP, updated_at TIMESTAMP
);
CREATE TABLE public.transactions (
    transaction_id BIGSERIAL PRIMARY KEY, order_id INT NOT NULL REFERENCES public.orders(order_id),
    account_id INT NOT NULL REFERENCES public.accounts(account_id), amount NUMERIC(15,2), status VARCHAR(32), posted_at TIMESTAMP
);

\copy public.customers FROM 'customers.csv' WITH (FORMAT csv, HEADER true)
\copy public.accounts FROM 'accounts.csv' WITH (FORMAT csv, HEADER true)
\copy public.orders FROM 'orders.csv' WITH (FORMAT csv, HEADER true)
INSERT INTO public.transactions(order_id, account_id, amount, status, posted_at)
SELECT order_id, account_id, amount, CASE WHEN status = 'COMPLETED' THEN 'POSTED' ELSE status END, updated_at FROM public.orders;

CREATE INDEX idx_accounts_customer ON public.accounts(customer_id);
CREATE INDEX idx_orders_account ON public.orders(account_id);
CREATE INDEX idx_transactions_order ON public.transactions(order_id);
ANALYZE;
COMMIT;