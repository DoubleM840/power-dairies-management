from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models import MpesaTransaction


def _status_badge(status):
    colours = {
        'COMPLETED': 'success',
        'PENDING':   'warning',
        'FAILED':    'danger',
        'CANCELLED': 'secondary',
    }
    colour = colours.get(status, 'secondary')
    return format_html(
        '<span class="badge text-bg-{}">{}</span>', colour, status
    )


@admin.register(MpesaTransaction)
class MpesaTransactionAdmin(admin.ModelAdmin):
    # ── List view ──────────────────────────────────────────────────────────
    list_display = (
        'user', 'phone_number', 'amount_display', 'status_badge',
        'mpesa_receipt_number', 'short_checkout_id',
        'date_requested', 'date_completed',
    )
    list_filter  = ('status', 'date_requested')
    search_fields = (
        'phone_number', 'mpesa_receipt_number',
        'checkout_request_id', 'user__username',
    )
    ordering      = ('-date_requested',)
    date_hierarchy = 'date_requested'

    # ── Detail view ────────────────────────────────────────────────────────
    readonly_fields = (
        'user', 'phone_number', 'amount', 'checkout_request_id',
        'mpesa_receipt_number', 'result_code', 'result_desc',
        'date_requested', 'date_completed',
    )
    fieldsets = (
        ('Transaction', {
            'fields': (
                'user', 'phone_number', 'amount',
                'checkout_request_id', 'mpesa_receipt_number',
            ),
        }),
        ('Status', {
            'fields': ('status', 'result_code', 'result_desc'),
        }),
        ('Timestamps', {
            'fields': ('date_requested', 'date_completed'),
            'classes': ('collapse',),
        }),
    )

    # ── Custom columns ─────────────────────────────────────────────────────
    @admin.display(description='Amount (KES)', ordering='amount')
    def amount_display(self, obj):
        return f'KES {obj.amount:,.2f}'

    @admin.display(description='Status')
    def status_badge(self, obj):
        return _status_badge(obj.status)

    @admin.display(description='Checkout ID')
    def short_checkout_id(self, obj):
        cid = obj.checkout_request_id or ''
        return cid[:24] + '…' if len(cid) > 24 else cid

    # ── Admin action: manually fulfil a COMPLETED transaction ─────────────
    actions = ['fulfil_completed']

    @admin.action(description='Fulfil selected COMPLETED transactions (create orders/payment)')
    def fulfil_completed(self, request, queryset):
        from mpesa.views import _fulfil_completed_transaction
        fulfilled = 0
        skipped   = 0
        for txn in queryset:
            if txn.status == 'COMPLETED':
                _fulfil_completed_transaction(txn, receipt_number=txn.mpesa_receipt_number)
                fulfilled += 1
            else:
                skipped += 1
        msg = f'{fulfilled} transaction(s) fulfilled.'
        if skipped:
            msg += f' {skipped} skipped (not COMPLETED).'
        self.message_user(request, msg)

    # ── Admin action: retry pending STK query ─────────────────────────────
    @admin.action(description='Query Safaricom for PENDING transactions')
    def query_pending(self, request, queryset):
        from mpesa.services import MpesaService
        from mpesa.views import _fulfil_completed_transaction
        mpesa    = MpesaService()
        updated  = 0
        still_pending = 0
        for txn in queryset.filter(status='PENDING'):
            data, error = mpesa.query_stk_push_status(txn.checkout_request_id)
            if data and not error:
                code = str(data.get('ResultCode', ''))
                if code == '0':
                    receipt = data.get('MpesaReceiptNumber')
                    txn = mpesa.update_transaction(
                        txn.checkout_request_id,
                        status='COMPLETED',
                        result_code=code,
                        result_desc=data.get('ResultDesc', ''),
                        mpesa_receipt_number=receipt,
                        date_completed=timezone.now(),
                    )
                    _fulfil_completed_transaction(txn, receipt_number=receipt)
                    updated += 1
                elif code not in ('', 'None'):
                    status = 'CANCELLED' if code == '1032' else 'FAILED'
                    mpesa.update_transaction(
                        txn.checkout_request_id,
                        status=status,
                        result_code=code,
                        result_desc=data.get('ResultDesc', ''),
                    )
                    updated += 1
                else:
                    still_pending += 1
        msg = f'{updated} transaction(s) updated.'
        if still_pending:
            msg += f' {still_pending} still pending at Safaricom.'
        self.message_user(request, msg)

    actions = ['fulfil_completed', 'query_pending']
