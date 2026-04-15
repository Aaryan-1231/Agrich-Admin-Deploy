// Configuration
const API_URL = window.location.origin + '/api';
let adminToken = localStorage.getItem('adminToken');
let adminEmail = localStorage.getItem('adminEmail');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    if (adminToken && adminEmail) {
        showDashboard();
    } else {
        showLogin();
    }
    
    // Login form handler
    document.getElementById('loginForm').addEventListener('submit', handleLogin);
});

// Show/Hide screens
function showLogin() {
    document.getElementById('loginScreen').classList.remove('hidden');
    document.getElementById('dashboardScreen').classList.add('hidden');
}

function showDashboard() {
    document.getElementById('loginScreen').classList.add('hidden');
    document.getElementById('dashboardScreen').classList.remove('hidden');
    document.getElementById('adminName').textContent = adminEmail;
    loadDashboardData();
}

// Handle login
async function handleLogin(e) {
    e.preventDefault();
    
    const email = document.getElementById('adminEmail').value;
    const password = document.getElementById('adminPassword').value;
    const errorDiv = document.getElementById('loginError');
    
    try {
        const response = await fetch(`${API_URL}/admin/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
        });
        
        const data = await response.json();
        
        if (data.success) {
            adminToken = data.token;
            adminEmail = data.admin.email;
            localStorage.setItem('adminToken', adminToken);
            localStorage.setItem('adminEmail', adminEmail);
            showDashboard();
        } else {
            errorDiv.textContent = 'Invalid credentials';
        }
    } catch (error) {
        errorDiv.textContent = 'Login failed. Please try again.';
    }
}

// Logout
function logout() {
    localStorage.removeItem('adminToken');
    localStorage.removeItem('adminEmail');
    adminToken = null;
    adminEmail = null;
    showLogin();
}

// Load dashboard data
async function loadDashboardData() {
    await loadStats();
    await loadPendingApprovals();
    await loadPendingTransactions();
    await loadMandiPrices();
    await loadKYC();
    await loadUsers();
    await loadTenders();
    await loadAuctions();
}

// Load statistics
async function loadStats() {
    try {
        const response = await fetch(`${API_URL}/admin/dashboard/stats`);
        const data = await response.json();
        
        document.getElementById('statTotalUsers').textContent = data.total_users;
        document.getElementById('statTotalBuyers').textContent = data.total_buyers;
        document.getElementById('statTotalSellers').textContent = data.total_sellers;
        document.getElementById('statActiveTenders').textContent = data.active_tenders;
        document.getElementById('statActiveAuctions').textContent = data.active_auctions;
        document.getElementById('statPendingKYC').textContent = data.pending_kyc;
    } catch (error) {
        console.error('Error loading stats:', error);
    }
}

// Load pending user approvals
async function loadPendingApprovals() {
    try {
        const response = await fetch(`${API_URL}/admin/users/pending`);
        const data = await response.json();
        const container = document.getElementById('approvalsList');
        
        if (data.pending_users.length === 0) {
            container.innerHTML = '<div class="empty-state"><div class="empty-state-icon">✅</div><div class="empty-state-text">No users pending approval</div></div>';
            return;
        }
        
        container.innerHTML = data.pending_users.map(user => `
            <div class="data-card approval-card">
                <div class="data-card-header">
                    <div>
                        <div class="data-card-title">${user.company_name}</div>
                        <div class="data-card-subtitle">${user.phone}</div>
                    </div>
                    <div class="data-card-actions">
                        <button class="btn-sm btn-approve" onclick="approveUser('${user._id}', true)">✓ Approve</button>
                        <button class="btn-sm btn-reject" onclick="approveUser('${user._id}', false)">✗ Reject</button>
                    </div>
                </div>
                <div class="info-grid">
                    <div class="info-item">
                        <div class="info-label">Role</div>
                        <div class="info-value">
                            <span class="role-badge ${user.business_type === 'buyer' ? 'role-buyer' : 'role-seller'}">
                                ${user.business_type.toUpperCase()}
                            </span>
                        </div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Location</div>
                        <div class="info-value">${user.location || 'Not provided'}</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Registered</div>
                        <div class="info-value">${user.created_at ? new Date(user.created_at).toLocaleDateString('en-IN', {day: '2-digit', month: '2-digit', year: 'numeric'}) : 'N/A'}</div>
                    </div>
                </div>
            </div>
        `).join('');
    } catch (error) {
        console.error('Error loading pending approvals:', error);
    }
}

// Approve/Reject user
async function approveUser(userId, approved) {
    const action = approved ? 'approve' : 'reject';
    
    if (!confirm(`Are you sure you want to ${action} this user?`)) return;
    
    try {
        const response = await fetch(`${API_URL}/admin/users/approve?user_id=${userId}&approved=${approved}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        
        const data = await response.json();
        if (data.success) {
            alert(`User ${approved ? 'approved' : 'rejected'} successfully!`);
            loadPendingApprovals();
            loadStats();
        } else {
            alert('Failed: ' + (data.detail || 'Unknown error'));
        }
    } catch (error) {
        alert('Failed to update user status');
    }
}

// Load pending transactions (quality check)
async function loadPendingTransactions() {
    try {
        const response = await fetch(`${API_URL}/admin/transactions/pending`);
        const data = await response.json();
        const container = document.getElementById('transactionsList');
        
        if (data.pending_transactions.length === 0) {
            container.innerHTML = '<div class="empty-state"><div class="empty-state-icon">✅</div><div class="empty-state-text">No pending transactions</div></div>';
            return;
        }
        
        container.innerHTML = data.pending_transactions.map(txn => `
            <div class="data-card transaction-card">
                <div class="data-card-header">
                    <div>
                        <div class="data-card-title">${txn.tender_variety} (${txn.tender_size})</div>
                        <div class="data-card-subtitle">Tender ID: ${txn.tender_id}</div>
                    </div>
                    <div class="data-card-actions">
                        <button class="btn-sm btn-approve" onclick="approveTransaction('${txn.tender_id}', ${txn.bid_index}, true)">✓ Approve</button>
                        <button class="btn-sm btn-reject" onclick="approveTransaction('${txn.tender_id}', ${txn.bid_index}, false)">✗ Reject</button>
                    </div>
                </div>
                <div class="transaction-parties">
                    <div class="party">
                        <span class="party-label">BUYER</span>
                        <span class="party-name">${txn.buyer_name}</span>
                        ${txn.buyer_phone ? `<span class="party-phone">${txn.buyer_phone}</span>` : ''}
                    </div>
                    <div class="party-arrow">→</div>
                    <div class="party">
                        <span class="party-label">SELLER</span>
                        <span class="party-name">${txn.seller_name}</span>
                    </div>
                </div>
                <div class="info-grid">
                    <div class="info-item">
                        <div class="info-label">Quantity</div>
                        <div class="info-value highlight-value">${txn.quantity} MT</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Rate</div>
                        <div class="info-value highlight-value">₹${txn.rate}/kg</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Delivery Location</div>
                        <div class="info-value">${txn.delivery_location}</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Accepted At</div>
                        <div class="info-value">${new Date(txn.accepted_at).toLocaleString()}</div>
                    </div>
                </div>
            </div>
        `).join('');
    } catch (error) {
        console.error('Error loading pending transactions:', error);
    }
}

// Approve/Reject transaction
async function approveTransaction(tenderId, bidIndex, approved) {
    const action = approved ? 'approve' : 'reject';
    const notes = prompt(`Enter any notes for this ${action} (optional):`);
    
    if (!confirm(`Are you sure you want to ${action} this transaction?`)) return;
    
    try {
        const response = await fetch(`${API_URL}/admin/transactions/approve?tender_id=${tenderId}&bid_index=${bidIndex}&approved=${approved}&notes=${encodeURIComponent(notes || '')}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        
        const data = await response.json();
        if (data.success) {
            alert(`Transaction ${approved ? 'approved' : 'rejected'} successfully!`);
            loadPendingTransactions();
            loadStats();
        } else {
            alert('Failed: ' + (data.detail || 'Unknown error'));
        }
    } catch (error) {
        alert('Failed to update transaction status');
    }
}

// Load mandi prices
async function loadMandiPrices() {
    try {
        const response = await fetch(`${API_URL}/admin/mandi/all`);
        const data = await response.json();
        const container = document.getElementById('mandiPricesList');
        
        if (data.prices.length === 0) {
            container.innerHTML = '<div class="empty-state"><div class="empty-state-icon">📊</div><div class="empty-state-text">No mandi prices added yet. Add your first price above.</div></div>';
            return;
        }
        
        container.innerHTML = `
            <table class="data-table">
                <thead>
                    <tr>
                        <th>State</th>
                        <th>Mandi</th>
                        <th>Variety</th>
                        <th>Price (₹/kg)</th>
                        <th>Last Updated</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    ${data.prices.map(price => `
                        <tr>
                            <td>${price.state}</td>
                            <td>${price.mandi}</td>
                            <td>${price.variety}</td>
                            <td class="price-cell">₹${price.price}</td>
                            <td>${price.date || 'N/A'}</td>
                            <td>
                                <button class="btn-sm btn-reject" onclick="deleteMandiPrice('${price._id}')">Delete</button>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    } catch (error) {
        console.error('Error loading mandi prices:', error);
    }
}

// Add/Update mandi price
async function addMandiPrice() {
    const state = document.getElementById('mandiState').value;
    const mandi = document.getElementById('mandiName').value;
    const variety = document.getElementById('mandiVariety').value;
    const price = document.getElementById('mandiPrice').value;
    
    if (!state || !mandi || !variety || !price) {
        alert('Please fill all fields');
        return;
    }
    
    try {
        const response = await fetch(`${API_URL}/admin/mandi/update?state=${encodeURIComponent(state)}&mandi=${encodeURIComponent(mandi)}&variety=${encodeURIComponent(variety)}&price=${price}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        
        const data = await response.json();
        if (data.success) {
            alert(data.message);
            // Clear form
            document.getElementById('mandiState').value = '';
            document.getElementById('mandiName').value = '';
            document.getElementById('mandiVariety').value = '';
            document.getElementById('mandiPrice').value = '';
            loadMandiPrices();
        } else {
            alert('Failed: ' + (data.detail || 'Unknown error'));
        }
    } catch (error) {
        alert('Failed to add mandi price');
    }
}

// Delete mandi price
async function deleteMandiPrice(priceId) {
    if (!confirm('Are you sure you want to delete this price entry?')) return;
    
    try {
        const response = await fetch(`${API_URL}/admin/mandi/${priceId}`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        if (data.success) {
            alert('Price entry deleted');
            loadMandiPrices();
        } else {
            alert('Failed: ' + (data.detail || 'Unknown error'));
        }
    } catch (error) {
        alert('Failed to delete price entry');
    }
}

// Load KYC queue
async function loadKYC() {
    try {
        const response = await fetch(`${API_URL}/admin/kyc/pending`);
        const data = await response.json();
        const container = document.getElementById('kycList');
        
        if (data.pending_kyc.length === 0) {
            container.innerHTML = '<div class="empty-state"><div class="empty-state-icon">✅</div><div class="empty-state-text">No pending KYC approvals</div></div>';
            return;
        }
        
        container.innerHTML = data.pending_kyc.map(item => `
            <div class="data-card">
                <div class="data-card-header">
                    <div>
                        <div class="data-card-title">${item.user.company_name}</div>
                        <div class="data-card-subtitle">${item.user.phone} • ${item.user.business_type.toUpperCase()}</div>
                    </div>
                    <div class="data-card-actions">
                        <button class="btn-sm btn-approve" onclick="approveKYC('${item.user._id}', 'approved')">✓ Approve</button>
                        <button class="btn-sm btn-reject" onclick="approveKYC('${item.user._id}', 'rejected')">✗ Reject</button>
                    </div>
                </div>
                <div class="info-grid">
                    <div class="info-item">
                        <div class="info-label">Location</div>
                        <div class="info-value">${item.user.location}</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Status</div>
                        <div class="info-value"><span class="badge badge-warning">${item.user.kyc_status.toUpperCase()}</span></div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Registered</div>
                        <div class="info-value">${new Date(item.user.created_at).toLocaleDateString()}</div>
                    </div>
                </div>
            </div>
        `).join('');
    } catch (error) {
        console.error('Error loading KYC:', error);
    }
}

// Approve/Reject KYC
async function approveKYC(userId, status) {
    if (!confirm(`Are you sure you want to ${status} this KYC?`)) return;
    
    try {
        const response = await fetch(`${API_URL}/admin/kyc/approve`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: userId, status })
        });
        
        const data = await response.json();
        if (data.success) {
            alert(`KYC ${status} successfully!`);
            loadKYC();
            loadStats();
        }
    } catch (error) {
        alert('Failed to update KYC status');
    }
}

// Load users
async function loadUsers() {
    try {
        const response = await fetch(`${API_URL}/admin/users`);
        const data = await response.json();
        const container = document.getElementById('usersList');
        
        container.innerHTML = data.users.map(user => `
            <div class="data-card">
                <div class="data-card-header">
                    <div>
                        <div class="data-card-title">${user.company_name}</div>
                        <div class="data-card-subtitle">${user.phone} • ${user.business_type.toUpperCase()}</div>
                    </div>
                    <div class="data-card-actions">
                        ${user.suspended ? 
                            `<button class="btn-sm btn-approve" onclick="suspendUser('${user._id}', false)">Activate</button>` : 
                            `<button class="btn-sm btn-suspend" onclick="suspendUser('${user._id}', true)">Suspend</button>`
                        }
                    </div>
                </div>
                <div class="info-grid">
                    <div class="info-item">
                        <div class="info-label">Location</div>
                        <div class="info-value">${user.location}</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">KYC Status</div>
                        <div class="info-value"><span class="badge ${user.kyc_status === 'approved' ? 'badge-success' : 'badge-warning'}">${user.kyc_status.toUpperCase()}</span></div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Status</div>
                        <div class="info-value"><span class="badge ${user.suspended ? 'badge-error' : 'badge-success'}">${user.suspended ? 'SUSPENDED' : 'ACTIVE'}</span></div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Total Trades</div>
                        <div class="info-value">${user.total_trades || 0}</div>
                    </div>
                </div>
            </div>
        `).join('');
    } catch (error) {
        console.error('Error loading users:', error);
    }
}

// Suspend/Activate user
async function suspendUser(userId, suspended) {
    const action = suspended ? 'suspend' : 'activate';
    if (!confirm(`Are you sure you want to ${action} this user?`)) return;
    
    try {
        const response = await fetch(`${API_URL}/admin/users/suspend`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: userId, suspended, reason: `Admin ${action}d` })
        });
        
        const data = await response.json();
        if (data.success) {
            alert(`User ${action}d successfully!`);
            loadUsers();
        }
    } catch (error) {
        alert(`Failed to ${action} user`);
    }
}

// Load tenders
async function loadTenders() {
    try {
        const response = await fetch(`${API_URL}/admin/tenders/all`);
        const data = await response.json();
        const container = document.getElementById('tendersList');
        
        if (data.tenders.length === 0) {
            container.innerHTML = '<div class="empty-state"><div class="empty-state-icon">📋</div><div class="empty-state-text">No tenders yet</div></div>';
            return;
        }
        
        container.innerHTML = data.tenders.map(tender => `
            <div class="data-card">
                <div class="data-card-header">
                    <div>
                        <div class="data-card-title">${tender.variety} (${tender.size})</div>
                        <div class="data-card-subtitle">By ${tender.buyer_name}</div>
                    </div>
                    <span class="badge ${tender.status === 'active' ? 'badge-success' : 'badge-info'}">${tender.status.toUpperCase()}</span>
                </div>
                <div class="info-grid">
                    <div class="info-item">
                        <div class="info-label">Quantity</div>
                        <div class="info-value">${tender.quantity_mt} MT</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Location</div>
                        <div class="info-value">${tender.delivery_location}</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Bids</div>
                        <div class="info-value">${tender.bids?.length || 0} bids</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Ends At</div>
                        <div class="info-value">${new Date(tender.ends_at).toLocaleString()}</div>
                    </div>
                </div>
            </div>
        `).join('');
    } catch (error) {
        console.error('Error loading tenders:', error);
    }
}

// Load auctions
async function loadAuctions() {
    try {
        const response = await fetch(`${API_URL}/admin/auctions/all`);
        const data = await response.json();
        const container = document.getElementById('auctionsList');
        
        if (data.auctions.length === 0) {
            container.innerHTML = '<div class="empty-state"><div class="empty-state-icon">🔨</div><div class="empty-state-text">No auctions yet</div></div>';
            return;
        }
        
        container.innerHTML = data.auctions.map(auction => `
            <div class="data-card">
                <div class="data-card-header">
                    <div>
                        <div class="data-card-title">${auction.variety} (${auction.size})</div>
                        <div class="data-card-subtitle">By ${auction.seller_name}</div>
                    </div>
                    <span class="badge ${auction.status === 'active' ? 'badge-success' : 'badge-info'}">${auction.status.toUpperCase()}</span>
                </div>
                <div class="info-grid">
                    <div class="info-item">
                        <div class="info-label">Quantity</div>
                        <div class="info-value">${auction.quantity_mt} MT</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Base Price</div>
                        <div class="info-value">₹${auction.base_price}/quintal</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Bids</div>
                        <div class="info-value">${auction.bids?.length || 0} bids</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Ends At</div>
                        <div class="info-value">${new Date(auction.ends_at).toLocaleString()}</div>
                    </div>
                </div>
            </div>
        `).join('');
    } catch (error) {
        console.error('Error loading auctions:', error);
    }
}

// Tab navigation
function showTab(tabName) {
    // Remove active class from all tabs and content
    document.querySelectorAll('.nav-tab').forEach(tab => tab.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
    
    // Add active class to selected tab and content
    event.target.classList.add('active');
    document.getElementById(`${tabName}Tab`).classList.add('active');
}
