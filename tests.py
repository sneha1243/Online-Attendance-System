from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Attendance, Student, Subject, Teacher


User = get_user_model()


class AttendanceWorkflowTests(TestCase):
	def setUp(self):
		self.teacher_user = User.objects.create_user(
			username='teacher', password='secure-pass-123', first_name='Taylor'
		)
		self.teacher = Teacher.objects.create(user=self.teacher_user)
		self.subject = Subject.objects.create(name='Biology', code='BIO101')
		self.subject.teachers.add(self.teacher)
		self.student_user = User.objects.create_user(
			username='student', password='secure-pass-123', first_name='Sam'
		)
		self.student = Student.objects.create(user=self.student_user, student_id='S-1001')
		self.student.subjects.add(self.subject)

	def test_teacher_can_mark_attendance_for_enrolled_students(self):
		self.client.force_login(self.teacher_user)

		response = self.client.post(reverse('finalproject:mark_attendance'), {
			'subject': self.subject.pk,
			'date': '2026-09-29',
			f'status_{self.student.pk}': Attendance.Status.LATE,
		})

		self.assertRedirects(
			response,
			f"{reverse('finalproject:mark_attendance')}?subject={self.subject.pk}&date=2026-09-29&saved=1",
		)
		record = Attendance.objects.get(student=self.student, subject=self.subject)
		self.assertEqual(record.status, Attendance.Status.LATE)
		self.assertEqual(record.marked_by, self.teacher)

	def test_marking_same_day_updates_existing_record(self):
		Attendance.objects.create(
			student=self.student,
			subject=self.subject,
			date=date(2026, 9, 29),
			status=Attendance.Status.ABSENT,
			marked_by=self.teacher,
		)
		self.client.force_login(self.teacher_user)

		self.client.post(reverse('finalproject:mark_attendance'), {
			'subject': self.subject.pk,
			'date': '2026-09-29',
			f'status_{self.student.pk}': Attendance.Status.PRESENT,
		})

		self.assertEqual(Attendance.objects.count(), 1)
		self.assertEqual(Attendance.objects.get().status, Attendance.Status.PRESENT)

	def test_teacher_cannot_mark_unassigned_subject(self):
		other_subject = Subject.objects.create(name='Chemistry', code='CHEM101')
		self.client.force_login(self.teacher_user)

		response = self.client.get(
			reverse('finalproject:mark_attendance'), {'subject': other_subject.pk}
		)

		self.assertEqual(response.status_code, 404)

	def test_teacher_attendance_page_renders_enrolled_students(self):
		self.client.force_login(self.teacher_user)

		response = self.client.get(reverse('finalproject:mark_attendance'))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Sam')
		self.assertContains(response, 'BIO101')

	def test_teacher_report_page_renders(self):
		self.client.force_login(self.teacher_user)

		response = self.client.get(reverse('finalproject:attendance_report'))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Attendance report')

	def test_student_sees_only_their_own_attendance(self):
		other_user = User.objects.create_user(username='other-student', password='secure-pass-123')
		other_student = Student.objects.create(user=other_user, student_id='S-1002')
		Attendance.objects.create(
			student=self.student,
			subject=self.subject,
			date=date(2026, 9, 29),
			status=Attendance.Status.PRESENT,
			marked_by=self.teacher,
		)
		Attendance.objects.create(
			student=other_student,
			subject=self.subject,
			date=date(2026, 9, 29),
			status=Attendance.Status.ABSENT,
			marked_by=self.teacher,
		)
		self.client.force_login(self.student_user)

		response = self.client.get(reverse('finalproject:student_attendance'))

		self.assertEqual(response.status_code, 200)
		self.assertEqual(len(response.context['records']), 1)
		self.assertEqual(response.context['records'][0].student, self.student)

	def test_student_cannot_open_teacher_attendance_form(self):
		self.client.force_login(self.student_user)

		response = self.client.get(reverse('finalproject:mark_attendance'))

		self.assertEqual(response.status_code, 403)

	def test_login_redirects_to_role_home(self):
		response = self.client.post(reverse('finalproject:login'), {
			'username': 'teacher',
			'password': 'secure-pass-123',
		})

		self.assertRedirects(response, reverse('finalproject:dashboard'))

	def test_unauthenticated_user_redirects_to_project_login(self):
		response = self.client.get(reverse('finalproject:dashboard'))

		self.assertRedirects(response, f"{reverse('finalproject:login')}?next=%2F")
