"""
Selectors - All database read operations for hostel management.

This module contains ALL .objects. queries for the hostel management module.
NO .objects. should appear anywhere else (especially not in views or services for reads).
"""

from django.db.models import Q, Count, F
from django.contrib.auth.models import User
from applications.globals.models import ExtraInfo, Staff, Faculty
from applications.academic_information.models import Student

from .models import (
    Hall,
    HallCaretaker,
    HallWarden,
    UserHostelMapping,
    GuestRoomBooking,
    StaffSchedule,
    HostelNoticeBoard,
    HostelStudentAttendence,
    HallRoom,
    WorkerReport,
    HostelInventory,
    HostelInventoryInspection,
    HostelInventoryInspectionItem,
    HostelResourceRequest,
    HostelResourceRequestItem,
    HostelInventoryUpdateLog,
    HostelLeave,
    HostelComplaint,
    HostelAllotment,
    StudentDetails,
    GuestRoom,
    GuestRoomPolicy,
    HostelFine,
    StudentRoomAllocation,
    HostelRoomGroup,
    HostelRoomGroupMember,
    RoomChangeRequest,
    RoomAllocationStatus,
    HostelTransactionHistory,
    HostelHistory,
    BookingStatus,
    LeaveStatus,
    FineStatus,
)


# ══════════════════════════════════════════════════════════════
# HALL SELECTORS
# ══════════════════════════════════════════════════════════════

def get_all_halls():
    """Retrieve all halls ordered by hall_id."""
    return Hall.objects.all().order_by('hall_id')


def get_hall_by_id(hall_id: int):
    """Retrieve a specific hall by its database ID."""
    return Hall.objects.get(id=hall_id)


def get_hall_by_hall_id(hall_id: str):
    """Retrieve a specific hall by its hall_id string."""
    return Hall.objects.get(hall_id=hall_id)


def get_hall_by_hall_id_or_none(hall_id: str):
    """Retrieve a specific hall by hall_id, returning None if missing."""
    return Hall.objects.filter(hall_id=hall_id).first()


def hall_exists_by_hall_id(hall_id: str) -> bool:
    """Check if a hall exists by hall_id."""
    return Hall.objects.filter(hall_id=hall_id).exists()


# ══════════════════════════════════════════════════════════════
# HALL CARETAKER SELECTORS
# ══════════════════════════════════════════════════════════════

def get_all_hall_caretakers():
    """Retrieve all hall caretakers with related data."""
    return HallCaretaker.objects.all().select_related('hall', 'staff__id__user')


def get_caretaker_by_hall(hall):
    """Get caretaker for a specific hall."""
    return HallCaretaker.objects.filter(hall=hall).select_related('staff__id__user').first()


def get_caretaker_by_staff_id(staff_id):
    """Get caretaker assignment by staff ID."""
    return HallCaretaker.objects.filter(staff_id=staff_id).select_related('hall').first()


def get_hall_for_caretaker_user(user: User):
    """Get the hall managed by a caretaker user."""
    try:
        staff_id = user.extrainfo.id
        caretaker = HallCaretaker.objects.filter(staff_id=staff_id).select_related('hall').first()
        return caretaker.hall if caretaker else None
    except:
        return None


# ══════════════════════════════════════════════════════════════
# HALL WARDEN SELECTORS
# ══════════════════════════════════════════════════════════════

def get_all_hall_wardens():
    """Retrieve all hall wardens with related data."""
    return HallWarden.objects.all().select_related('hall', 'faculty__id__user')


def get_warden_by_hall(hall):
    """Get warden for a specific hall."""
    return HallWarden.objects.filter(hall=hall).select_related('faculty__id__user').first()


def get_warden_by_faculty_id(faculty_id):
    """Get warden assignment by faculty ID."""
    return HallWarden.objects.filter(faculty_id=faculty_id).select_related('hall').first()


def get_hall_for_warden_user(user: User):
    """Get the hall managed by a warden user."""
    try:
        faculty_id = user.extrainfo.id
        warden = HallWarden.objects.filter(faculty_id=faculty_id).select_related('hall').first()
        return warden.hall if warden else None
    except:
        return None


# ══════════════════════════════════════════════════════════════
# GUEST ROOM BOOKING SELECTORS
# ══════════════════════════════════════════════════════════════

def get_all_guest_room_bookings():
    """Retrieve all guest room bookings."""
    return GuestRoomBooking.objects.all().select_related('hall', 'intender').order_by('-booking_date')


def get_booking_by_id(booking_id: int):
    """Retrieve a specific booking by ID."""
    return GuestRoomBooking.objects.select_related('hall', 'intender').get(id=booking_id)


def get_pending_bookings_by_hall(hall):
    """Get all pending guest room bookings for a hall."""
    return GuestRoomBooking.objects.filter(
        hall=hall,
        status=BookingStatus.PENDING
    ).select_related('hall', 'intender')


def get_bookings_by_user(user: User):
    """Get all bookings made by a specific user."""
    return GuestRoomBooking.objects.filter(intender=user).select_related('hall').order_by('-arrival_date')


def get_booking_by_id_and_user(*, booking_id: int, user: User):
    """Retrieve a booking by ID scoped to requesting user."""
    return GuestRoomBooking.objects.select_related('hall', 'intender').get(id=booking_id, intender=user)


def get_bookings_by_hall(*, hall, statuses=None):
    """Get bookings for a hall, optionally filtered by status set."""
    qs = GuestRoomBooking.objects.filter(hall=hall).select_related('hall', 'intender')
    if statuses:
        qs = qs.filter(status__in=statuses)
    return qs.order_by('-booking_date', '-id')


def get_bookings_by_hall_and_date_range(*, hall, start_date, end_date):
    """Get hall bookings intersecting the provided date range."""
    return GuestRoomBooking.objects.filter(
        hall=hall,
        arrival_date__lte=end_date,
        departure_date__gte=start_date,
    ).select_related('hall', 'intender').order_by('-arrival_date', '-id')


def get_student_active_bookings(*, user: User, hall):
    """Get active bookings for student in a hall."""
    return GuestRoomBooking.objects.filter(
        intender=user,
        hall=hall,
        status__in=[
            BookingStatus.PENDING,
            BookingStatus.APPROVED,
            BookingStatus.CONFIRMED,
            BookingStatus.CHECKED_IN,
            BookingStatus.CANCEL_REQUESTED,
        ],
    )


def get_overlapping_bookings_for_room(*, hall, guest_room_id: str, start_date, end_date):
    """Get active bookings overlapping the requested period for a guest room."""
    return GuestRoomBooking.objects.filter(
        hall=hall,
        guest_room_id=str(guest_room_id),
        status__in=[
            BookingStatus.APPROVED,
            BookingStatus.CONFIRMED,
            BookingStatus.CHECKED_IN,
        ],
        arrival_date__lt=end_date,
        departure_date__gt=start_date,
    )


def get_pending_fines_for_student_in_hall(*, student, hall):
    """Get pending fines for student in a hall."""
    return HostelFine.objects.filter(student=student, hall=hall, status=FineStatus.PENDING)


# ══════════════════════════════════════════════════════════════
# GUEST ROOM SELECTORS
# ══════════════════════════════════════════════════════════════

def get_all_guest_rooms():
    """Retrieve all guest rooms."""
    return GuestRoom.objects.all().select_related('hall')


def get_guest_room_by_id(room_id: int):
    """Retrieve a specific guest room by ID."""
    return GuestRoom.objects.select_related('hall').get(id=room_id)


def get_guest_room_by_hall_and_room_label(*, hall, room_label: str):
    """Get guest room by hall and room label/code."""
    return GuestRoom.objects.filter(hall=hall, room__iexact=(room_label or '').strip()).select_related('hall').first()


def get_vacant_guest_rooms_by_hall(hall):
    """Get all vacant guest rooms for a specific hall."""
    return GuestRoom.objects.filter(hall=hall, vacant=True).select_related('hall')


def get_guest_rooms_by_hall_and_type(*, hall, room_type: str):
    """Get guest rooms for hall filtered by room type."""
    return GuestRoom.objects.filter(hall=hall, room_type=room_type).select_related('hall')


def count_vacant_rooms_by_hall_and_type(hall_id: int, room_type: str) -> int:
    """Count vacant rooms of a specific type in a hall."""
    return GuestRoom.objects.filter(hall_id=hall_id, room_type=room_type, vacant=True).count()


def get_guest_room_policy_by_hall(*, hall):
    """Get guest room policy for hall, if configured."""
    return GuestRoomPolicy.objects.filter(hall=hall).first()


def get_or_create_guest_room_policy_by_hall(*, hall):
    """Get or create guest room policy for hall."""
    return GuestRoomPolicy.objects.get_or_create(hall=hall)


# ══════════════════════════════════════════════════════════════
# STAFF SCHEDULE SELECTORS
# ══════════════════════════════════════════════════════════════

def get_all_staff_schedules():
    """Retrieve all staff schedules."""
    return StaffSchedule.objects.all().select_related('hall', 'staff_id__id__user')


def get_staff_schedule_by_hall(hall):
    """Get all staff schedules for a specific hall."""
    return StaffSchedule.objects.filter(hall=hall).select_related('staff_id__id__user')


def get_staff_schedule_by_id(schedule_id: int):
    """Get a specific staff schedule by ID."""
    return StaffSchedule.objects.select_related('hall', 'staff_id__id__user').get(id=schedule_id)


def get_schedule_by_staff_id(staff_id):
    """Get schedule for a specific staff member."""
    return StaffSchedule.objects.filter(staff_id=staff_id).select_related('hall').first()


# ══════════════════════════════════════════════════════════════
# NOTICE BOARD SELECTORS
# ══════════════════════════════════════════════════════════════

def get_all_notices():
    """Retrieve all hostel notices, latest first."""
    return HostelNoticeBoard.objects.all().select_related('hall', 'posted_by__user').order_by('-id')


def get_notice_by_id(notice_id: int):
    """Retrieve a specific notice by ID."""
    return HostelNoticeBoard.objects.select_related('hall', 'posted_by__user').get(id=notice_id)


def get_notices_by_hall(hall):
    """Get all notices for a specific hall."""
    return HostelNoticeBoard.objects.filter(hall=hall).select_related('hall', 'posted_by__user').order_by('-id')


def get_notices_by_hall_ids(hall_ids):
    """Get all notices for a set of hall_id values."""
    return HostelNoticeBoard.objects.filter(
        hall__hall_id__in=hall_ids
    ).select_related('hall', 'posted_by__user').order_by('-id')


# ══════════════════════════════════════════════════════════════
# USER-HALL MAPPING SELECTORS
# ══════════════════════════════════════════════════════════════

def get_user_hall_mapping_by_extrainfo_id(extrainfo_id: str):
    """Get hall mapping for a specific ExtraInfo ID."""
    return UserHostelMapping.objects.filter(
        user_id=extrainfo_id
    ).select_related('hall', 'user__user').first()


def get_user_hall_mapping_for_user(user: User):
    """Get hall mapping for a django auth user."""
    try:
        extrainfo_id = user.extrainfo.id
    except Exception:
        return None

    return get_user_hall_mapping_by_extrainfo_id(extrainfo_id)


def get_student_by_extrainfo_or_none(extrainfo):
    """Resolve student by ExtraInfo object, returning None if missing."""
    return Student.objects.filter(id=extrainfo).select_related('id__user').first()


# ══════════════════════════════════════════════════════════════
# STUDENT ATTENDANCE SELECTORS
# ══════════════════════════════════════════════════════════════

def get_all_attendance():
    """Retrieve all student attendance records."""
    return HostelStudentAttendence.objects.all().select_related('hall', 'student_id__id__user')


def get_attendance_by_hall(hall):
    """Get all attendance records for a specific hall."""
    return HostelStudentAttendence.objects.filter(hall=hall).select_related('student_id__id__user')


def get_attendance_by_student_and_date(student, date):
    """Check if attendance exists for a student on a specific date."""
    return HostelStudentAttendence.objects.filter(student_id=student, date=date).first()


def attendance_exists(student, date) -> bool:
    """Check if attendance record exists."""
    return HostelStudentAttendence.objects.filter(student_id=student, date=date).exists()


# ══════════════════════════════════════════════════════════════
# HALL ROOM SELECTORS
# ══════════════════════════════════════════════════════════════

def get_all_hall_rooms():
    """Retrieve all hall rooms."""
    return HallRoom.objects.all().select_related('hall')


def get_rooms_by_hall(hall):
    """Get all rooms for a specific hall."""
    return HallRoom.objects.filter(hall=hall)


def get_room_by_id(room_id: int):
    """Retrieve a specific room by ID."""
    return HallRoom.objects.select_related('hall').get(id=room_id)


def get_available_rooms_by_hall(hall):
    """Get all available rooms (not at full capacity) for a specific hall."""
    return HallRoom.objects.filter(hall=hall).filter(room_cap__gt=F('room_occupied'))


def get_room_by_details(hall, block_no: str, room_no: str):
    """Get a specific room by hall, block and room number."""
    return HallRoom.objects.filter(hall=hall, block_no=block_no, room_no=room_no).first()


def get_allotted_rooms_by_hall(hall):
    """Get all rooms with at least one occupant."""
    return HallRoom.objects.filter(hall=hall, room_occupied__gt=0)


# ══════════════════════════════════════════════════════════════
# WORKER REPORT SELECTORS
# ══════════════════════════════════════════════════════════════

def get_all_worker_reports():
    """Retrieve all worker reports."""
    return WorkerReport.objects.all().select_related('hall')


def get_worker_reports_by_hall(hall):
    """Get all worker reports for a specific hall."""
    return WorkerReport.objects.filter(hall=hall)


def get_worker_reports_by_hall_and_period(hall, year: int, month: int):
    """Get worker reports for a specific hall and time period."""
    return WorkerReport.objects.filter(hall=hall, year=year, month=month)


# ══════════════════════════════════════════════════════════════
# HOSTEL INVENTORY SELECTORS
# ══════════════════════════════════════════════════════════════

def get_all_inventory():
    """Retrieve all hostel inventory items."""
    return HostelInventory.objects.all().select_related('hall').order_by('inventory_id')


def get_inventory_by_id(inventory_id: int):
    """Retrieve a specific inventory item by ID."""
    return HostelInventory.objects.select_related('hall').get(inventory_id=inventory_id)


def get_inventory_by_hall(hall_id: int):
    """Get all inventory items for a specific hall."""
    return HostelInventory.objects.filter(hall_id=hall_id).order_by('inventory_id')


def get_inventory_by_hall_instance(*, hall):
    """Get inventory items for hall object."""
    return HostelInventory.objects.filter(hall=hall).order_by('inventory_id')


def get_resource_requests_by_hall(*, hall):
    """Get resource requests for a hall."""
    return HostelResourceRequest.objects.filter(hall=hall).select_related(
        'hall',
        'caretaker__id__user',
        'reviewed_by_warden__id__user',
        'reviewed_by_admin',
    ).prefetch_related('items').order_by('-created_at')


def get_all_resource_requests():
    """Get all resource requests."""
    return HostelResourceRequest.objects.all().select_related(
        'hall',
        'caretaker__id__user',
        'reviewed_by_warden__id__user',
        'reviewed_by_admin',
    ).prefetch_related('items').order_by('-created_at')


def get_resource_request_by_id(request_id: int):
    """Get resource request by ID."""
    return HostelResourceRequest.objects.select_related(
        'hall',
        'caretaker__id__user',
        'reviewed_by_warden__id__user',
        'reviewed_by_admin',
    ).prefetch_related('items').get(id=request_id)


def get_inventory_inspections_by_hall(*, hall):
    """Get inventory inspections for hall."""
    return HostelInventoryInspection.objects.filter(hall=hall).select_related(
        'hall',
        'caretaker__id__user',
    ).prefetch_related('items__inventory').order_by('-created_at')


def get_inventory_update_logs_by_hall(*, hall):
    """Get inventory update logs for hall."""
    return HostelInventoryUpdateLog.objects.filter(hall=hall).select_related(
        'inventory',
        'updated_by',
    ).order_by('-created_at')


# ══════════════════════════════════════════════════════════════
# LEAVE SELECTORS
# ══════════════════════════════════════════════════════════════

def get_all_leaves():
    """Retrieve all hostel leave applications."""
    return HostelLeave.objects.all().order_by('-start_date')


def get_leave_by_id(leave_id: int):
    """Retrieve a specific leave application by ID."""
    return HostelLeave.objects.get(id=leave_id)


def get_leaves_by_roll_number(roll_num: str):
    """Get all leave applications for a specific student."""
    return HostelLeave.objects.filter(roll_num__iexact=roll_num).order_by('-start_date')


def get_pending_leaves():
    """Get all pending leave applications."""
    return HostelLeave.objects.filter(status=LeaveStatus.PENDING).order_by('-start_date')


def get_leaves_by_roll_number_and_hall(*, roll_num: str, hall):
    """Get all leave applications for a student within a specific hall."""
    return HostelLeave.objects.filter(
        roll_num__iexact=roll_num,
        hall=hall,
    ).order_by('-start_date')


def get_leaves_by_hall(*, hall):
    """Get all leave applications for a specific hall."""
    return HostelLeave.objects.filter(hall=hall).order_by('-start_date')


def get_active_pending_leave_for_student(*, roll_num: str):
    """Return active pending leave request for a student if it exists."""
    return HostelLeave.objects.filter(
        roll_num__iexact=roll_num,
        status__iexact='pending',
    ).first()


# ══════════════════════════════════════════════════════════════
# COMPLAINT SELECTORS
# ══════════════════════════════════════════════════════════════

def get_all_complaints():
    """Retrieve all hostel complaints with relationships."""
    return HostelComplaint.objects.select_related(
        'student__id__user',
        'hall'
    ).all()


def get_complaint_by_id(complaint_id: int):
    """Retrieve a specific complaint by ID with relationships."""
    return HostelComplaint.objects.select_related(
        'student__id__user',
        'hall'
    ).get(id=complaint_id)


def get_complaints_by_student_and_hall(student, hall):
    """Get all complaints filed by a specific student in their hostel."""
    return HostelComplaint.objects.filter(
        student=student,
        hall=hall
    ).select_related('student__id__user', 'hall')


def get_complaints_by_hall(hall):
    """Get all complaints in a specific hostel."""
    return HostelComplaint.objects.filter(
        hall=hall
    ).select_related('student__id__user', 'hall').order_by('-created_at')


def get_escalated_complaints_by_hall(hall):
    """Get only escalated complaints in a specific hostel for warden view."""
    return HostelComplaint.objects.filter(
        hall=hall,
        status='escalated'
    ).select_related(
        'student__id__user',
        'hall',
        'escalated_by'
    ).order_by('-escalated_at')


def get_all_complaints_by_hall(hall):
    """Get all complaints (all statuses) in a specific hostel for warden view."""
    return HostelComplaint.objects.filter(
        hall=hall
    ).select_related(
        'student__id__user',
        'hall',
        'escalated_by',
        'resolved_by'
    ).order_by('-created_at')


def get_complaints_by_hall_and_date_range(hall, start_date, end_date):
    """Get complaints in date range for report generation."""
    return HostelComplaint.objects.filter(
        hall=hall,
        created_at__range=[start_date, end_date]
    ).select_related('student__id__user', 'hall')


def get_complaints_by_hall_and_status(hall, status):
    """Get complaints filtered by hall and status."""
    return HostelComplaint.objects.filter(
        hall=hall,
        status=status
    ).select_related(
        'student__id__user',
        'escalated_by',
        'resolved_by',
        'hall'
    ).order_by('-created_at')


def get_warden_by_hall(hall):
    """Get the warden assigned to a hall."""
    from .models import HallWarden
    return HallWarden.objects.select_related(
        'faculty__id__user'
    ).get(hall=hall)


# ══════════════════════════════════════════════════════════════
# HOSTEL ALLOTMENT SELECTORS
# ══════════════════════════════════════════════════════════════

def get_all_allotments():
    """Retrieve all hostel allotments."""
    return HostelAllotment.objects.all().select_related('hall', 'assignedCaretaker__id__user', 'assignedWarden__id__user')


def get_allotment_by_id(allotment_id: int):
    """Retrieve a specific allotment by ID."""
    return HostelAllotment.objects.select_related('hall', 'assignedCaretaker', 'assignedWarden').get(id=allotment_id)


def get_allotments_by_hall(hall):
    """Get all allotments for a specific hall."""
    return HostelAllotment.objects.filter(hall=hall).select_related('assignedCaretaker', 'assignedWarden')


# ══════════════════════════════════════════════════════════════
# STUDENT DETAILS SELECTORS
# ══════════════════════════════════════════════════════════════

def get_all_student_details():
    """Retrieve all student details."""
    return StudentDetails.objects.all()


def get_student_details_by_id(student_id: str):
    """Retrieve student details by ID."""
    return StudentDetails.objects.get(id=student_id)


def get_student_details_by_id_or_none(student_id: str):
    """Retrieve student details by ID, returning None if missing."""
    return StudentDetails.objects.filter(id=student_id).first()


def get_student_details_by_hall_id(hall_id: str):
    """Get all student details for a specific hall."""
    return StudentDetails.objects.filter(hall_id=hall_id)


# ══════════════════════════════════════════════════════════════
# STUDENT SELECTORS (from globals)
# ══════════════════════════════════════════════════════════════

def get_all_students():
    """Retrieve all students."""
    return Student.objects.all().select_related('id__user')


def get_student_by_id(student_id: str):
    """Retrieve a specific student by ID."""
    return Student.objects.select_related('id__user').get(id=student_id)


def get_student_by_username_or_none(username: str):
    """Retrieve student by auth username, returning None if not found."""
    return Student.objects.filter(id__user__username__iexact=username).select_related('id__user').first()


def get_students_by_hall_no(hall_no: int):
    """Get all students in a specific hall."""
    return Student.objects.filter(hall_no=hall_no).select_related('id__user')


def student_exists(student_id: str) -> bool:
    """Check if a student exists."""
    return Student.objects.filter(id_id=student_id).exists()


# ══════════════════════════════════════════════════════════════
# HOSTEL FINE SELECTORS
# ══════════════════════════════════════════════════════════════

def get_student_fines(*, student):
    """
    Get all fines for a specific student (scoped to student's own account per BR-HM-012.a).
    """
    return HostelFine.objects.filter(student=student).select_related('hall', 'caretaker', 'student__id__user').order_by('-created_at')


def get_hostel_fines(*, hall):
    """
    Get all fines for a specific hall (scoped to caretaker/warden hall per BR-HM-012.b).
    """
    return HostelFine.objects.filter(hall=hall).select_related('student', 'caretaker').order_by('-created_at')


def get_repeat_offenders(*, hall, threshold=3):
    """
    Identify repeat offenders in a hall (per BR-HM-014.c).

    Returns students with unpaid fines exceeding the threshold.
    """
    from django.db.models import Count

    repeat_offenders = HostelFine.objects.filter(
        hall=hall,
        status=FineStatus.PENDING
    ).values('student_id').annotate(
        fine_count=Count('fine_id')
    ).filter(fine_count__gte=threshold).values_list('student_id', flat=True)

    return list(repeat_offenders)


def get_fine_by_id(fine_id: int):
    """Retrieve a specific fine by ID."""
    return HostelFine.objects.select_related('student', 'hall', 'caretaker').get(fine_id=fine_id)


def get_fines_by_hall(hall_id: int):
    """Get all fines for a specific hall."""
    return HostelFine.objects.filter(hall_id=hall_id).select_related('student', 'caretaker').order_by('-created_at')


def get_fines_by_student(student_id: str):
    """Get all fines for a specific student."""
    return HostelFine.objects.filter(student_id=student_id).select_related('hall', 'caretaker', 'student__id__user').order_by('-created_at')


def get_pending_fines_by_student(student_id: str):
    """Get all pending fines for a specific student."""
    return HostelFine.objects.filter(student_id=student_id, status=FineStatus.PENDING).order_by('-created_at')


def get_students_in_hall(*, hall):
    """Get students currently mapped to the specified hall."""
    hall_number_digits = ''.join(ch for ch in hall.hall_id if ch.isdigit())
    if not hall_number_digits:
        return Student.objects.none()

    return Student.objects.filter(
        hall_no=int(hall_number_digits)
    ).select_related('id__user').order_by('id__user__username')


def get_students_by_usernames(*, usernames):
    """Fetch student rows by usernames with related user records."""
    return Student.objects.filter(
        id__user__username__in=usernames
    ).select_related('id__user')


def get_group_membership_for_student(*, student):
    """Get hostel group membership for student, if any."""
    return HostelRoomGroupMember.objects.filter(student=student).select_related('group').first()


def get_group_by_signature(*, hall, member_signature: str):
    """Resolve existing hostel group by deterministic member signature."""
    return HostelRoomGroup.objects.filter(hall=hall, member_signature=member_signature).first()


def get_groups_for_hall(*, hall):
    """Get all groups for a hostel hall with memberships."""
    return HostelRoomGroup.objects.filter(hall=hall).prefetch_related('memberships__student__id__user').order_by('id')


def get_group_memberships_for_students(*, hall, students):
    """Get group memberships for provided students within hall."""
    return HostelRoomGroupMember.objects.filter(
        student__in=students,
        group__hall=hall,
    ).select_related('group', 'student__id__user')


def get_student_room_allocation_active(*, student):
    """Get active room allocation for student."""
    return StudentRoomAllocation.objects.filter(
        student=student,
        status=RoomAllocationStatus.ACTIVE,
    ).select_related('room', 'hall', 'assigned_by__id__user').first()


def get_room_by_hall_and_details(*, hall, block_no: str, room_no: str):
    """Get room by hall + block + room number."""
    return HallRoom.objects.filter(
        hall=hall,
        block_no=block_no,
        room_no=str(room_no),
    ).first()


def get_pending_room_change_by_student(*, student):
    """Get latest pending room change request for student, if any."""
    return RoomChangeRequest.objects.filter(
        student=student,
        status='Pending',
    ).order_by('-created_at').first()


def get_room_change_requests_by_student(*, student):
    """Get room change request history for student."""
    return RoomChangeRequest.objects.filter(student=student).select_related(
        'hall',
        'allocated_room',
    ).order_by('-created_at')


def get_room_change_request_by_id(*, request_id: int):
    """Get room change request by numeric ID."""
    return RoomChangeRequest.objects.select_related(
        'hall',
        'student__id__user',
        'caretaker_decided_by__id__user',
        'warden_decided_by__id__user',
        'allocated_room',
    ).get(id=request_id)


def get_room_change_requests_by_hall_and_status(*, hall, statuses=None):
    """Get room change requests for a hall, optionally filtered by statuses."""
    qs = RoomChangeRequest.objects.filter(hall=hall).select_related(
        'student__id__user',
        'allocated_room',
        'caretaker_decided_by__id__user',
        'warden_decided_by__id__user',
    )
    if statuses:
        qs = qs.filter(status__in=statuses)
    return qs.order_by('-created_at', '-id')


# ══════════════════════════════════════════════════════════════
# HISTORY SELECTORS
# ══════════════════════════════════════════════════════════════

def get_all_transaction_history():
    """Retrieve all transaction history."""
    return HostelTransactionHistory.objects.all().select_related('hall').order_by('-timestamp')


def get_transaction_history_by_hall(hall):
    """Get transaction history for a specific hall."""
    return HostelTransactionHistory.objects.filter(hall=hall).order_by('-timestamp')


def get_all_hostel_history():
    """Retrieve all hostel history."""
    return HostelHistory.objects.all().select_related('hall', 'caretaker__id__user', 'warden__id__user').order_by('-timestamp')


def get_hostel_history_by_hall(hall):
    """Get hostel history for a specific hall."""
    return HostelHistory.objects.filter(hall=hall).select_related('caretaker__id__user', 'warden__id__user').order_by('-timestamp')


# ══════════════════════════════════════════════════════════════
# STAFF & FACULTY SELECTORS (from globals)
# ══════════════════════════════════════════════════════════════

def get_all_staff():
    """Retrieve all staff members."""
    return Staff.objects.all().select_related('id__user')


def get_staff_by_id(staff_id):
    """Retrieve a specific staff member by ID."""
    return Staff.objects.select_related('id__user').get(pk=staff_id)


def get_staff_by_username(username: str):
    """Get staff member by username."""
    return Staff.objects.select_related('id__user').get(id__user__username=username)


def get_staff_by_extrainfo_id(extrainfo_id):
    """Get staff member by linked ExtraInfo primary key."""
    return Staff.objects.select_related('id__user').filter(id=extrainfo_id).first()


def get_all_faculty():
    """Retrieve all faculty members."""
    return Faculty.objects.all().select_related('id__user')


def get_faculty_by_id(faculty_id):
    """Retrieve a specific faculty member by ID."""
    return Faculty.objects.select_related('id__user').get(pk=faculty_id)


def get_faculty_by_username(username: str):
    """Get faculty member by username."""
    return Faculty.objects.select_related('id__user').get(id__user__username=username)


def get_faculty_by_extrainfo_id(extrainfo_id):
    """Get faculty member by linked ExtraInfo primary key."""
    return Faculty.objects.select_related('id__user').filter(id=extrainfo_id).first()


# ══════════════════════════════════════════════════════════════
# USER SELECTORS
# ══════════════════════════════════════════════════════════════

def get_user_by_username(username: str):
    """Get user by username."""
    return User.objects.get(username=username)


def user_exists_by_username(username: str) -> bool:
    """Check if user exists by username."""
    return User.objects.filter(username=username).exists()
