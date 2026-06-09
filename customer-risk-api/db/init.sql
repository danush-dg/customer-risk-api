CREATE TABLE IF NOT EXISTS customer_risk_profiles (
    customer_id  VARCHAR PRIMARY KEY,
    risk_tier    VARCHAR NOT NULL,
    risk_factors TEXT[]  NOT NULL,
    CHECK (risk_tier IN ('LOW', 'MEDIUM', 'HIGH'))
);

INSERT INTO customer_risk_profiles (customer_id, risk_tier, risk_factors) VALUES
    ('CUST-001', 'LOW',    ARRAY['account in good standing', 'consistent payment history', 'low utilisation rate']),
    ('CUST-002', 'LOW',    ARRAY['no missed payments in 24 months', 'single product relationship']),
    ('CUST-003', 'LOW',    ARRAY['long tenure', 'stable address history', 'verified income']),
    ('CUST-004', 'MEDIUM', ARRAY['two late payments in past year', 'moderate utilisation']),
    ('CUST-005', 'MEDIUM', ARRAY['recent address change', 'elevated exposure relative to income']),
    ('CUST-006', 'MEDIUM', ARRAY['disputed transaction on file', 'partial identity verification']),
    ('CUST-007', 'HIGH',   ARRAY['three missed payments', 'account referred to collections']),
    ('CUST-008', 'HIGH',   ARRAY['fraud alert on file', 'multiple failed authentication attempts']),
    ('CUST-009', 'HIGH',   ARRAY['default recorded', 'county court judgement', 'high utilisation across all accounts']);
