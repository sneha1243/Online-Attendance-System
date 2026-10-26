from django.conf import settings
from django.db import models


class Teacher(models.Model):
	user = models.OneToOneField(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name='teacher_profile',
	)

	def __str__(self):
		return self.user.get_full_name() or self.user.username


class Subject(models.Model):
	name = models.CharField(max_length=100)
	code = models.CharField(max_length=20, unique=True)
	teachers = models.ManyToManyField(Teacher, related_name='subjects', blank=True)

	class Meta:
		ordering = ['name']

	def __str__(self):
		return f'{self.code} - {self.name}'


class Student(models.Model):
	user = models.OneToOneField(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name='student_profile',
	)
	student_id = models.CharField(max_length=30, unique=True)
	class_name = models.CharField(max_length=60, blank=True)
	subjects = models.ManyToManyField(Subject, related_name='students', blank=True)

	class Meta:
		ordering = ['student_id']

	def __str__(self):
		return f'{self.student_id} - {self.user.get_full_name() or self.user.username}'


class Attendance(models.Model):
	class Status(models.TextChoices):
		PRESENT = 'present', 'Present'
		ABSENT = 'absent', 'Absent'
		LATE = 'late', 'Late'

	student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='attendance_records')
	subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='attendance_records')
	date = models.DateField()
	status = models.CharField(max_length=10, choices=Status.choices)
	marked_by = models.ForeignKey(Teacher, on_delete=models.PROTECT, related_name='attendance_records')
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ['-date', 'subject__name', 'student__student_id']
		constraints = [
			models.UniqueConstraint(
				fields=['student', 'subject', 'date'],
				name='unique_student_subject_attendance_per_day',
			),
		]

	def __str__(self):
		return f'{self.student} - {self.subject.code} - {self.date}: {self.get_status_display()}'
