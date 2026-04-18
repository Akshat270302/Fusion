"""
Admin configuration for Hostel Management.

Register ALL models with proper configuration.
"""

from django.contrib import admin
from .models import (
    Hall,
    HallCaretaker,
    HallWarden,
    GuestRoomBooking,
    StaffSchedule,
    HostelNoticeBoard,
    HostelStudentAttendence,
    HallRoom,
    WorkerReport,
    HostelInventory,
    HostelLeave,
    HostelComplaint,
    HostelAllotment,
    StudentDetails,
    GuestRoom,
    GuestRoomPolicy,
    HostelFine,
    RoomChangeRequest,
    HostelTransactionHistory,
    HostelHistory,
    UserHostelMapping,
)


@admin.register(Hall)
class HallAdmin(admin.ModelAdmin):
    list_display = ['hall_id', 'hall_name', 'max_accomodation', 'number_students', 'assigned_batch', 'type_of_seater']
    list_filter = ['type_of_seater', 'assigned_batch']
    search_fields = ['hall_id', 'hall_name']
    ordering = ['hall_id']


@admin.register(HallCaretaker)
class HallCaretakerAdmin(admin.ModelAdmin):
    list_display = ['hall', 'staff', 'get_staff_username']
    list_filter = ['hall']
    search_fields = ['hall__hall_name', 'staff__id__user__username']

    def get_staff_username(self, obj):
        return obj.staff.id.user.username
    get_staff_username.short_description = 'Staff Username'


@admin.register(HallWarden)
class HallWardenAdmin(admin.ModelAdmin):
    list_display = ['hall', 'faculty', 'get_faculty_username']
    list_filter = ['hall']
    search_fields = ['hall__hall_name', 'faculty__id__user__username']

    def get_faculty_username(self, obj):
        return obj.faculty.id.user.username
    get_faculty_username.short_description = 'Faculty Username'


@admin.register(UserHostelMapping)
class UserHostelMappingAdmin(admin.ModelAdmin):
    list_display = ['user', 'get_username', 'hall', 'role', 'updated_at']
    list_filter = ['hall', 'role']
    search_fields = ['user__id', 'user__user__username', 'hall__hall_id', 'hall__hall_name']

    def get_username(self, obj):
        return obj.user.user.username
    get_username.short_description = 'Username'


@admin.register(GuestRoomBooking)
class GuestRoomBookingAdmin(admin.ModelAdmin):
    list_display = ['id', 'guest_name', 'hall', 'arrival_date', 'departure_date', 'status', 'room_type', 'booking_date']
    list_filter = ['status', 'room_type', 'hall', 'booking_date']
    search_fields = ['guest_name', 'guest_phone', 'intender__username']
    date_hierarchy = 'booking_date'
    ordering = ['-booking_date']


@admin.register(GuestRoom)
class GuestRoomAdmin(admin.ModelAdmin):
    list_display = ['id', 'hall', 'room', 'room_type', 'room_status', 'vacant', 'occupied_till']
    list_filter = ['hall', 'room_type', 'room_status', 'vacant']
    search_fields = ['room', 'hall__hall_name']


@admin.register(GuestRoomPolicy)
class GuestRoomPolicyAdmin(admin.ModelAdmin):
    list_display = [
        'hall',
        'feature_enabled',
        'charge_per_day',
        'min_advance_days',
        'max_advance_days',
        'max_booking_duration_days',
        'max_concurrent_bookings_per_student',
        'updated_at',
    ]
    list_filter = ['feature_enabled', 'hall']
    search_fields = ['hall__hall_id', 'hall__hall_name']


@admin.register(StaffSchedule)
class StaffScheduleAdmin(admin.ModelAdmin):
    list_display = ['staff_id', 'hall', 'staff_type', 'day', 'start_time', 'end_time']
    list_filter = ['hall', 'staff_type', 'day']
    search_fields = ['staff_id__id__user__username', 'hall__hall_name']


@admin.register(HostelNoticeBoard)
class HostelNoticeBoardAdmin(admin.ModelAdmin):
    list_display = ['id', 'head_line', 'hall', 'posted_by', 'get_posted_date']
    list_filter = ['hall']
    search_fields = ['head_line', 'description', 'posted_by__user__username']
    ordering = ['-id']

    def get_posted_date(self, obj):
        return obj.id
    get_posted_date.short_description = 'Posted Date'


@admin.register(HostelStudentAttendence)
class HostelStudentAttendenceAdmin(admin.ModelAdmin):
    list_display = ['student_id', 'hall', 'date', 'present']
    list_filter = ['hall', 'present', 'date']
    search_fields = ['student_id__id__user__username']
    date_hierarchy = 'date'


@admin.register(HallRoom)
class HallRoomAdmin(admin.ModelAdmin):
    list_display = ['hall', 'block_no', 'room_no', 'room_cap', 'room_occupied', 'get_available']
    list_filter = ['hall', 'block_no', 'room_cap']
    search_fields = ['room_no', 'hall__hall_name']

    def get_available(self, obj):
        return obj.room_cap - obj.room_occupied
    get_available.short_description = 'Available'


@admin.register(WorkerReport)
class WorkerReportAdmin(admin.ModelAdmin):
    list_display = ['worker_id', 'worker_name', 'hall', 'year', 'month', 'absent', 'total_day', 'remark']
    list_filter = ['hall', 'year', 'month']
    search_fields = ['worker_id', 'worker_name']


@admin.register(HostelInventory)
class HostelInventoryAdmin(admin.ModelAdmin):
    list_display = ['inventory_id', 'hall', 'inventory_name', 'cost', 'quantity']
    list_filter = ['hall']
    search_fields = ['inventory_name']
    ordering = ['inventory_id']


@admin.register(HostelLeave)
class HostelLeaveAdmin(admin.ModelAdmin):
    list_display = ['id', 'student_name', 'roll_num', 'start_date', 'end_date', 'status', 'phone_number']
    list_filter = ['status', 'start_date']
    search_fields = ['student_name', 'roll_num']
    date_hierarchy = 'start_date'
    ordering = ['-start_date']


@admin.register(HostelComplaint)
class HostelComplaintAdmin(admin.ModelAdmin):
    list_display = ['id', 'get_student', 'title', 'get_hall', 'status', 'created_at']
    list_filter = ['hall', 'status', 'created_at']
    search_fields = ['student__id__user__username', 'title', 'description']
    readonly_fields = ['created_at', 'updated_at']
    
    def get_student(self, obj):
        return f"{obj.student.id.user.username}"
    get_student.short_description = 'Student'
    
    def get_hall(self, obj):
        return obj.hall.hall_name
    get_hall.short_description = 'Hall'


@admin.register(HostelAllotment)
class HostelAllotmentAdmin(admin.ModelAdmin):
    list_display = ['id', 'hall', 'assignedCaretaker', 'assignedWarden', 'assignedBatch']
    list_filter = ['hall', 'assignedBatch']
    search_fields = ['hall__hall_name', 'assignedBatch']


@admin.register(StudentDetails)
class StudentDetailsAdmin(admin.ModelAdmin):
    list_display = ['id', 'first_name', 'last_name', 'programme', 'batch', 'hall_id', 'room_num']
    list_filter = ['programme', 'batch', 'hall_id']
    search_fields = ['id', 'first_name', 'last_name']


@admin.register(HostelFine)
class HostelFineAdmin(admin.ModelAdmin):
    list_display = ['fine_id', 'student_name', 'student', 'hall', 'amount', 'status', 'reason']
    list_filter = ['hall', 'status']
    search_fields = ['student_name', 'student__id__id', 'reason']
    ordering = ['fine_id']


@admin.register(RoomChangeRequest)
class RoomChangeRequestAdmin(admin.ModelAdmin):
    list_display = [
        'request_id',
        'student',
        'hall',
        'status',
        'caretaker_decision',
        'warden_decision',
        'created_at',
        'allocated_at',
    ]
    list_filter = ['hall', 'status', 'caretaker_decision', 'warden_decision']
    search_fields = ['request_id', 'student__id__user__username', 'reason', 'current_room_no']
    ordering = ['-created_at']


@admin.register(HostelTransactionHistory)
class HostelTransactionHistoryAdmin(admin.ModelAdmin):
    list_display = ['id', 'hall', 'change_type', 'previous_value', 'new_value', 'timestamp']
    list_filter = ['hall', 'change_type', 'timestamp']
    search_fields = ['change_type', 'previous_value', 'new_value']
    date_hierarchy = 'timestamp'
    ordering = ['-timestamp']


@admin.register(HostelHistory)
class HostelHistoryAdmin(admin.ModelAdmin):
    list_display = ['id', 'hall', 'caretaker', 'warden', 'batch', 'timestamp']
    list_filter = ['hall', 'timestamp']
    search_fields = ['hall__hall_name', 'batch']
    date_hierarchy = 'timestamp'
    ordering = ['-timestamp']
