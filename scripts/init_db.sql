CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY,
    name VARCHAR(120) NOT NULL
);

INSERT INTO users (id, name) VALUES
('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'Alice'),
('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'Bob'),
('cccccccc-cccc-cccc-cccc-cccccccccccc', 'Carol')
ON CONFLICT (id) DO NOTHING;
