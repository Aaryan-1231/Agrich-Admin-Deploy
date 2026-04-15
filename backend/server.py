from fastapi import FastAPI, APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import json
import httpx
from supabase import create_client, Client

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Supabase connection
SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://qnzfadvdxouztyvpbxbc.supabase.co')
SUPABASE_KEY = os.environ.get('SUPABASE_SERVICE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFuemZhZHZkeG91enR5dnBieGJjIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NjEzODU2OCwiZXhwIjoyMDkxNzE0NTY4fQ.VZVawQnqspj8dXbG3QLZN0RmZ_BDKrYSq4bsd4DHqVQ')

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Create the main app
app = FastAPI(title="Agrich API", description="B2B Potato Trading Platform", version="2.0.0")
api_router = APIRouter(prefix="/api")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# WebSocket connection manager for real-time bidding
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, auction_id: str):
        await websocket.accept()
        if auction_id not in self.active_connections:
            self.active_connections[auction_id] = []
        self.active_connections[auction_id].append(websocket)

    def disconnect(self, websocket: WebSocket, auction_id: str):
        if auction_id in self.active_connections:
            self.active_connections[auction_id].remove(websocket)

    async def broadcast(self, auction_id: str, message: dict):
        if auction_id in self.active_connections:
            for connection in self.active_connections[auction_id]:
                try:
                    await connection.send_json(message)
                except:
                    pass

manager = ConnectionManager()

# ==================== MODELS ====================

# Auth Models
class SendOTPRequest(BaseModel):
    phone: str

class VerifyOTPRequest(BaseModel):
    phone: str
    otp: str
    firebase_uid: Optional[str] = None

# User Models
class UserCreate(BaseModel):
    phone: str
    company_name: str
    business_type: str  # "buyer", "seller", "both"
    location: str
    address: str
    firebase_uid: Optional[str] = None

# KYC Models
class KYCUpload(BaseModel):
    user_id: str
    document_type: str
    document_number: str
    document_url: str

# Tender Models
class TenderCreate(BaseModel):
    variety: str
    size: str
    quantity_mt: float
    delivery_location: str
    delivery_coordinates: Optional[dict] = None
    date_range: dict
    buyer_rate: float

class TenderBid(BaseModel):
    tender_id: str
    quantity_accepted: float

# Push Notification Models
class PushTokenRegister(BaseModel):
    user_id: str
    push_token: str
    platform: str

# Admin Models
class AdminLogin(BaseModel):
    email: str
    password: str

class KYCApproval(BaseModel):
    kyc_id: str
    approved: bool
    rejection_reason: Optional[str] = None

# ==================== PUSH NOTIFICATION HELPERS ====================

async def send_push_notification(push_token: str, title: str, body: str, data: dict = None):
    """Send a push notification via Expo Push Service"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://exp.host/--/api/v2/push/send",
                json={
                    "to": push_token,
                    "sound": "default",
                    "title": title,
                    "body": body,
                    "data": data or {}
                },
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json"
                },
                timeout=10.0
            )
            result = response.json()
            logger.info(f"Push notification sent: {result}")
            return result
    except Exception as e:
        logger.error(f"Failed to send push notification: {e}")
        return None

async def send_notification_to_user(user_id: str, title: str, body: str, data: dict = None):
    """Send notification to a specific user"""
    result = supabase.table("push_tokens").select("push_token").eq("user_id", user_id).execute()
    if result.data and len(result.data) > 0:
        push_token = result.data[0].get("push_token")
        if push_token:
            return await send_push_notification(push_token, title, body, data)
    return None

async def send_notification_to_all_sellers(title: str, body: str, data: dict = None):
    """Send notification to all approved sellers"""
    result = supabase.table("users").select("id").eq("business_type", "seller").eq("approved", True).execute()
    for user in result.data:
        await send_notification_to_user(user["id"], title, body, data)

async def send_notification_to_all_buyers(title: str, body: str, data: dict = None):
    """Send notification to all approved buyers"""
    result = supabase.table("users").select("id").eq("business_type", "buyer").eq("approved", True).execute()
    for user in result.data:
        await send_notification_to_user(user["id"], title, body, data)

# ==================== AUTH ENDPOINTS ====================

@api_router.post("/auth/send-otp")
async def send_otp(request: SendOTPRequest):
    """Mock OTP sending - in production, Firebase handles this"""
    return {"success": True, "message": "OTP sent successfully"}

@api_router.post("/auth/verify-otp")
async def verify_otp(request: VerifyOTPRequest):
    """Verify OTP and check user status"""
    if len(request.otp) != 6:
        raise HTTPException(status_code=400, detail="Invalid OTP")
    
    # Check if user exists
    result = supabase.table("users").select("*").eq("phone", request.phone).execute()
    
    if not result.data or len(result.data) == 0:
        # New user
        return {
            "success": True,
            "new_user": True,
            "phone": request.phone
        }
    
    user = result.data[0]
    
    # Update Firebase UID if provided
    if request.firebase_uid:
        supabase.table("users").update({"firebase_uid": request.firebase_uid}).eq("id", user["id"]).execute()
    
    # Check if user is approved
    if not user.get("approved", False):
        return {
            "success": False,
            "pending_approval": True,
            "message": "Your account is pending admin approval."
        }
    
    # Generate mock token
    token = f"token_{request.phone}_{datetime.utcnow().timestamp()}"
    
    return {
        "success": True,
        "new_user": False,
        "token": token,
        "user": user
    }

@api_router.post("/auth/register")
async def register_user(user_data: UserCreate):
    """Register a new user"""
    # Check if phone already exists
    existing = supabase.table("users").select("id").eq("phone", user_data.phone).execute()
    if existing.data and len(existing.data) > 0:
        raise HTTPException(status_code=400, detail="Phone number already registered")
    
    # Create user
    new_user = {
        "phone": user_data.phone,
        "company_name": user_data.company_name,
        "business_type": user_data.business_type,
        "location": user_data.location,
        "address": user_data.address,
        "firebase_uid": user_data.firebase_uid,
        "approved": False,
        "created_at": datetime.utcnow().isoformat()
    }
    
    result = supabase.table("users").insert(new_user).execute()
    
    return {
        "success": True,
        "pending_approval": True,
        "message": "Registration successful! Your account is pending admin approval."
    }

# ==================== PUSH NOTIFICATION ENDPOINTS ====================

@api_router.post("/notifications/register-token")
async def register_push_token(token_data: PushTokenRegister):
    """Register or update a user's push notification token"""
    supabase.table("push_tokens").upsert({
        "user_id": token_data.user_id,
        "push_token": token_data.push_token,
        "platform": token_data.platform,
        "updated_at": datetime.utcnow().isoformat()
    }, on_conflict="user_id").execute()
    
    return {"success": True, "message": "Push token registered successfully"}

@api_router.delete("/notifications/unregister-token")
async def unregister_push_token(user_id: str):
    """Remove a user's push notification token"""
    supabase.table("push_tokens").delete().eq("user_id", user_id).execute()
    return {"success": True, "message": "Push token removed successfully"}

# ==================== KYC ENDPOINTS ====================

@api_router.post("/kyc/upload")
async def upload_kyc(kyc_data: KYCUpload):
    """Upload KYC document"""
    new_kyc = {
        "user_id": kyc_data.user_id,
        "document_type": kyc_data.document_type,
        "document_number": kyc_data.document_number,
        "document_url": kyc_data.document_url,
        "status": "pending",
        "created_at": datetime.utcnow().isoformat()
    }
    
    result = supabase.table("kyc_documents").insert(new_kyc).execute()
    return {"success": True, "kyc_id": result.data[0]["id"]}

@api_router.get("/kyc/status/{user_id}")
async def get_kyc_status(user_id: str):
    """Get KYC status for a user"""
    result = supabase.table("kyc_documents").select("*").eq("user_id", user_id).execute()
    return {"documents": result.data}

# ==================== TENDER ENDPOINTS ====================

@api_router.post("/tenders/create")
async def create_tender(tender_data: TenderCreate, user_id: str):
    """Create a new tender (Buyer only)"""
    new_tender = {
        "buyer_id": user_id,
        "variety": tender_data.variety,
        "size": tender_data.size,
        "quantity_mt": tender_data.quantity_mt,
        "delivery_location": tender_data.delivery_location,
        "delivery_coordinates": tender_data.delivery_coordinates,
        "date_from": tender_data.date_range.get("from"),
        "date_to": tender_data.date_range.get("to"),
        "buyer_rate": tender_data.buyer_rate,
        "status": "active",
        "created_at": datetime.utcnow().isoformat()
    }
    
    result = supabase.table("tenders").insert(new_tender).execute()
    tender = result.data[0]
    
    # Notify all sellers
    await send_notification_to_all_sellers(
        title="New Tender Available!",
        body=f"{tender_data.variety} - {tender_data.quantity_mt} MT @ ₹{tender_data.buyer_rate}/kg",
        data={
            "type": "new_tender",
            "tender_id": tender["id"],
            "variety": tender_data.variety
        }
    )
    
    return {"success": True, "tender": tender}

@api_router.get("/tenders/active")
async def get_active_tenders(user_id: Optional[str] = None):
    """Get all active tenders with bids"""
    # Get tenders
    query = supabase.table("tenders").select("*, users!tenders_buyer_id_fkey(company_name, phone)").eq("status", "active")
    
    # If user is a buyer, only show their own tenders
    if user_id:
        user_result = supabase.table("users").select("business_type").eq("id", user_id).execute()
        if user_result.data and user_result.data[0].get("business_type") == "buyer":
            query = query.eq("buyer_id", user_id)
    
    result = query.order("created_at", desc=True).execute()
    
    # Get bids for each tender
    tenders = []
    for tender in result.data:
        bids_result = supabase.table("tender_bids").select("*, users!tender_bids_seller_id_fkey(company_name)").eq("tender_id", tender["id"]).execute()
        tender["bids"] = bids_result.data
        tender["buyer_name"] = tender.get("users", {}).get("company_name", "Unknown")
        tenders.append(tender)
    
    return tenders

@api_router.get("/tenders/{tender_id}")
async def get_tender(tender_id: str):
    """Get a single tender with details"""
    result = supabase.table("tenders").select("*, users!tenders_buyer_id_fkey(company_name, phone, location)").eq("id", tender_id).execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="Tender not found")
    
    tender = result.data[0]
    
    # Get bids
    bids_result = supabase.table("tender_bids").select("*, users!tender_bids_seller_id_fkey(company_name, location)").eq("tender_id", tender_id).execute()
    tender["bids"] = bids_result.data
    tender["buyer_name"] = tender.get("users", {}).get("company_name", "Unknown")
    
    return tender

@api_router.post("/tenders/bid")
async def place_tender_bid(bid_data: TenderBid, user_id: str):
    """Seller accepts a tender (places bid)"""
    # Get tender
    tender_result = supabase.table("tenders").select("*").eq("id", bid_data.tender_id).execute()
    if not tender_result.data:
        raise HTTPException(status_code=404, detail="Tender not found")
    
    tender = tender_result.data[0]
    
    # Get user info
    user_result = supabase.table("users").select("company_name, business_type").eq("id", user_id).execute()
    if not user_result.data:
        raise HTTPException(status_code=404, detail="User not found")
    
    user = user_result.data[0]
    
    if user["business_type"] == "buyer":
        raise HTTPException(status_code=400, detail="Buyers cannot accept tenders")
    
    # Calculate total accepted quantity
    existing_bids = supabase.table("tender_bids").select("quantity_accepted").eq("tender_id", bid_data.tender_id).execute()
    total_accepted = sum(b["quantity_accepted"] for b in existing_bids.data)
    
    remaining = tender["quantity_mt"] - total_accepted
    quantity_to_accept = min(bid_data.quantity_accepted, remaining)
    
    if quantity_to_accept <= 0:
        raise HTTPException(status_code=400, detail="No quantity remaining for this tender")
    
    # Create bid
    new_bid = {
        "tender_id": bid_data.tender_id,
        "seller_id": user_id,
        "seller_name": user["company_name"],
        "quantity_accepted": quantity_to_accept,
        "status": "pending",
        "created_at": datetime.utcnow().isoformat()
    }
    
    supabase.table("tender_bids").insert(new_bid).execute()
    
    # Notify buyer
    await send_notification_to_user(
        user_id=tender["buyer_id"],
        title="Order Accepted!",
        body=f"{user['company_name']} accepted {quantity_to_accept} MT of {tender['variety']}",
        data={
            "type": "order_accepted",
            "tender_id": bid_data.tender_id
        }
    )
    
    return {"success": True, "message": f"Order accepted for {quantity_to_accept} MT! Awaiting quality check."}

# ==================== USER ENDPOINTS ====================

@api_router.get("/users/{user_id}/profile")
async def get_user_profile(user_id: str):
    """Get user profile with stats"""
    result = supabase.table("users").select("*").eq("id", user_id).execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="User not found")
    
    user = result.data[0]
    
    # Get stats
    if user["business_type"] == "buyer":
        tenders = supabase.table("tenders").select("id").eq("buyer_id", user_id).execute()
        user["total_tenders"] = len(tenders.data)
    else:
        bids = supabase.table("tender_bids").select("id").eq("seller_id", user_id).execute()
        user["total_bids"] = len(bids.data)
    
    return user

@api_router.get("/user/transactions")
async def get_user_transactions(user_id: str):
    """Get user's transaction history"""
    # Get user
    user_result = supabase.table("users").select("business_type").eq("id", user_id).execute()
    if not user_result.data:
        raise HTTPException(status_code=404, detail="User not found")
    
    user = user_result.data[0]
    
    active_contracts = []
    past_transactions = []
    
    if user["business_type"] == "buyer":
        # Get buyer's tenders
        tenders = supabase.table("tenders").select("*, tender_bids(*)").eq("buyer_id", user_id).order("created_at", desc=True).execute()
        
        for tender in tenders.data:
            for bid in tender.get("tender_bids", []):
                transaction = {
                    "id": bid["id"],
                    "type": "purchase",
                    "variety": tender["variety"],
                    "quantity_mt": bid["quantity_accepted"],
                    "rate_per_kg": tender["buyer_rate"],
                    "total_value": bid["quantity_accepted"] * tender["buyer_rate"] * 1000,
                    "counterparty": bid.get("seller_name", "Unknown"),
                    "status": bid["status"],
                    "date": bid["created_at"]
                }
                
                if bid["status"] == "pending":
                    active_contracts.append(transaction)
                else:
                    past_transactions.append(transaction)
    else:
        # Get seller's bids
        bids = supabase.table("tender_bids").select("*, tenders(*)").eq("seller_id", user_id).order("created_at", desc=True).execute()
        
        for bid in bids.data:
            tender = bid.get("tenders", {})
            transaction = {
                "id": bid["id"],
                "type": "sale",
                "variety": tender.get("variety", "Unknown"),
                "quantity_mt": bid["quantity_accepted"],
                "rate_per_kg": tender.get("buyer_rate", 0),
                "total_value": bid["quantity_accepted"] * tender.get("buyer_rate", 0) * 1000,
                "counterparty": "Buyer",
                "status": bid["status"],
                "date": bid["created_at"]
            }
            
            if bid["status"] == "pending":
                active_contracts.append(transaction)
            else:
                past_transactions.append(transaction)
    
    return {
        "active_contracts": active_contracts,
        "past_transactions": past_transactions
    }

# ==================== MARKET PRICES ENDPOINTS ====================

@api_router.get("/mandi/prices")
async def get_mandi_prices(state: Optional[str] = None):
    """Get market prices"""
    query = supabase.table("market_prices").select("*")
    
    if state:
        query = query.eq("state", state)
    
    result = query.order("updated_at", desc=True).execute()
    return result.data

@api_router.post("/mandi/prices")
async def update_mandi_price(variety: str, state: str, price_per_kg: float):
    """Update market price (admin only)"""
    # Check if exists
    existing = supabase.table("market_prices").select("id").eq("variety", variety).eq("state", state).execute()
    
    if existing.data:
        supabase.table("market_prices").update({
            "price_per_kg": price_per_kg,
            "updated_at": datetime.utcnow().isoformat()
        }).eq("id", existing.data[0]["id"]).execute()
    else:
        supabase.table("market_prices").insert({
            "variety": variety,
            "state": state,
            "price_per_kg": price_per_kg,
            "updated_at": datetime.utcnow().isoformat()
        }).execute()
    
    return {"success": True}

# ==================== ADMIN ENDPOINTS ====================

@api_router.post("/admin/login")
async def admin_login(credentials: AdminLogin):
    """Admin login"""
    if credentials.email == "admin@agrich.com" and credentials.password == "admin123":
        return {
            "success": True,
            "token": "admin_token_secure",
            "admin": {"email": credentials.email, "role": "admin"}
        }
    raise HTTPException(status_code=401, detail="Invalid credentials")

@api_router.get("/admin/dashboard/stats")
async def get_dashboard_stats():
    """Get admin dashboard statistics"""
    users = supabase.table("users").select("id, business_type, approved").execute()
    tenders = supabase.table("tenders").select("id, status").execute()
    bids = supabase.table("tender_bids").select("id, status").execute()
    
    total_users = len(users.data)
    buyers = len([u for u in users.data if u["business_type"] == "buyer"])
    sellers = len([u for u in users.data if u["business_type"] == "seller"])
    pending_approvals = len([u for u in users.data if not u["approved"]])
    
    active_tenders = len([t for t in tenders.data if t["status"] == "active"])
    pending_quality_checks = len([b for b in bids.data if b["status"] == "pending"])
    
    return {
        "total_users": total_users,
        "buyers": buyers,
        "sellers": sellers,
        "pending_approvals": pending_approvals,
        "active_tenders": active_tenders,
        "pending_quality_checks": pending_quality_checks
    }

@api_router.get("/admin/users")
async def get_all_users(skip: int = 0, limit: int = 50):
    """Get all users"""
    result = supabase.table("users").select("*").range(skip, skip + limit - 1).order("created_at", desc=True).execute()
    return result.data

@api_router.get("/admin/users/pending")
async def get_pending_users():
    """Get users pending approval"""
    result = supabase.table("users").select("*").eq("approved", False).order("created_at", desc=True).execute()
    return result.data

@api_router.post("/admin/users/approve")
async def approve_user(user_id: str, approved: bool = True):
    """Approve or reject a user"""
    supabase.table("users").update({"approved": approved}).eq("id", user_id).execute()
    
    if approved:
        await send_notification_to_user(
            user_id=user_id,
            title="Account Approved!",
            body="Your Agrich account has been approved. Start trading now!",
            data={"type": "account_approved"}
        )
    
    status = "approved" if approved else "rejected"
    return {"success": True, "message": f"User {status} successfully"}

@api_router.get("/admin/kyc/pending")
async def get_pending_kyc():
    """Get pending KYC documents"""
    result = supabase.table("kyc_documents").select("*, users(company_name, phone)").eq("status", "pending").execute()
    return result.data

@api_router.post("/admin/kyc/approve")
async def approve_kyc(approval: KYCApproval):
    """Approve or reject KYC document"""
    status = "approved" if approval.approved else "rejected"
    update_data = {"status": status}
    
    if approval.rejection_reason:
        update_data["rejection_reason"] = approval.rejection_reason
    
    supabase.table("kyc_documents").update(update_data).eq("id", approval.kyc_id).execute()
    
    return {"success": True, "message": f"KYC {status}"}

@api_router.get("/admin/tenders/all")
async def get_all_tenders():
    """Get all tenders for admin"""
    result = supabase.table("tenders").select("*, users!tenders_buyer_id_fkey(company_name), tender_bids(*)").order("created_at", desc=True).execute()
    return result.data

@api_router.post("/admin/transactions/approve")
async def approve_transaction(tender_id: str, bid_id: str, approved: bool, notes: str = None):
    """Approve or reject a transaction (quality check)"""
    new_status = "approved" if approved else "rejected"
    
    update_data = {"status": new_status}
    if notes:
        update_data["admin_notes"] = notes
    
    supabase.table("tender_bids").update(update_data).eq("id", bid_id).execute()
    
    # Get bid and tender info for notification
    bid_result = supabase.table("tender_bids").select("*, tenders(variety, buyer_id)").eq("id", bid_id).execute()
    
    if bid_result.data:
        bid = bid_result.data[0]
        tender = bid.get("tenders", {})
        
        # Notify seller
        await send_notification_to_user(
            user_id=bid["seller_id"],
            title=f"Quality Check {'Approved' if approved else 'Failed'}!",
            body=f"Your {bid['quantity_accepted']} MT of {tender.get('variety', 'potato')} has {'passed' if approved else 'failed'} quality check.",
            data={"type": f"quality_check_{'approved' if approved else 'rejected'}", "tender_id": tender_id}
        )
        
        # Notify buyer
        await send_notification_to_user(
            user_id=tender.get("buyer_id"),
            title=f"Quality Check {'Approved' if approved else 'Failed'}!",
            body=f"{bid['quantity_accepted']} MT {'passed' if approved else 'failed'} quality check.",
            data={"type": f"quality_check_{'approved' if approved else 'rejected'}", "tender_id": tender_id}
        )
    
    return {"success": True, "message": f"Transaction {new_status}"}

# ==================== WEBSOCKET FOR REAL-TIME ====================

@api_router.websocket("/ws/auction/{auction_id}")
async def websocket_endpoint(websocket: WebSocket, auction_id: str):
    await manager.connect(websocket, auction_id)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.broadcast(auction_id, {"type": "message", "data": data})
    except WebSocketDisconnect:
        manager.disconnect(websocket, auction_id)

# ==================== CORS & STATIC FILES ====================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount admin dashboard
admin_path = ROOT_DIR.parent / "admin-dashboard"
if admin_path.exists():
    app.mount("/api/admin", StaticFiles(directory=str(admin_path), html=True), name="admin")

# Include API router
app.include_router(api_router)

@app.get("/")
async def root():
    return {"message": "Agrich API v2.0 - Powered by Supabase", "status": "running"}

# ==================== STARTUP/SHUTDOWN ====================

@app.on_event("startup")
async def startup():
    logger.info("Agrich API started with Supabase backend")

@app.on_event("shutdown")
async def shutdown():
    logger.info("Agrich API shutting down")
