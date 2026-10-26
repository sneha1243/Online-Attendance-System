from datetime import date
from functools import wraps

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST

from .models import Attendance, Student, Subject, Teacher


def _teacher_for(user):
	try:
		return user.teacher_profile
	except Teacher.DoesNotExist:
		return None


def _student_for(user):
	try:
		return user.student_profile
	except Student.DoesNotExist:
		return None


def _role_required(role):
	def decorator(view):
		@wraps(view)
		@login_required
		def wrapped(request, *args, **kwargs):
			if role == 'teacher' and _teacher_for(request.user):
				return view(request, *args, **kwargs)
			if role == 'student' and _student_for(request.user):
				return view(request, *args, **kwargs)
			if role == 'staff' and request.user.is_staff:
				return view(request, *args, **kwargs)
			raise PermissionDenied

		return wrapped

	return decorator


def _attendance_manager_required(view):
	@wraps(view)
	@login_required
	def wrapped(request, *args, **kwargs):
		if request.user.is_staff or _teacher_for(request.user):
			return view(request, *args, **kwargs)
		raise PermissionDenied

	return wrapped


def _landing_for(user):
	if user.is_staff:
		return redirect('finalproject:dashboard')
	if _teacher_for(user):
		return redirect('finalproject:dashboard')
	if _student_for(user):
		return redirect('finalproject:student_attendance')
	return redirect('finalproject:login')


def login_view(request: HttpRequest) -> HttpResponse:
	if request.user.is_authenticated:
		return _landing_for(request.user)

	form = AuthenticationForm(request, data=request.POST or None)
	if request.method == 'POST' and form.is_valid():
		user = authenticate(
			request,
			username=form.cleaned_data['username'],
			password=form.cleaned_data['password'],
		)
		if user is not None:
			login(request, user)
			return _landing_for(user)

	return render(request, 'finalproject/login.html', {'form': form})


@require_POST
@login_required
def logout_view(request: HttpRequest) -> HttpResponse:
	logout(request)
	return redirect('finalproject:login')


@login_required
def dashboard(request: HttpRequest) -> HttpResponse:
	user = request.user
	if user.is_staff:
		today = date.today()
		context = {
			'role': 'admin',
			'student_count': Student.objects.count(),
			'teacher_count': Teacher.objects.count(),
			'subject_count': Subject.objects.count(),
			'today_count': Attendance.objects.filter(date=today).count(),
			'recent_records': Attendance.objects.select_related(
				'student__user', 'subject', 'marked_by__user'
			)[:8],
		}
		return render(request, 'finalproject/dashboard.html', context)

	teacher = _teacher_for(user)
	if teacher:
		subjects = teacher.subjects.all()
		context = {
			'role': 'teacher',
			'subjects': subjects,
			'subject_count': subjects.count(),
			'student_count': Student.objects.filter(subjects__teachers=teacher).distinct().count(),
			'today_count': Attendance.objects.filter(subject__teachers=teacher, date=date.today()).count(),
			'recent_records': Attendance.objects.filter(subject__teachers=teacher).select_related(
				'student__user', 'subject'
			)[:8],
		}
		return render(request, 'finalproject/dashboard.html', context)

	if _student_for(user):
		return redirect('finalproject:student_attendance')
	raise PermissionDenied


@_role_required('teacher')
def mark_attendance(request: HttpRequest) -> HttpResponse:
	teacher = _teacher_for(request.user)
	subjects = Subject.objects.filter(teachers=teacher)
	subject_id = request.GET.get('subject') or request.POST.get('subject')
	selected_subject = get_object_or_404(subjects, pk=subject_id) if subject_id else subjects.first()
	selected_date = parse_date(request.GET.get('date', '') or request.POST.get('date', '')) or date.today()
	students = selected_subject.students.select_related('user').all() if selected_subject else Student.objects.none()

	if request.method == 'POST' and selected_subject:
		for student in students:
			status = request.POST.get(f'status_{student.pk}')
			if status in Attendance.Status.values:
				Attendance.objects.update_or_create(
					student=student,
					subject=selected_subject,
					date=selected_date,
					defaults={'status': status, 'marked_by': teacher},
				)
		return redirect(
			f"{request.path}?subject={selected_subject.pk}&date={selected_date.isoformat()}&saved=1"
		)

	existing = {}
	if selected_subject:
		existing = {
			record.student_id: record.status
			for record in Attendance.objects.filter(subject=selected_subject, date=selected_date)
		}

	return render(request, 'finalproject/mark_attendance.html', {
		'role': 'teacher',
		'subjects': subjects,
		'selected_subject': selected_subject,
		'selected_date': selected_date,
		'students': students,
		'existing': existing,
		'saved': request.GET.get('saved') == '1',
	})


@_attendance_manager_required
def attendance_report(request: HttpRequest) -> HttpResponse:
	records = Attendance.objects.select_related(
		'student__user', 'subject', 'marked_by__user'
	)
	if not request.user.is_staff:
		teacher = _teacher_for(request.user)
		records = records.filter(subject__teachers=teacher)

	date_from = parse_date(request.GET.get('from', ''))
	date_to = parse_date(request.GET.get('to', ''))
	subject_id = request.GET.get('subject')
	if date_from:
		records = records.filter(date__gte=date_from)
	if date_to:
		records = records.filter(date__lte=date_to)
	if subject_id:
		records = records.filter(subject_id=subject_id)

	subjects = Subject.objects.all() if request.user.is_staff else _teacher_for(request.user).subjects.all()
	summary = records.aggregate(
		total=Count('id'),
		present=Count('id', filter=Q(status=Attendance.Status.PRESENT)),
		absent=Count('id', filter=Q(status=Attendance.Status.ABSENT)),
		late=Count('id', filter=Q(status=Attendance.Status.LATE)),
	)
	return render(request, 'finalproject/attendance_report.html', {
		'role': 'admin' if request.user.is_staff else 'teacher',
		'records': records,
		'subjects': subjects,
		'selected_subject': subject_id or '',
		'date_from': request.GET.get('from', ''),
		'date_to': request.GET.get('to', ''),
		'summary': summary,
	})


@_role_required('student')
def student_attendance(request: HttpRequest) -> HttpResponse:
	student = _student_for(request.user)
	records = student.attendance_records.select_related('subject', 'marked_by__user')
	date_from = parse_date(request.GET.get('from', ''))
	date_to = parse_date(request.GET.get('to', ''))
	if date_from:
		records = records.filter(date__gte=date_from)
	if date_to:
		records = records.filter(date__lte=date_to)
	summary = records.aggregate(
		total=Count('id'),
		present=Count('id', filter=Q(status=Attendance.Status.PRESENT)),
		absent=Count('id', filter=Q(status=Attendance.Status.ABSENT)),
		late=Count('id', filter=Q(status=Attendance.Status.LATE)),
	)
	return render(request, 'finalproject/student_attendance.html', {
		'role': 'student',
		'student': student,
		'records': records,
		'date_from': request.GET.get('from', ''),
		'date_to': request.GET.get('to', ''),
		'summary': summary,
	})
