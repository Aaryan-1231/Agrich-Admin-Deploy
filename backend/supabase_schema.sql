-- Agrich Database Schema for Supabase (PostgreSQL)
-- Run this in Supabase SQL Editor

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ==================== USERS TABLE ====================
CREATE TABLE IF NOT EXISTS users (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  phone VARCHAR(15) UNIQUE NOT NULL,
  company_name VARCHAR(255) NOT NULL,
  business_type VARCHAR(20) CHECK (business_type IN ('buyer', 'seller', 'both')),
  location VARCHAR(255),
  address TEXT,
  firebase_uid VARCHAR(255),
  approved BOOLEAN DEFAULT FALSE,
  suspended BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create index on phone for fast lookups
CREATE INDEX IF NOT EXISTS idx_users_phone ON users(phone);
CREATE INDEX IF NOT EXISTS idx_users_firebase_uid ON users(firebase_uid);

-- ==================== TENDERS TABLE ====================
CREATE TABLE IF NOT EXISTS tenders (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  buyer_id UUID REFERENCES users(id) ON DELETE CASCADE,
  variety VARCHAR(50) NOT NULL,
  size VARCHAR(30),
  quantity_mt DECIMAL(10,2) NOT NULL,
  delivery_location VARCHAR(255),
  delivery_coordinates JSONB,
  date_from DATE,
  date_to DATE,
  buyer_rate DECIMAL(10,2) NOT NULL, -- per kg
  status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'completed', 'cancelled')),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tenders_buyer_id ON tenders(buyer_id);
CREATE INDEX IF NOT EXISTS idx_tenders_status ON tenders(status);

-- ==================== TENDER BIDS TABLE ====================
CREATE TABLE IF NOT EXISTS tender_bids (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tender_id UUID REFERENCES tenders(id) ON DELETE CASCADE,
  seller_id UUID REFERENCES users(id) ON DELETE CASCADE,
  seller_name VARCHAR(255),
  quantity_accepted DECIMAL(10,2) NOT NULL,
  status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
  admin_notes TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tender_bids_tender_id ON tender_bids(tender_id);
CREATE INDEX IF NOT EXISTS idx_tender_bids_seller_id ON tender_bids(seller_id);

-- ==================== KYC DOCUMENTS TABLE ====================
CREATE TABLE IF NOT EXISTS kyc_documents (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  document_type VARCHAR(20) NOT NULL CHECK (document_type IN ('GST', 'PAN', 'AADHAAR', 'FSSAI')),
  document_number VARCHAR(50),
  document_url TEXT,
  status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
  rejection_reason TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_kyc_user_id ON kyc_documents(user_id);

-- ==================== MARKET PRICES TABLE ====================
CREATE TABLE IF NOT EXISTS market_prices (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  variety VARCHAR(50) NOT NULL,
  state VARCHAR(100),
  price_per_kg DECIMAL(10,2) NOT NULL,
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_market_prices_variety ON market_prices(variety);

-- ==================== PUSH TOKENS TABLE ====================
CREATE TABLE IF NOT EXISTS push_tokens (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  push_token TEXT NOT NULL,
  platform VARCHAR(20) CHECK (platform IN ('ios', 'android', 'web')),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  UNIQUE(user_id)
);

-- ==================== AUCTIONS TABLE (for future use) ====================
CREATE TABLE IF NOT EXISTS auctions (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  seller_id UUID REFERENCES users(id) ON DELETE CASCADE,
  variety VARCHAR(50) NOT NULL,
  size VARCHAR(30),
  quantity_mt DECIMAL(10,2) NOT NULL,
  pickup_location VARCHAR(255),
  pickup_coordinates JSONB,
  base_price DECIMAL(10,2) NOT NULL,
  current_bid DECIMAL(10,2),
  current_bidder_id UUID REFERENCES users(id),
  end_time TIMESTAMP WITH TIME ZONE,
  status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'completed', 'cancelled')),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ==================== AUCTION BIDS TABLE ====================
CREATE TABLE IF NOT EXISTS auction_bids (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  auction_id UUID REFERENCES auctions(id) ON DELETE CASCADE,
  bidder_id UUID REFERENCES users(id) ON DELETE CASCADE,
  bidder_name VARCHAR(255),
  bid_amount DECIMAL(10,2) NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ==================== RATINGS TABLE ====================
CREATE TABLE IF NOT EXISTS ratings (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  from_user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  to_user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  tender_id UUID REFERENCES tenders(id) ON DELETE CASCADE,
  rating INTEGER CHECK (rating >= 1 AND rating <= 5),
  review TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ==================== INSERT DEFAULT MARKET PRICES ====================
INSERT INTO market_prices (variety, state, price_per_kg) VALUES
  ('Jyoti', 'Gujarat', 22.50),
  ('Chipsona', 'Gujarat', 28.00),
  ('Kufri Pukhraj', 'Gujarat', 24.50),
  ('Lady Rosetta', 'Gujarat', 32.00),
  ('Atlantic', 'Gujarat', 30.00),
  ('Jyoti', 'Punjab', 21.00),
  ('Chipsona', 'Punjab', 27.00),
  ('Kufri Pukhraj', 'Punjab', 23.50),
  ('Jyoti', 'Uttar Pradesh', 20.50),
  ('Chipsona', 'Uttar Pradesh', 26.50),
  ('Kufri Pukhraj', 'Uttar Pradesh', 23.00)
ON CONFLICT DO NOTHING;

-- ==================== CREATE VIEW FOR TENDER WITH BIDS ====================
CREATE OR REPLACE VIEW tender_details AS
SELECT 
  t.*,
  u.company_name as buyer_name,
  u.phone as buyer_phone,
  (SELECT COUNT(*) FROM tender_bids tb WHERE tb.tender_id = t.id) as bid_count,
  (SELECT COALESCE(SUM(tb.quantity_accepted), 0) FROM tender_bids tb WHERE tb.tender_id = t.id) as total_accepted_quantity
FROM tenders t
LEFT JOIN users u ON t.buyer_id = u.id;

-- ==================== ROW LEVEL SECURITY (Optional) ====================
-- Enable RLS on tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenders ENABLE ROW LEVEL SECURITY;
ALTER TABLE tender_bids ENABLE ROW LEVEL SECURITY;
ALTER TABLE kyc_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE push_tokens ENABLE ROW LEVEL SECURITY;

-- Create policies for public read on tenders
CREATE POLICY "Tenders are viewable by everyone" ON tenders FOR SELECT USING (true);
CREATE POLICY "Users can create tenders" ON tenders FOR INSERT WITH CHECK (true);

-- Create policies for users
CREATE POLICY "Users are viewable by everyone" ON users FOR SELECT USING (true);
CREATE POLICY "Users can be created" ON users FOR INSERT WITH CHECK (true);
CREATE POLICY "Users can update own profile" ON users FOR UPDATE USING (true);

-- Create policies for bids
CREATE POLICY "Bids are viewable by everyone" ON tender_bids FOR SELECT USING (true);
CREATE POLICY "Users can create bids" ON tender_bids FOR INSERT WITH CHECK (true);

-- Create policies for market prices (public read)
CREATE POLICY "Market prices are viewable by everyone" ON market_prices FOR SELECT USING (true);

-- Create policies for push tokens
CREATE POLICY "Push tokens CRUD" ON push_tokens FOR ALL USING (true);

-- Create policies for KYC
CREATE POLICY "KYC documents viewable" ON kyc_documents FOR SELECT USING (true);
CREATE POLICY "KYC documents can be created" ON kyc_documents FOR INSERT WITH CHECK (true);

COMMENT ON TABLE users IS 'Agrich platform users - buyers, sellers, and admins';
COMMENT ON TABLE tenders IS 'Buyer tender requests for potato procurement';
COMMENT ON TABLE tender_bids IS 'Seller acceptances/bids on buyer tenders';
COMMENT ON TABLE market_prices IS 'Current mandi prices for different potato varieties';
