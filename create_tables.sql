-- Create users table
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL,
    email TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    hubspot_api_key VARCHAR(255),
    slack_webhook_url VARCHAR(255)
);

-- Create user_packages table
CREATE TABLE IF NOT EXISTS user_packages (
    id TEXT PRIMARY KEY,
    user_id TEXT REFERENCES users(id),
    package_name TEXT NOT NULL,
    lead_volume INTEGER DEFAULT 0,
    status TEXT DEFAULT 'inactive',
    stripe_subscription_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    next_delivery TIMESTAMPTZ
);

-- Create leads table
CREATE TABLE IF NOT EXISTS leads (
    id TEXT PRIMARY KEY,
    user_id TEXT REFERENCES users(id),
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    phone TEXT,
    linkedin_url TEXT,
    source TEXT,
    score INTEGER DEFAULT 0,
    verified BOOLEAN DEFAULT FALSE,
    phone_verified BOOLEAN DEFAULT FALSE,
    linkedin_verified BOOLEAN DEFAULT FALSE,
    status TEXT DEFAULT 'New',
    date_added TIMESTAMPTZ DEFAULT NOW(),
    hubspot_id TEXT,
    crm_id VARCHAR(50)
);