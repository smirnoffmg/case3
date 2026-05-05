CREATE TABLE users (
  id BIGINT PRIMARY KEY,
  email TEXT NOT NULL,
  password_hash TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE products (
  id BIGINT PRIMARY KEY,
  sku TEXT NOT NULL,
  name TEXT NOT NULL,
  price_cents BIGINT NOT NULL
);

CREATE TABLE orders (
  id BIGINT PRIMARY KEY,
  user_id BIGINT NOT NULL,
  status TEXT NOT NULL,
  total_cents BIGINT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT fk_orders_user FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE order_items (
  id BIGINT PRIMARY KEY,
  order_id BIGINT NOT NULL,
  product_id BIGINT NOT NULL,
  qty BIGINT NOT NULL,
  unit_price_cents BIGINT NOT NULL,
  CONSTRAINT fk_order_items_order FOREIGN KEY (order_id) REFERENCES orders(id),
  CONSTRAINT fk_order_items_product FOREIGN KEY (product_id) REFERENCES products(id)
);

CREATE TABLE payments (
  id BIGINT PRIMARY KEY,
  order_id BIGINT NOT NULL,
  card_number TEXT NOT NULL,
  amount_cents BIGINT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT fk_payments_order FOREIGN KEY (order_id) REFERENCES orders(id)
);

