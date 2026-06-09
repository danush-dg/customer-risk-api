CREATE TABLE IF NOT EXISTS customer_risk_profiles (
    customer_id   VARCHAR PRIMARY KEY,
    risk_tier     VARCHAR NOT NULL CHECK (risk_tier IN ('LOW', 'MEDIUM', 'HIGH')),
    risk_factors  TEXT[]  NOT NULL
);

INSERT INTO customer_risk_profiles (customer_id, risk_tier, risk_factors) VALUES
    ('CUST-001', 'LOW',    ARRAY['no missed payments in 24 months', 'low credit utilisation', 'stable employment history']),
    ('CUST-002', 'LOW',    ARRAY['long account tenure', 'no derogatory marks', 'consistent income reported']),
    ('CUST-003', 'LOW',    ARRAY['recent credit inquiry resolved', 'low debt-to-income ratio', 'no collection accounts']),
    ('CUST-004', 'MEDIUM', ARRAY['two late payments in past 12 months', 'moderate credit utilisation', 'short credit history']),
    ('CUST-005', 'MEDIUM', ARRAY['recent new account opened', 'elevated debt-to-income ratio', 'one unresolved dispute']),
    ('CUST-006', 'MEDIUM', ARRAY['seasonal income variability', 'mixed payment history', 'partial balance on revolving credit']),
    ('CUST-007', 'HIGH',   ARRAY['three or more missed payments', 'account in collections', 'high credit utilisation over 90%']),
    ('CUST-008', 'HIGH',   ARRAY['bankruptcy filing within 5 years', 'multiple derogatory marks', 'no positive tradelines']),
    ('CUST-009', 'HIGH',   ARRAY['charge-off on record', 'debt settlement history', 'repeated insufficient funds events']);
