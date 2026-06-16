from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal


class EmployeeProfile(models.Model):
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('INACTIVE', 'Inactive'),
        ('SUSPENDED', 'Suspended'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    employee_id = models.CharField(max_length=50, unique=True, verbose_name="Employee ID")
    department = models.CharField(max_length=100, default='General')
    designation = models.CharField(max_length=100, default='Associate')
    date_of_joining = models.DateField(default=timezone.now)
    basic_salary = models.DecimalField(max_digits=12, decimal_places=2,default=Decimal('0.00'))
    housing_allowance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    transport_allowance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    emergency_contact = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')

    @property
    def total_earnings(self):
        return self.basic_salary + self.housing_allowance + self.transport_allowance

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.employee_id})"


class Attendance(models.Model):
    STATUS_CHOICES = [
        ('PRESENT', 'Present'),
        ('LATE', 'Late'),
        ('ABSENT', 'Absent'),
        ('ON_LEAVE', 'On Leave'),
    ]

    employee = models.ForeignKey(EmployeeProfile, on_delete=models.CASCADE, related_name='attendances')
    date = models.DateField(default=timezone.now)
    clock_in = models.DateTimeField(blank=True, null=True)
    clock_out = models.DateTimeField(blank=True, null=True)
    latitude_in = models.FloatField(blank=True, null=True)
    longitude_in = models.FloatField(blank=True, null=True)
    latitude_out = models.FloatField(blank=True, null=True)
    longitude_out = models.FloatField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PRESENT')
    notes = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        unique_together = ('employee', 'date')

    def __str__(self):
        return f"{self.employee.employee_id} - {self.date} ({self.status})"


class LeaveRequest(models.Model):
    LEAVE_TYPES = [
    ('CL', 'Casual Leave'),
    ('SL', 'Sick Leave'),
    ('EL', 'Earned Leave'),
    ('ML', 'Maternity Leave'),
    ('PL', 'Paternity Leave'),
    ('LWP', 'Leave Without Pay'),
]

    STATUS_CHOICES = [
        ('PENDING', 'Pending Approval'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]

    employee = models.ForeignKey(EmployeeProfile, on_delete=models.CASCADE, related_name='leave_requests')
    leave_type = models.CharField(max_length=20, choices=LEAVE_TYPES, default='ANNUAL')
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    submission_date = models.DateTimeField(auto_now_add=True)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True, related_name='approved_leaves')
    rejection_reason = models.TextField(blank=True, null=True)

    @property
    def duration_days(self):
        delta = self.end_date - self.start_date
        return delta.days + 1

    def __str__(self):
        return f"{self.employee.user.username} - {self.leave_type} ({self.duration_days} days)"


class PayrollPeriod(models.Model):
    STATUS_CHOICES = [
        ('OPEN', 'Open'),
        ('CALCULATING', 'Calculating'),
        ('PROCESSING', 'Processing'),
        ('PAID', 'Paid'),
    ]

    month = models.PositiveIntegerField()
    year = models.PositiveIntegerField()
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='OPEN')

    class Meta:
        unique_together = ('month', 'year')

    def __str__(self):
        months_list = ["", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
        return f"{months_list[self.month]} {self.year} (Status: {self.status})"


class Payslip(models.Model):
    employee = models.ForeignKey(
        EmployeeProfile,
        on_delete=models.CASCADE,
        related_name='payslips'
    )
    payroll_period = models.ForeignKey(
        PayrollPeriod,
        on_delete=models.CASCADE,
        related_name='payslips'
    )

    # Financial breakdown
    basic_salary = models.DecimalField(max_digits=12, decimal_places=2)
    housing_allowance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    transport_allowance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    overtime_pay = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    bonus = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    # Deductions
    social_security = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    tax_withheld = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    loan_deductions = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    other_deductions = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    net_salary = models.DecimalField(max_digits=12, decimal_places=2)
    released = models.BooleanField(default=False)
    payment_date = models.DateField(blank=True, null=True)

    class Meta:
        unique_together = ('employee', 'payroll_period')

    @property
    def gross_salary(self):
        return (
            Decimal(str(self.basic_salary))
            + Decimal(str(self.housing_allowance))
            + Decimal(str(self.transport_allowance))
            + Decimal(str(self.overtime_pay))
            + Decimal(str(self.bonus))
        )

    @property
    def total_deductions(self):
        return (
            Decimal(str(self.social_security))
            + Decimal(str(self.tax_withheld))
            + Decimal(str(self.loan_deductions))
            + Decimal(str(self.other_deductions))
        )

    def save(self, *args, **kwargs):
        self.net_salary = self.gross_salary - self.total_deductions
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Payslip {self.employee.employee_id} - {self.payroll_period}"