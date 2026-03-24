"""
Services - All business logic and write operations for hostel management.

This module contains ALL business logic, validation, and write operations.
For reads, this module calls selectors. It NEVER uses .objects. for reads.
"""

from django.db import transaction
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import datetime, date
import re

from applications.globals.models import Staff, Faculty
from applications.academic_information.models import Student

from . import selectors
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
    HostelLeave,
    HostelComplaint,
    HostelAllotment,
    StudentDetails,
    GuestRoom,
    HostelFine,
    StudentRoomAllocation,
    HostelTransactionHistory,
    HostelHistory,
    BookingStatus,
    LeaveStatus,
    FineStatus,
    ComplaintStatus,
    FineCategory,
    RoomAllocationStatus,
    RoomType,
    AttendanceStatus,
)


# ══════════════════════════════════════════════════════════════
# CUSTOM EXCEPTIONS
# ══════════════════════════════════════════════════════════════

class HostelManagementError(Exception):
    """Base exception for hostel management module."""
    pass


class HallNotFoundError(HostelManagementError):
    """Hall does not exist."""
    pass


class HallAlreadyExistsError(HostelManagementError):
    """Hall with this ID already exists."""
    pass


class RoomNotAvailableError(HostelManagementError):
    """Room is full or unavailable."""
    pass


class RoomNotFoundError(HostelManagementError):
    """Room does not exist."""
    pass


class StudentNotFoundError(HostelManagementError):
    """Student does not exist."""
    pass


class StaffNotFoundError(HostelManagementError):
    """Staff member does not exist."""
    pass


class FacultyNotFoundError(HostelManagementError):
    """Faculty member does not exist."""
    pass


class InvalidOperationError(HostelManagementError):
    """Operation not allowed in current state."""
    pass


class AttendanceAlreadyMarkedError(HostelManagementError):
    """Attendance already marked for this date."""
    pass


class InsufficientRoomsError(HostelManagementError):
    """Not enough rooms available."""
    pass


class GuestCapacityExceededError(HostelManagementError):
    """Number of guests exceeds room capacity."""
    pass


class UnauthorizedAccessError(HostelManagementError):
    """User not authorized for this operation."""
    pass


class BookingNotFoundError(HostelManagementError):
    """Booking does not exist."""
    pass


class LeaveNotFoundError(HostelManagementError):
    """Leave application does not exist."""
    pass


class FineNotFoundError(HostelManagementError):
    """Fine does not exist."""
    pass


class InventoryNotFoundError(HostelManagementError):
    """Inventory item does not exist."""
    pass


class StudentHostelAssignmentMissingError(HostelManagementError):
    """Student does not have an active hostel assignment."""
    pass


class UserHallMappingMissingError(HostelManagementError):
    """Authenticated user is not mapped to any hostel hall."""
    pass


class LeaveValidationError(HostelManagementError):
    """Leave request input is invalid."""
    pass


class RoomAssignmentError(HostelManagementError):
    """Room assignment cannot be completed."""
    pass


def _upsert_user_hall_mapping(*, extrainfo, hall, role: str):
    """Create or update explicit user-hall mapping used by hostel workflows."""
    normalized_role = role if role in {
        UserHostelMapping.ROLE_STUDENT,
        UserHostelMapping.ROLE_WARDEN,
        UserHostelMapping.ROLE_CARETAKER,
    } else UserHostelMapping.ROLE_OTHER

    mapping, _ = UserHostelMapping.objects.update_or_create(
        user=extrainfo,
        defaults={
            'hall': hall,
            'role': normalized_role,
        }
    )
    return mapping


def resolve_user_hall_mapping_service(*, user, strict: bool = True):
    """
    Resolve hall mapping for user.

    Resolution order:
    1) explicit UserHostelMapping
    2) HallWarden assignment
    3) HallCaretaker assignment
    4) StudentDetails.hall_id
    5) Student.hall_no
    """
    mapping = selectors.get_user_hall_mapping_for_user(user)
    if mapping:
        return mapping

    try:
        extrainfo = user.extrainfo
    except Exception:
        if strict:
            raise UserHallMappingMissingError('User profile is missing.')
        return None

    warden_assignment = selectors.get_warden_by_faculty_id(extrainfo.id)
    if warden_assignment and warden_assignment.hall:
        return _upsert_user_hall_mapping(
            extrainfo=extrainfo,
            hall=warden_assignment.hall,
            role=UserHostelMapping.ROLE_WARDEN,
        )

    caretaker_assignment = selectors.get_caretaker_by_staff_id(extrainfo.id)
    if caretaker_assignment and caretaker_assignment.hall:
        return _upsert_user_hall_mapping(
            extrainfo=extrainfo,
            hall=caretaker_assignment.hall,
            role=UserHostelMapping.ROLE_CARETAKER,
        )

    student_details = selectors.get_student_details_by_id_or_none(user.username)
    if student_details and student_details.hall_id:
        hall = selectors.get_hall_by_hall_id_or_none(student_details.hall_id)
        if hall:
            return _upsert_user_hall_mapping(
                extrainfo=extrainfo,
                hall=hall,
                role=UserHostelMapping.ROLE_STUDENT,
            )

    student = selectors.get_student_by_extrainfo_or_none(extrainfo)
    if student and student.hall_no:
        hall = selectors.get_hall_by_hall_id_or_none(f'hall{student.hall_no}')
        if hall:
            return _upsert_user_hall_mapping(
                extrainfo=extrainfo,
                hall=hall,
                role=UserHostelMapping.ROLE_STUDENT,
            )

    if strict:
        raise UserHallMappingMissingError('Hostel mapping is not configured for this user.')
    return None


# ══════════════════════════════════════════════════════════════
# HALL SERVICES
# ══════════════════════════════════════════════════════════════

@transaction.atomic
def create_hall(*, hall_id: str, hall_name: str, max_accomodation: int, type_of_seater: str, **kwargs):
    """Create a new hall."""
    if selectors.hall_exists_by_hall_id(hall_id):
        raise HallAlreadyExistsError(f"Hall with ID {hall_id} already exists.")

    hall = Hall.objects.create(
        hall_id=hall_id,
        hall_name=hall_name,
        max_accomodation=max_accomodation,
        type_of_seater=type_of_seater,
        **kwargs
    )
    return hall


@transaction.atomic
def update_hall(*, hall_id: int, **update_fields):
    """Update hall information."""
    try:
        hall = selectors.get_hall_by_id(hall_id)
    except Hall.DoesNotExist:
        raise HallNotFoundError(f"Hall with ID {hall_id} not found.")

    for field, value in update_fields.items():
        setattr(hall, field, value)
    hall.save()
    return hall


@transaction.atomic
def delete_hall(*, hall_id: int):
    """Delete a hall and its related data."""
    try:
        hall = selectors.get_hall_by_id(hall_id)
    except Hall.DoesNotExist:
        raise HallNotFoundError(f"Hall with ID {hall_id} not found.")

    # Delete related allotments
    HostelAllotment.objects.filter(hall=hall).delete()

    # Delete the hall
    hall.delete()


# ══════════════════════════════════════════════════════════════
# HALL CARETAKER SERVICES
# ══════════════════════════════════════════════════════════════

@transaction.atomic
def assign_caretaker(*, hall_id: str, caretaker_username: str):
    """Assign a caretaker to a hall."""
    try:
        hall = selectors.get_hall_by_hall_id(hall_id)
    except Hall.DoesNotExist:
        raise HallNotFoundError(f"Hall with ID {hall_id} not found.")

    try:
        caretaker_staff = selectors.get_staff_by_username(caretaker_username)
    except Staff.DoesNotExist:
        raise StaffNotFoundError(f"Caretaker with username {caretaker_username} not found.")

    # Get previous caretaker for history
    prev_hall_caretaker = selectors.get_caretaker_by_hall(hall)

    # Delete any previous assignments of this caretaker
    HallCaretaker.objects.filter(staff=caretaker_staff).delete()

    # Delete any previously assigned caretaker to this hall
    HallCaretaker.objects.filter(hall=hall).delete()

    # Create new assignment
    hall_caretaker = HallCaretaker.objects.create(hall=hall, staff=caretaker_staff)
    _upsert_user_hall_mapping(
        extrainfo=caretaker_staff.id,
        hall=hall,
        role=UserHostelMapping.ROLE_CARETAKER,
    )

    # Update hostel allotments
    hostel_allotments = selectors.get_allotments_by_hall(hall)
    for hostel_allotment in hostel_allotments:
        hostel_allotment.assignedCaretaker = caretaker_staff
        hostel_allotment.save(update_fields=['assignedCaretaker'])

    # Record transaction history
    HostelTransactionHistory.objects.create(
        hall=hall,
        change_type='Caretaker',
        previous_value=prev_hall_caretaker.staff.id if (prev_hall_caretaker and prev_hall_caretaker.staff) else 'None',
        new_value=caretaker_username
    )

    # Create hostel history
    current_warden = selectors.get_warden_by_hall(hall)
    HostelHistory.objects.create(
        hall=hall,
        caretaker=caretaker_staff,
        batch=hall.assigned_batch,
        warden=current_warden.faculty if (current_warden and current_warden.faculty) else None
    )

    return hall_caretaker


# ══════════════════════════════════════════════════════════════
# HALL WARDEN SERVICES
# ══════════════════════════════════════════════════════════════

@transaction.atomic
def assign_warden(*, hall_id: str, warden_username: str):
    """Assign a warden to a hall."""
    try:
        hall = selectors.get_hall_by_hall_id(hall_id)
    except Hall.DoesNotExist:
        raise HallNotFoundError(f"Hall with ID {hall_id} not found.")

    try:
        warden = selectors.get_faculty_by_username(warden_username)
    except Faculty.DoesNotExist:
        raise FacultyNotFoundError(f"Warden with username {warden_username} not found.")

    # Get previous warden for history
    prev_hall_warden = selectors.get_warden_by_hall(hall)

    # Delete any previous assignments of this warden
    HallWarden.objects.filter(faculty=warden).delete()

    # Delete any previously assigned warden to this hall
    HallWarden.objects.filter(hall=hall).delete()

    # Create new assignment
    hall_warden = HallWarden.objects.create(hall=hall, faculty=warden)
    _upsert_user_hall_mapping(
        extrainfo=warden.id,
        hall=hall,
        role=UserHostelMapping.ROLE_WARDEN,
    )

    # Update hostel allotments
    hostel_allotments = selectors.get_allotments_by_hall(hall)
    for hostel_allotment in hostel_allotments:
        hostel_allotment.assignedWarden = warden
        hostel_allotment.save(update_fields=['assignedWarden'])

    # Record transaction history
    HostelTransactionHistory.objects.create(
        hall=hall,
        change_type='Warden',
        previous_value=prev_hall_warden.faculty.id if (prev_hall_warden and prev_hall_warden.faculty) else 'None',
        new_value=warden_username
    )

    # Create hostel history
    current_caretaker = selectors.get_caretaker_by_hall(hall)
    HostelHistory.objects.create(
        hall=hall,
        caretaker=current_caretaker.staff if (current_caretaker and current_caretaker.staff) else None,
        batch=hall.assigned_batch,
        warden=warden
    )

    return hall_warden


# ══════════════════════════════════════════════════════════════
# BATCH ASSIGNMENT SERVICES
# ══════════════════════════════════════════════════════════════

@transaction.atomic
def assign_batch_to_hall(*, hall_id: str, batch: str):
    """Assign a batch to a hall."""
    try:
        hall = selectors.get_hall_by_hall_id(hall_id)
    except Hall.DoesNotExist:
        raise HallNotFoundError(f"Hall with ID {hall_id} not found.")

    previous_batch = hall.assigned_batch if hall.assigned_batch is not None else '0'
    hall.assigned_batch = batch
    hall.save(update_fields=['assigned_batch'])

    # Update room allotments
    room_allotments = selectors.get_allotments_by_hall(hall)
    for room_allotment in room_allotments:
        room_allotment.assignedBatch = batch
        room_allotment.save(update_fields=['assignedBatch'])

    # Update student hall allotments
    hall_number = int(''.join(filter(str.isdigit, hall.hall_id)))
    students = Student.objects.filter(batch=int(batch))
    for student in students:
        student.hall_no = hall_number
        student.save(update_fields=['hall_no'])

    # Record transaction history
    HostelTransactionHistory.objects.create(
        hall=hall,
        change_type='Batch',
        previous_value=previous_batch,
        new_value=batch
    )

    # Create hostel history
    current_caretaker = selectors.get_caretaker_by_hall(hall)
    current_warden = selectors.get_warden_by_hall(hall)
    HostelHistory.objects.create(
        hall=hall,
        caretaker=current_caretaker.staff if (current_caretaker and current_caretaker.staff) else None,
        batch=batch,
        warden=current_warden.faculty if (current_warden and current_warden.faculty) else None
    )

    return hall


# ══════════════════════════════════════════════════════════════
# GUEST ROOM BOOKING SERVICES
# ══════════════════════════════════════════════════════════════

@transaction.atomic
def create_guest_room_booking(
    *,
    hall_id: int,
    intender: User,
    guest_name: str,
    guest_phone: str,
    purpose: str,
    arrival_date: str,
    arrival_time: str,
    departure_date: str,
    departure_time: str,
    rooms_required: int,
    total_guest: int,
    room_type: str,
    **kwargs
):
    """Create a new guest room booking request."""
    try:
        hall = selectors.get_hall_by_id(hall_id)
    except Hall.DoesNotExist:
        raise HallNotFoundError(f"Hall with ID {hall_id} not found.")

    # Check room availability
    available_rooms_count = selectors.count_vacant_rooms_by_hall_and_type(hall_id, room_type)
    if available_rooms_count < rooms_required:
        raise InsufficientRoomsError("Not enough available rooms for this booking.")

    # Check guest capacity
    max_guests = {'single': 1, 'double': 2, 'triple': 3}
    if total_guest > rooms_required * max_guests.get(room_type, 1):
        raise GuestCapacityExceededError("Number of guests exceeds the capacity of selected rooms.")

    booking = GuestRoomBooking.objects.create(
        hall=hall,
        intender=intender,
        guest_name=guest_name,
        guest_phone=guest_phone,
        purpose=purpose,
        arrival_date=arrival_date,
        arrival_time=arrival_time,
        departure_date=departure_date,
        departure_time=departure_time,
        rooms_required=rooms_required,
        total_guest=total_guest,
        room_type=room_type,
        booking_date=timezone.now().date(),
        **kwargs
    )
    return booking


@transaction.atomic
def approve_guest_room_booking(*, booking_id: int, guest_room_id: int):
    """Approve a guest room booking and assign a room."""
    try:
        booking = selectors.get_booking_by_id(booking_id)
    except GuestRoomBooking.DoesNotExist:
        raise BookingNotFoundError(f"Booking with ID {booking_id} not found.")

    if booking.status != BookingStatus.PENDING:
        raise InvalidOperationError("Only PENDING bookings can be approved.")

    try:
        guest_room = selectors.get_guest_room_by_id(guest_room_id)
    except GuestRoom.DoesNotExist:
        raise RoomNotFoundError(f"Guest room with ID {guest_room_id} not found.")

    # Update booking
    booking.guest_room_id = str(guest_room.id)
    booking.status = BookingStatus.CONFIRMED
    booking.save(update_fields=['guest_room_id', 'status'])

    # Update guest room
    guest_room.occupied_till = booking.departure_date
    guest_room.vacant = False
    guest_room.save(update_fields=['occupied_till', 'vacant'])

    return booking


@transaction.atomic
def reject_guest_room_booking(*, booking_id: int):
    """Reject a guest room booking."""
    try:
        booking = selectors.get_booking_by_id(booking_id)
    except GuestRoomBooking.DoesNotExist:
        raise BookingNotFoundError(f"Booking with ID {booking_id} not found.")

    if booking.status != BookingStatus.PENDING:
        raise InvalidOperationError("Only PENDING bookings can be rejected.")

    booking.status = BookingStatus.REJECTED
    booking.save(update_fields=['status'])
    return booking


# ══════════════════════════════════════════════════════════════
# STAFF SCHEDULE SERVICES
# ══════════════════════════════════════════════════════════════

@transaction.atomic
def create_or_update_staff_schedule(
    *,
    hall,
    staff_id,
    staff_type: str,
    day: str,
    start_time: str,
    end_time: str
):
    """Create or update a staff schedule."""
    existing_schedule = selectors.get_schedule_by_staff_id(staff_id)

    if existing_schedule:
        existing_schedule.hall = hall
        existing_schedule.day = day
        existing_schedule.start_time = datetime.strptime(start_time, '%H:%M').time()
        existing_schedule.end_time = datetime.strptime(end_time, '%H:%M').time()
        existing_schedule.staff_type = staff_type
        existing_schedule.save(update_fields=['hall', 'day', 'start_time', 'end_time', 'staff_type'])
        return existing_schedule
    else:
        schedule = StaffSchedule.objects.create(
            hall=hall,
            staff_id=staff_id,
            day=day,
            staff_type=staff_type,
            start_time=datetime.strptime(start_time, '%H:%M').time(),
            end_time=datetime.strptime(end_time, '%H:%M').time()
        )
        return schedule


@transaction.atomic
def delete_staff_schedule(*, staff_id):
    """Delete a staff schedule."""
    schedule = selectors.get_schedule_by_staff_id(staff_id)
    if schedule:
        schedule.delete()


# ══════════════════════════════════════════════════════════════
# NOTICE BOARD SERVICES
# ══════════════════════════════════════════════════════════════

@transaction.atomic
def create_notice(*, hall, posted_by, head_line: str, description: str, content=None):
    """Create a new hostel notice."""
    notice = HostelNoticeBoard.objects.create(
        hall=hall,
        posted_by=posted_by,
        head_line=head_line,
        description=description,
        content=content
    )
    return notice


@transaction.atomic
def createNoticeService(*, title: str, content: str, user=None, hall=None, posted_by=None, role: str = None):
    """Create and publish a hostel notice scoped to publisher's mapped hall."""
    if user is not None:
        mapping = resolve_user_hall_mapping_service(user=user, strict=True)
        role = mapping.role
        hall = mapping.hall
        posted_by = user.extrainfo

    if role not in [UserHostelMapping.ROLE_WARDEN, UserHostelMapping.ROLE_CARETAKER]:
        raise UnauthorizedAccessError('Only warden or caretaker can create notices.')
    if hall is None:
        raise UserHallMappingMissingError('Hostel mapping is required to create notices.')

    notice = HostelNoticeBoard.objects.create(
        hall=hall,
        posted_by=posted_by,
        role=role,
        head_line=title,
        description=content,
    )
    return notice


@transaction.atomic
def delete_notice(*, notice_id: int):
    """Delete a notice."""
    try:
        notice = selectors.get_notice_by_id(notice_id)
    except HostelNoticeBoard.DoesNotExist:
        raise HostelManagementError(f"Notice with ID {notice_id} not found.")
    notice.delete()


def getAllNoticesService(*, user=None):
    """Return notices scoped to authenticated user's mapped hall."""
    if user is None or user.is_superuser:
        return selectors.get_all_notices()

    mapping = resolve_user_hall_mapping_service(user=user, strict=True)
    return selectors.get_notices_by_hall(mapping.hall)


def get_student_notice_board_service(*, student_roll_number: str):
    """Return notices visible to a student based on hostel assignment."""
    student_details = selectors.get_student_details_by_id_or_none(student_roll_number)
    if not student_details:
        raise StudentHostelAssignmentMissingError('Student profile not found for hostel notice view.')
    if not student_details.hall_id:
        raise StudentHostelAssignmentMissingError('Hostel assignment not found for student.')

    hall = selectors.get_hall_by_hall_id_or_none(student_details.hall_id)
    if not hall:
        raise StudentHostelAssignmentMissingError('Mapped hostel does not exist for student.')

    return selectors.get_notices_by_hall(hall)


# ══════════════════════════════════════════════════════════════
# STUDENT ALLOTMENT SERVICES
# ══════════════════════════════════════════════════════════════

def _hall_number_from_hall_id(hall_id: str):
    digits = ''.join(ch for ch in str(hall_id) if ch.isdigit())
    return int(digits) if digits else None


def _serialize_student_for_allotment(student):
    full_name = f"{student.id.user.first_name} {student.id.user.last_name}".strip()
    return {
        'id__user__username': student.id.user.username,
        'full_name': full_name or student.id.user.username,
        'programme': student.programme,
        'batch': str(student.batch),
        'cpi': float(student.cpi),
        'category': student.category,
        'hall_id': f"hall{student.hall_no}" if student.hall_no else '',
        'room_no': student.room_no or '',
        'specialization': student.specialization or '',
        'curr_semester_no': student.curr_semester_no,
    }


def searchStudentsService(*, user, query: str = None):
    """Search students within authenticated user's hostel."""
    mapping = resolve_user_hall_mapping_service(user=user, strict=True)
    if mapping.role not in [
        UserHostelMapping.ROLE_CARETAKER,
        UserHostelMapping.ROLE_WARDEN,
        UserHostelMapping.ROLE_STUDENT,
    ]:
        raise UnauthorizedAccessError('You are not authorized to access student allotment data.')

    students = selectors.get_students_in_hall(hall=mapping.hall)

    if query:
        query_normalized = query.strip().lower()
        students = [
            st for st in students
            if query_normalized in st.id.user.username.lower()
            or query_normalized in (st.id.user.get_full_name() or '').lower()
            or query_normalized in (st.room_no or '').lower()
        ]

    return [_serialize_student_for_allotment(st) for st in students]


def getStudentDetailsService(*, user, student_id: str):
    """Get student details within authenticated user's hostel scope."""
    mapping = resolve_user_hall_mapping_service(user=user, strict=True)
    student = selectors.get_student_by_username_or_none(student_id)
    if not student:
        try:
            student = selectors.get_student_by_id(student_id)
        except Student.DoesNotExist:
            student = None

    if not student:
        raise StudentNotFoundError(f'Student with ID {student_id} not found.')

    student_hall = _resolve_student_hall(student=student)
    if not student_hall or student_hall.id != mapping.hall_id:
        raise UnauthorizedAccessError('Student does not belong to your hostel.')

    payload = _serialize_student_for_allotment(student)
    active_allocation = selectors.get_student_room_allocation_active(student=student)
    payload['allocation'] = {
        'status': active_allocation.status,
        'assigned_at': active_allocation.assigned_at.isoformat() if active_allocation else None,
    } if active_allocation else None

    hall_rooms = selectors.get_rooms_by_hall(mapping.hall)
    payload['available_rooms'] = [
        {
            'id': room.id,
            'label': f"{room.block_no}-{room.room_no}",
            'capacity': room.room_cap,
            'occupied_count': room.room_occupied,
            'available': room.room_occupied < room.room_cap,
        }
        for room in hall_rooms
        if room.room_occupied < room.room_cap
    ]
    return payload


@transaction.atomic
def assignRoomService(*, user, student_id: str, room_id=None, room_label: str = None):
    """Assign room to student for caretaker within same hostel."""
    mapping = resolve_user_hall_mapping_service(user=user, strict=True)
    if mapping.role != UserHostelMapping.ROLE_CARETAKER:
        raise UnauthorizedAccessError('Only caretaker can assign rooms.')

    student = selectors.get_student_by_username_or_none(student_id)
    if not student:
        try:
            student = selectors.get_student_by_id(student_id)
        except Student.DoesNotExist:
            student = None
    if not student:
        raise StudentNotFoundError(f'Student with ID {student_id} not found.')

    student_hall = _resolve_student_hall(student=student)
    if not student_hall or student_hall.id != mapping.hall_id:
        raise UnauthorizedAccessError('Student does not belong to your hostel.')

    room = None
    if room_id:
        room = selectors.get_room_by_id(int(room_id))
    elif room_label:
        match = re.match(r'^\s*([A-Za-z])\s*[-]?\s*([0-9]+)\s*$', str(room_label))
        if not match:
            raise RoomAssignmentError('Invalid room format. Use block-room like A-101.')
        block_no, room_no = match.group(1).upper(), match.group(2)
        room = selectors.get_room_by_hall_and_details(hall=mapping.hall, block_no=block_no, room_no=room_no)

    if not room:
        raise RoomNotFoundError('Selected room does not exist.')
    if room.hall_id != mapping.hall_id:
        raise UnauthorizedAccessError('Room must belong to your hostel.')
    if room.room_occupied >= room.room_cap:
        raise RoomNotAvailableError('Selected room is already full.')

    # Vacate previous active assignment if present.
    active_allocation = selectors.get_student_room_allocation_active(student=student)
    if active_allocation:
        old_room = active_allocation.room
        if old_room.id == room.id:
            raise RoomAssignmentError('Student is already assigned to this room.')
        if old_room.room_occupied > 0:
            old_room.room_occupied -= 1
            old_room.save(update_fields=['room_occupied'])
        active_allocation.status = RoomAllocationStatus.VACATED
        active_allocation.vacated_at = timezone.now()
        active_allocation.save(update_fields=['status', 'vacated_at'])

    room.room_occupied += 1
    room.save(update_fields=['room_occupied'])

    hall_number = _hall_number_from_hall_id(mapping.hall.hall_id)
    student.room_no = f"{room.block_no}-{room.room_no}"
    if hall_number:
        student.hall_no = hall_number
    student.save(update_fields=['room_no', 'hall_no'])

    caretaker_staff = Staff.objects.filter(id=user.extrainfo).first()
    allocation = StudentRoomAllocation.objects.create(
        student=student,
        room=room,
        hall=mapping.hall,
        assigned_by=caretaker_staff,
        status=RoomAllocationStatus.ACTIVE,
    )
    return allocation


def getStudentRoomService(*, user):
    """Get currently authenticated student's room details."""
    mapping = resolve_user_hall_mapping_service(user=user, strict=True)
    if mapping.role != UserHostelMapping.ROLE_STUDENT:
        raise UnauthorizedAccessError('Only students can view their allotted room.')

    student = selectors.get_student_by_extrainfo_or_none(user.extrainfo)
    if not student:
        raise StudentNotFoundError('Student profile not found for current user.')

    student_hall = _resolve_student_hall(student=student)
    if not student_hall or student_hall.id != mapping.hall_id:
        raise UnauthorizedAccessError('Student hostel mapping is invalid.')

    allocation = selectors.get_student_room_allocation_active(student=student)
    return {
        'student_id': student.id.user.username,
        'room_number': student.room_no,
        'hostel_id': student_hall.hall_id,
        'hostel_name': student_hall.hall_name,
        'allocation_date': allocation.assigned_at.isoformat() if allocation else None,
        'status': allocation.status if allocation else 'unassigned',
        # Keep existing student card fields for compatibility.
        'id__user__username': student.id.user.username,
        'programme': student.programme,
        'batch': str(student.batch),
        'cpi': float(student.cpi),
        'category': student.category,
        'hall_id': student_hall.hall_id,
        'room_no': student.room_no or '',
    }


# ══════════════════════════════════════════════════════════════
# LEAVE REQUEST SERVICES (HOSTEL-SCOPED)
# ══════════════════════════════════════════════════════════════

@transaction.atomic
def submitLeaveRequestService(*, user, start_date: str, end_date: str, reason: str, phone_number: str = None, student_name: str = None, roll_num: str = None):
    """Submit hostel leave request for authenticated student."""
    mapping = resolve_user_hall_mapping_service(user=user, strict=True)
    if mapping.role != UserHostelMapping.ROLE_STUDENT:
        raise UnauthorizedAccessError('Only students can submit leave requests.')

    if not start_date or not end_date or not reason:
        raise LeaveValidationError('start_date, end_date and reason are required.')

    try:
        start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
    except ValueError:
        raise LeaveValidationError('Invalid date format. Use YYYY-MM-DD.')

    if end_date_obj < start_date_obj:
        raise LeaveValidationError('end_date must be greater than or equal to start_date.')

    current_roll_num = (user.username or '').strip()
    if not current_roll_num:
        raise LeaveValidationError('Unable to resolve student roll number.')

    existing_pending = selectors.get_active_pending_leave_for_student(roll_num=current_roll_num)
    if existing_pending:
        raise LeaveValidationError('Only one pending leave request is allowed at a time.')

    student = selectors.get_student_by_extrainfo_or_none(user.extrainfo)
    if not student:
        raise StudentNotFoundError('Student record not found for authenticated user.')

    resolved_student_name = (student_name or user.get_full_name() or user.username).strip()

    leave = HostelLeave.objects.create(
        student_name=resolved_student_name,
        roll_num=current_roll_num,
        student=student,
        hall=mapping.hall,
        reason=reason.strip(),
        phone_number=(phone_number or '').strip() or None,
        start_date=start_date_obj,
        end_date=end_date_obj,
        status='pending',
    )
    return leave


def getStudentLeaveRequestsService(*, user):
    """Fetch leave requests for authenticated student only."""
    mapping = resolve_user_hall_mapping_service(user=user, strict=True)
    if mapping.role != UserHostelMapping.ROLE_STUDENT:
        raise UnauthorizedAccessError('Only students can view their leave requests.')
    return selectors.get_leaves_by_roll_number_and_hall(
        roll_num=user.username,
        hall=mapping.hall,
    )


def getPendingLeaveRequestsService(*, user):
    """Fetch all leave requests scoped to caretaker/warden hall."""
    mapping = resolve_user_hall_mapping_service(user=user, strict=True)
    if mapping.role not in [UserHostelMapping.ROLE_CARETAKER, UserHostelMapping.ROLE_WARDEN]:
        raise UnauthorizedAccessError('Only caretaker or warden can manage leave requests.')
    return selectors.get_leaves_by_hall(hall=mapping.hall)


def _resolve_attendance_date(date_value):
    if not date_value:
        return timezone.now().date()

    if isinstance(date_value, date):
        return date_value

    if isinstance(date_value, str):
        try:
            return datetime.strptime(date_value, '%Y-%m-%d').date()
        except ValueError:
            raise InvalidOperationError('Invalid date format. Use YYYY-MM-DD.')

    raise InvalidOperationError('Invalid date value provided.')


def _resolve_student_for_attendance(student_identifier):
    student = selectors.get_student_by_username_or_none(str(student_identifier))
    if student:
        return student

    try:
        return selectors.get_student_by_id(str(student_identifier))
    except Student.DoesNotExist:
        raise StudentNotFoundError(f'Student with ID {student_identifier} not found.')


def getStudentsForAttendanceService(*, user):
    """Return all students from authenticated caretaker's hostel."""
    mapping = resolve_user_hall_mapping_service(user=user, strict=True)
    if mapping.role != UserHostelMapping.ROLE_CARETAKER:
        raise UnauthorizedAccessError('Only caretaker can fetch students for attendance.')

    students = selectors.get_students_in_hall(hall=mapping.hall)
    payload = []
    for student in students:
        full_name = f"{student.id.user.first_name} {student.id.user.last_name}".strip() or student.id.user.username
        payload.append(
            {
                'student_id': student.id.user.username,
                'name': full_name,
                'room_no': student.room_no or '',
                'hostel_id': mapping.hall.hall_id,
                'hostel_name': mapping.hall.hall_name,
            }
        )
    return payload


@transaction.atomic
def submitAttendanceService(*, user, attendance_entries, date_value=None):
    """Create or update per-student attendance for a caretaker's hostel and date."""
    mapping = resolve_user_hall_mapping_service(user=user, strict=True)
    if mapping.role != UserHostelMapping.ROLE_CARETAKER:
        raise UnauthorizedAccessError('Only caretaker can submit attendance.')

    if not isinstance(attendance_entries, list) or not attendance_entries:
        raise InvalidOperationError('attendance_entries must be a non-empty list.')

    attendance_date = _resolve_attendance_date(date_value)
    caretaker_staff = Staff.objects.filter(id=user.extrainfo).first()
    if not caretaker_staff:
        raise UnauthorizedAccessError('Caretaker profile not found for current user.')

    seen_students = set()
    created_count = 0
    updated_count = 0

    for entry in attendance_entries:
        if not isinstance(entry, dict):
            raise InvalidOperationError('Each attendance entry must be an object.')

        student_identifier = entry.get('student_id')
        status_value = str(entry.get('status', '')).strip().lower()

        if not student_identifier:
            raise InvalidOperationError('student_id is required in each attendance entry.')
        if status_value not in [AttendanceStatus.PRESENT, AttendanceStatus.ABSENT]:
            raise InvalidOperationError('status must be either present or absent.')

        if student_identifier in seen_students:
            raise InvalidOperationError(f'Duplicate student_id {student_identifier} in request payload.')
        seen_students.add(student_identifier)

        student = _resolve_student_for_attendance(student_identifier)
        student_hall = _resolve_student_hall(student=student)
        if not student_hall or student_hall.id != mapping.hall_id:
            raise UnauthorizedAccessError(f'Student {student_identifier} does not belong to your hostel.')

        attendance_record, created = HostelStudentAttendence.objects.update_or_create(
            student_id=student,
            date=attendance_date,
            defaults={
                'hall': mapping.hall,
                'status': status_value,
                'present': status_value == AttendanceStatus.PRESENT,
                'marked_by': caretaker_staff,
            },
        )

        if created:
            created_count += 1
        else:
            updated_count += 1

    return {
        'date': attendance_date.isoformat(),
        'hostel_id': mapping.hall.hall_id,
        'created_count': created_count,
        'updated_count': updated_count,
        'total_submitted': len(attendance_entries),
    }


def getStudentAttendanceService(*, user):
    """Return attendance history for authenticated student from own hostel only."""
    mapping = resolve_user_hall_mapping_service(user=user, strict=True)
    if mapping.role != UserHostelMapping.ROLE_STUDENT:
        raise UnauthorizedAccessError('Only students can view attendance history.')

    student = selectors.get_student_by_extrainfo_or_none(user.extrainfo)
    if not student:
        raise StudentNotFoundError('Student profile not found for current user.')

    student_hall = _resolve_student_hall(student=student)
    if not student_hall or student_hall.id != mapping.hall_id:
        raise UnauthorizedAccessError('Student hostel mapping is invalid.')

    records = HostelStudentAttendence.objects.filter(
        student_id=student,
        hall=mapping.hall,
    ).select_related('marked_by__id__user').order_by('-date')

    return [
        {
            'date': record.date.isoformat(),
            'status': record.status,
            'hostel_id': mapping.hall.hall_id,
            'marked_by': record.marked_by.id.user.username if record.marked_by and record.marked_by.id and record.marked_by.id.user else None,
            'created_at': record.created_at.isoformat() if record.created_at else None,
        }
        for record in records
    ]


@transaction.atomic
def updateLeaveStatusService(*, user, leave_id: int, status: str, remark: str = None):
    """Update leave request status for caretaker/warden within their hall."""
    mapping = resolve_user_hall_mapping_service(user=user, strict=True)
    if mapping.role not in [UserHostelMapping.ROLE_CARETAKER, UserHostelMapping.ROLE_WARDEN]:
        raise UnauthorizedAccessError('Only caretaker or warden can update leave status.')

    try:
        leave = selectors.get_leave_by_id(leave_id)
    except HostelLeave.DoesNotExist:
        raise LeaveNotFoundError(f'Leave application with ID {leave_id} not found.')

    if leave.hall_id != mapping.hall_id:
        raise UnauthorizedAccessError('You can only update leave requests from your hostel.')

    normalized_status = (status or '').strip().lower()
    if normalized_status not in ['approved', 'rejected']:
        raise InvalidOperationError('status must be either approved or rejected.')

    leave.status = normalized_status
    leave.remark = (remark or '').strip() or None
    leave.save(update_fields=['status', 'remark', 'updated_at'])
    return leave


# ══════════════════════════════════════════════════════════════
# STUDENT ATTENDANCE SERVICES
# ══════════════════════════════════════════════════════════════

@transaction.atomic
def mark_attendance(*, student_id: str, date: str):
    """Mark attendance for a student."""
    try:
        student = selectors.get_student_by_id(student_id)
    except Student.DoesNotExist:
        raise StudentNotFoundError(f"Student with ID {student_id} not found.")

    if selectors.attendance_exists(student, date):
        raise AttendanceAlreadyMarkedError(f"Attendance already marked for {student_id} on {date}.")

    hall = selectors.get_hall_by_hall_id(f'hall{student.hall_no}')

    record = HostelStudentAttendence.objects.create(
        student_id=student,
        hall=hall,
        date=date,
        present=True
    )
    return record


# ══════════════════════════════════════════════════════════════
# ROOM MANAGEMENT SERVICES
# ══════════════════════════════════════════════════════════════

@transaction.atomic
def change_student_room(*, student_id: str, new_room_no: str, new_hall_no: str):
    """Change a student's room assignment."""
    try:
        student = selectors.get_student_by_id(student_id)
    except Student.DoesNotExist:
        raise StudentNotFoundError(f"Student with ID {student_id} not found.")

    # Remove from old room
    if student.hall_no and student.room_no:
        old_hall = selectors.get_hall_by_hall_id(f'hall{student.hall_no}')
        block = str(student.room_no[0]) if student.room_no else ''
        room_digits = re.findall('[0-9]+', str(student.room_no))
        if room_digits:
            old_room = selectors.get_room_by_details(old_hall, block, room_digits[0])
            if old_room and old_room.room_occupied > 0:
                old_room.room_occupied -= 1
                old_room.save(update_fields=['room_occupied'])
                old_hall.number_students -= 1
                old_hall.save(update_fields=['number_students'])

    # Add to new room
    new_hall = selectors.get_hall_by_hall_id(f'hall{new_hall_no}')
    block = str(new_room_no[0])
    room_digits = re.findall('[0-9]+', new_room_no)
    if not room_digits:
        raise RoomNotFoundError(f"Invalid room number format: {new_room_no}")

    new_room = selectors.get_room_by_details(new_hall, block, room_digits[0])
    if not new_room:
        raise RoomNotFoundError(f"Room {new_room_no} not found in hall {new_hall_no}.")

    if new_room.room_occupied >= new_room.room_cap:
        raise RoomNotAvailableError(f"Room {new_room_no} is at full capacity.")

    new_room.room_occupied += 1
    new_room.save(update_fields=['room_occupied'])
    new_hall.number_students += 1
    new_hall.save(update_fields=['number_students'])

    # Update student
    student.hall_no = int(new_hall_no)
    student.room_no = new_room_no
    student.save(update_fields=['hall_no', 'room_no'])

    return student


# ══════════════════════════════════════════════════════════════
# LEAVE SERVICES
# ══════════════════════════════════════════════════════════════

@transaction.atomic
def create_leave_application(
    *,
    student_name: str,
    roll_num: str,
    reason: str,
    start_date: str,
    end_date: str,
    phone_number: str = None,
    file_upload=None
):
    """Create a new leave application."""
    leave = HostelLeave.objects.create(
        student_name=student_name,
        roll_num=roll_num,
        reason=reason,
        phone_number=phone_number,
        start_date=start_date,
        end_date=end_date,
        file_upload=file_upload,
        status=LeaveStatus.PENDING
    )
    return leave


@transaction.atomic
def update_leave_status(*, leave_id: int, status: str, remark: str = None):
    """Approve or reject a leave application."""
    try:
        leave = selectors.get_leave_by_id(leave_id)
    except HostelLeave.DoesNotExist:
        raise LeaveNotFoundError(f"Leave application with ID {leave_id} not found.")

    if status not in [LeaveStatus.APPROVED, LeaveStatus.REJECTED]:
        raise InvalidOperationError(f"Invalid leave status: {status}")

    leave.status = status
    if remark:
        leave.remark = remark
    leave.save(update_fields=['status', 'remark'])
    return leave


# ══════════════════════════════════════════════════════════════
# COMPLAINT SERVICES
# ══════════════════════════════════════════════════════════════


@transaction.atomic
def submitComplaintService(*, user, title: str, description: str):
    """
    Submit a complaint by student with hostel-scoped auto-linking.
    
    Validates:
    - User is a student in hostel
    - Title and description are not empty
    Auto-links complaint to student's hostel, defaults status to pending
    """
    mapping = resolve_user_hall_mapping_service(user=user, strict=True)
    if mapping.role != UserHostelMapping.ROLE_STUDENT:
        raise UnauthorizedAccessError('Only students can submit complaints.')
    
    title = str(title).strip()
    description = str(description).strip()
    if not title or len(title) < 3:
        raise InvalidOperationError('Complaint title must be at least 3 characters.')
    if not description or len(description) < 10:
        raise InvalidOperationError('Complaint description must be at least 10 characters.')
    
    student = selectors.get_student_by_username_or_none(user.username)
    if not student:
        try:
            student = selectors.get_student_by_id(user.username)
        except Student.DoesNotExist:
            student = None
    if not student:
        raise StudentNotFoundError(f'Student profile not found for user {user.username}.')
    
    complaint = HostelComplaint.objects.create(
        student=student,
        hall=mapping.hall,
        title=title,
        description=description,
        status=ComplaintStatus.PENDING,
    )
    return complaint


def getStudentComplaintsService(*, user):
    """
    Fetch ONLY student's own complaints, scoped to their hostel.
    
    Enforces:
    - User must be a student
    - Can view only own complaints
    - Results filtered to their hostel
    """
    mapping = resolve_user_hall_mapping_service(user=user, strict=True)
    if mapping.role != UserHostelMapping.ROLE_STUDENT:
        raise UnauthorizedAccessError('Only students can view their own complaints.')
    
    student = selectors.get_student_by_username_or_none(user.username)
    if not student:
        try:
            student = selectors.get_student_by_id(user.username)
        except Student.DoesNotExist:
            student = None
    if not student:
        raise StudentNotFoundError(f'Student profile not found for user {user.username}.')
    
    return selectors.get_complaints_by_student_and_hall(
        student=student,
        hall=mapping.hall
    )


def getHostelComplaintsService(*, user):
    """
    Fetch ALL complaints in caretaker's hostel.
    
    Enforces:
    - User must be a caretaker
    - Can view only complaints from their assigned hostel
    """
    mapping = resolve_user_hall_mapping_service(user=user, strict=True)
    if mapping.role != UserHostelMapping.ROLE_CARETAKER:
        raise UnauthorizedAccessError('Only caretaker can view hostel complaints.')
    
    return selectors.get_complaints_by_hall(hall=mapping.hall)


@transaction.atomic
def updateComplaintStatusService(*, user, complaint_id: int, status: str):
    """
    Update complaint status by caretaker, scoped to their hostel.
    
    Validates:
    - User is caretaker
    - Complaint belongs to their hostel
    - New status is valid (pending, in_progress, resolved)
    """
    mapping = resolve_user_hall_mapping_service(user=user, strict=True)
    if mapping.role != UserHostelMapping.ROLE_CARETAKER:
        raise UnauthorizedAccessError('Only caretaker can update complaint status.')
    
    try:
        complaint = selectors.get_complaint_by_id(complaint_id)
    except HostelComplaint.DoesNotExist:
        raise InvalidOperationError(f'Complaint with ID {complaint_id} not found.')
    
    if complaint.hall.id != mapping.hall_id:
        raise UnauthorizedAccessError('Complaint does not belong to your hostel.')
    
    if status not in [ComplaintStatus.PENDING, ComplaintStatus.IN_PROGRESS, ComplaintStatus.RESOLVED]:
        raise InvalidOperationError(f'Invalid complaint status: {status}')
    
    complaint.status = status
    complaint.save(update_fields=['status', 'updated_at'])
    return complaint


@transaction.atomic
def escalateComplaintService(*, user, complaint_id: int, escalation_reason: str, remarks: str = ''):
    """
    Escalate complaint to warden by caretaker.
    
    Validates:
    - User is caretaker
    - Complaint belongs to their hostel
    - Complaint status is 'in_progress'
    - Escalation reason is provided (mandatory)
    
    Updates:
    - Status to 'escalated'
    - Sets escalation_reason and remarks
    - Sets escalated_by and escalated_at timestamp
    
    Notifications:
    - Notifies assigned warden
    - Notifies student
    """
    # Validate user is caretaker
    mapping = resolve_user_hall_mapping_service(user=user, strict=True)
    if mapping.role != UserHostelMapping.ROLE_CARETAKER:
        raise UnauthorizedAccessError('Only caretaker can escalate complaints.')
    
    # Get and validate complaint
    try:
        complaint = selectors.get_complaint_by_id(complaint_id)
    except HostelComplaint.DoesNotExist:
        raise InvalidOperationError(f'Complaint with ID {complaint_id} not found.')
    
    # Verify complaint belongs to caretaker's hostel
    if complaint.hall.id != mapping.hall_id:
        raise UnauthorizedAccessError('Complaint does not belong to your hostel.')
    
    # Validate complaint status is 'in_progress'
    if complaint.status != ComplaintStatus.IN_PROGRESS:
        raise InvalidOperationError(
            f'Can only escalate complaints with "in_progress" status. Current status: {complaint.status}'
        )
    
    # Validate escalation reason
    escalation_reason = escalation_reason.strip() if escalation_reason else ''
    if not escalation_reason:
        raise InvalidOperationError('Escalation reason is mandatory.')
    
    if len(escalation_reason) < 10:
        raise InvalidOperationError('Escalation reason must be at least 10 characters.')
    
    # Update complaint with escalation data
    complaint.status = ComplaintStatus.ESCALATED
    complaint.escalation_reason = escalation_reason
    complaint.escalated_by = user
    complaint.escalated_at = timezone.now()
    complaint.save(update_fields=['status', 'escalation_reason', 'escalated_by', 'escalated_at', 'updated_at'])
    
    # Send notifications
    try:
        from applications.notification import notify
        
        # Notify warden(s) assigned to this hall
        if complaint.hall:
            wardens = HostelAllotment.objects.filter(hall=complaint.hall).values_list('assignedWarden', flat=True)
            for warden_id in wardens:
                if warden_id:
                    try:
                        warden_user = Faculty.objects.get(id=warden_id).id.user
                        notify(
                            recipient=warden_user,
                            sender=user,
                            type='complaint_escalated',
                            title='Complaint Escalated',
                            description=f'Complaint #{complaint.id} "{complaint.title}" has been escalated to you by caretaker.'
                        )
                    except (Faculty.DoesNotExist, AttributeError):
                        pass  # Skip if warden not found
        
        # Notify student
        if complaint.student:
            try:
                student_user = complaint.student.id.user
                notify(
                    recipient=student_user,
                    sender=user,
                    type='complaint_escalated',
                    title='Complaint Escalated',
                    description=f'Your complaint #{complaint.id} "{complaint.title}" has been escalated to the warden for priority handling.'
                )
            except (Student.DoesNotExist, AttributeError):
                pass  # Skip if student not found
    except ImportError:
        pass  # Notification module not available, continue without notifications
    
    return complaint


# ══════════════════════════════════════════════════════════════
# WARDEN COMPLAINT MANAGEMENT SERVICES
# ══════════════════════════════════════════════════════════════

def getEscalatedComplaintsService(*, user):
    """
    Get all escalated complaints for warden in their assigned hall.
    
    Validates:
    - User is warden
    - Returns only escalated complaints
    """
    mapping = resolve_user_hall_mapping_service(user=user, strict=True)
    if mapping.role != UserHostelMapping.ROLE_WARDEN:
        raise UnauthorizedAccessError('Only warden can view escalated complaints.')
    
    return selectors.get_escalated_complaints_by_hall(hall=mapping.hall)


def getAllComplaintsForWardenService(*, user):
    """
    Get all complaints (all statuses) for warden to view full complaint history.
    
    Validates:
    - User is warden
    """
    mapping = resolve_user_hall_mapping_service(user=user, strict=True)
    if mapping.role != UserHostelMapping.ROLE_WARDEN:
        raise UnauthorizedAccessError('Only warden can view hostel complaints.')
    
    return selectors.get_all_complaints_by_hall(hall=mapping.hall)


@transaction.atomic
def resolveComplaintService(*, user, complaint_id: int, resolution_notes: str):
    """
    Warden resolves an escalated complaint.
    
    Validates:
    - User is warden
    - Complaint belongs to their hostel
    - Complaint status is 'escalated'
    - Resolution notes provided (mandatory)
    
    Updates:
    - Status to 'resolved'
    - Sets resolution_notes
    - Sets resolved_by and resolved_at timestamp
    
    Notifications:
    - Notify Student: Complaint resolved
    - Notify Caretaker: Complaint resolved by warden
    """
    # Validate user is warden
    mapping = resolve_user_hall_mapping_service(user=user, strict=True)
    if mapping.role != UserHostelMapping.ROLE_WARDEN:
        raise UnauthorizedAccessError('Only warden can resolve complaints.')
    
    # Get and validate complaint
    try:
        complaint = selectors.get_complaint_by_id(complaint_id)
    except HostelComplaint.DoesNotExist:
        raise InvalidOperationError(f'Complaint with ID {complaint_id} not found.')
    
    # Verify complaint belongs to warden's hostel
    if complaint.hall.id != mapping.hall_id:
        raise UnauthorizedAccessError('Complaint does not belong to your hostel.')
    
    # Validate complaint is escalated (can only resolve escalated ones)
    if complaint.status != ComplaintStatus.ESCALATED:
        raise InvalidOperationError(
            f'Can only resolve escalated complaints. Current status: {complaint.status}'
        )
    
    # Validate resolution notes
    resolution_notes = resolution_notes.strip() if resolution_notes else ''
    if not resolution_notes:
        raise InvalidOperationError('Resolution notes are mandatory.')
    
    if len(resolution_notes) < 10:
        raise InvalidOperationError('Resolution notes must be at least 10 characters.')
    
    # Update complaint with resolution data
    complaint.status = ComplaintStatus.RESOLVED
    complaint.resolution_notes = resolution_notes
    complaint.resolved_by = user
    complaint.resolved_at = timezone.now()
    complaint.save(update_fields=[
        'status',
        'resolution_notes',
        'resolved_by',
        'resolved_at',
        'updated_at'
    ])
    
    # Send notifications
    try:
        from applications.notification import notify
        
        # Notify student
        if complaint.student:
            try:
                student_user = complaint.student.id.user
                notify(
                    recipient=student_user,
                    sender=user,
                    type='complaint_resolved',
                    title='Complaint Resolved',
                    description=f'Your complaint #{complaint.id} "{complaint.title}" has been resolved by the warden.'
                )
            except (Student.DoesNotExist, AttributeError):
                pass
        
        # Notify caretaker who escalated it
        if complaint.escalated_by:
            try:
                notify(
                    recipient=complaint.escalated_by,
                    sender=user,
                    type='complaint_resolved',
                    title='Escalated Complaint Resolved',
                    description=f'Complaint #{complaint.id} "{complaint.title}" you escalated has been resolved by warden.'
                )
            except:
                pass
    except ImportError:
        pass
    
    return complaint


@transaction.atomic
def reassignComplaintService(
    *,
    user,
    complaint_id: int,
    caretaker_id: int,
    instructions: str = ''
):
    """
    Warden reassigns escalated complaint back to a caretaker.
    
    Validates:
    - User is warden
    - Complaint belongs to their hostel
    - Complaint status is 'escalated'
    - Caretaker exists and is assigned to same hall
    
    Updates:
    - Status remains 'in_progress' (back to caretaker handling)
    - Sets reassigned_to, reassignment_instructions, reassigned_at
    - Warden can clear escalation_reason if resolving inline
    
    Notifications:
    - Notify Caretaker: Complaint reassigned with instructions
    """
    # Validate user is warden
    mapping = resolve_user_hall_mapping_service(user=user, strict=True)
    if mapping.role != UserHostelMapping.ROLE_WARDEN:
        raise UnauthorizedAccessError('Only warden can reassign complaints.')
    
    # Get and validate complaint
    try:
        complaint = selectors.get_complaint_by_id(complaint_id)
    except HostelComplaint.DoesNotExist:
        raise InvalidOperationError(f'Complaint with ID {complaint_id} not found.')
    
    # Verify complaint belongs to warden's hostel
    if complaint.hall.id != mapping.hall_id:
        raise UnauthorizedAccessError('Complaint does not belong to your hostel.')
    
    # Validate complaint is escalated
    if complaint.status != ComplaintStatus.ESCALATED:
        raise InvalidOperationError(
            f'Can only reassign escalated complaints. Current status: {complaint.status}'
        )
    
    # Validate caretaker exists and is in the same hall
    try:
        caretaker = Staff.objects.get(id=caretaker_id)
    except Staff.DoesNotExist:
        raise InvalidOperationError(f'Caretaker with ID {caretaker_id} not found.')
    
    # Verify caretaker is assigned to this hall
    caretaker_mapping = UserHostelMapping.objects.filter(
        user=caretaker.id.user,
        hall=complaint.hall,
        role=UserHostelMapping.ROLE_CARETAKER
    ).first()
    
    if not caretaker_mapping:
        raise UnauthorizedAccessError(
            f'Caretaker is not assigned to {complaint.hall.hall_name}.'
        )
    
    # Update complaint with reassignment
    complaint.status = ComplaintStatus.IN_PROGRESS  # Back to caretaker
    complaint.reassigned_to = caretaker
    complaint.reassignment_instructions = instructions.strip() if instructions else ''
    complaint.reassigned_at = timezone.now()
    complaint.save(update_fields=[
        'status',
        'reassigned_to',
        'reassignment_instructions',
        'reassigned_at',
        'updated_at'
    ])
    
    # Send notification to caretaker
    try:
        from applications.notification import notify
        
        try:
            notify(
                recipient=caretaker.id.user,
                sender=user,
                type='complaint_reassigned',
                title='Complaint Reassigned',
                description=f'Complaint #{complaint.id} "{complaint.title}" has been reassigned to you by warden with instructions.'
            )
        except:
            pass
    except ImportError:
        pass
    
    return complaint


@transaction.atomic
def file_complaint(
    *,
    hall_name: str,
    student_name: str,
    roll_number: str,
    description: str,
    contact_number: str
):
    """File a new hostel complaint."""
    complaint = HostelComplaint.objects.create(
        hall_name=hall_name,
        student_name=student_name,
        roll_number=roll_number,
        description=description,
        contact_number=contact_number
    )
    return complaint


# ══════════════════════════════════════════════════════════════
# FINE SERVICES
# ══════════════════════════════════════════════════════════════

def _resolve_staff_from_user(*, user):
    """Resolve Staff object for authenticated caretaker user."""
    staff = Staff.objects.filter(id=user.extrainfo).first()
    if not staff:
        raise UnauthorizedAccessError('Caretaker profile not found for current user.')
    return staff


def _resolve_student_hall(*, student):
    """Resolve student's hall using explicit mapping first and Student fallback."""
    student_mapping = selectors.get_user_hall_mapping_by_extrainfo_id(student.id_id)
    if student_mapping and student_mapping.hall:
        return student_mapping.hall

    if student.hall_no:
        return selectors.get_hall_by_hall_id_or_none(f'hall{student.hall_no}')

    return None


@transaction.atomic
def imposeFineService(*, user, student_id: str, amount, reason: str, category: str = None, evidence=None):
    """Impose fine by caretaker for student in same hostel."""
    mapping = resolve_user_hall_mapping_service(user=user, strict=True)
    if mapping.role != UserHostelMapping.ROLE_CARETAKER:
        raise UnauthorizedAccessError('Only caretaker can impose fines.')

    try:
        amount_value = float(amount)
    except (TypeError, ValueError):
        raise InvalidOperationError('amount must be a valid number.')

    if amount_value <= 0:
        raise InvalidOperationError('Fine amount must be greater than 0.')

    if not reason or not str(reason).strip():
        raise InvalidOperationError('reason is required.')

    fine_category = category or FineCategory.RULE_VIOLATION
    valid_categories = {choice[0] for choice in FineCategory.choices}
    if fine_category not in valid_categories:
        raise InvalidOperationError('Invalid violation category selected.')

    if evidence and hasattr(evidence, 'size') and evidence.size > 5 * 1024 * 1024:
        raise InvalidOperationError('Evidence file size must not exceed 5MB.')

    student = selectors.get_student_by_username_or_none(student_id)
    if not student:
        try:
            student = selectors.get_student_by_id(student_id)
        except Student.DoesNotExist:
            student = None
    if not student:
        raise StudentNotFoundError(f'Student with ID {student_id} not found.')

    student_hall = _resolve_student_hall(student=student)
    if not student_hall or student_hall.id != mapping.hall_id:
        raise UnauthorizedAccessError('Student is not in your assigned hostel.')

    caretaker_staff = _resolve_staff_from_user(user=user)

    student_full_name = f"{student.id.user.first_name} {student.id.user.last_name}".strip() or student.id.user.username

    fine = HostelFine.objects.create(
        student=student,
        caretaker=caretaker_staff,
        hall=mapping.hall,
        student_name=student_full_name,
        amount=amount_value,
        category=fine_category,
        status=FineStatus.PENDING,
        reason=str(reason).strip(),
        evidence=evidence,
    )
    return fine


def getStudentFinesService(*, user):
    """Return fines for authenticated student, scoped to own hostel."""
    mapping = resolve_user_hall_mapping_service(user=user, strict=True)
    if mapping.role != UserHostelMapping.ROLE_STUDENT:
        raise UnauthorizedAccessError('Only students can view my fines.')

    student = selectors.get_student_by_extrainfo_or_none(user.extrainfo)
    if not student:
        raise StudentNotFoundError('Student profile not found for current user.')

    return HostelFine.objects.filter(
        student=student,
        hall=mapping.hall,
    ).select_related('hall', 'caretaker__id__user', 'student__id__user').order_by('-created_at')


def getHostelFinesService(*, user):
    """Return fines for caretaker's hostel only."""
    mapping = resolve_user_hall_mapping_service(user=user, strict=True)
    if mapping.role != UserHostelMapping.ROLE_CARETAKER:
        raise UnauthorizedAccessError('Only caretaker can view hostel fines.')

    return selectors.get_hostel_fines(hall=mapping.hall)

@transaction.atomic
def impose_fine_service(*, caretaker, student_id, amount, category, reason, evidence=None):
    """
    Impose a fine on a student with full validation per BR-HM-013.

    Validates:
    - Amount > 0
    - Category is valid
    - Reason is not empty
    - Evidence file size and type if provided
    """
    return imposeFineService(
        user=caretaker,
        student_id=student_id,
        amount=amount,
        category=category,
        reason=reason,
        evidence=evidence,
    )


@transaction.atomic
def update_fine(*, fine_id: int, **update_fields):
    """Update fine information."""
    try:
        fine = selectors.get_fine_by_id(fine_id)
    except HostelFine.DoesNotExist:
        raise FineNotFoundError(f"Fine with ID {fine_id} not found.")

    for field, value in update_fields.items():
        setattr(fine, field, value)
    fine.save()
    return fine


@transaction.atomic
def update_fine_status_service(*, fine_id, new_status, user):
    """
    Update fine payment status per BR-HM-014.

    Only authorized staff can change status to 'Paid' after verification.
    """
    # Validate status
    if new_status not in [FineStatus.PENDING, FineStatus.PAID]:
        raise InvalidOperationError("Invalid fine status.")

    # BR-HM-014.b: Only authorized staff can change to Paid
    if new_status == FineStatus.PAID:
        mapping = resolve_user_hall_mapping_service(user=user, strict=True)
        if mapping.role not in [UserHostelMapping.ROLE_CARETAKER, UserHostelMapping.ROLE_WARDEN]:
            raise UnauthorizedAccessError("Only caretakers or wardens can mark fines as paid.")

    try:
        fine = selectors.get_fine_by_id(fine_id)
    except HostelFine.DoesNotExist:
        raise FineNotFoundError(f"Fine with ID {fine_id} not found.")

    # Ensure user has access to this fine's hall
    mapping = resolve_user_hall_mapping_service(user=user, strict=True)
    if fine.hall_id != mapping.hall_id:
        raise UnauthorizedAccessError("You can only update fines from your assigned hostel.")

    fine.status = new_status
    fine.save(update_fields=['status', 'updated_at'])

    return fine


@transaction.atomic
def delete_fine(*, fine_id: int):
    """Delete a fine."""
    try:
        fine = selectors.get_fine_by_id(fine_id)
    except HostelFine.DoesNotExist:
        raise FineNotFoundError(f"Fine with ID {fine_id} not found.")
    fine.delete()


# ══════════════════════════════════════════════════════════════
# INVENTORY SERVICES
# ══════════════════════════════════════════════════════════════

@transaction.atomic
def create_inventory_item(
    *,
    hall_id: int,
    inventory_name: str,
    cost: float,
    quantity: int
):
    """Create a new inventory item."""
    inventory = HostelInventory.objects.create(
        hall_id=hall_id,
        inventory_name=inventory_name,
        cost=cost,
        quantity=quantity
    )
    return inventory


@transaction.atomic
def update_inventory_item(*, inventory_id: int, **update_fields):
    """Update inventory item information."""
    try:
        inventory = selectors.get_inventory_by_id(inventory_id)
    except HostelInventory.DoesNotExist:
        raise InventoryNotFoundError(f"Inventory item with ID {inventory_id} not found.")

    for field, value in update_fields.items():
        setattr(inventory, field, value)
    inventory.save()
    return inventory


@transaction.atomic
def delete_inventory_item(*, inventory_id: int):
    """Delete an inventory item."""
    try:
        inventory = selectors.get_inventory_by_id(inventory_id)
    except HostelInventory.DoesNotExist:
        raise InventoryNotFoundError(f"Inventory item with ID {inventory_id} not found.")
    inventory.delete()


# ══════════════════════════════════════════════════════════════
# WORKER REPORT SERVICES
# ══════════════════════════════════════════════════════════════

@transaction.atomic
def create_worker_report(
    *,
    hall,
    worker_id: str,
    worker_name: str,
    year: int,
    month: int,
    absent: int,
    total_day: int,
    remark: str
):
    """Create a worker report entry."""
    report = WorkerReport.objects.create(
        hall=hall,
        worker_id=worker_id,
        worker_name=worker_name,
        year=year,
        month=month,
        absent=absent,
        total_day=total_day,
        remark=remark
    )
    return report


# ══════════════════════════════════════════════════════════════
# STUDENT DETAILS SERVICES (for updating extended info)
# ══════════════════════════════════════════════════════════════

@transaction.atomic
def update_student_details(*, student_id: str, **update_fields):
    """Update extended student details."""
    try:
        student_details = selectors.get_student_details_by_id(student_id)
        for field, value in update_fields.items():
            setattr(student_details, field, value)
        student_details.save()
        return student_details
    except StudentDetails.DoesNotExist:
        # Create if doesn't exist
        return StudentDetails.objects.create(id=student_id, **update_fields)


@transaction.atomic
def remove_student_from_hostel(*, student_id: str):
    """Remove a student from hostel (set hall_no to 0)."""
    try:
        student = selectors.get_student_by_id(student_id)
    except Student.DoesNotExist:
        raise StudentNotFoundError(f"Student with ID {student_id} not found.")

    student.hall_no = 0
    student.save(update_fields=['hall_no'])
    return student
