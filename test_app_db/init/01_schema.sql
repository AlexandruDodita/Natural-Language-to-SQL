-- ============================================================
-- Car Rental Service — Schema
-- ============================================================

-- 1. Locations (branch offices)
CREATE TABLE locations (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    city        VARCHAR(100) NOT NULL,
    address     VARCHAR(255) NOT NULL,
    phone       VARCHAR(20),
    created_at  TIMESTAMP DEFAULT NOW()
);

-- 2. Employees
CREATE TABLE employees (
    id          SERIAL PRIMARY KEY,
    location_id INTEGER NOT NULL REFERENCES locations(id) ON DELETE CASCADE,
    first_name  VARCHAR(50) NOT NULL,
    last_name   VARCHAR(50) NOT NULL,
    role        VARCHAR(30) NOT NULL CHECK (role IN ('manager', 'agent', 'mechanic', 'receptionist')),
    salary      NUMERIC(10,2) NOT NULL,
    hire_date   DATE NOT NULL,
    email       VARCHAR(150),
    phone       VARCHAR(20),
    created_at  TIMESTAMP DEFAULT NOW()
);

-- 3. Vehicle categories
CREATE TABLE vehicle_categories (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(50) NOT NULL UNIQUE,
    description     TEXT,
    daily_rate_min  NUMERIC(10,2) NOT NULL,
    daily_rate_max  NUMERIC(10,2) NOT NULL
);

-- 4. Vehicles
CREATE TABLE vehicles (
    id              SERIAL PRIMARY KEY,
    category_id     INTEGER NOT NULL REFERENCES vehicle_categories(id) ON DELETE RESTRICT,
    location_id     INTEGER NOT NULL REFERENCES locations(id) ON DELETE CASCADE,
    make            VARCHAR(50) NOT NULL,
    model           VARCHAR(50) NOT NULL,
    year            INTEGER NOT NULL CHECK (year BETWEEN 2015 AND 2025),
    license_plate   VARCHAR(20) NOT NULL UNIQUE,
    color           VARCHAR(30),
    daily_rate      NUMERIC(10,2) NOT NULL,
    mileage         INTEGER NOT NULL DEFAULT 0,
    status          VARCHAR(20) NOT NULL DEFAULT 'available'
                        CHECK (status IN ('available', 'rented', 'maintenance', 'retired')),
    created_at      TIMESTAMP DEFAULT NOW()
);

-- 5. Clients (customers)
CREATE TABLE clients (
    id                  SERIAL PRIMARY KEY,
    first_name          VARCHAR(50) NOT NULL,
    last_name           VARCHAR(50) NOT NULL,
    email               VARCHAR(150) NOT NULL UNIQUE,
    phone               VARCHAR(20),
    drivers_license     VARCHAR(30) NOT NULL,
    date_of_birth       DATE NOT NULL,
    registration_date   DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at          TIMESTAMP DEFAULT NOW()
);

-- 6. Reservations
CREATE TABLE reservations (
    id              SERIAL PRIMARY KEY,
    client_id       INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    vehicle_id      INTEGER NOT NULL REFERENCES vehicles(id) ON DELETE CASCADE,
    pickup_location INTEGER NOT NULL REFERENCES locations(id) ON DELETE CASCADE,
    return_location INTEGER NOT NULL REFERENCES locations(id) ON DELETE CASCADE,
    pickup_date     DATE NOT NULL,
    return_date     DATE NOT NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'confirmed'
                        CHECK (status IN ('confirmed', 'active', 'completed', 'cancelled', 'no_show')),
    total_cost      NUMERIC(10,2),
    created_at      TIMESTAMP DEFAULT NOW(),
    CONSTRAINT chk_dates CHECK (return_date >= pickup_date)
);

-- 7. Payments
CREATE TABLE payments (
    id              SERIAL PRIMARY KEY,
    reservation_id  INTEGER NOT NULL REFERENCES reservations(id) ON DELETE CASCADE,
    amount          NUMERIC(10,2) NOT NULL,
    payment_method  VARCHAR(20) NOT NULL
                        CHECK (payment_method IN ('credit_card', 'debit_card', 'cash')),
    payment_date    DATE NOT NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'completed'
                        CHECK (status IN ('completed', 'pending', 'refunded', 'failed')),
    created_at      TIMESTAMP DEFAULT NOW()
);

-- 8. Maintenance records
CREATE TABLE maintenance_records (
    id              SERIAL PRIMARY KEY,
    vehicle_id      INTEGER NOT NULL REFERENCES vehicles(id) ON DELETE CASCADE,
    maintenance_type VARCHAR(30) NOT NULL
                        CHECK (maintenance_type IN ('oil_change', 'tire_rotation', 'brake_service',
                                                     'general_inspection', 'engine_repair', 'body_repair',
                                                     'transmission', 'ac_service', 'battery_replacement')),
    description     TEXT,
    cost            NUMERIC(10,2) NOT NULL,
    maintenance_date DATE NOT NULL,
    mileage_at_service INTEGER,
    completed       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMP DEFAULT NOW()
);

-- 9. Reviews
CREATE TABLE reviews (
    id              SERIAL PRIMARY KEY,
    reservation_id  INTEGER NOT NULL REFERENCES reservations(id) ON DELETE CASCADE,
    rating          INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comment         TEXT,
    review_date     DATE NOT NULL,
    created_at      TIMESTAMP DEFAULT NOW()
);

-- Indexes for common query patterns
CREATE INDEX idx_reservations_client      ON reservations(client_id);
CREATE INDEX idx_reservations_vehicle     ON reservations(vehicle_id);
CREATE INDEX idx_reservations_pickup_date ON reservations(pickup_date);
CREATE INDEX idx_reservations_status      ON reservations(status);
CREATE INDEX idx_payments_reservation     ON payments(reservation_id);
CREATE INDEX idx_vehicles_category        ON vehicles(category_id);
CREATE INDEX idx_vehicles_location        ON vehicles(location_id);
CREATE INDEX idx_employees_location       ON employees(location_id);
CREATE INDEX idx_reviews_reservation      ON reviews(reservation_id);
CREATE INDEX idx_maintenance_vehicle      ON maintenance_records(vehicle_id);
