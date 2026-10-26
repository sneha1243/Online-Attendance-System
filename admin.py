from django.contrib import admin

from .models import Attendance, Student, Subject, Teacher


@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
	list_display = ('user',)
	search_fields = ('user__username', 'user__first_name', 'user__last_name')


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
	list_display = ('student_id', 'user', 'class_name')
	list_filter = ('class_name', 'subjects')
	search_fields = ('student_id', 'user__username', 'user__first_name', 'user__last_name')
	filter_horizontal = ('subjects',)


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
	list_display = ('code', 'name')
	search_fields = ('code', 'name')
	filter_horizontal = ('teachers',)


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
	list_display = ('date', 'student', 'subject', 'status', 'marked_by')
	list_filter = ('date', 'subject', 'status')
	search_fields = ('student__student_id', 'student__user__username', 'subject__code')
	date_hierarchy = 'date'
