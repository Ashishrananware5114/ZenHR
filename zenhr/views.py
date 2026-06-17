import json
import os
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User
from django.utils import timezone
from django.http import JsonResponse
from django.db.models import Sum, Avg, Count, Q
import json
from datetime import datetime, timedelta

from .models import EmployeeProfile, Attendance, LeaveRequest, PayrollPeriod, Payslip

# Gemini API setup (requires GEMINI_API_KEY)
from google import genai
import os

def check_is_manager(user):
    return user.is_staff or user.groups.filter(name='Managers').exists()

@login_required
def dashboard_view(request):
    is_manager = check_is_manager(request.user)
    profile = getattr(request.user, 'profile', None)
    
    if not profile:
        # Auto-create profile if missing for simplicity
        profile = EmployeeProfile.objects.create(
            user=request.user,
            employee_id=f"EMP-{request.user.id:04d}",
            department="Operations",
            designation="Team Member",
            basic_salary=35000.00,
housing_allowance=5000.00,
transport_allowance=2500.00
        )

    context = {
        'is_manager': is_manager,
        'profile': profile,
    }

    if is_manager:
        # HR/Management Dashboard
        context.update({
            'total_employees': EmployeeProfile.objects.count(),
            'active_employees': EmployeeProfile.objects.filter(status='ACTIVE').count(),
            'pending_leaves': LeaveRequest.objects.filter(status='PENDING').count(),
            'today_presents': Attendance.objects.filter(date=timezone.now().date(), status='PRESENT').count(),
            'today_lates': Attendance.objects.filter(date=timezone.now().date(), status='LATE').count(),
            'dept_breakdown': list(EmployeeProfile.objects.values('department').annotate(count=Count('id'))),
            'leave_requests': LeaveRequest.objects.filter(status='PENDING').order_by('-submission_date')[:5],
            'recent_puns': Attendance.objects.order_by('-date')[:5],
        })
    else:
        # ESS Self-Service Dashboard
        today_attn = Attendance.objects.filter(employee=profile, date=timezone.now().date()).first()
        my_leaves = LeaveRequest.objects.filter(employee=profile).order_by('-submission_date')[:5]
        latest_payslip = Payslip.objects.filter(employee=profile, released=True).order_by('-payroll_period__year', '-payroll_period__month').first()
        
        # Calculate working days this month
        start_month = timezone.now().date().replace(day=1)
        present_count = Attendance.objects.filter(employee=profile, date__gte=start_month, status__in=['PRESENT', 'LATE']).count()
        absent_count = Attendance.objects.filter(employee=profile, date__gte=start_month, status='ABSENT').count()
        
        context.update({
            'today_attn': today_attn,
            'my_leaves': my_leaves,
            'latest_payslip': latest_payslip,
            'presence_percentage': int((present_count / 30) * 100) if present_count else 0,
            'stat_presents': present_count,
            'stat_absents': absent_count,
        })
        
    return render(request, 'zenhr/dashboard.html', context)


# --- EMPLOYEE MANAGEMENT ---
@login_required
def employee_list_view(request):
    is_manager = check_is_manager(request.user)
    if not is_manager:
        return redirect('ess_portal')
        
    query = request.GET.get('q', '')
    department = request.GET.get('department', '')
    
    employees = EmployeeProfile.objects.all()
    if query:
        employees = employees.filter(
    Q(user__first_name__icontains=query) |
    Q(user__last_name__icontains=query) |
    Q(employee_id__icontains=query)
)
    if department:
        employees = employees.filter(department=department)
        
    departments = EmployeeProfile.objects.values_list('department', flat=True).distinct()
    
    context = {
        'employees': employees,
        'departments': departments,
        'query': query,
        'selected_dept': department,
    }
    return render(request, 'zenhr/employees.html', context)


@login_required
@staff_member_required
def create_employee_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        email = request.POST['email']
        first_name = request.POST['first_name']
        last_name = request.POST['last_name']

        last_emp = EmployeeProfile.objects.count() + 1
        emp_id = f"EMP-{last_emp:04d}"

        dept = request.POST['department']
        desg = request.POST['designation']

        basic = float(request.POST['basic_salary'] or 0)
        house = float(request.POST['housing_allowance'] or 0)
        transport = float(request.POST['transport_allowance'] or 0)

        password = request.POST.get('password', 'ZenHRDefault99@')

        if User.objects.filter(username=username).exists():
            return render(request, 'zenhr/employee_form.html', {
                'error': 'Username already exists'
            })

        user = User.objects.create_user(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            password=password
        )

        EmployeeProfile.objects.create(
            user=user,
            employee_id=emp_id,
            department=dept,
            designation=desg,
            basic_salary=basic,
            housing_allowance=house,
            transport_allowance=transport,
            status='ACTIVE'
        )
        messages.success(request, f"✅ Employee '{first_name}' has been successfully onboarded into ZenHR.")
        return redirect('employees')

    return render(request, 'zenhr/employee_form.html')


# --- ATTENDANCE ---
@login_required
def attendance_view(request):
    profile = request.user.profile
    today = timezone.now().date()
    attendance_record = Attendance.objects.filter(employee=profile, date=today).first()
    
    if request.method == 'POST':
        action = request.POST.get('action')
        lat = float(request.POST.get('latitude') or 0.0)
        lon = float(request.POST.get('longitude') or 0.0)
        
        if action == 'punch_in':
            if not attendance_record:
                # Calculate status (e.g., late if after 09:15 AM)
                now_time = timezone.now().time()
                status = 'PRESENT'
                if now_time > datetime.strptime('09:15:00', '%H:%M:%S').time():
                    status = 'LATE'
                    
                Attendance.objects.create(
                    employee=profile,
                    date=today,
                    clock_in=timezone.now(),
                    latitude_in=lat,
                    longitude_in=lon,
                    status=status
                )
        elif action == 'punch_out':
            if attendance_record and not attendance_record.clock_out:
                attendance_record.clock_out = timezone.now()
                attendance_record.latitude_out = lat
                attendance_record.longitude_out = lon
                attendance_record.save()
                
        return redirect('attendance')

    my_records = Attendance.objects.filter(employee=profile).order_by('-date')
    context = {
        'today_record': attendance_record,
        'my_records': my_records,
    }
    return render(request, 'zenhr/attendance.html', context)


# --- LEAVE MANAGEMENT ---
@login_required
def leave_view(request):
    is_manager = check_is_manager(request.user)
    profile = request.user.profile
    
    if request.method == 'POST':
        if 'request_leave' in request.POST:
            # ESS Submission
            LeaveRequest.objects.create(
                employee=profile,
                leave_type=request.POST['leave_type'],
                start_date=request.POST['start_date'],
                end_date=request.POST['end_date'],
                reason=request.POST['reason'],
                status='PENDING'
            )
        elif 'approve_leave' in request.POST and is_manager:
            leave_id = request.POST['leave_id']
            leave = get_object_or_404(LeaveRequest, id=leave_id)
            leave.status = 'APPROVED'
            leave.approved_by = request.user
            leave.save()
        elif 'reject_leave' in request.POST and is_manager:
            leave_id = request.POST['leave_id']
            leave = get_object_or_404(LeaveRequest, id=leave_id)
            leave.status = 'REJECTED'
            leave.approved_by = request.user
            leave.rejection_reason = request.POST.get('rejection_reason', '')
            leave.save()
        return redirect('leaves')

    if is_manager:
        leaves = LeaveRequest.objects.all().order_by('-submission_date')
    else:
        leaves = LeaveRequest.objects.filter(employee=profile).order_by('-submission_date')

    context = {
        'leaves': leaves,
        'is_manager': is_manager,
    }
    return render(request, 'zenhr/leaves.html', context)


# --- PAYROLL MODULE ---
@login_required
def payroll_view(request):
    is_manager = check_is_manager(request.user)
    if not is_manager:
        return redirect('ess_portal')
        
    periods = PayrollPeriod.objects.all().order_by('-year', '-month')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'create_period':
            month = int(request.POST['month'])
            year = int(request.POST['year'])
            
            # Start/End Dates
            start_date = datetime(year, month, 1).date()
            if month == 12:
                end_date = datetime(year + 1, 1, 1).date() - timedelta(days=1)
            else:
                end_date = datetime(year, month + 1, 1).date() - timedelta(days=1)
                
            period, created = PayrollPeriod.objects.get_or_create(
    month=month,
    year=year,
    defaults={
        'start_date': start_date,
        'end_date': end_date,
        'status': 'OPEN'
    }
)

            if created:
                # Create payslips for all active employees
                for emp in EmployeeProfile.objects.filter(status='ACTIVE'):
                    Payslip.objects.create(
                        employee=emp,
                        payroll_period=period,
                        basic_salary=emp.basic_salary,
                        housing_allowance=emp.housing_allowance,
                        transport_allowance=emp.transport_allowance,
                        social_security=emp.basic_salary * Decimal('0.12'),
                        tax_withheld=Decimal('0.00'),
                        net_salary=Decimal('0.00')
                    )
                   
                    
        elif action == 'release_payroll':
            period_id = request.POST['period_id']
            period = get_object_or_404(PayrollPeriod, id=period_id)
            period.status = 'PAID'
            period.save()
            
            # Set payment date for all associated payslips and release
            Payslip.objects.filter(payroll_period=period).update(released=True, payment_date=timezone.now().date())
            
        return redirect('payroll')

    context = {
        'periods': periods,
    }
    return render(request, 'zenhr/payroll.html', context)


# --- ESS PORTAL ---
# --- ESS PORTAL ---
@login_required
def ess_portal_view(request):
    print("REQUEST METHOD =", request.method)

    profile = request.user.profile
    my_payslips = Payslip.objects.filter(
        employee=profile,
        released=True
    ).order_by('-payroll_period__year', '-payroll_period__month')

    if request.method == 'POST' and 'update_profile' in request.POST:
        print("FORM SUBMITTED")

        profile.phone_number = request.POST['phone_number']
        profile.address = request.POST['address']
        profile.emergency_contact = request.POST['emergency_contact']
        profile.save()

        request.user.first_name = request.POST['first_name']
        request.user.last_name = request.POST['last_name']
        request.user.save()
        messages.success(request, "Profile updated successfully!")
        print("USER SAVED")

        return redirect('ess_portal')

    context = {
        'profile': profile,
        'my_payslips': my_payslips,
    }

    return render(request, 'zenhr/ess.html', context)


# --- PAYROLL AI ASSISTANT ---
@login_required
def ai_assistant_view(request):
    return render(request, 'zenhr/ai_assistant.html')


@login_required
def ai_query_api_view(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=400)
        
    try:
        data = json.loads(request.body)
        query = data.get('query', '')
    except Exception:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
        
    if not query:
        return JsonResponse({'error': 'Query empty'}, status=400)
    
    api_key = os.environ.get('GEMINI_API_KEY', 'AQ.Ab8RN6I8XxfZfXkeWfZDBOnlI76N5DMiaA-wcoXUkgFK_T3tzA')
        
    # Build database context to ground the Gemini response
    profile_summary = []
    employees = EmployeeProfile.objects.all()
    for e in employees:
        profile_summary.append(
            f"Employee: {e.user.get_full_name() or e.user.username} | Employee ID: {e.employee_id} | "
            f"Dept: {e.department} | Design: {e.designation} | Basic Salary: {e.basic_salary} | "
            f"Total Earnings: {e.total_earnings} | Days on Leave (Approved): {LeaveRequest.objects.filter(employee=e, status='APPROVED').count()}"
        )
    database_context = "\n".join(profile_summary)
    
    system_instruction = f"""
    You are ZenHR's Payroll and Employee Self-Service AI-driven Expert.
    You assist management and employees with payroll, taxes, allowances, salary computation, leaves, and database analytics.
    
    Here is the live corporate directory context (grounding data):
    {database_context}
    
    Be clear, concise, professional, and execute exact numeric calculations (such as tax brackets, base salary projections, housing expenses) when requested.
    """
    
    try:
        client = genai.Client(api_key=api_key, http_options={"headers": {"User-Agent": "aistudio-build"}})
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=query,
            config={
                'systemInstruction': system_instruction
            }
        )
        return JsonResponse({'answer': response.text})
    except Exception as ex:
        return JsonResponse({'error': f"Gemini error: {str(ex)}"}, status=500)
