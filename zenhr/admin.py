from django.contrib import admin
from .models import EmployeeProfile, Attendance, LeaveRequest, PayrollPeriod, Payslip


@admin.register(EmployeeProfile)
class EmployeeProfileAdmin(admin.ModelAdmin):
    list_display = ('employee_id', 'get_full_name', 'department', 'designation', 'status', 'total_earnings')
    list_filter = ('department', 'status')
    search_fields = ('employee_id', 'user__first_name', 'user__last_name', 'user__username', 'department')

    def get_full_name(self, obj):
        return obj.user.get_full_name() or obj.user.username
    get_full_name.short_description = 'Employee Name'


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('employee', 'date', 'clock_in', 'clock_out', 'status')
    list_filter = ('status', 'date')
    search_fields = ('employee__employee_id', 'employee__user__first_name', 'employee__user__last_name')


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ('employee', 'leave_type', 'start_date', 'end_date', 'duration_days', 'status')
    list_filter = ('status', 'leave_type')
    search_fields = ('employee__employee_id', 'employee__user__first_name', 'employee__user__last_name', 'reason')
    actions = ['approve_leaves', 'reject_leaves']

    def approve_leaves(self, request, queryset):
        queryset.update(status='APPROVED', approved_by=request.user)
    approve_leaves.short_description = "Approve selected leave requests"

    def reject_leaves(self, request, queryset):
        queryset.update(status='REJECTED', approved_by=request.user)
    reject_leaves.short_description = "Reject selected leave requests"


class PayslipInline(admin.TabularInline):
    model = Payslip
    extra = 1


@admin.register(PayrollPeriod)
class PayrollPeriodAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'start_date', 'end_date', 'status')
    list_filter = ('status', 'year')
    inlines = [PayslipInline]


@admin.register(Payslip)
class PayslipAdmin(admin.ModelAdmin):
    list_display = ('employee', 'payroll_period', 'gross_salary', 'total_deductions', 'net_salary', 'released', 'payment_date')
    list_filter = ('released', 'payroll_period')
    search_fields = ('employee__employee_id', 'employee__user__first_name', 'employee__user__last_name')
