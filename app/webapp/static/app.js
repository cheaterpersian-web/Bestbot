// Telegram Web App initialization
let tg = window.Telegram.WebApp;
let user = null;
let services = [];
let servers = [];
let categories = [];
let plans = [];

// Initialize the app
document.addEventListener('DOMContentLoaded', function() {
    tg.ready();
    tg.expand();
    
    // Set theme colors
    document.body.style.backgroundColor = tg.themeParams.bg_color || '#ffffff';
    document.body.style.color = tg.themeParams.text_color || '#000000';
    
    // Get user data
    user = tg.initDataUnsafe.user;
    if (user) {
        loadUserData();
        loadUserServices();
        loadServers();
    } else {
        showError('خطا در دریافت اطلاعات کاربر');
    }
    
    // Setup event listeners
    setupEventListeners();
});

function setupEventListeners() {
    // Server selection
    document.getElementById('server-select').addEventListener('change', function() {
        const serverId = this.value;
        if (serverId) {
            loadCategories(serverId);
        }
    });
    
    // Category selection
    document.getElementById('category-select').addEventListener('change', function() {
        const categoryId = this.value;
        if (categoryId) {
            loadPlans(categoryId);
        }
    });
    
    // Plan selection
    document.getElementById('plan-select').addEventListener('change', function() {
        const planId = this.value;
        if (planId) {
            showPlanDetails(planId);
        }
    });
}

function loadUserData() {
    if (!user) return;
    
    document.getElementById('user-name').textContent = `${user.first_name} ${user.last_name || ''}`.trim();
    document.getElementById('user-username').textContent = user.username ? `@${user.username}` : 'ندارد';
    document.getElementById('user-id').textContent = user.id;
    document.getElementById('user-join-date').textContent = new Date(user.id * 1000).toLocaleDateString('fa-IR');
    
    // Profile tab
    document.getElementById('profile-name').value = `${user.first_name} ${user.last_name || ''}`.trim();
    document.getElementById('profile-username').value = user.username ? `@${user.username}` : 'ندارد';
    document.getElementById('profile-id').value = user.id;
    document.getElementById('profile-join-date').value = new Date(user.id * 1000).toLocaleDateString('fa-IR');
    
    // Load user stats
    loadUserStats();
}

async function loadUserStats() {
    try {
        const response = await fetch('/api/user/stats', {
            headers: {
                'Authorization': `Bearer ${tg.initData}`
            }
        });
        
        if (response.ok) {
            const stats = await response.json();
            document.getElementById('wallet-balance').textContent = `${stats.wallet_balance.toLocaleString('fa-IR')} تومان`;
            document.getElementById('wallet-balance-tab').textContent = `${stats.wallet_balance.toLocaleString('fa-IR')} تومان`;
            document.getElementById('active-services').textContent = stats.active_services;
            document.getElementById('total-purchases').textContent = stats.total_purchases;
            document.getElementById('total-spent').textContent = `${stats.total_spent.toLocaleString('fa-IR')} تومان`;
        }
    } catch (error) {
        console.error('Error loading user stats:', error);
    }
}

async function loadUserServices() {
    try {
        const response = await fetch('/api/user/services', {
            headers: {
                'Authorization': `Bearer ${tg.initData}`
            }
        });
        
        if (response.ok) {
            services = await response.json();
            displayServices();
        }
    } catch (error) {
        console.error('Error loading services:', error);
        showError('خطا در بارگذاری سرویس‌ها');
    }
}

function displayServices() {
    const servicesList = document.getElementById('services-list');
    servicesList.innerHTML = '';
    
    if (services.length === 0) {
        servicesList.innerHTML = `
            <div class="text-center py-4">
                <i class="fas fa-server fa-3x text-muted mb-3"></i>
                <p class="text-muted">هیچ سرویس فعالی ندارید</p>
                <button class="btn btn-primary" onclick="switchToBuyTab()">
                    <i class="fas fa-shopping-cart"></i> خرید سرویس جدید
                </button>
            </div>
        `;
        return;
    }
    
    services.forEach(service => {
        const serviceCard = document.createElement('div');
        serviceCard.className = 'service-card';
        
        const statusClass = service.is_active ? 'status-active' : 'status-expired';
        const statusText = service.is_active ? 'فعال' : 'منقضی شده';
        
        serviceCard.innerHTML = `
            <div class="row">
                <div class="col-8">
                    <h6><i class="fas fa-server"></i> ${service.remark || 'سرویس VPN'}</h6>
                    <p class="mb-1">
                        <small><i class="fas fa-calendar"></i> انقضا: ${new Date(service.expires_at).toLocaleDateString('fa-IR')}</small>
                    </p>
                    <p class="mb-0">
                        <small><i class="fas fa-database"></i> حجم: ${service.traffic_gb} گیگابایت</small>
                    </p>
                </div>
                <div class="col-4 text-end">
                    <span class="status-badge ${statusClass}">${statusText}</span>
                    <div class="mt-2">
                        <button class="btn btn-light btn-sm" onclick="showServiceDetails(${service.id})">
                            <i class="fas fa-eye"></i>
                        </button>
                    </div>
                </div>
            </div>
        `;
        
        servicesList.appendChild(serviceCard);
    });
}

async function loadServers() {
    try {
        const response = await fetch('/api/servers', {
            headers: {
                'Authorization': `Bearer ${tg.initData}`
            }
        });
        
        if (response.ok) {
            servers = await response.json();
            displayServers();
        }
    } catch (error) {
        console.error('Error loading servers:', error);
    }
}

function displayServers() {
    const serverSelect = document.getElementById('server-select');
    serverSelect.innerHTML = '<option value="">انتخاب سرور</option>';
    
    servers.forEach(server => {
        const option = document.createElement('option');
        option.value = server.id;
        option.textContent = server.name;
        serverSelect.appendChild(option);
    });
}

async function loadCategories(serverId) {
    try {
        const response = await fetch(`/api/servers/${serverId}/categories`, {
            headers: {
                'Authorization': `Bearer ${tg.initData}`
            }
        });
        
        if (response.ok) {
            categories = await response.json();
            displayCategories();
        }
    } catch (error) {
        console.error('Error loading categories:', error);
    }
}

function displayCategories() {
    const categorySelect = document.getElementById('category-select');
    categorySelect.innerHTML = '<option value="">انتخاب دسته‌بندی</option>';
    
    categories.forEach(category => {
        const option = document.createElement('option');
        option.value = category.id;
        option.textContent = category.title;
        categorySelect.appendChild(option);
    });
}

async function loadPlans(categoryId) {
    try {
        const response = await fetch(`/api/categories/${categoryId}/plans`, {
            headers: {
                'Authorization': `Bearer ${tg.initData}`
            }
        });
        
        if (response.ok) {
            plans = await response.json();
            displayPlans();
        }
    } catch (error) {
        console.error('Error loading plans:', error);
    }
}

function displayPlans() {
    const planSelect = document.getElementById('plan-select');
    planSelect.innerHTML = '<option value="">انتخاب پلن</option>';
    
    plans.forEach(plan => {
        const option = document.createElement('option');
        option.value = plan.id;
        option.textContent = `${plan.title} - ${plan.price_irr.toLocaleString('fa-IR')} تومان`;
        planSelect.appendChild(option);
    });
}

function showPlanDetails(planId) {
    const plan = plans.find(p => p.id == planId);
    if (!plan) return;
    
    const planDetails = document.getElementById('plan-details');
    const planInfo = document.getElementById('plan-info');
    const planPrice = document.getElementById('plan-price');
    const buyButton = document.getElementById('buy-button');
    
    planInfo.innerHTML = `
        <strong>مدت:</strong> ${plan.duration_days} روز<br>
        <strong>حجم:</strong> ${plan.traffic_gb} گیگابایت<br>
        <strong>نوع:</strong> ${plan.protocol || 'V2Ray'}
    `;
    
    planPrice.textContent = plan.price_irr.toLocaleString('fa-IR');
    planDetails.style.display = 'block';
    buyButton.disabled = false;
}

async function buyService() {
    const planId = document.getElementById('plan-select').value;
    if (!planId) {
        showError('لطفاً پلن را انتخاب کنید');
        return;
    }
    
    const plan = plans.find(p => p.id == planId);
    if (!plan) return;
    
    // Show confirmation
    const confirmed = confirm(`آیا می‌خواهید پلن "${plan.title}" را به قیمت ${plan.price_irr.toLocaleString('fa-IR')} تومان خریداری کنید؟`);
    
    if (confirmed) {
        try {
            const response = await fetch('/api/purchase', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${tg.initData}`
                },
                body: JSON.stringify({
                    plan_id: planId
                })
            });
            
            if (response.ok) {
                const result = await response.json();
                showSuccess('سرویس با موفقیت خریداری شد!');
                
                // Refresh services
                loadUserServices();
                loadUserStats();
                
                // Switch to services tab
                switchToServicesTab();
            } else {
                const error = await response.json();
                showError(error.message || 'خطا در خرید سرویس');
            }
        } catch (error) {
            console.error('Error purchasing service:', error);
            showError('خطا در خرید سرویس');
        }
    }
}

function showServiceDetails(serviceId) {
    const service = services.find(s => s.id == serviceId);
    if (!service) return;
    
    const modalBody = document.getElementById('service-modal-body');
    modalBody.innerHTML = `
        <div class="row">
            <div class="col-6">
                <strong>شناسه سرویس:</strong><br>
                ${service.id}
            </div>
            <div class="col-6">
                <strong>وضعیت:</strong><br>
                <span class="status-badge ${service.is_active ? 'status-active' : 'status-expired'}">
                    ${service.is_active ? 'فعال' : 'منقضی شده'}
                </span>
            </div>
        </div>
        <hr>
        <div class="row">
            <div class="col-6">
                <strong>تاریخ خرید:</strong><br>
                ${new Date(service.purchased_at).toLocaleDateString('fa-IR')}
            </div>
            <div class="col-6">
                <strong>تاریخ انقضا:</strong><br>
                ${new Date(service.expires_at).toLocaleDateString('fa-IR')}
            </div>
        </div>
        <hr>
        <div class="row">
            <div class="col-6">
                <strong>حجم کل:</strong><br>
                ${service.traffic_gb} گیگابایت
            </div>
            <div class="col-6">
                <strong>حجم مصرفی:</strong><br>
                ${service.used_traffic_gb || 0} گیگابایت
            </div>
        </div>
        <hr>
        <div class="config-link">
            <strong>لینک کانفیگ:</strong><br>
            <code>${service.config_link || 'در حال تولید...'}</code>
        </div>
        ${service.qr_code ? `
        <div class="qr-code">
            <strong>QR Code:</strong><br>
            <img src="${service.qr_code}" alt="QR Code">
        </div>
        ` : ''}
    `;
    
    const modal = new bootstrap.Modal(document.getElementById('serviceModal'));
    modal.show();
}

function showTopUp() {
    const modal = new bootstrap.Modal(document.getElementById('topUpModal'));
    modal.show();
}

async function processTopUp() {
    const amount = document.getElementById('topup-amount').value;
    const paymentMethod = document.getElementById('payment-method').value;
    
    if (!amount || amount < 10000) {
        showError('مبلغ باید حداقل 10,000 تومان باشد');
        return;
    }
    
    try {
        const response = await fetch('/api/wallet/topup', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${tg.initData}`
            },
            body: JSON.stringify({
                amount: parseInt(amount),
                payment_method: paymentMethod
            })
        });
        
        if (response.ok) {
            const result = await response.json();
            showSuccess('درخواست شارژ ثبت شد. منتظر تایید باشید.');
            
            // Close modal
            const modal = bootstrap.Modal.getInstance(document.getElementById('topUpModal'));
            modal.hide();
            
            // Refresh wallet balance
            loadUserStats();
        } else {
            const error = await response.json();
            showError(error.message || 'خطا در ثبت درخواست شارژ');
        }
    } catch (error) {
        console.error('Error processing top-up:', error);
        showError('خطا در ثبت درخواست شارژ');
    }
}

function showReferral() {
    const referralLink = `https://t.me/${tg.initDataUnsafe.user.username || 'bot'}_bot?start=ref_${user.id}`;
    
    tg.showAlert(`لینک دعوت شما:\n\n${referralLink}\n\nبا هر دعوت موفق، پاداش دریافت خواهید کرد!`);
}

function showSupport() {
    tg.openTelegramLink('https://t.me/support_username');
}

function refreshServices() {
    loadUserServices();
    showSuccess('سرویس‌ها بروزرسانی شدند');
}

function switchToBuyTab() {
    const buyTab = document.getElementById('buy-tab');
    buyTab.click();
}

function switchToServicesTab() {
    const servicesTab = document.getElementById('services-tab');
    servicesTab.click();
}

function showError(message) {
    tg.showAlert(message);
}

function showSuccess(message) {
    tg.showAlert(message);
}

// Hide loading and show app
setTimeout(() => {
    document.getElementById('loading').style.display = 'none';
    document.getElementById('app').style.display = 'block';
}, 1000);