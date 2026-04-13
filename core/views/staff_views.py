# core/views/staff_views.py

import json
from datetime import timedelta
from django.utils import timezone
from django.db.models import Q, Count
from django.http import JsonResponse, HttpResponseForbidden
from django.template.response import TemplateResponse
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required

from user.models import CustomUser
from shop.models import SaleOrder, Coupon, CouponStatus, OrderTransaction, TransactionStatus
from messaging.models import MessageAuth, MessageBody, Inbox, InboxType, MessageStatus


# ===========================================================================
# SECURITY & HELPERS
# ===========================================================================

def staff_role_required(view_func):
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_staff:
            return HttpResponseForbidden("Unauthorized: Staff access required.")
        
        # FIX: Allow superusers to bypass the strict role check
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        
        role_name = getattr(request.user.role, "role_name", None) if hasattr(request.user, "role") else None
        if role_name != "STAFF":
            return HttpResponseForbidden("Forbidden: Role mismatch. Expected STAFF.")
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def render_partial_or_full(request, template_name, context):
    """
    Helper to return a full template or partial based on AJAX header.
    (Assumes templates are structured to handle 'base_template' context variable 
    or the frontend strips the layout, as per standard Django AJAX patterns).
    """
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        # Signal to the template to extend a blank/empty base if implemented, 
        # or simply rely on the frontend JS innerHTML extraction logic.
        context['is_ajax'] = True 
    return TemplateResponse(request, template_name, context)


def _get_conversations(user, filter_role=None):
    """
    Helper to get unique conversation threads for a user.
    If filter_role is provided, only includes threads where the *other* user has that role.
    Returns a list of dicts: { 'other_user': user_obj, 'latest_preview': str, 'latest_time': datetime, 'unread': bool }
    """
    # Fetch all messages where user is sender or receiver
    messages = MessageAuth.objects.filter(
        Q(sender=user) | Q(receiver=user)
    ).select_related('sender', 'sender__role', 'receiver', 'receiver__role', 'body', 'message_status').order_by('-sent_at')

    conversations = {}
    for msg in messages:
        other_user = msg.receiver if msg.sender == user else msg.sender
        
        # Apply role filter if requested
        if filter_role:
            other_role = getattr(other_user.role, "role_name", "") if hasattr(other_user, "role") else ""
            if isinstance(filter_role, list):
                if other_role not in filter_role: continue
            else:
                if other_role != filter_role: continue

        if other_user.id not in conversations:
            is_unread = (msg.receiver == user and msg.message_status and msg.message_status.status_name != "READ")
            preview = msg.body.text_content[:40] + "…" if hasattr(msg, 'body') and msg.body.text_content else "[Media]"
            
            conversations[other_user.id] = {
                'other_user': other_user,
                'latest_preview': preview,
                'latest_time': msg.sent_at or msg.created_at,
                'unread': is_unread
            }
            
    # Sort by latest message time descending
    sorted_convos = sorted(conversations.values(), key=lambda x: x['latest_time'], reverse=True)
    return sorted_convos


# ===========================================================================
# PAGE VIEWS
# ===========================================================================

@login_required
@staff_role_required
def staff_dashboard_view(request):
    today = timezone.now().date()
    now = timezone.now()
    hour = now.hour
    if hour < 12:
        greeting = "Morning"
    elif hour < 17:
        greeting = "Afternoon"
    else:
        greeting = "Evening"
    
    # 1. Stats
    total_orders_today = SaleOrder.objects.filter(order_date__date=today).count()
    total_orders_all = SaleOrder.objects.count()
    
    # Pending Orders (Orders whose latest transaction is PENDING/INITIATED)
    pending_orders = OrderTransaction.objects.filter(
        status__status_name__in=['PENDING', 'INITIATED']
    ).values('sale_order').distinct().count()
    
    # Open Customer Messages (Unread messages from CUSTOMER role)
    open_customer_messages = MessageAuth.objects.filter(
        receiver=request.user, 
        sender__role__role_name="CUSTOMER"
    ).exclude(message_status__status_name="READ").count()
    
    # Active Coupons
    active_coupons = Coupon.objects.filter(status__status_name="ONGOING").count()
    
    # Recent Orders (Top 5)
    recent_orders = SaleOrder.objects.select_related('session__user').prefetch_related('transactions__status').order_by('-order_date')[:5]
    
    # 2. Chart Data: Orders per day for the last 14 days
    chart_labels = []
    chart_data = []
    for i in range(13, -1, -1):
        target_date = today - timedelta(days=i)
        chart_labels.append(target_date.strftime("%b %d"))
        count = SaleOrder.objects.filter(order_date__date=target_date).count()
        chart_data.append(count)
        
    context = {
        'greeting': greeting,
        'today': now.strftime("%A, %d %B %Y"),
        'total_orders_today': total_orders_today,
        'total_orders_all': total_orders_all,
        'pending_orders': pending_orders,
        'open_customer_messages': open_customer_messages,
        'active_coupons': active_coupons,
        'recent_orders': recent_orders,
        'chart_labels': json.dumps(chart_labels),
        'chart_data': json.dumps(chart_data),
    }
    return render_partial_or_full(request, "admin/staff/dashboard.html", context)


@login_required
@staff_role_required
def staff_messages_view(request):
    # Filter conversations to only include STAFF, SUPERVISOR, ADMIN, INVENTORY_MANAGER
    staff_roles = ["STAFF", "SUPERVISOR", "ADMIN", "INVENTORY_MANAGER"]
    conversations = _get_conversations(request.user, filter_role=staff_roles)
    
    # Provide list of all staff users for the "Compose" modal
    all_staff = CustomUser.objects.filter(is_staff=True, is_active=True).exclude(id=request.user.id)
    staff_users_json = json.dumps([{"id": u.id, "username": u.username} for u in all_staff])
    
    context = {
        'conversations': conversations,
        'staff_users_json': staff_users_json,
    }
    return render_partial_or_full(request, "admin/staff/messages.html", context)


@login_required
@staff_role_required
def staff_user_messages_view(request):
    # Filter conversations to only include CUSTOMER role
    conversations = _get_conversations(request.user, filter_role="CUSTOMER")
    
    context = {
        'conversations': conversations,
    }
    return render_partial_or_full(request, "admin/staff/user_messages.html", context)


@login_required
@staff_role_required
def staff_coupons_view(request):
    coupons = Coupon.objects.select_related('status').all().order_by('-start_date')
    
    count_ongoing = coupons.filter(status__status_name="ONGOING").count()
    count_expired = coupons.filter(status__status_name="EXPIRED").count()
    count_draft = coupons.filter(status__status_name="DRAFT").count()
    
    context = {
        'coupons': coupons,
        'count_ongoing': count_ongoing,
        'count_expired': count_expired,
        'count_draft': count_draft,
        'transaction_statuses': TransactionStatus.objects.all()
    }
    return render_partial_or_full(request, "admin/staff/coupons.html", context)


@login_required
@staff_role_required
def staff_orders_view(request):
    orders = SaleOrder.objects.select_related('session__user', 'coupon').prefetch_related(
        'order_products', 'transactions__status'
    ).order_by('-order_date')
    
    # Annotate latest transaction status for filtering/display logic
    for order in orders:
        latest_tx = order.transactions.order_by('-transaction_date').first()
        order.latest_tx_status = latest_tx.status.status_name if latest_tx and latest_tx.status else "NONE"
        
    transaction_statuses = TransactionStatus.objects.all()
    
    context = {
        'orders': orders,
        'transaction_statuses': transaction_statuses,
    }
    return render_partial_or_full(request, "admin/staff/orders.html", context)


# ===========================================================================
# AJAX API VIEWS
# ===========================================================================

@login_required
@staff_role_required
def staff_send_message(request):
    """POST only. Sends a message via fetch() without page reload."""
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Invalid request method."})
        
    try:
        data = json.loads(request.body)
        receiver_id = data.get('receiver_id')
        text = data.get('text', '').strip()
        
        if not receiver_id or not text:
            return JsonResponse({"success": False, "error": "Missing receiver or text."})
            
        receiver = get_object_or_404(CustomUser, id=receiver_id)
        
        # Determine status
        status_sent, _ = MessageStatus.objects.get_or_create(status_name="SENT")
        
        # Create Auth
        msg_auth = MessageAuth.objects.create(
            sender=request.user,
            receiver=receiver,
            message_status=status_sent,
            sent_at=timezone.now()
        )
        
        # Create Body
        MessageBody.objects.create(
            message_auth=msg_auth,
            text_content=text
        )
        
        # Create Inbox entries
        type_sent, _ = InboxType.objects.get_or_create(type_name="SENT")
        type_received, _ = InboxType.objects.get_or_create(type_name="RECEIVED")
        
        Inbox.objects.create(user=request.user, message_auth=msg_auth, inbox_type=type_sent)
        Inbox.objects.create(user=receiver, message_auth=msg_auth, inbox_type=type_received)
        
        return JsonResponse({"success": True})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


@login_required
@staff_role_required
def staff_thread_view(request):
    """GET only. Returns JSON of a conversation thread."""
    other_user_id = request.GET.get('user_id')
    if not other_user_id:
        return JsonResponse({"success": False, "error": "Missing user_id"})
        
    messages = MessageAuth.objects.filter(
        Q(sender=request.user, receiver_id=other_user_id) |
        Q(sender_id=other_user_id, receiver=request.user)
    ).select_related('body', 'sender').order_by('sent_at')
    
    thread = []
    for msg in messages:
        thread.append({
            "id": msg.id,
            "text": msg.body.text_content if hasattr(msg, 'body') else "",
            "is_mine": msg.sender == request.user,
            "sender": msg.sender.username,
            "time": msg.sent_at.strftime("%H:%M") if msg.sent_at else ""
        })
        
    return JsonResponse({"success": True, "messages": thread})


@login_required
@staff_role_required
def staff_customer_thread_view(request):
    """GET only. Identical logic to staff_thread_view but semantic separation."""
    return staff_thread_view(request)


@login_required
@staff_role_required
def staff_mark_read(request):
    """POST only. Marks all messages from a specific user as READ."""
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Invalid request method."})
        
    try:
        data = json.loads(request.body)
        user_id = data.get('user_id')
        
        if not user_id:
            return JsonResponse({"success": False, "error": "Missing user_id"})
            
        status_read, _ = MessageStatus.objects.get_or_create(status_name="READ")
        
        MessageAuth.objects.filter(
            sender_id=user_id, 
            receiver=request.user
        ).exclude(message_status=status_read).update(message_status=status_read)
        
        return JsonResponse({"success": True})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


@login_required
@staff_role_required
def api_coupon_detail(request, pk):
    """GET only. Returns detailed JSON for a single coupon."""
    coupon = get_object_or_404(Coupon.objects.select_related('status'), pk=pk)
    
    data = {
        "id": coupon.id,
        "coupon_code": coupon.coupon_code,
        "discount_type": coupon.discount_type,
        "discount_value": str(coupon.discount_value),
        "start_date": coupon.start_date.strftime("%d %b %Y"),
        "end_date": coupon.end_date.strftime("%d %b %Y"),
        "status": coupon.status.status_name if coupon.status else "UNKNOWN",
        "description": coupon.description,
    }
    return JsonResponse({"success": True, "coupon": data})

@login_required
@staff_role_required
def api_order_detail(request, pk):
    """GET only. Returns detailed JSON for a single order and its items/transactions."""
    order = get_object_or_404(
        SaleOrder.objects.select_related('session__user', 'coupon')
        .prefetch_related('order_products__product', 'transactions__status', 'transactions__processor'),
        pk=pk
    )
    
    products = []
    for op in order.order_products.all():
        products.append({
            "product_name": op.product.name if op.product else "Deleted Product",
            "quantity": op.quantity,
            "price_at_purchase": str(op.price_at_purchase),
            "subtotal": str(op.subtotal)
        })
        
    transactions = []
    for tx in order.transactions.order_by('-transaction_date'):
        transactions.append({
            "transaction_id": tx.transaction_id,
            "status": tx.status.status_name if tx.status else "UNKNOWN",
            "processor": tx.processor.processor_name if tx.processor else "Unknown Gateway",
            "date": tx.transaction_date.strftime("%d %b %Y, %H:%M")
        })
        
    data = {
        "id": order.id,
        "customer": order.session.user.username if order.session and order.session.user else "Guest",
        "order_date": order.order_date.strftime("%d %b %Y, %H:%M"),
        "total_amount": str(order.total_amount),
        "coupon": order.coupon.coupon_code if order.coupon else None,
        "products": products,
        "transactions": transactions
    }
    
    return JsonResponse({"success": True, "order": data})

# 👇 ADD THIS NEW VIEW AT THE BOTTOM 👇
@login_required
@staff_role_required
def api_coupon_toggle(request, pk):
    """PATCH only. Toggles a coupon between ONGOING and EXPIRED."""
    if request.method != "PATCH":
        return JsonResponse({"success": False, "error": "Invalid method"})
    
    try:
        data = json.loads(request.body)
        new_status_name = data.get("status")
        
        coupon = get_object_or_404(Coupon, pk=pk)
        new_status = get_object_or_404(CouponStatus, status_name=new_status_name)
        
        coupon.status = new_status
        coupon.save()
        return JsonResponse({"success": True})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})