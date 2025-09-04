"""
API Documentation for VPN Telegram Bot

This module provides comprehensive API documentation and examples for the VPN bot system.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class APIResponse(BaseModel):
    """Standard API response format"""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    error_code: Optional[str] = None


class UserInfo(BaseModel):
    """User information model"""
    id: int
    telegram_user_id: int
    username: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    wallet_balance: float
    total_spent: float
    total_services: int
    is_verified: bool
    created_at: datetime
    last_seen_at: Optional[datetime]


class ServiceInfo(BaseModel):
    """Service information model"""
    id: int
    user_id: int
    server_name: str
    plan_title: str
    remark: str
    uuid: str
    subscription_url: str
    is_active: bool
    is_test: bool
    expires_at: Optional[datetime]
    traffic_used_gb: float
    traffic_limit_gb: Optional[float]
    purchased_at: datetime


class TransactionInfo(BaseModel):
    """Transaction information model"""
    id: int
    user_id: int
    amount: float
    currency: str
    type: str
    status: str
    description: Optional[str]
    payment_gateway: str
    created_at: datetime
    approved_at: Optional[datetime]


class ServerInfo(BaseModel):
    """Server information model"""
    id: int
    name: str
    panel_type: str
    is_active: bool
    current_connections: int
    max_connections: Optional[int]
    sync_status: str
    last_sync_at: Optional[datetime]


class PlanInfo(BaseModel):
    """Plan information model"""
    id: int
    title: str
    price_irr: float
    duration_days: Optional[int]
    traffic_gb: Optional[int]
    is_active: bool
    is_popular: bool
    is_recommended: bool
    sales_count: int


# API Endpoints Documentation
API_DOCUMENTATION = {
    "title": "VPN Telegram Bot API",
    "version": "1.0.0",
    "description": "Comprehensive API for VPN service management",
    "base_url": "https://your-domain.com/api/v1",
    "authentication": {
        "type": "Bearer Token",
        "header": "Authorization: Bearer <token>",
        "description": "Admin API tokens are required for most endpoints"
    },
    "endpoints": {
        "users": {
            "GET /users": {
                "description": "Get list of all users",
                "parameters": {
                    "page": "Page number (default: 1)",
                    "limit": "Items per page (default: 50, max: 100)",
                    "search": "Search by username or telegram_id",
                    "is_blocked": "Filter by blocked status (true/false)",
                    "is_verified": "Filter by verification status (true/false)"
                },
                "response": {
                    "success": True,
                    "data": {
                        "users": [UserInfo],
                        "total": 100,
                        "page": 1,
                        "pages": 2
                    }
                }
            },
            "GET /users/{user_id}": {
                "description": "Get specific user information",
                "response": {
                    "success": True,
                    "data": UserInfo
                }
            },
            "PUT /users/{user_id}": {
                "description": "Update user information",
                "body": {
                    "wallet_balance": "New wallet balance",
                    "is_blocked": "Block/unblock user",
                    "notes": "Admin notes about user"
                },
                "response": {
                    "success": True,
                    "message": "User updated successfully"
                }
            },
            "POST /users/{user_id}/block": {
                "description": "Block a user",
                "body": {
                    "reason": "Reason for blocking"
                },
                "response": {
                    "success": True,
                    "message": "User blocked successfully"
                }
            }
        },
        "services": {
            "GET /services": {
                "description": "Get list of all services",
                "parameters": {
                    "user_id": "Filter by user ID",
                    "server_id": "Filter by server ID",
                    "is_active": "Filter by active status",
                    "is_test": "Filter by test services"
                },
                "response": {
                    "success": True,
                    "data": {
                        "services": [ServiceInfo],
                        "total": 50
                    }
                }
            },
            "GET /services/{service_id}": {
                "description": "Get specific service information",
                "response": {
                    "success": True,
                    "data": ServiceInfo
                }
            },
            "POST /services": {
                "description": "Create a new service",
                "body": {
                    "user_id": "User ID",
                    "server_id": "Server ID",
                    "plan_id": "Plan ID",
                    "remark": "Service remark",
                    "duration_days": "Service duration",
                    "traffic_gb": "Traffic limit"
                },
                "response": {
                    "success": True,
                    "data": ServiceInfo
                }
            },
            "PUT /services/{service_id}": {
                "description": "Update service",
                "body": {
                    "is_active": "Active status",
                    "traffic_limit_gb": "New traffic limit",
                    "expires_at": "New expiration date"
                },
                "response": {
                    "success": True,
                    "message": "Service updated successfully"
                }
            },
            "DELETE /services/{service_id}": {
                "description": "Delete a service",
                "response": {
                    "success": True,
                    "message": "Service deleted successfully"
                }
            }
        },
        "transactions": {
            "GET /transactions": {
                "description": "Get list of transactions",
                "parameters": {
                    "user_id": "Filter by user ID",
                    "status": "Filter by status (pending/approved/rejected)",
                    "type": "Filter by type (wallet_topup/purchase/refund)",
                    "payment_gateway": "Filter by payment gateway"
                },
                "response": {
                    "success": True,
                    "data": {
                        "transactions": [TransactionInfo],
                        "total": 200
                    }
                }
            },
            "GET /transactions/{transaction_id}": {
                "description": "Get specific transaction",
                "response": {
                    "success": True,
                    "data": TransactionInfo
                }
            },
            "POST /transactions/{transaction_id}/approve": {
                "description": "Approve a transaction",
                "response": {
                    "success": True,
                    "message": "Transaction approved successfully"
                }
            },
            "POST /transactions/{transaction_id}/reject": {
                "description": "Reject a transaction",
                "body": {
                    "reason": "Rejection reason"
                },
                "response": {
                    "success": True,
                    "message": "Transaction rejected successfully"
                }
            }
        },
        "servers": {
            "GET /servers": {
                "description": "Get list of servers",
                "response": {
                    "success": True,
                    "data": [ServerInfo]
                }
            },
            "POST /servers": {
                "description": "Add new server",
                "body": {
                    "name": "Server name",
                    "api_base_url": "API base URL",
                    "api_key": "API key",
                    "panel_type": "Panel type (xui/3xui/hiddify)",
                    "auth_mode": "Authentication mode"
                },
                "response": {
                    "success": True,
                    "data": ServerInfo
                }
            },
            "PUT /servers/{server_id}": {
                "description": "Update server",
                "body": {
                    "name": "New name",
                    "is_active": "Active status",
                    "api_key": "New API key"
                },
                "response": {
                    "success": True,
                    "message": "Server updated successfully"
                }
            },
            "POST /servers/{server_id}/sync": {
                "description": "Sync server data",
                "response": {
                    "success": True,
                    "message": "Server sync initiated"
                }
            }
        },
        "plans": {
            "GET /plans": {
                "description": "Get list of plans",
                "parameters": {
                    "category_id": "Filter by category",
                    "server_id": "Filter by server",
                    "is_active": "Filter by active status"
                },
                "response": {
                    "success": True,
                    "data": [PlanInfo]
                }
            },
            "POST /plans": {
                "description": "Create new plan",
                "body": {
                    "category_id": "Category ID",
                    "server_id": "Server ID",
                    "title": "Plan title",
                    "price_irr": "Price in IRR",
                    "duration_days": "Duration in days",
                    "traffic_gb": "Traffic limit in GB"
                },
                "response": {
                    "success": True,
                    "data": PlanInfo
                }
            }
        },
        "analytics": {
            "GET /analytics/dashboard": {
                "description": "Get dashboard analytics",
                "response": {
                    "success": True,
                    "data": {
                        "total_users": 1000,
                        "active_services": 500,
                        "total_revenue": 50000000,
                        "daily_signups": 10,
                        "daily_revenue": 1000000
                    }
                }
            },
            "GET /analytics/revenue": {
                "description": "Get revenue analytics",
                "parameters": {
                    "period": "Time period (daily/weekly/monthly)",
                    "start_date": "Start date (YYYY-MM-DD)",
                    "end_date": "End date (YYYY-MM-DD)"
                },
                "response": {
                    "success": True,
                    "data": {
                        "period": "daily",
                        "revenue_data": [
                            {"date": "2024-01-01", "amount": 1000000},
                            {"date": "2024-01-02", "amount": 1500000}
                        ]
                    }
                }
            }
        },
        "webhooks": {
            "POST /webhooks/zarinpal": {
                "description": "Zarinpal payment webhook",
                "body": {
                    "authority": "Payment authority",
                    "status": "Payment status",
                    "amount": "Payment amount"
                },
                "response": {
                    "success": True,
                    "message": "Webhook processed"
                }
            },
            "POST /webhooks/panel": {
                "description": "Panel service webhook",
                "body": {
                    "service_id": "Service ID",
                    "event": "Event type",
                    "data": "Event data"
                },
                "response": {
                    "success": True,
                    "message": "Webhook processed"
                }
            }
        }
    },
    "error_codes": {
        "AUTH_REQUIRED": "Authentication required",
        "AUTH_INVALID": "Invalid authentication token",
        "PERMISSION_DENIED": "Insufficient permissions",
        "USER_NOT_FOUND": "User not found",
        "SERVICE_NOT_FOUND": "Service not found",
        "SERVER_NOT_FOUND": "Server not found",
        "PLAN_NOT_FOUND": "Plan not found",
        "TRANSACTION_NOT_FOUND": "Transaction not found",
        "INVALID_PARAMETERS": "Invalid request parameters",
        "SERVER_ERROR": "Internal server error",
        "RATE_LIMITED": "Rate limit exceeded",
        "SERVICE_UNAVAILABLE": "Service temporarily unavailable"
    },
    "rate_limits": {
        "default": "100 requests per minute",
        "admin": "500 requests per minute",
        "webhook": "1000 requests per minute"
    }
}


def get_api_documentation() -> Dict[str, Any]:
    """Get complete API documentation"""
    return API_DOCUMENTATION


def get_endpoint_documentation(endpoint: str) -> Optional[Dict[str, Any]]:
    """Get documentation for specific endpoint"""
    endpoints = API_DOCUMENTATION["endpoints"]
    
    for category, category_endpoints in endpoints.items():
        if endpoint in category_endpoints:
            return category_endpoints[endpoint]
    
    return None


def generate_openapi_spec() -> Dict[str, Any]:
    """Generate OpenAPI 3.0 specification"""
    return {
        "openapi": "3.0.0",
        "info": {
            "title": API_DOCUMENTATION["title"],
            "version": API_DOCUMENTATION["version"],
            "description": API_DOCUMENTATION["description"]
        },
        "servers": [
            {
                "url": API_DOCUMENTATION["base_url"],
                "description": "Production server"
            }
        ],
        "security": [
            {
                "bearerAuth": []
            }
        ],
        "components": {
            "securitySchemes": {
                "bearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "JWT"
                }
            },
            "schemas": {
                "UserInfo": UserInfo.model_json_schema(),
                "ServiceInfo": ServiceInfo.model_json_schema(),
                "TransactionInfo": TransactionInfo.model_json_schema(),
                "ServerInfo": ServerInfo.model_json_schema(),
                "PlanInfo": PlanInfo.model_json_schema(),
                "APIResponse": APIResponse.model_json_schema()
            }
        }
    }