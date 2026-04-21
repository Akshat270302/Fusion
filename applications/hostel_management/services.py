"""
Services - All business logic and write operations for hostel management.

This module contains ALL business logic, validation, and write operations.
For reads, this module calls selectors. It NEVER uses .objects. for reads.
"""

from django.db import transaction
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import datetime, date, timedelta
from decimal import Decimal
import re

from applications.globals.models import Staff, Faculty, HoldsDesignation
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
    ExtendedStay,
    RoomVacationRequest,
    RoomVacationChecklistItem,
    HostelGeneratedReport,
    HostelReportFilterTemplate,
    HostelReportAttachment,
    HostelReportAuditLog,
    HostelTransactionHistory,
    HostelHistory,
    BookingStatus,
    LeaveStatus,
    FineStatus,
    ComplaintStatus,
    FineCategory,
    RoomChangeRequestStatus,
    ExtendedStayStatusChoices,
    VacationRequestStatusChoices,
    ChecklistVerificationStatus,
    HostelReportTypeChoices,
    HostelReportStatusChoices,
    HostelReportPriorityChoices,
    ReviewDecisionStatus,
    RoomAllocationStatus,
    RoomStatus,
    RoomType,
    AttendanceStatus,
    InventoryConditionStatus,
    InventoryRequestType,
    WorkflowStatus,
    HostelOperationalStatus,
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


class RoomChangeRequestNotFoundError(HostelManagementError):
    """Room change request does not exist."""
    pass


class BookingNotFoundError(HostelManagementError):
    """Booking does not exist."""
    pass


class LeaveNotFoundError(HostelManagementError):
    """Leave application does not exist."""
    pass


class ExtendedStayRequestNotFoundError(HostelManagementError):
    """Extended stay request does not exist."""
    pass


class RoomVacationRequestNotFoundError(HostelManagementError):
    """Room vacation request does not exist."""
    pass


class FineNotFoundError(HostelManagementError):
    """Fine does not exist."""
    pass


class InventoryNotFoundError(HostelManagementError):
    """Inventory item does not exist."""
    pass


class InventoryRequestNotFoundError(HostelManagementError):
    """Inventory resource request does not exist."""
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


class HostelReportNotFoundError(HostelManagementError):
    """Hostel report does not exist."""
    pass


class HostelReportValidationError(HostelManagementError):
    """Hostel report input is invalid."""
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


def resolve_hostel_rbac_role_service(*, user):
    """Resolve canonical hostel RBAC role for authenticated user."""
    if user.is_superuser:
        return 'super_admin', None

    designation_is_super_admin = HoldsDesignation.objects.filter(working=user).filter(
        designation__name__in=['super_admin', 'SuperAdmin']
    ).exists()
    if designation_is_super_admin:
        return 'super_admin', None

    mapping = resolve_user_hall_mapping_service(user=user, strict=False)
    if not mapping:
        return 'other', None
    return mapping.role, mapping


def _get_required_hall_for_super_admin(*, hall_id: str):
    """Resolve hall by hall_id for super-admin scoped dashboards/actions."""
    normalized_hall_id = (hall_id or '').strip()
    if not normalized_hall_id:
        raise InvalidOperationError('hall_id is required for super admin requests.')

    hall = selectors.get_hall_by_hall_id_or_none(normalized_hall_id)
    if not hall:
        raise InvalidOperationError('Invalid hall_id provided.')
    return hall


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


def _normalize_booking_status(status_value: str) -> str:
    """Normalize status aliases to canonical booking statuses."""
    status_value = (status_value or '').strip()
    if not status_value:
        return status_value

    alias_map = {
        'Confirmed': BookingStatus.APPROVED,
        'Complete': BookingStatus.COMPLETED,
    }
    return alias_map.get(status_value, status_value)


def _resolve_student_booking_context(*, user):
    """Resolve student role and mapped hall for booking workflow."""
    mapping = resolve_user_hall_mapping_service(user=user, strict=True)
    if mapping.role != UserHostelMapping.ROLE_STUDENT:
        raise UnauthorizedAccessError('Only students can manage guest room requests.')
    return mapping


def _resolve_caretaker_booking_context(*, user):
    """Resolve caretaker role and mapped hall for booking workflow."""
    mapping = resolve_user_hall_mapping_service(user=user, strict=True)
    if mapping.role != UserHostelMapping.ROLE_CARETAKER:
        raise UnauthorizedAccessError('Only caretaker can manage guest room requests.')

    caretaker = selectors.get_staff_by_extrainfo_id(user.extrainfo.id)
    if not caretaker:
        raise UnauthorizedAccessError('Caretaker profile not found for current user.')
    return mapping, caretaker


def _get_or_create_guest_room_policy(*, hall):
    policy, _ = selectors.get_or_create_guest_room_policy_by_hall(hall=hall)
    return policy


def _validate_booking_dates(*, start_date: date, end_date: date, policy):
    """Validate booking dates against configured policy."""
    if end_date <= start_date:
        raise InvalidOperationError('Check-out date must be after check-in date.')

    today = timezone.now().date()
    advance_days = (start_date - today).days
    duration_days = (end_date - start_date).days

    if advance_days < policy.min_advance_days:
        raise InvalidOperationError(
            f'Booking must be requested at least {policy.min_advance_days} day(s) in advance.'
        )

    if advance_days > policy.max_advance_days:
        raise InvalidOperationError(
            f'Booking cannot be requested more than {policy.max_advance_days} day(s) in advance.'
        )

    if duration_days > policy.max_booking_duration_days:
        raise InvalidOperationError(
            f'Booking duration cannot exceed {policy.max_booking_duration_days} day(s).'
        )


def _calculate_booking_charge(*, policy, start_date: date, end_date: date, rooms_required: int) -> Decimal:
    """Calculate booking total from policy and duration."""
    days = max((end_date - start_date).days, 1)
    charge_per_day = Decimal(str(policy.charge_per_day or 0))
    return charge_per_day * Decimal(days) * Decimal(rooms_required)


def _get_room_capacity_by_type(room_type: str) -> int:
    room_type = (room_type or '').strip().lower()
    return {
        RoomType.SINGLE: 1,
        RoomType.DOUBLE: 2,
        RoomType.TRIPLE: 3,
    }.get(room_type, 1)


def checkGuestRoomAvailabilityService(
    *,
    user,
    start_date: date,
    end_date: date,
    room_type: str,
    rooms_required: int = 1,
):
    """Check available guest rooms for student's mapped hall and selected period."""
    mapping = _resolve_student_booking_context(user=user)
    policy = _get_or_create_guest_room_policy(hall=mapping.hall)

    if not policy.feature_enabled:
        raise InvalidOperationError('Guest room booking feature is currently disabled for this hostel.')

    _validate_booking_dates(start_date=start_date, end_date=end_date, policy=policy)

    if rooms_required <= 0:
        raise InvalidOperationError('rooms_required must be at least 1.')

    candidate_rooms = selectors.get_guest_rooms_by_hall_and_type(hall=mapping.hall, room_type=room_type)
    available_rooms = []
    for room in candidate_rooms:
        if room.room_status != RoomStatus.AVAILABLE:
            continue

        overlapping = selectors.get_overlapping_bookings_for_room(
            hall=mapping.hall,
            guest_room_id=str(room.id),
            start_date=start_date,
            end_date=end_date,
        )
        if overlapping.exists():
            continue

        available_rooms.append(room)

    total_days = max((end_date - start_date).days, 1)
    charge_per_day = Decimal(str(policy.charge_per_day or 0))
    estimated_total = charge_per_day * Decimal(total_days) * Decimal(rooms_required)

    return {
        'hall_id': mapping.hall.hall_id,
        'hall_name': mapping.hall.hall_name,
        'available_count': len(available_rooms),
        'rooms_required': rooms_required,
        'is_available': len(available_rooms) >= rooms_required,
        'rooms': [
            {
                'id': room.id,
                'room': room.room,
                'room_type': room.room_type,
                'room_status': room.room_status,
            }
            for room in available_rooms
        ],
        'policy': {
            'charge_per_day': float(charge_per_day),
            'min_advance_days': policy.min_advance_days,
            'max_advance_days': policy.max_advance_days,
            'max_booking_duration_days': policy.max_booking_duration_days,
            'max_concurrent_bookings_per_student': policy.max_concurrent_bookings_per_student,
        },
        'estimated_total_charge': float(estimated_total),
    }


@transaction.atomic
def submitGuestRoomBookingService(
    *,
    user,
    guest_name: str,
    guest_phone: str,
    guest_email: str,
    guest_address: str,
    rooms_required: int,
    total_guest: int,
    purpose: str,
    arrival_date: date,
    arrival_time,
    departure_date: date,
    departure_time,
    nationality: str,
    room_type: str,
):
    """Submit a guest room booking request by student."""
    mapping = _resolve_student_booking_context(user=user)
    policy = _get_or_create_guest_room_policy(hall=mapping.hall)

    if not policy.feature_enabled:
        raise InvalidOperationError('Guest room booking feature is currently disabled for this hostel.')

    guest_name = (guest_name or '').strip()
    guest_phone = (guest_phone or '').strip()
    purpose = (purpose or '').strip()

    if not guest_name:
        raise InvalidOperationError('Guest name is required.')
    if not guest_phone:
        raise InvalidOperationError('Guest contact number is required.')
    if not purpose:
        raise InvalidOperationError('Purpose/reason is required.')

    if rooms_required <= 0:
        raise InvalidOperationError('rooms_required must be at least 1.')

    _validate_booking_dates(start_date=arrival_date, end_date=departure_date, policy=policy)

    per_room_capacity = _get_room_capacity_by_type(room_type)
    if total_guest > rooms_required * per_room_capacity:
        raise InvalidOperationError('Number of guests exceeds selected room capacity.')

    active_bookings_count = selectors.get_student_active_bookings(user=user, hall=mapping.hall).count()
    if active_bookings_count >= policy.max_concurrent_bookings_per_student:
        raise InvalidOperationError(
            'Maximum concurrent booking limit reached for this hostel policy.'
        )

    availability = checkGuestRoomAvailabilityService(
        user=user,
        start_date=arrival_date,
        end_date=departure_date,
        room_type=room_type,
        rooms_required=rooms_required,
    )
    if not availability['is_available']:
        raise RoomNotAvailableError('No rooms available for selected dates. Try alternate dates.')

    total_charge = _calculate_booking_charge(
        policy=policy,
        start_date=arrival_date,
        end_date=departure_date,
        rooms_required=rooms_required,
    )

    booking = GuestRoomBooking.objects.create(
        hall=mapping.hall,
        intender=user,
        guest_name=guest_name,
        guest_phone=guest_phone,
        guest_email=(guest_email or '').strip(),
        guest_address=(guest_address or '').strip(),
        rooms_required=rooms_required,
        total_guest=total_guest,
        purpose=purpose,
        arrival_date=arrival_date,
        arrival_time=arrival_time,
        departure_date=departure_date,
        departure_time=departure_time,
        nationality=(nationality or '').strip(),
        room_type=room_type,
        status=BookingStatus.PENDING,
        booking_charge_per_day=policy.charge_per_day,
        total_charge=total_charge,
    )

    hall_caretaker = selectors.get_caretaker_by_hall(mapping.hall)
    if hall_caretaker and hall_caretaker.staff and hall_caretaker.staff.id and hall_caretaker.staff.id.user:
        try:
            from notification.views import hostel_notifications
            hostel_notifications(sender=user, recipient=hall_caretaker.staff.id.user, type='guestRoom_request')
        except Exception:
            pass

    return booking


def getStudentGuestBookingsService(*, user):
    """Get booking history for authenticated student."""
    _resolve_student_booking_context(user=user)
    return selectors.get_bookings_by_user(user)


def getStudentGuestBookingDetailService(*, user, booking_id: int):
    """Get a single booking detail for authenticated student."""
    _resolve_student_booking_context(user=user)
    return selectors.get_booking_by_id_and_user(booking_id=booking_id, user=user)


@transaction.atomic
def modifyGuestRoomBookingService(
    *,
    user,
    booking_id: int,
    guest_name: str,
    guest_phone: str,
    guest_email: str,
    guest_address: str,
    rooms_required: int,
    total_guest: int,
    purpose: str,
    arrival_date: date,
    arrival_time,
    departure_date: date,
    departure_time,
    nationality: str,
    room_type: str,
):
    """Modify pending booking request by student and keep it in pending queue."""
    mapping = _resolve_student_booking_context(user=user)
    booking = selectors.get_booking_by_id_and_user(booking_id=booking_id, user=user)

    if booking.hall_id != mapping.hall_id:
        raise UnauthorizedAccessError('Booking does not belong to your hostel.')
    if booking.status != BookingStatus.PENDING:
        raise InvalidOperationError('Only pending requests can be modified.')

    policy = _get_or_create_guest_room_policy(hall=mapping.hall)
    _validate_booking_dates(start_date=arrival_date, end_date=departure_date, policy=policy)

    capacity = _get_room_capacity_by_type(room_type)
    if total_guest > rooms_required * capacity:
        raise InvalidOperationError('Number of guests exceeds selected room capacity.')

    availability = checkGuestRoomAvailabilityService(
        user=user,
        start_date=arrival_date,
        end_date=departure_date,
        room_type=room_type,
        rooms_required=rooms_required,
    )
    if not availability['is_available']:
        raise RoomNotAvailableError('No rooms available for selected dates. Try alternate dates.')

    booking.guest_name = (guest_name or '').strip()
    booking.guest_phone = (guest_phone or '').strip()
    booking.guest_email = (guest_email or '').strip()
    booking.guest_address = (guest_address or '').strip()
    booking.rooms_required = rooms_required
    booking.total_guest = total_guest
    booking.purpose = (purpose or '').strip()
    booking.arrival_date = arrival_date
    booking.arrival_time = arrival_time
    booking.departure_date = departure_date
    booking.departure_time = departure_time
    booking.nationality = (nationality or '').strip()
    booking.room_type = room_type
    booking.status = BookingStatus.PENDING
    booking.modified_count = booking.modified_count + 1
    booking.last_modified_at = timezone.now()
    booking.total_charge = _calculate_booking_charge(
        policy=policy,
        start_date=arrival_date,
        end_date=departure_date,
        rooms_required=rooms_required,
    )
    booking.save()

    hall_caretaker = selectors.get_caretaker_by_hall(mapping.hall)
    if hall_caretaker and hall_caretaker.staff and hall_caretaker.staff.id and hall_caretaker.staff.id.user:
        try:
            from notification.views import hostel_notifications
            hostel_notifications(sender=user, recipient=hall_caretaker.staff.id.user, type='guestRoom_modified')
        except Exception:
            pass

    return booking


@transaction.atomic
def cancelGuestRoomBookingService(*, user, booking_id: int, cancel_reason: str = ''):
    """Cancel booking by student before check-in date."""
    _resolve_student_booking_context(user=user)
    booking = selectors.get_booking_by_id_and_user(booking_id=booking_id, user=user)

    allowed_statuses = [
        BookingStatus.PENDING,
        BookingStatus.APPROVED,
        BookingStatus.CONFIRMED,
    ]
    if booking.status not in allowed_statuses:
        raise InvalidOperationError('Only pending/approved bookings can be cancelled.')

    today = timezone.now().date()
    if booking.arrival_date <= today:
        raise InvalidOperationError('Booking cannot be cancelled on/after check-in date.')

    previous_status = booking.status
    booking.status = BookingStatus.CANCELED
    booking.cancel_reason = (cancel_reason or '').strip()
    booking.canceled_at = timezone.now()
    booking.save(update_fields=['status', 'cancel_reason', 'canceled_at', 'updated_at'])

    if previous_status in [BookingStatus.APPROVED, BookingStatus.CONFIRMED] and booking.guest_room_id:
        room = GuestRoom.objects.filter(id=booking.guest_room_id, hall=booking.hall).first()
        if room:
            room.vacant = True
            room.occupied_till = None
            room.room_status = RoomStatus.AVAILABLE
            room.save(update_fields=['vacant', 'occupied_till', 'room_status'])

    hall_caretaker = selectors.get_caretaker_by_hall(booking.hall)
    if hall_caretaker and hall_caretaker.staff and hall_caretaker.staff.id and hall_caretaker.staff.id.user:
        try:
            from notification.views import hostel_notifications
            hostel_notifications(sender=user, recipient=hall_caretaker.staff.id.user, type='guestRoom_cancelled')
        except Exception:
            pass

    return booking


def getCaretakerPendingGuestBookingsService(*, user):
    """Get pending booking queue for caretaker's assigned hall."""
    mapping, _ = _resolve_caretaker_booking_context(user=user)
    return selectors.get_bookings_by_hall(
        hall=mapping.hall,
        statuses=[BookingStatus.PENDING],
    )


@transaction.atomic
def decideGuestRoomBookingService(*, user, booking_id: int, decision: str, guest_room_id: int = None, comment: str = ''):
    """Caretaker approves or rejects a pending booking request."""
    mapping, caretaker = _resolve_caretaker_booking_context(user=user)

    try:
        booking = selectors.get_booking_by_id(booking_id)
    except GuestRoomBooking.DoesNotExist:
        raise BookingNotFoundError(f'Booking with ID {booking_id} not found.')

    if booking.hall_id != mapping.hall_id:
        raise UnauthorizedAccessError('Booking does not belong to your hostel.')
    if booking.status != BookingStatus.PENDING:
        raise InvalidOperationError('Only pending requests can be approved/rejected.')

    normalized_decision = (decision or '').strip().lower()
    if normalized_decision not in ['approved', 'rejected']:
        raise InvalidOperationError('decision must be either approved or rejected.')

    booking.decision_by = caretaker
    booking.decision_comment = (comment or '').strip()
    booking.decision_at = timezone.now()

    if normalized_decision == 'approved':
        if not guest_room_id:
            raise InvalidOperationError('guest_room_id is required for approval.')

        room = None
        try:
            room = selectors.get_guest_room_by_id(int(guest_room_id))
        except Exception:
            room = selectors.get_guest_room_by_hall_and_room_label(
                hall=mapping.hall,
                room_label=str(guest_room_id),
            )
        if not room:
            raise RoomNotFoundError('Selected guest room was not found.')
        if room.hall_id != mapping.hall_id:
            raise UnauthorizedAccessError('Selected room does not belong to your hostel.')
        if room.room_status != RoomStatus.AVAILABLE:
            raise RoomNotAvailableError('Selected room is not available for booking.')

        overlapping = selectors.get_overlapping_bookings_for_room(
            hall=mapping.hall,
            guest_room_id=str(room.id),
            start_date=booking.arrival_date,
            end_date=booking.departure_date,
        )
        if overlapping.exists():
            raise RoomNotAvailableError('Selected room is already booked for the requested dates.')

        booking.status = BookingStatus.APPROVED
        booking.guest_room_id = str(room.id)
        booking.rejection_reason = ''
        booking.save()

        room.vacant = False
        room.occupied_till = booking.departure_date
        room.room_status = RoomStatus.BOOKED
        room.save(update_fields=['vacant', 'occupied_till', 'room_status'])

        try:
            from notification.views import hostel_notifications
            hostel_notifications(sender=user, recipient=booking.intender, type='guestRoom_accept')
        except Exception:
            pass
    else:
        if not comment:
            raise InvalidOperationError('Rejection reason/comment is required.')

        booking.status = BookingStatus.REJECTED
        booking.rejection_reason = comment.strip()
        booking.guest_room_id = ''
        booking.save()

        try:
            from notification.views import hostel_notifications
            hostel_notifications(sender=user, recipient=booking.intender, type='guestRoom_reject')
        except Exception:
            pass

    return booking


def getCaretakerBookingsByStatusService(*, user, statuses):
    """Get caretaker hall bookings filtered by statuses."""
    mapping, _ = _resolve_caretaker_booking_context(user=user)
    normalized = [_normalize_booking_status(value) for value in statuses]
    return selectors.get_bookings_by_hall(hall=mapping.hall, statuses=normalized)


@transaction.atomic
def checkInGuestBookingService(*, user, booking_id: int, id_proof_type: str, id_proof_number: str, notes: str = ''):
    """Caretaker checks in a guest for an approved booking."""
    mapping, caretaker = _resolve_caretaker_booking_context(user=user)
    try:
        booking = selectors.get_booking_by_id(booking_id)
    except GuestRoomBooking.DoesNotExist:
        raise BookingNotFoundError(f'Booking with ID {booking_id} not found.')

    if booking.hall_id != mapping.hall_id:
        raise UnauthorizedAccessError('Booking does not belong to your hostel.')
    if booking.status not in [BookingStatus.APPROVED, BookingStatus.CONFIRMED]:
        raise InvalidOperationError('Only approved bookings can be checked in.')
    if not booking.guest_room_id:
        raise InvalidOperationError('No room has been assigned for this booking.')
    if not id_proof_type or not id_proof_number:
        raise InvalidOperationError('Guest identity proof type and number are required.')

    room = GuestRoom.objects.filter(id=booking.guest_room_id, hall=booking.hall).first()
    if not room:
        raise RoomNotFoundError('Assigned guest room not found.')

    booking.status = BookingStatus.CHECKED_IN
    booking.checked_in_at = timezone.now()
    booking.checked_in_by = caretaker
    booking.id_proof_type = id_proof_type.strip()
    booking.id_proof_number = id_proof_number.strip()
    booking.checkin_notes = (notes or '').strip()
    booking.save()

    room.room_status = RoomStatus.CHECKED_IN
    room.vacant = False
    room.save(update_fields=['room_status', 'vacant'])
    return booking


@transaction.atomic
def checkOutGuestBookingService(
    *,
    user,
    booking_id: int,
    inspection_notes: str = '',
    damage_report: str = '',
    damage_amount=0,
):
    """Caretaker checks out guest, releases room, and optionally imposes damage fine."""
    mapping, caretaker = _resolve_caretaker_booking_context(user=user)
    try:
        booking = selectors.get_booking_by_id(booking_id)
    except GuestRoomBooking.DoesNotExist:
        raise BookingNotFoundError(f'Booking with ID {booking_id} not found.')

    if booking.hall_id != mapping.hall_id:
        raise UnauthorizedAccessError('Booking does not belong to your hostel.')
    if booking.status != BookingStatus.CHECKED_IN:
        raise InvalidOperationError('Only checked-in bookings can be checked out.')

    try:
        damage_amount_value = Decimal(str(damage_amount or 0))
    except Exception:
        raise InvalidOperationError('damage_amount must be a valid number.')

    booking.checked_out_at = timezone.now()
    booking.checked_out_by = caretaker
    booking.inspection_notes = (inspection_notes or '').strip()
    booking.damage_report = (damage_report or '').strip()
    booking.damage_amount = damage_amount_value
    booking.completed_with_damages = damage_amount_value > 0
    booking.status = BookingStatus.COMPLETED
    booking.save()

    room = GuestRoom.objects.filter(id=booking.guest_room_id, hall=booking.hall).first()
    if room:
        room.vacant = True
        room.occupied_till = None
        room.room_status = RoomStatus.AVAILABLE
        room.save(update_fields=['vacant', 'occupied_till', 'room_status'])

    if damage_amount_value > 0:
        student = selectors.get_student_by_username_or_none(booking.intender.username)
        if student:
            HostelFine.objects.create(
                student=student,
                caretaker=caretaker,
                hall=mapping.hall,
                student_name=(booking.intender.get_full_name() or booking.intender.username).strip(),
                amount=damage_amount_value,
                category=FineCategory.DAMAGE,
                status=FineStatus.PENDING,
                reason=(booking.damage_report or 'Damage reported during guest room checkout.').strip(),
            )
            try:
                from notification.views import hostel_notifications
                hostel_notifications(sender=user, recipient=booking.intender, type='fine_imposed')
            except Exception:
                pass

    try:
        from notification.views import hostel_notifications
        hostel_notifications(sender=user, recipient=booking.intender, type='guestRoom_checkout')
    except Exception:
        pass

    return booking


def getGuestRoomPolicyService(*, user):
    """Get configured guest room policy for caretaker's hall."""
    mapping, _ = _resolve_caretaker_booking_context(user=user)
    return _get_or_create_guest_room_policy(hall=mapping.hall)


@transaction.atomic
def upsertGuestRoomPolicyService(
    *,
    user,
    feature_enabled: bool,
    charge_per_day,
    min_advance_days: int,
    max_advance_days: int,
    max_booking_duration_days: int,
    max_concurrent_bookings_per_student: int,
    eligibility_note: str = '',
):
    """Create/update guest room policy for caretaker's hall."""
    mapping, _ = _resolve_caretaker_booking_context(user=user)
    policy = _get_or_create_guest_room_policy(hall=mapping.hall)

    if max_advance_days < min_advance_days:
        raise InvalidOperationError('max_advance_days must be >= min_advance_days.')
    if max_booking_duration_days <= 0:
        raise InvalidOperationError('max_booking_duration_days must be > 0.')
    if max_concurrent_bookings_per_student <= 0:
        raise InvalidOperationError('max_concurrent_bookings_per_student must be > 0.')

    try:
        charge_value = Decimal(str(charge_per_day))
    except Exception:
        raise InvalidOperationError('charge_per_day must be a valid number.')
    if charge_value < 0:
        raise InvalidOperationError('charge_per_day cannot be negative.')

    policy.feature_enabled = bool(feature_enabled)
    policy.charge_per_day = charge_value
    policy.min_advance_days = min_advance_days
    policy.max_advance_days = max_advance_days
    policy.max_booking_duration_days = max_booking_duration_days
    policy.max_concurrent_bookings_per_student = max_concurrent_bookings_per_student
    policy.eligibility_note = (eligibility_note or '').strip()
    policy.save()
    return policy


def getGuestRoomBookingReportService(*, user, start_date: date, end_date: date):
    """Generate aggregated guest room booking report for caretaker hall."""
    mapping, _ = _resolve_caretaker_booking_context(user=user)
    if end_date < start_date:
        raise InvalidOperationError('end_date must be greater than or equal to start_date.')

    bookings = selectors.get_bookings_by_hall_and_date_range(
        hall=mapping.hall,
        start_date=start_date,
        end_date=end_date,
    )

    status_counts = {}
    total_revenue = Decimal('0')
    damages_total = Decimal('0')
    for booking in bookings:
        status_key = _normalize_booking_status(booking.status)
        status_counts[status_key] = status_counts.get(status_key, 0) + 1
        total_revenue += Decimal(str(booking.total_charge or 0))
        damages_total += Decimal(str(booking.damage_amount or 0))

    return {
        'hall_id': mapping.hall.hall_id,
        'hall_name': mapping.hall.hall_name,
        'from': start_date.isoformat(),
        'to': end_date.isoformat(),
        'total_bookings': len(bookings),
        'status_breakdown': status_counts,
        'revenue_generated': float(total_revenue),
        'damage_fines_total': float(damages_total),
        'bookings': [
            {
                'booking_id': booking.id,
                'student': booking.intender.username,
                'guest_name': booking.guest_name,
                'room_id': booking.guest_room_id,
                'arrival_date': booking.arrival_date.isoformat(),
                'departure_date': booking.departure_date.isoformat(),
                'status': _normalize_booking_status(booking.status),
                'total_charge': float(booking.total_charge or 0),
                'damage_amount': float(booking.damage_amount or 0),
            }
            for booking in bookings
        ],
    }


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
    parsed_start = datetime.strptime(start_time, '%H:%M').time()
    parsed_end = datetime.strptime(end_time, '%H:%M').time()
    shift_label = _infer_shift_label(day=day, start_time=parsed_start, end_time=parsed_end)

    if existing_schedule:
        existing_schedule.hall = hall
        existing_schedule.day = day
        existing_schedule.start_time = parsed_start
        existing_schedule.end_time = parsed_end
        existing_schedule.staff_type = staff_type
        existing_schedule.shift_label = shift_label
        existing_schedule.save(update_fields=['hall', 'day', 'start_time', 'end_time', 'staff_type', 'shift_label'])
        return existing_schedule
    else:
        schedule = StaffSchedule.objects.create(
            hall=hall,
            staff_id=staff_id,
            day=day,
            staff_type=staff_type,
            shift_label=shift_label,
            start_time=parsed_start,
            end_time=parsed_end,
        )
        return schedule


@transaction.atomic
def delete_staff_schedule(*, staff_id):
    """Delete a staff schedule."""
    schedule = selectors.get_schedule_by_staff_id(staff_id)
    if schedule:
        schedule.delete()


GUARD_DUTY_CONCERN_PREFIX = '[Guard Duty]'
GUARD_DUTY_ALLOWED_DAYS = {
    'Monday',
    'Tuesday',
    'Wednesday',
    'Thursday',
    'Friday',
    'Saturday',
    'Sunday',
}


def _normalize_guard_day(day: str) -> str:
    normalized = str(day or '').strip().capitalize()
    if normalized not in GUARD_DUTY_ALLOWED_DAYS:
        raise InvalidOperationError('Invalid day provided for guard duty schedule.')
    return normalized


def _parse_guard_time(value, field_name: str):
    if isinstance(value, datetime):
        return value.time()
    if hasattr(value, 'hour') and hasattr(value, 'minute'):
        return value
    try:
        return datetime.strptime(str(value), '%H:%M').time()
    except Exception:
        raise InvalidOperationError(f'Invalid {field_name}. Use HH:MM format.')


def _infer_shift_label(*, day: str, start_time, end_time):
    start_hour = int(getattr(start_time, 'hour', 0))
    end_hour = int(getattr(end_time, 'hour', 0))

    if 5 <= start_hour < 12:
        base = 'Morning'
    elif 12 <= start_hour < 18:
        base = 'Evening'
    else:
        base = 'Night'

    if end_hour <= start_hour:
        base = 'Night'

    return f'{base} Shift ({day})'


def _serialize_guard_schedule(schedule):
    return {
        'id': schedule.id,
        'hall_id': schedule.hall.hall_id,
        'hall_name': schedule.hall.hall_name,
        'staff_id': schedule.staff_id.id.id,
        'staff_username': schedule.staff_id.id.user.username,
        'staff_name': schedule.staff_id.id.user.username,
        'staff_type': schedule.staff_type,
        'day': schedule.day,
        'start_time': schedule.start_time.strftime('%H:%M') if schedule.start_time else None,
        'end_time': schedule.end_time.strftime('%H:%M') if schedule.end_time else None,
    }


def _serialize_guard_concern(complaint):
    return {
        'id': complaint.id,
        'hall_id': complaint.hall.hall_id if complaint.hall else None,
        'hall_name': complaint.hall.hall_name if complaint.hall else None,
        'subject': complaint.title.replace(f'{GUARD_DUTY_CONCERN_PREFIX} ', '', 1),
        'message': complaint.description,
        'status': complaint.status,
        'raised_by': complaint.escalated_by.username if complaint.escalated_by else None,
        'raised_at': complaint.escalated_at or complaint.created_at,
        'response_notes': complaint.resolution_notes,
        'resolved_by': complaint.resolved_by.username if complaint.resolved_by else None,
        'resolved_at': complaint.resolved_at,
        'created_at': complaint.created_at,
    }


def _get_guard_staff_pool():
    guard_user_ids = list(
        HoldsDesignation.objects.filter(
            designation__name__iregex=r'guard|security'
        ).values_list('working_id', flat=True)
    )

    staff_qs = Staff.objects.select_related('id__user').all()
    if guard_user_ids:
        scoped = staff_qs.filter(id__user__id__in=guard_user_ids)
        if scoped.exists():
            staff_qs = scoped

    return [
        {
            'staff_id': staff.id.id,
            'username': staff.id.user.username,
            'name': f'{staff.id.user.first_name} {staff.id.user.last_name}'.strip() or staff.id.user.username,
        }
        for staff in staff_qs.order_by('id__user__username')
    ]


def _assert_guard_schedule_overlap_conflicts(*, staff, day: str, start_time, end_time, exclude_schedule_id=None, override_policy=False):
    conflicts = StaffSchedule.objects.filter(
        staff_id=staff,
        day=day,
        staff_type__iexact='guard',
    )
    if exclude_schedule_id is not None:
        conflicts = conflicts.exclude(id=exclude_schedule_id)

    overlap_exists = False
    for existing in conflicts:
        if not existing.start_time or not existing.end_time:
            continue
        if start_time < existing.end_time and end_time > existing.start_time:
            overlap_exists = True
            break

    if overlap_exists and not override_policy:
        raise InvalidOperationError('Guard has overlapping duty timings. Enable override_policy to proceed.')

    if conflicts.count() >= 2 and not override_policy:
        raise InvalidOperationError('Guard already has multiple shifts for this day. Enable override_policy to proceed.')


def _resolve_guard_hall_context(*, user, hall_id: str = None, for_write: bool = False):
    role, mapping = resolve_hostel_rbac_role_service(user=user)
    if role == 'super_admin':
        hall = _get_required_hall_for_super_admin(hall_id=hall_id)
        return role, hall

    if for_write:
        raise UnauthorizedAccessError('Only super admin can assign or modify guard duty schedules.')

    if role not in [UserHostelMapping.ROLE_WARDEN, UserHostelMapping.ROLE_CARETAKER]:
        raise UnauthorizedAccessError('Only super admin, warden, or caretaker can access guard duty data.')
    if not mapping or not mapping.hall:
        raise UserHallMappingMissingError('Hostel mapping is not configured for this user.')

    return role, mapping.hall


def getGuardDutySchedulesService(*, user, hall_id: str = None, day: str = None):
    """Return guard duty schedules and security overview for a hall."""
    _, hall = _resolve_guard_hall_context(user=user, hall_id=hall_id, for_write=False)

    duty_qs = StaffSchedule.objects.filter(
        hall=hall,
        staff_type__iexact='guard',
    ).select_related('hall', 'staff_id__id__user').order_by('day', 'start_time', 'id')

    if day:
        duty_qs = duty_qs.filter(day=_normalize_guard_day(day))

    schedules = [_serialize_guard_schedule(entry) for entry in duty_qs]

    current_dt = timezone.now()
    if timezone.is_naive(current_dt):
        current_local_dt = current_dt
    else:
        current_local_dt = timezone.localtime(current_dt)

    weekday = current_local_dt.strftime('%A')
    now_time = current_local_dt.time()
    active_shifts = [
        entry for entry in duty_qs
        if entry.day == weekday
        and entry.start_time
        and entry.end_time
        and entry.start_time <= now_time < entry.end_time
    ]

    day_counts = {day_name: 0 for day_name in GUARD_DUTY_ALLOWED_DAYS}
    for entry in duty_qs:
        if entry.day in day_counts:
            day_counts[entry.day] += 1

    uncovered_days = [day_name for day_name, count in day_counts.items() if count == 0]

    return {
        'hall': {
            'hall_id': hall.hall_id,
            'hall_name': hall.hall_name,
        },
        'available_guards': _get_guard_staff_pool(),
        'schedules': schedules,
        'overview': {
            'total_guard_shifts': len(schedules),
            'active_guard_count': len(active_shifts),
            'active_shifts': [_serialize_guard_schedule(entry) for entry in active_shifts],
            'uncovered_days': uncovered_days,
            'coverage_by_day': day_counts,
            'critical_gap': len(active_shifts) == 0,
        },
    }


@transaction.atomic
def createGuardDutyScheduleService(*, user, hall_id: str, staff_id: int, day: str, start_time, end_time, override_policy: bool = False):
    """Create a guard duty schedule entry. Only super admin is allowed."""
    _, hall = _resolve_guard_hall_context(user=user, hall_id=hall_id, for_write=True)

    try:
        staff = selectors.get_staff_by_id(staff_id)
    except Staff.DoesNotExist:
        raise StaffNotFoundError('Guard staff not found.')

    normalized_day = _normalize_guard_day(day)
    parsed_start = _parse_guard_time(start_time, 'start_time')
    parsed_end = _parse_guard_time(end_time, 'end_time')
    if parsed_end <= parsed_start:
        raise InvalidOperationError('end_time must be after start_time.')
    shift_label = _infer_shift_label(day=normalized_day, start_time=parsed_start, end_time=parsed_end)

    _assert_guard_schedule_overlap_conflicts(
        staff=staff,
        day=normalized_day,
        start_time=parsed_start,
        end_time=parsed_end,
        override_policy=bool(override_policy),
    )

    schedule = StaffSchedule.objects.create(
        hall=hall,
        staff_id=staff,
        staff_type='Guard',
        shift_label=shift_label,
        day=normalized_day,
        start_time=parsed_start,
        end_time=parsed_end,
    )

    return _serialize_guard_schedule(schedule)


@transaction.atomic
def updateGuardDutyScheduleService(
    *,
    user,
    schedule_id: int,
    hall_id: str,
    staff_id=None,
    day: str = None,
    start_time=None,
    end_time=None,
    override_policy: bool = False,
):
    """Update an existing guard duty schedule entry. Only super admin is allowed."""
    _, hall = _resolve_guard_hall_context(user=user, hall_id=hall_id, for_write=True)

    try:
        schedule = StaffSchedule.objects.select_related('staff_id__id__user', 'hall').get(id=schedule_id)
    except StaffSchedule.DoesNotExist:
        raise InvalidOperationError('Guard duty schedule not found.')

    if schedule.hall_id != hall.id:
        raise UnauthorizedAccessError('Selected hall does not match this schedule entry.')

    new_staff = schedule.staff_id
    if staff_id is not None:
        try:
            new_staff = selectors.get_staff_by_id(staff_id)
        except Staff.DoesNotExist:
            raise StaffNotFoundError('Guard staff not found.')

    new_day = _normalize_guard_day(day or schedule.day)
    new_start = _parse_guard_time(start_time if start_time is not None else schedule.start_time, 'start_time')
    new_end = _parse_guard_time(end_time if end_time is not None else schedule.end_time, 'end_time')

    if new_end <= new_start:
        raise InvalidOperationError('end_time must be after start_time.')
    shift_label = _infer_shift_label(day=new_day, start_time=new_start, end_time=new_end)

    _assert_guard_schedule_overlap_conflicts(
        staff=new_staff,
        day=new_day,
        start_time=new_start,
        end_time=new_end,
        exclude_schedule_id=schedule.id,
        override_policy=bool(override_policy),
    )

    schedule.staff_id = new_staff
    schedule.day = new_day
    schedule.start_time = new_start
    schedule.end_time = new_end
    schedule.staff_type = 'Guard'
    schedule.shift_label = shift_label
    schedule.save(update_fields=['staff_id', 'day', 'start_time', 'end_time', 'staff_type', 'shift_label'])

    return _serialize_guard_schedule(schedule)


@transaction.atomic
def deleteGuardDutyScheduleService(*, user, schedule_id: int, hall_id: str):
    """Delete a guard duty schedule entry. Only super admin is allowed."""
    _, hall = _resolve_guard_hall_context(user=user, hall_id=hall_id, for_write=True)

    try:
        schedule = StaffSchedule.objects.get(id=schedule_id)
    except StaffSchedule.DoesNotExist:
        raise InvalidOperationError('Guard duty schedule not found.')

    if schedule.hall_id != hall.id:
        raise UnauthorizedAccessError('Selected hall does not match this schedule entry.')

    day_entries = StaffSchedule.objects.filter(
        hall=hall,
        day=schedule.day,
        staff_type__iexact='guard',
    ).count()
    if day_entries <= 1:
        raise InvalidOperationError('Cannot remove the last guard shift for this day. Coverage gap detected.')

    schedule.delete()


@transaction.atomic
def raiseGuardDutyConcernService(*, user, subject: str, message: str):
    """Allow warden/caretaker to raise guard-duty concerns for super admin."""
    role, mapping = resolve_hostel_rbac_role_service(user=user)
    if role not in [UserHostelMapping.ROLE_WARDEN, UserHostelMapping.ROLE_CARETAKER]:
        raise UnauthorizedAccessError('Only warden or caretaker can raise guard duty concerns.')
    if not mapping or not mapping.hall:
        raise UserHallMappingMissingError('Hostel mapping is not configured for this user.')

    normalized_subject = str(subject or '').strip()
    normalized_message = str(message or '').strip()
    if len(normalized_subject) < 3:
        raise InvalidOperationError('Concern subject must be at least 3 characters long.')
    if len(normalized_message) < 10:
        raise InvalidOperationError('Concern message must be at least 10 characters long.')

    concern = HostelComplaint.objects.create(
        student=None,
        hall=mapping.hall,
        title=f'{GUARD_DUTY_CONCERN_PREFIX} {normalized_subject}',
        description=normalized_message,
        status=ComplaintStatus.ESCALATED,
        escalation_reason='Guard duty concern raised for super admin review.',
        escalated_by=user,
        escalated_at=timezone.now(),
    )
    return _serialize_guard_concern(concern)


def listGuardDutyConcernsService(*, user, hall_id: str = None):
    """List guard-duty concerns for super admin or mapped hall users."""
    role, mapping = resolve_hostel_rbac_role_service(user=user)
    if role == 'super_admin':
        hall = _get_required_hall_for_super_admin(hall_id=hall_id)
    elif role in [UserHostelMapping.ROLE_WARDEN, UserHostelMapping.ROLE_CARETAKER]:
        if not mapping or not mapping.hall:
            raise UserHallMappingMissingError('Hostel mapping is not configured for this user.')
        hall = mapping.hall
    else:
        raise UnauthorizedAccessError('You are not authorized to view guard duty concerns.')

    concerns = HostelComplaint.objects.filter(
        hall=hall,
        title__startswith=GUARD_DUTY_CONCERN_PREFIX,
    ).select_related('hall', 'escalated_by', 'resolved_by').order_by('-created_at')

    return [_serialize_guard_concern(concern) for concern in concerns]


@transaction.atomic
def resolveGuardDutyConcernService(*, user, concern_id: int, hall_id: str, response_notes: str):
    """Resolve a guard-duty concern. Only super admin is allowed."""
    role, _ = resolve_hostel_rbac_role_service(user=user)
    if role != 'super_admin':
        raise UnauthorizedAccessError('Only super admin can resolve guard duty concerns.')

    hall = _get_required_hall_for_super_admin(hall_id=hall_id)

    try:
        concern = HostelComplaint.objects.select_related('hall').get(id=concern_id)
    except HostelComplaint.DoesNotExist:
        raise InvalidOperationError('Guard duty concern not found.')

    if not concern.title.startswith(GUARD_DUTY_CONCERN_PREFIX):
        raise InvalidOperationError('Provided concern is not a guard duty concern.')
    if concern.hall_id != hall.id:
        raise UnauthorizedAccessError('Selected hall does not match this concern.')

    notes = str(response_notes or '').strip()
    if len(notes) < 5:
        raise InvalidOperationError('Resolution notes must be at least 5 characters long.')

    concern.status = ComplaintStatus.RESOLVED
    concern.resolution_notes = notes
    concern.resolved_by = user
    concern.resolved_at = timezone.now()
    concern.save(update_fields=['status', 'resolution_notes', 'resolved_by', 'resolved_at', 'updated_at'])
    return _serialize_guard_concern(concern)


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


def getAllNoticesService(*, user=None, hall_id: str = None):
    """Return notices scoped to authenticated user's mapped hall."""
    if user is None:
        return selectors.get_all_notices()

    role, _ = resolve_hostel_rbac_role_service(user=user)
    if role == 'super_admin':
        hall = _get_required_hall_for_super_admin(hall_id=hall_id)
        return selectors.get_notices_by_hall(hall)

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

def _build_group_signature(*, students):
    usernames = sorted(st.id.user.username.strip().lower() for st in students)
    return '|'.join(usernames)


def _serialize_group(group):
    members = [
        {
            'student_id': membership.student.id.user.username,
            'full_name': (membership.student.id.user.get_full_name() or membership.student.id.user.username).strip(),
        }
        for membership in group.memberships.select_related('student__id__user').all().order_by('student__id__user__username')
    ]
    return {
        'group_id': group.id,
        'hall_id': group.hall.hall_id if group.hall else '',
        'members': members,
        'is_auto_generated': group.is_auto_generated,
        'room_number': (
            f"{group.allotted_room.block_no}-{group.allotted_room.room_no}"
            if group.allotted_room else ''
        ),
        'created_at': group.created_at.isoformat() if group.created_at else None,
    }


@transaction.atomic
def createStudentGroupService(*, user, member_roll_numbers):
    """Student creates a hostel group by adding 2 more members (self + 2)."""
    role, mapping = resolve_hostel_rbac_role_service(user=user)
    if role != UserHostelMapping.ROLE_STUDENT or not mapping:
        raise UnauthorizedAccessError('Only students can create groups.')

    student = selectors.get_student_by_extrainfo_or_none(user.extrainfo)
    if not student:
        raise StudentNotFoundError('Student profile not found for current user.')

    requested = [str(value).strip() for value in (member_roll_numbers or []) if str(value).strip()]
    if len(requested) != 2:
        raise InvalidOperationError('Exactly 2 roll numbers are required to form a group of 3.')

    group_roll_numbers = [user.username] + requested
    normalized_rolls = [value.lower() for value in group_roll_numbers]
    if len(set(normalized_rolls)) != 3:
        raise InvalidOperationError('Group members must be unique.')

    students = list(selectors.get_students_by_usernames(usernames=group_roll_numbers))
    student_by_username = {row.id.user.username.lower(): row for row in students}
    missing = [value for value in normalized_rolls if value not in student_by_username]
    if missing:
        raise StudentNotFoundError(f"Student(s) not found: {', '.join(sorted(set(missing)))}")

    selected_students = [student_by_username[key] for key in normalized_rolls]

    for member in selected_students:
        member_hall = _resolve_student_hall(student=member)
        if not member_hall or member_hall.id != mapping.hall_id:
            raise InvalidOperationError('All group members must belong to the same hostel.')
        existing_membership = selectors.get_group_membership_for_student(student=member)
        if existing_membership:
            raise InvalidOperationError(f"Student {member.id.user.username} is already part of a group.")

    signature = _build_group_signature(students=selected_students)
    existing_group = selectors.get_group_by_signature(hall=mapping.hall, member_signature=signature)
    if existing_group:
        raise InvalidOperationError('This group already exists.')

    group = HostelRoomGroup.objects.create(
        hall=mapping.hall,
        created_by=user,
        is_auto_generated=False,
        member_signature=signature,
    )
    HostelRoomGroupMember.objects.bulk_create(
        [HostelRoomGroupMember(group=group, student=member) for member in selected_students]
    )

    try:
        from notification.views import hostel_notifications

        for member in selected_students:
            hostel_notifications(sender=user, recipient=member.id.user, type='group_created')
    except Exception:
        pass

    group = HostelRoomGroup.objects.prefetch_related('memberships__student__id__user').get(id=group.id)
    return _serialize_group(group)

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
    roommates = []
    if allocation:
        roommate_allocations = StudentRoomAllocation.objects.filter(
            hall=allocation.hall,
            room=allocation.room,
            status=RoomAllocationStatus.ACTIVE,
        ).select_related('student__id__user')
        for item in roommate_allocations:
            if item.student_id == student.id:
                continue
            roommates.append(
                {
                    'student_id': item.student.id.user.username,
                    'full_name': (item.student.id.user.get_full_name() or item.student.id.user.username).strip(),
                }
            )

    membership = selectors.get_group_membership_for_student(student=student)
    return {
        'student_id': student.id.user.username,
        'room_number': student.room_no,
        'hostel_id': student_hall.hall_id,
        'hostel_name': student_hall.hall_name,
        'allocation_date': allocation.assigned_at.isoformat() if allocation else None,
        'status': allocation.status if allocation else 'unassigned',
        'roommates': roommates,
        'group_id': membership.group_id if membership else None,
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
# ROOM CHANGE REQUEST SERVICES (UC-013/014/015)
# ══════════════════════════════════════════════════════════════

def _serialize_room_change_request(request_obj):
    return {
        'id': request_obj.id,
        'request_id': request_obj.request_id,
        'student_username': request_obj.student.id.user.username,
        'student_name': request_obj.student.id.user.get_full_name() or request_obj.student.id.user.username,
        'hall_id': request_obj.hall.hall_id if request_obj.hall else '',
        'hall_name': request_obj.hall.hall_name if request_obj.hall else '',
        'current_room_no': request_obj.current_room_no,
        'current_hall_id': request_obj.current_hall_id,
        'reason': request_obj.reason,
        'preferred_room': request_obj.preferred_room,
        'preferred_hall': request_obj.preferred_hall,
        'status': request_obj.status,
        'caretaker_decision': request_obj.caretaker_decision,
        'caretaker_remarks': request_obj.caretaker_remarks,
        'caretaker_decided_at': request_obj.caretaker_decided_at.isoformat() if request_obj.caretaker_decided_at else None,
        'warden_decision': request_obj.warden_decision,
        'warden_remarks': request_obj.warden_remarks,
        'warden_decided_at': request_obj.warden_decided_at.isoformat() if request_obj.warden_decided_at else None,
        'allocated_room': (
            f"{request_obj.allocated_room.block_no}-{request_obj.allocated_room.room_no}"
            if request_obj.allocated_room else ''
        ),
        'allocation_notes': request_obj.allocation_notes,
        'allocated_at': request_obj.allocated_at.isoformat() if request_obj.allocated_at else None,
        'created_at': request_obj.created_at.isoformat() if request_obj.created_at else None,
    }


@transaction.atomic
def submitRoomChangeRequestService(*, user, reason: str, preferred_room: str = '', preferred_hall: str = ''):
    """Student submits room change request for current active allocation."""
    mapping = resolve_user_hall_mapping_service(user=user, strict=True)
    if mapping.role != UserHostelMapping.ROLE_STUDENT:
        raise UnauthorizedAccessError('Only students can submit room change requests.')

    reason_value = (reason or '').strip()
    if not reason_value:
        raise InvalidOperationError('reason is required.')

    student = selectors.get_student_by_extrainfo_or_none(user.extrainfo)
    if not student:
        raise StudentNotFoundError('Student profile not found for current user.')

    active_allocation = selectors.get_student_room_allocation_active(student=student)
    if not active_allocation:
        raise InvalidOperationError('No active room allocation found. You cannot request room change.')

    existing_pending = selectors.get_pending_room_change_by_student(student=student)
    if existing_pending:
        raise InvalidOperationError('You already have a pending room change request.')

    request_obj = RoomChangeRequest.objects.create(
        hall=mapping.hall,
        student=student,
        requested_by=user,
        current_room_no=student.room_no or '',
        current_hall_id=mapping.hall.hall_id,
        reason=reason_value,
        preferred_room=(preferred_room or '').strip(),
        preferred_hall=(preferred_hall or '').strip(),
        status=RoomChangeRequestStatus.PENDING,
        caretaker_decision=ReviewDecisionStatus.PENDING,
        warden_decision=ReviewDecisionStatus.PENDING,
    )

    caretaker = selectors.get_caretaker_by_hall(mapping.hall)
    warden = selectors.get_warden_by_hall(mapping.hall)
    try:
        from notification.views import hostel_notifications
        if caretaker and caretaker.staff and caretaker.staff.id and caretaker.staff.id.user:
            hostel_notifications(sender=user, recipient=caretaker.staff.id.user, type='roomChange_request')
        if warden and warden.faculty and warden.faculty.id and warden.faculty.id.user:
            hostel_notifications(sender=user, recipient=warden.faculty.id.user, type='roomChange_request')
    except Exception:
        pass

    return _serialize_room_change_request(request_obj)


def getMyRoomChangeRequestsService(*, user):
    """Student views own room change request history."""
    mapping = resolve_user_hall_mapping_service(user=user, strict=True)
    if mapping.role != UserHostelMapping.ROLE_STUDENT:
        raise UnauthorizedAccessError('Only students can view their room change requests.')

    student = selectors.get_student_by_extrainfo_or_none(user.extrainfo)
    if not student:
        raise StudentNotFoundError('Student profile not found for current user.')

    requests = selectors.get_room_change_requests_by_student(student=student)
    return [_serialize_room_change_request(item) for item in requests]


def getRoomChangeRequestsForReviewService(*, user, statuses=None):
    """Caretaker/Warden dashboard view for room change requests in own hall."""
    mapping = resolve_user_hall_mapping_service(user=user, strict=True)
    if mapping.role not in [UserHostelMapping.ROLE_CARETAKER, UserHostelMapping.ROLE_WARDEN]:
        raise UnauthorizedAccessError('Only caretaker/warden can view room change requests.')

    normalized_statuses = statuses or [
        RoomChangeRequestStatus.PENDING,
        RoomChangeRequestStatus.APPROVED,
    ]
    requests = selectors.get_room_change_requests_by_hall_and_status(
        hall=mapping.hall,
        statuses=normalized_statuses,
    )
    return [_serialize_room_change_request(item) for item in requests]


def _apply_room_change_review_decision(*, request_obj, decision: str, remarks: str):
    decision_value = (decision or '').strip().capitalize()
    remarks_value = (remarks or '').strip()
    if decision_value not in [ReviewDecisionStatus.APPROVED, ReviewDecisionStatus.REJECTED]:
        raise InvalidOperationError('decision must be Approved or Rejected.')
    if decision_value == ReviewDecisionStatus.REJECTED and not remarks_value:
        raise InvalidOperationError('remarks are required when rejecting a request.')
    return decision_value, remarks_value


def _pick_room_for_auto_room_change(*, request_obj):
    """Pick a target room for automatic post-approval allocation."""
    current_room_value = (request_obj.current_room_no or '').strip().lower()
    preferred_room_value = (request_obj.preferred_room or '').strip()

    if preferred_room_value:
        match = re.match(r'^\s*([A-Za-z])\s*[-]?\s*([0-9]+)\s*$', preferred_room_value)
        if match:
            block_no, room_no = match.group(1).upper(), match.group(2)
            preferred_room = selectors.get_room_by_hall_and_details(
                hall=request_obj.hall,
                block_no=block_no,
                room_no=room_no,
            )
            if preferred_room and preferred_room.room_occupied < preferred_room.room_cap:
                preferred_label = f"{preferred_room.block_no}-{preferred_room.room_no}".lower()
                if preferred_label != current_room_value:
                    return preferred_room

    candidates = selectors.get_available_rooms_by_hall(request_obj.hall).order_by('block_no', 'room_no', 'id')
    for room in candidates:
        room_label = f"{room.block_no}-{room.room_no}".lower()
        if room_label == current_room_value:
            continue
        return room

    return None


def _auto_allocate_after_dual_approval(*, request_obj):
    """Allocate room automatically once both caretaker and warden approve."""
    if request_obj.status != RoomChangeRequestStatus.APPROVED:
        return False
    if request_obj.caretaker_decision != ReviewDecisionStatus.APPROVED:
        return False
    if request_obj.warden_decision != ReviewDecisionStatus.APPROVED:
        return False
    if request_obj.allocated_room_id:
        return True

    caretaker = selectors.get_caretaker_by_hall(request_obj.hall)
    if not caretaker or not caretaker.staff or not caretaker.staff.id or not caretaker.staff.id.user:
        return False

    target_room = _pick_room_for_auto_room_change(request_obj=request_obj)
    if not target_room:
        return False

    allocation = assignRoomService(
        user=caretaker.staff.id.user,
        student_id=request_obj.student.id.user.username,
        room_id=target_room.id,
    )

    request_obj.allocated_room = allocation.room
    request_obj.allocation_notes = request_obj.allocation_notes or 'Auto allocated after dual approval.'
    request_obj.allocated_at = timezone.now()
    request_obj.status = RoomChangeRequestStatus.ALLOCATED
    request_obj.save(update_fields=['allocated_room', 'allocation_notes', 'allocated_at', 'status', 'updated_at'])
    return True


@transaction.atomic
def caretakerReviewRoomChangeRequestService(*, user, room_change_request_id: int, decision: str, remarks: str = ''):
    """Caretaker reviews room change request as first reviewer."""
    mapping = resolve_user_hall_mapping_service(user=user, strict=True)
    if mapping.role != UserHostelMapping.ROLE_CARETAKER:
        raise UnauthorizedAccessError('Only caretaker can submit caretaker review decision.')

    try:
        request_obj = selectors.get_room_change_request_by_id(request_id=room_change_request_id)
    except RoomChangeRequest.DoesNotExist:
        raise RoomChangeRequestNotFoundError('Room change request not found.')

    if request_obj.hall_id != mapping.hall_id:
        raise UnauthorizedAccessError('Room change request does not belong to your hostel.')
    if request_obj.status not in [RoomChangeRequestStatus.PENDING, RoomChangeRequestStatus.APPROVED]:
        raise InvalidOperationError('Only pending/approved requests can be reviewed.')

    decision_value, remarks_value = _apply_room_change_review_decision(
        request_obj=request_obj,
        decision=decision,
        remarks=remarks,
    )

    caretaker_staff = selectors.get_staff_by_extrainfo_id(user.extrainfo.id)
    request_obj.caretaker_decision = decision_value
    request_obj.caretaker_remarks = remarks_value
    request_obj.caretaker_decided_by = caretaker_staff
    request_obj.caretaker_decided_at = timezone.now()

    if decision_value == ReviewDecisionStatus.REJECTED:
        request_obj.status = RoomChangeRequestStatus.REJECTED
    elif request_obj.warden_decision == ReviewDecisionStatus.APPROVED:
        request_obj.status = RoomChangeRequestStatus.APPROVED
    else:
        request_obj.status = RoomChangeRequestStatus.PENDING

    request_obj.save()
    allocated = _auto_allocate_after_dual_approval(request_obj=request_obj)

    try:
        from notification.views import hostel_notifications
        if request_obj.status == RoomChangeRequestStatus.REJECTED:
            notif_type = 'roomChange_reject'
        elif allocated or request_obj.status == RoomChangeRequestStatus.ALLOCATED:
            notif_type = 'roomChange_allocated'
        else:
            notif_type = 'roomChange_reviewed'
        hostel_notifications(sender=user, recipient=request_obj.requested_by, type=notif_type)
    except Exception:
        pass

    return _serialize_room_change_request(request_obj)


@transaction.atomic
def wardenReviewRoomChangeRequestService(*, user, room_change_request_id: int, decision: str, remarks: str = ''):
    """Warden reviews room change request for policy compliance."""
    mapping = resolve_user_hall_mapping_service(user=user, strict=True)
    if mapping.role != UserHostelMapping.ROLE_WARDEN:
        raise UnauthorizedAccessError('Only warden can submit warden review decision.')

    try:
        request_obj = selectors.get_room_change_request_by_id(request_id=room_change_request_id)
    except RoomChangeRequest.DoesNotExist:
        raise RoomChangeRequestNotFoundError('Room change request not found.')

    if request_obj.hall_id != mapping.hall_id:
        raise UnauthorizedAccessError('Room change request does not belong to your hostel.')
    if request_obj.status not in [RoomChangeRequestStatus.PENDING, RoomChangeRequestStatus.APPROVED]:
        raise InvalidOperationError('Only pending/approved requests can be reviewed.')

    decision_value, remarks_value = _apply_room_change_review_decision(
        request_obj=request_obj,
        decision=decision,
        remarks=remarks,
    )

    warden_faculty = selectors.get_faculty_by_extrainfo_id(user.extrainfo.id)
    request_obj.warden_decision = decision_value
    request_obj.warden_remarks = remarks_value
    request_obj.warden_decided_by = warden_faculty
    request_obj.warden_decided_at = timezone.now()

    if decision_value == ReviewDecisionStatus.REJECTED:
        request_obj.status = RoomChangeRequestStatus.REJECTED
    elif request_obj.caretaker_decision == ReviewDecisionStatus.APPROVED:
        request_obj.status = RoomChangeRequestStatus.APPROVED
    else:
        request_obj.status = RoomChangeRequestStatus.PENDING

    request_obj.save()
    allocated = _auto_allocate_after_dual_approval(request_obj=request_obj)

    try:
        from notification.views import hostel_notifications
        if request_obj.status == RoomChangeRequestStatus.REJECTED:
            notif_type = 'roomChange_reject'
        elif allocated or request_obj.status == RoomChangeRequestStatus.ALLOCATED:
            notif_type = 'roomChange_allocated'
        else:
            notif_type = 'roomChange_reviewed'
        hostel_notifications(sender=user, recipient=request_obj.requested_by, type=notif_type)
    except Exception:
        pass

    return _serialize_room_change_request(request_obj)


@transaction.atomic
def allocateApprovedRoomChangeRequestService(*, user, room_change_request_id: int, room_id=None, room_label: str = None, notes: str = ''):
    """Caretaker allocates new room for fully approved room change request."""
    mapping = resolve_user_hall_mapping_service(user=user, strict=True)
    if mapping.role != UserHostelMapping.ROLE_CARETAKER:
        raise UnauthorizedAccessError('Only caretaker can allocate room after approval.')

    try:
        request_obj = selectors.get_room_change_request_by_id(request_id=room_change_request_id)
    except RoomChangeRequest.DoesNotExist:
        raise RoomChangeRequestNotFoundError('Room change request not found.')

    if request_obj.hall_id != mapping.hall_id:
        raise UnauthorizedAccessError('Room change request does not belong to your hostel.')
    if request_obj.status != RoomChangeRequestStatus.APPROVED:
        raise InvalidOperationError('Only approved requests can be allocated.')
    if request_obj.caretaker_decision != ReviewDecisionStatus.APPROVED or request_obj.warden_decision != ReviewDecisionStatus.APPROVED:
        raise InvalidOperationError('Both caretaker and warden must approve before allocation.')

    student_username = request_obj.student.id.user.username
    allocation = assignRoomService(
        user=user,
        student_id=student_username,
        room_id=room_id,
        room_label=room_label,
    )

    request_obj.allocated_room = allocation.room
    request_obj.allocation_notes = (notes or '').strip()
    request_obj.allocated_at = timezone.now()
    request_obj.status = RoomChangeRequestStatus.ALLOCATED
    request_obj.save(update_fields=['allocated_room', 'allocation_notes', 'allocated_at', 'status', 'updated_at'])

    try:
        from notification.views import hostel_notifications
        hostel_notifications(sender=user, recipient=request_obj.requested_by, type='roomChange_allocated')
    except Exception:
        pass

    return _serialize_room_change_request(request_obj)


def _validate_extended_stay_dates(*, start_date_obj: date, end_date_obj: date):
    if end_date_obj < start_date_obj:
        raise InvalidOperationError('end_date must be greater than or equal to start_date.')

    if start_date_obj < timezone.now().date():
        raise InvalidOperationError('start_date cannot be in the past.')


def _serialize_extended_stay(request_obj: ExtendedStay):
    return {
        'id': request_obj.id,
        'hall_id': request_obj.hall.hall_id if request_obj.hall else None,
        'hall_name': request_obj.hall.hall_name if request_obj.hall else None,
        'student_username': request_obj.student.id.user.username if request_obj.student and request_obj.student.id and request_obj.student.id.user else None,
        'requested_by': request_obj.requested_by.username if request_obj.requested_by else None,
        'start_date': request_obj.start_date.isoformat() if request_obj.start_date else None,
        'end_date': request_obj.end_date.isoformat() if request_obj.end_date else None,
        'reason': request_obj.reason,
        'faculty_authorization': request_obj.faculty_authorization,
        'status': request_obj.status,
        'caretaker_decision': request_obj.caretaker_decision,
        'caretaker_remarks': request_obj.caretaker_remarks,
        'caretaker_decided_by': request_obj.caretaker_decided_by.id.user.username if request_obj.caretaker_decided_by and request_obj.caretaker_decided_by.id and request_obj.caretaker_decided_by.id.user else None,
        'caretaker_decided_at': request_obj.caretaker_decided_at.isoformat() if request_obj.caretaker_decided_at else None,
        'warden_decision': request_obj.warden_decision,
        'warden_remarks': request_obj.warden_remarks,
        'warden_decided_by': request_obj.warden_decided_by.id.user.username if request_obj.warden_decided_by and request_obj.warden_decided_by.id and request_obj.warden_decided_by.id.user else None,
        'warden_decided_at': request_obj.warden_decided_at.isoformat() if request_obj.warden_decided_at else None,
        'cancel_reason': request_obj.cancel_reason,
        'canceled_at': request_obj.canceled_at.isoformat() if request_obj.canceled_at else None,
        'modified_count': request_obj.modified_count,
        'last_modified_at': request_obj.last_modified_at.isoformat() if request_obj.last_modified_at else None,
        'created_at': request_obj.created_at.isoformat() if request_obj.created_at else None,
        'updated_at': request_obj.updated_at.isoformat() if request_obj.updated_at else None,
    }


@transaction.atomic
def submitExtendedStayRequestService(*, user, start_date: date, end_date: date, reason: str, faculty_authorization: str):
    """Student submits extended stay request during vacation period."""
    mapping = resolve_user_hall_mapping_service(user=user, strict=True)
    if mapping.role != UserHostelMapping.ROLE_STUDENT:
        raise UnauthorizedAccessError('Only students can submit extended stay requests.')

    student = selectors.get_student_by_extrainfo_or_none(user.extrainfo)
    if not student:
        raise StudentNotFoundError('Student profile not found for current user.')

    reason_value = (reason or '').strip()
    auth_value = (faculty_authorization or '').strip()
    if not reason_value:
        raise InvalidOperationError('reason is required.')
    if not auth_value:
        raise InvalidOperationError('faculty_authorization is required.')

    _validate_extended_stay_dates(start_date_obj=start_date, end_date_obj=end_date)

    pending = selectors.get_pending_extended_stay_by_student(student=student)
    if pending:
        raise InvalidOperationError('You already have a pending extended stay request.')

    request_obj = ExtendedStay.objects.create(
        hall=mapping.hall,
        student=student,
        requested_by=user,
        start_date=start_date,
        end_date=end_date,
        reason=reason_value,
        faculty_authorization=auth_value,
        status=ExtendedStayStatusChoices.PENDING,
        caretaker_decision=ReviewDecisionStatus.PENDING,
        warden_decision=ReviewDecisionStatus.PENDING,
    )

    caretaker = selectors.get_caretaker_by_hall(mapping.hall)
    warden = selectors.get_warden_by_hall(mapping.hall)
    try:
        from notification.views import hostel_notifications
        if caretaker and caretaker.staff and caretaker.staff.id and caretaker.staff.id.user:
            hostel_notifications(sender=user, recipient=caretaker.staff.id.user, type='extendedStay_request')
        if warden and warden.faculty and warden.faculty.id and warden.faculty.id.user:
            hostel_notifications(sender=user, recipient=warden.faculty.id.user, type='extendedStay_request')
    except Exception:
        pass

    return _serialize_extended_stay(request_obj)


def getMyExtendedStayRequestsService(*, user):
    """Student views own extended stay request history."""
    mapping = resolve_user_hall_mapping_service(user=user, strict=True)
    if mapping.role != UserHostelMapping.ROLE_STUDENT:
        raise UnauthorizedAccessError('Only students can view their extended stay requests.')

    student = selectors.get_student_by_extrainfo_or_none(user.extrainfo)
    if not student:
        raise StudentNotFoundError('Student profile not found for current user.')

    requests = selectors.get_extended_stay_requests_by_student(student=student)
    return [_serialize_extended_stay(item) for item in requests]


@transaction.atomic
def modifyExtendedStayRequestService(*, user, request_id: int, start_date: date, end_date: date, reason: str, faculty_authorization: str):
    """Student modifies own pending extended stay request."""
    mapping = resolve_user_hall_mapping_service(user=user, strict=True)
    if mapping.role != UserHostelMapping.ROLE_STUDENT:
        raise UnauthorizedAccessError('Only students can modify extended stay requests.')

    try:
        request_obj = selectors.get_extended_stay_request_by_id_and_user(request_id=request_id, user=user)
    except ExtendedStay.DoesNotExist:
        raise ExtendedStayRequestNotFoundError('Extended stay request not found.')

    if request_obj.hall_id != mapping.hall_id:
        raise UnauthorizedAccessError('Request does not belong to your hostel.')
    if request_obj.status != ExtendedStayStatusChoices.PENDING:
        raise InvalidOperationError('Only pending requests can be modified.')

    reason_value = (reason or '').strip()
    auth_value = (faculty_authorization or '').strip()
    if not reason_value:
        raise InvalidOperationError('reason is required.')
    if not auth_value:
        raise InvalidOperationError('faculty_authorization is required.')

    _validate_extended_stay_dates(start_date_obj=start_date, end_date_obj=end_date)

    request_obj.start_date = start_date
    request_obj.end_date = end_date
    request_obj.reason = reason_value
    request_obj.faculty_authorization = auth_value
    request_obj.modified_count = request_obj.modified_count + 1
    request_obj.last_modified_at = timezone.now()
    request_obj.save(update_fields=['start_date', 'end_date', 'reason', 'faculty_authorization', 'modified_count', 'last_modified_at', 'updated_at'])

    try:
        caretaker = selectors.get_caretaker_by_hall(mapping.hall)
        warden = selectors.get_warden_by_hall(mapping.hall)
        from notification.views import hostel_notifications
        if caretaker and caretaker.staff and caretaker.staff.id and caretaker.staff.id.user:
            hostel_notifications(sender=user, recipient=caretaker.staff.id.user, type='extendedStay_modified')
        if warden and warden.faculty and warden.faculty.id and warden.faculty.id.user:
            hostel_notifications(sender=user, recipient=warden.faculty.id.user, type='extendedStay_modified')
    except Exception:
        pass

    return _serialize_extended_stay(request_obj)


@transaction.atomic
def cancelExtendedStayRequestService(*, user, request_id: int, cancel_reason: str = ''):
    """Student cancels own pending extended stay request."""
    mapping = resolve_user_hall_mapping_service(user=user, strict=True)
    if mapping.role != UserHostelMapping.ROLE_STUDENT:
        raise UnauthorizedAccessError('Only students can cancel extended stay requests.')

    try:
        request_obj = selectors.get_extended_stay_request_by_id_and_user(request_id=request_id, user=user)
    except ExtendedStay.DoesNotExist:
        raise ExtendedStayRequestNotFoundError('Extended stay request not found.')

    if request_obj.hall_id != mapping.hall_id:
        raise UnauthorizedAccessError('Request does not belong to your hostel.')
    if request_obj.status != ExtendedStayStatusChoices.PENDING:
        raise InvalidOperationError('Only pending requests can be cancelled.')

    request_obj.status = ExtendedStayStatusChoices.CANCELLED
    request_obj.cancel_reason = (cancel_reason or '').strip()
    request_obj.canceled_at = timezone.now()
    request_obj.save(update_fields=['status', 'cancel_reason', 'canceled_at', 'updated_at'])

    return _serialize_extended_stay(request_obj)


def getExtendedStayRequestsForReviewService(*, user, statuses=None):
    """Caretaker/Warden dashboard view for extended stay requests in own hall."""
    mapping = resolve_user_hall_mapping_service(user=user, strict=True)
    if mapping.role not in [UserHostelMapping.ROLE_CARETAKER, UserHostelMapping.ROLE_WARDEN]:
        raise UnauthorizedAccessError('Only caretaker/warden can view extended stay requests.')

    normalized_statuses = statuses or [
        ExtendedStayStatusChoices.PENDING,
        ExtendedStayStatusChoices.APPROVED,
        ExtendedStayStatusChoices.REJECTED,
    ]
    requests = selectors.get_extended_stay_requests_by_hall_and_status(
        hall=mapping.hall,
        statuses=normalized_statuses,
    )
    return [_serialize_extended_stay(item) for item in requests]


def _apply_extended_stay_review_decision(*, decision: str, remarks: str):
    decision_value = (decision or '').strip().capitalize()
    remarks_value = (remarks or '').strip()
    if decision_value not in [ReviewDecisionStatus.APPROVED, ReviewDecisionStatus.REJECTED]:
        raise InvalidOperationError('decision must be Approved or Rejected.')
    if decision_value == ReviewDecisionStatus.REJECTED and not remarks_value:
        raise InvalidOperationError('remarks are required when rejecting a request.')
    return decision_value, remarks_value


@transaction.atomic
def caretakerReviewExtendedStayRequestService(*, user, extended_stay_request_id: int, decision: str, remarks: str = ''):
    """Caretaker reviews extended stay request."""
    mapping = resolve_user_hall_mapping_service(user=user, strict=True)
    if mapping.role != UserHostelMapping.ROLE_CARETAKER:
        raise UnauthorizedAccessError('Only caretaker can submit caretaker review decision.')

    try:
        request_obj = selectors.get_extended_stay_request_by_id(request_id=extended_stay_request_id)
    except ExtendedStay.DoesNotExist:
        raise ExtendedStayRequestNotFoundError('Extended stay request not found.')

    if request_obj.hall_id != mapping.hall_id:
        raise UnauthorizedAccessError('Request does not belong to your hostel.')
    if request_obj.status not in [ExtendedStayStatusChoices.PENDING, ExtendedStayStatusChoices.APPROVED]:
        raise InvalidOperationError('Only pending/approved requests can be reviewed.')

    decision_value, remarks_value = _apply_extended_stay_review_decision(decision=decision, remarks=remarks)
    caretaker_staff = selectors.get_staff_by_extrainfo_id(user.extrainfo.id)

    request_obj.caretaker_decision = decision_value
    request_obj.caretaker_remarks = remarks_value
    request_obj.caretaker_decided_by = caretaker_staff
    request_obj.caretaker_decided_at = timezone.now()

    if decision_value == ReviewDecisionStatus.REJECTED:
        request_obj.status = ExtendedStayStatusChoices.REJECTED
    else:
        request_obj.status = ExtendedStayStatusChoices.APPROVED

    request_obj.save()

    try:
        from notification.views import hostel_notifications
        notif_type = 'extendedStay_approved' if request_obj.status == ExtendedStayStatusChoices.APPROVED else 'extendedStay_rejected' if request_obj.status == ExtendedStayStatusChoices.REJECTED else 'extendedStay_reviewed'
        hostel_notifications(sender=user, recipient=request_obj.requested_by, type=notif_type)
    except Exception:
        pass

    return _serialize_extended_stay(request_obj)


@transaction.atomic
def wardenReviewExtendedStayRequestService(*, user, extended_stay_request_id: int, decision: str, remarks: str = ''):
    """Warden reviews extended stay request."""
    mapping = resolve_user_hall_mapping_service(user=user, strict=True)
    if mapping.role != UserHostelMapping.ROLE_WARDEN:
        raise UnauthorizedAccessError('Only warden can submit warden review decision.')

    try:
        request_obj = selectors.get_extended_stay_request_by_id(request_id=extended_stay_request_id)
    except ExtendedStay.DoesNotExist:
        raise ExtendedStayRequestNotFoundError('Extended stay request not found.')

    if request_obj.hall_id != mapping.hall_id:
        raise UnauthorizedAccessError('Request does not belong to your hostel.')
    if request_obj.status not in [ExtendedStayStatusChoices.PENDING, ExtendedStayStatusChoices.APPROVED]:
        raise InvalidOperationError('Only pending/approved requests can be reviewed.')

    decision_value, remarks_value = _apply_extended_stay_review_decision(decision=decision, remarks=remarks)
    warden_faculty = selectors.get_faculty_by_extrainfo_id(user.extrainfo.id)

    request_obj.warden_decision = decision_value
    request_obj.warden_remarks = remarks_value
    request_obj.warden_decided_by = warden_faculty
    request_obj.warden_decided_at = timezone.now()

    if decision_value == ReviewDecisionStatus.REJECTED:
        request_obj.status = ExtendedStayStatusChoices.REJECTED
    else:
        request_obj.status = ExtendedStayStatusChoices.APPROVED

    request_obj.save()

    try:
        from notification.views import hostel_notifications
        notif_type = 'extendedStay_approved' if request_obj.status == ExtendedStayStatusChoices.APPROVED else 'extendedStay_rejected' if request_obj.status == ExtendedStayStatusChoices.REJECTED else 'extendedStay_reviewed'
        hostel_notifications(sender=user, recipient=request_obj.requested_by, type=notif_type)
    except Exception:
        pass

    return _serialize_extended_stay(request_obj)


# ══════════════════════════════════════════════════════════════
# ROOM VACATION SERVICES (UC-029/030/031)
# ══════════════════════════════════════════════════════════════

def _serialize_room_vacation_request(request_obj: RoomVacationRequest):
    checklist_items = list(request_obj.checklist_items.all())
    blocking_items = [item for item in checklist_items if item.is_blocking]
    unresolved_blocking = [
        item for item in blocking_items if item.status != ChecklistVerificationStatus.VERIFIED
    ]

    return {
        'id': request_obj.id,
        'hall_id': request_obj.hall.hall_id if request_obj.hall else None,
        'hall_name': request_obj.hall.hall_name if request_obj.hall else None,
        'student_username': request_obj.student.id.user.username if request_obj.student and request_obj.student.id and request_obj.student.id.user else None,
        'student_name': request_obj.student.id.user.get_full_name() if request_obj.student and request_obj.student.id and request_obj.student.id.user else '',
        'allocation_id': request_obj.allocation_id,
        'room_label': (
            f"{request_obj.allocation.room.block_no}-{request_obj.allocation.room.room_no}"
            if request_obj.allocation and request_obj.allocation.room
            else ''
        ),
        'intended_vacation_date': request_obj.intended_vacation_date.isoformat() if request_obj.intended_vacation_date else None,
        'reason': request_obj.reason,
        'status': request_obj.status,
        'checklist_generated_at': request_obj.checklist_generated_at.isoformat() if request_obj.checklist_generated_at else None,
        'checklist_acknowledged': request_obj.checklist_acknowledged,
        'checklist_acknowledged_at': request_obj.checklist_acknowledged_at.isoformat() if request_obj.checklist_acknowledged_at else None,
        'room_inspection_notes': request_obj.room_inspection_notes,
        'room_damages_found': request_obj.room_damages_found,
        'room_damage_description': request_obj.room_damage_description,
        'room_damage_fine_amount': float(request_obj.room_damage_fine_amount or 0),
        'caretaker_review_comments': request_obj.caretaker_review_comments,
        'borrowed_items_notes': request_obj.borrowed_items_notes,
        'behavior_notes': request_obj.behavior_notes,
        'clearance_certificate_no': request_obj.clearance_certificate_no,
        'clearance_approved_by': (
            request_obj.clearance_approved_by.id.user.username
            if request_obj.clearance_approved_by and request_obj.clearance_approved_by.id and request_obj.clearance_approved_by.id.user
            else None
        ),
        'clearance_approved_at': request_obj.clearance_approved_at.isoformat() if request_obj.clearance_approved_at else None,
        'finalized_by': request_obj.finalized_by.username if request_obj.finalized_by else None,
        'finalized_at': request_obj.finalized_at.isoformat() if request_obj.finalized_at else None,
        'completion_report': request_obj.completion_report or {},
        'checklist': [
            {
                'id': item.id,
                'code': item.code,
                'title': item.title,
                'details': item.details,
                'is_blocking': item.is_blocking,
                'status': item.status,
                'caretaker_comment': item.caretaker_comment,
                'metadata': item.metadata or {},
            }
            for item in checklist_items
        ],
        'checklist_summary': {
            'total': len(checklist_items),
            'blocking': len(blocking_items),
            'unresolved_blocking': len(unresolved_blocking),
        },
        'created_at': request_obj.created_at.isoformat() if request_obj.created_at else None,
        'updated_at': request_obj.updated_at.isoformat() if request_obj.updated_at else None,
    }


def _build_room_vacation_checklist(*, student, hall):
    pending_fines = selectors.get_pending_fines_for_student_in_hall(student=student, hall=hall)
    damage_fines = selectors.get_damage_fines_for_student_in_hall(student=student, hall=hall)
    active_bookings = selectors.get_open_guest_bookings_by_student_and_hall(
        user=student.id.user,
        hall=hall,
    )
    checked_in_bookings = active_bookings.filter(status=BookingStatus.CHECKED_IN)
    attendance_summary = selectors.get_attendance_summary_for_student(
        student=student,
        since_date=timezone.now().date() - timedelta(days=30),
    )
    attendance_issue = (
        attendance_summary['total_days'] > 0 and attendance_summary['percentage'] < 75
    )
    open_complaints_count = selectors.count_open_complaints_for_student_in_hall(
        student=student,
        hall=hall,
    )

    total_pending_fine_amount = sum(Decimal(str(row.amount or 0)) for row in pending_fines)
    total_damage_fine_amount = sum(Decimal(str(row.amount or 0)) for row in damage_fines)

    return [
        {
            'code': 'outstanding_fines',
            'title': 'Outstanding Fines',
            'details': (
                f"{pending_fines.count()} pending fine(s), total amount {total_pending_fine_amount}."
                if pending_fines.exists()
                else 'No outstanding fines found.'
            ),
            'is_blocking': pending_fines.exists(),
            'metadata': {
                'pending_fines_count': pending_fines.count(),
                'pending_fines_amount': float(total_pending_fine_amount),
            },
        },
        {
            'code': 'room_damage_assessment',
            'title': 'Pending Room Damage Assessments',
            'details': (
                f"{damage_fines.count()} pending damage fine(s), total amount {total_damage_fine_amount}."
                if damage_fines.exists()
                else 'No pending room damage assessments found.'
            ),
            'is_blocking': damage_fines.exists(),
            'metadata': {
                'damage_fines_count': damage_fines.count(),
                'damage_fines_amount': float(total_damage_fine_amount),
            },
        },
        {
            'code': 'borrowed_items',
            'title': 'Borrowed Items Not Returned',
            'details': (
                f"{checked_in_bookings.count()} active checked-in guest booking(s) indicate pending returns/closures."
                if checked_in_bookings.exists()
                else 'No active borrowed item indicators found.'
            ),
            'is_blocking': checked_in_bookings.exists(),
            'metadata': {
                'active_borrowed_booking_count': checked_in_bookings.count(),
            },
        },
        {
            'code': 'attendance_summary',
            'title': 'Attendance Record Summary',
            'details': (
                f"Last 30 days: {attendance_summary['present_days']} present, {attendance_summary['absent_days']} absent, {attendance_summary['percentage']}% attendance."
            ),
            'is_blocking': attendance_issue,
            'metadata': attendance_summary,
        },
        {
            'code': 'behavior_records',
            'title': 'Behavior and Discipline Records',
            'details': (
                f"{open_complaints_count} unresolved complaint/disciplinary record(s)."
                if open_complaints_count > 0
                else 'No unresolved behavior/disciplinary records found.'
            ),
            'is_blocking': False,
            'metadata': {
                'open_complaints_count': open_complaints_count,
            },
        },
    ]


def _store_room_vacation_checklist(*, request_obj, checklist_rows):
    RoomVacationChecklistItem.objects.filter(request=request_obj).delete()

    RoomVacationChecklistItem.objects.bulk_create(
        [
            RoomVacationChecklistItem(
                request=request_obj,
                code=row['code'],
                title=row['title'],
                details=row.get('details', ''),
                is_blocking=bool(row.get('is_blocking', False)),
                status=(
                    ChecklistVerificationStatus.PENDING_ACTION
                    if bool(row.get('is_blocking', False))
                    else ChecklistVerificationStatus.PENDING
                ),
                metadata=row.get('metadata') or {},
            )
            for row in checklist_rows
        ]
    )


def _get_super_admin_notification_recipients(*, exclude_user_id=None):
    super_admin_ids = set(User.objects.filter(is_superuser=True).values_list('id', flat=True))
    designated_super_admin_ids = HoldsDesignation.objects.filter(
        designation__name__in=['super_admin', 'SuperAdmin']
    ).values_list('working_id', flat=True)
    super_admin_ids.update(set(designated_super_admin_ids))

    qs = User.objects.filter(id__in=list(super_admin_ids))
    if exclude_user_id:
        qs = qs.exclude(id=exclude_user_id)
    return list(qs)


def _notify_room_vacation(*, sender, recipients, notif_type):
    if not recipients:
        return

    try:
        from notification.views import hostel_notifications

        seen = set()
        for recipient in recipients:
            if not recipient or recipient.id in seen:
                continue
            seen.add(recipient.id)
            hostel_notifications(sender=sender, recipient=recipient, type=notif_type)
    except Exception:
        pass


def _build_room_vacation_completion_report(*, request_obj):
    student = request_obj.student
    hall = request_obj.hall
    attendance_summary = selectors.get_attendance_summary_for_student(student=student)

    room_allocations = [
        {
            'allocation_id': row.id,
            'room': f"{row.room.block_no}-{row.room.room_no}" if row.room else None,
            'status': row.status,
            'assigned_at': row.assigned_at.isoformat() if row.assigned_at else None,
            'vacated_at': row.vacated_at.isoformat() if row.vacated_at else None,
        }
        for row in StudentRoomAllocation.objects.filter(student=student).select_related('room').order_by('-assigned_at')[:20]
    ]

    fine_history = [
        {
            'fine_id': row.fine_id,
            'amount': float(row.amount or 0),
            'category': row.category,
            'status': row.status,
            'reason': row.reason,
            'created_at': row.created_at.isoformat() if row.created_at else None,
        }
        for row in HostelFine.objects.filter(student=student).order_by('-created_at')[:50]
    ]

    complaint_history = [
        {
            'complaint_id': row.id,
            'title': row.title,
            'status': row.status,
            'created_at': row.created_at.isoformat() if row.created_at else None,
            'resolved_at': row.resolved_at.isoformat() if row.resolved_at else None,
        }
        for row in HostelComplaint.objects.filter(student=student, hall=hall).order_by('-created_at')[:50]
    ]

    leave_history = [
        {
            'leave_id': row.id,
            'start_date': row.start_date.isoformat() if row.start_date else None,
            'end_date': row.end_date.isoformat() if row.end_date else None,
            'status': row.status,
            'reason': row.reason,
        }
        for row in HostelLeave.objects.filter(student=student, hall=hall).order_by('-start_date')[:50]
    ]

    guest_bookings = [
        {
            'booking_id': row.id,
            'status': row.status,
            'arrival_date': row.arrival_date.isoformat() if row.arrival_date else None,
            'departure_date': row.departure_date.isoformat() if row.departure_date else None,
            'checked_in_at': row.checked_in_at.isoformat() if row.checked_in_at else None,
            'checked_out_at': row.checked_out_at.isoformat() if row.checked_out_at else None,
        }
        for row in GuestRoomBooking.objects.filter(intender=student.id.user, hall=hall).order_by('-booking_date')[:50]
    ]

    extended_stay_records = [
        {
            'request_id': row.id,
            'start_date': row.start_date.isoformat() if row.start_date else None,
            'end_date': row.end_date.isoformat() if row.end_date else None,
            'status': row.status,
            'created_at': row.created_at.isoformat() if row.created_at else None,
        }
        for row in ExtendedStay.objects.filter(student=student, hall=hall).order_by('-created_at')[:50]
    ]

    return {
        'generated_at': timezone.now().isoformat(),
        'student': {
            'username': student.id.user.username,
            'full_name': (student.id.user.get_full_name() or student.id.user.username).strip(),
            'hall_id': hall.hall_id if hall else None,
        },
        'room_allocation_history': room_allocations,
        'fine_records': fine_history,
        'complaint_records': complaint_history,
        'attendance_summary': attendance_summary,
        'leave_history': leave_history,
        'guest_room_bookings': guest_bookings,
        'extended_stay_records': extended_stay_records,
    }


def _validate_room_vacation_form(*, intended_vacation_date: date, reason: str):
    if not intended_vacation_date:
        raise InvalidOperationError('intended_vacation_date is required.')
    if intended_vacation_date < timezone.now().date():
        raise InvalidOperationError('intended_vacation_date cannot be in the past.')
    if not (reason or '').strip():
        raise InvalidOperationError('reason is required.')


def generateRoomVacationChecklistService(*, user, intended_vacation_date: date, reason: str):
    """Student previews generated room vacation clearance checklist."""
    mapping = resolve_user_hall_mapping_service(user=user, strict=True)
    if mapping.role != UserHostelMapping.ROLE_STUDENT:
        raise UnauthorizedAccessError('Only students can generate room vacation checklist.')

    _validate_room_vacation_form(
        intended_vacation_date=intended_vacation_date,
        reason=reason,
    )

    student = selectors.get_student_by_extrainfo_or_none(user.extrainfo)
    if not student:
        raise StudentNotFoundError('Student profile not found for current user.')

    active_allocation = selectors.get_student_room_allocation_active(student=student)
    if not active_allocation:
        raise InvalidOperationError('Active room allocation is required before requesting room vacation.')

    checklist = _build_room_vacation_checklist(student=student, hall=mapping.hall)
    return {
        'student_username': student.id.user.username,
        'student_name': (student.id.user.get_full_name() or student.id.user.username).strip(),
        'hall_id': mapping.hall.hall_id,
        'room_label': f"{active_allocation.room.block_no}-{active_allocation.room.room_no}" if active_allocation.room else '',
        'intended_vacation_date': intended_vacation_date.isoformat(),
        'reason': (reason or '').strip(),
        'checklist': checklist,
        'blocking_items_count': len([row for row in checklist if row.get('is_blocking')]),
    }


@transaction.atomic
def submitRoomVacationRequestService(*, user, intended_vacation_date: date, reason: str, checklist_acknowledged: bool):
    """Student submits room vacation request with generated checklist."""
    mapping = resolve_user_hall_mapping_service(user=user, strict=True)
    if mapping.role != UserHostelMapping.ROLE_STUDENT:
        raise UnauthorizedAccessError('Only students can submit room vacation requests.')

    _validate_room_vacation_form(
        intended_vacation_date=intended_vacation_date,
        reason=reason,
    )

    if not checklist_acknowledged:
        raise InvalidOperationError('Checklist acknowledgement is required before submission.')

    student = selectors.get_student_by_extrainfo_or_none(user.extrainfo)
    if not student:
        raise StudentNotFoundError('Student profile not found for current user.')

    active_allocation = selectors.get_student_room_allocation_active(student=student)
    if not active_allocation:
        raise InvalidOperationError('Active room allocation is required before requesting room vacation.')

    existing_pending = selectors.get_pending_room_vacation_by_student(student=student)
    if existing_pending:
        raise InvalidOperationError('You already have a pending room vacation request.')

    checklist = _build_room_vacation_checklist(student=student, hall=mapping.hall)

    request_obj = RoomVacationRequest.objects.create(
        hall=mapping.hall,
        student=student,
        requested_by=user,
        allocation=active_allocation,
        intended_vacation_date=intended_vacation_date,
        reason=(reason or '').strip(),
        status=VacationRequestStatusChoices.PENDING_CLEARANCE,
        checklist_generated_at=timezone.now(),
        checklist_acknowledged=True,
        checklist_acknowledged_at=timezone.now(),
    )
    _store_room_vacation_checklist(request_obj=request_obj, checklist_rows=checklist)

    recipients = []
    caretaker = selectors.get_caretaker_by_hall(mapping.hall)
    if caretaker and caretaker.staff and caretaker.staff.id and caretaker.staff.id.user:
        recipients.append(caretaker.staff.id.user)
    recipients.extend(_get_super_admin_notification_recipients(exclude_user_id=user.id))
    _notify_room_vacation(sender=user, recipients=recipients, notif_type='roomVacation_request')

    request_obj = selectors.get_room_vacation_request_by_id(request_id=request_obj.id)
    return _serialize_room_vacation_request(request_obj)


def getMyRoomVacationRequestsService(*, user):
    """Student views own room vacation request history."""
    mapping = resolve_user_hall_mapping_service(user=user, strict=True)
    if mapping.role != UserHostelMapping.ROLE_STUDENT:
        raise UnauthorizedAccessError('Only students can view their room vacation requests.')

    student = selectors.get_student_by_extrainfo_or_none(user.extrainfo)
    if not student:
        raise StudentNotFoundError('Student profile not found for current user.')

    requests = selectors.get_room_vacation_requests_by_student(student=student)
    return [_serialize_room_vacation_request(item) for item in requests]


def getRoomVacationRequestsForClearanceService(*, user, statuses=None):
    """Caretaker views room vacation requests in own hall for clearance processing."""
    mapping = resolve_user_hall_mapping_service(user=user, strict=True)
    if mapping.role != UserHostelMapping.ROLE_CARETAKER:
        raise UnauthorizedAccessError('Only caretaker can review room vacation clearance requests.')

    normalized_statuses = statuses or [
        VacationRequestStatusChoices.PENDING_CLEARANCE,
        VacationRequestStatusChoices.CLEARANCE_PENDING_ACTION_REQUIRED,
        VacationRequestStatusChoices.CLEARANCE_APPROVED,
    ]
    requests = selectors.get_room_vacation_requests_by_hall_and_status(
        hall=mapping.hall,
        statuses=normalized_statuses,
    )
    return [_serialize_room_vacation_request(item) for item in requests]


@transaction.atomic
def caretakerVerifyRoomVacationService(
    *,
    user,
    request_id: int,
    decision: str,
    caretaker_review_comments: str = '',
    room_inspection_notes: str = '',
    room_damages_found: bool = False,
    room_damage_description: str = '',
    room_damage_fine_amount=0,
    borrowed_items_notes: str = '',
    behavior_notes: str = '',
    checklist_updates=None,
):
    """Caretaker verifies checklist requirements and approves or requests corrections."""
    mapping = resolve_user_hall_mapping_service(user=user, strict=True)
    if mapping.role != UserHostelMapping.ROLE_CARETAKER:
        raise UnauthorizedAccessError('Only caretaker can verify room vacation clearance requirements.')

    try:
        request_obj = selectors.get_room_vacation_request_by_id(request_id=request_id)
    except RoomVacationRequest.DoesNotExist:
        raise RoomVacationRequestNotFoundError('Room vacation request not found.')

    if request_obj.hall_id != mapping.hall_id:
        raise UnauthorizedAccessError('Room vacation request does not belong to your hostel.')

    if request_obj.status not in [
        VacationRequestStatusChoices.PENDING_CLEARANCE,
        VacationRequestStatusChoices.CLEARANCE_PENDING_ACTION_REQUIRED,
    ]:
        raise InvalidOperationError('Only pending clearance requests can be reviewed.')

    try:
        damage_amount = Decimal(str(room_damage_fine_amount or 0))
    except Exception:
        raise InvalidOperationError('room_damage_fine_amount must be a valid number.')

    request_obj.room_inspection_notes = (room_inspection_notes or '').strip()
    request_obj.room_damages_found = bool(room_damages_found)
    request_obj.room_damage_description = (room_damage_description or '').strip()
    request_obj.room_damage_fine_amount = damage_amount if damage_amount > 0 else Decimal('0')
    request_obj.caretaker_review_comments = (caretaker_review_comments or '').strip()
    request_obj.borrowed_items_notes = (borrowed_items_notes or '').strip()
    request_obj.behavior_notes = (behavior_notes or '').strip()

    checklist_items = list(request_obj.checklist_items.all())
    checklist_map = {item.code: item for item in checklist_items}

    updates = checklist_updates or []
    for row in updates:
        code = (row.get('code') or '').strip()
        if not code or code not in checklist_map:
            continue

        item = checklist_map[code]
        status_value = (row.get('status') or item.status).strip()
        if status_value not in [
            ChecklistVerificationStatus.PENDING,
            ChecklistVerificationStatus.VERIFIED,
            ChecklistVerificationStatus.PENDING_ACTION,
        ]:
            raise InvalidOperationError(f'Invalid checklist status for {code}.')

        item.status = status_value
        item.caretaker_comment = (row.get('caretaker_comment') or row.get('comment') or '').strip()
        if 'is_blocking' in row:
            item.is_blocking = bool(row.get('is_blocking'))
        item.save(update_fields=['status', 'caretaker_comment', 'is_blocking', 'updated_at'])

    if request_obj.room_damages_found:
        damage_item = checklist_map.get('room_damage_assessment')
        if damage_item:
            damage_item.is_blocking = True
            damage_item.status = ChecklistVerificationStatus.PENDING_ACTION
            if request_obj.room_damage_description:
                damage_item.details = request_obj.room_damage_description
            damage_item.save(update_fields=['is_blocking', 'status', 'details', 'updated_at'])

        if damage_amount > 0:
            caretaker_staff = selectors.get_staff_by_extrainfo_id(user.extrainfo.id)
            HostelFine.objects.create(
                student=request_obj.student,
                caretaker=caretaker_staff,
                hall=request_obj.hall,
                student_name=(request_obj.student.id.user.get_full_name() or request_obj.student.id.user.username).strip(),
                amount=damage_amount,
                category=FineCategory.DAMAGE,
                status=FineStatus.PENDING,
                reason=request_obj.room_damage_description or 'Room vacation inspection identified pending damages.',
            )

    decision_value = (decision or '').strip().lower()
    if decision_value not in ['approve', 'request_corrections']:
        raise InvalidOperationError('decision must be approve or request_corrections.')

    blocking_pending = request_obj.checklist_items.filter(
        is_blocking=True,
    ).exclude(status=ChecklistVerificationStatus.VERIFIED).exists()

    caretaking_staff = selectors.get_staff_by_extrainfo_id(user.extrainfo.id)
    notif_type = 'roomVacation_corrections_required'
    if decision_value == 'approve':
        if blocking_pending:
            raise InvalidOperationError('All blocking checklist items must be verified before clearance approval.')

        request_obj.status = VacationRequestStatusChoices.CLEARANCE_APPROVED
        request_obj.clearance_approved_by = caretaking_staff
        request_obj.clearance_approved_at = timezone.now()
        if not request_obj.clearance_certificate_no:
            request_obj.clearance_certificate_no = (
                f"CLR-{timezone.now().strftime('%Y%m%d')}-{request_obj.id:06d}"
            )
        notif_type = 'roomVacation_clearance_approved'
    else:
        request_obj.status = VacationRequestStatusChoices.CLEARANCE_PENDING_ACTION_REQUIRED

    request_obj.save()

    recipients = [request_obj.requested_by]
    recipients.extend(_get_super_admin_notification_recipients(exclude_user_id=user.id))
    _notify_room_vacation(sender=user, recipients=recipients, notif_type=notif_type)

    request_obj = selectors.get_room_vacation_request_by_id(request_id=request_obj.id)
    return _serialize_room_vacation_request(request_obj)


def getRoomVacationRequestsForFinalizationService(*, user, statuses=None, hall_id: str = None):
    """Super admin views vacation requests ready for finalization."""
    role, _ = resolve_hostel_rbac_role_service(user=user)
    if role != 'super_admin':
        raise UnauthorizedAccessError('Only super admin can access room vacation finalization dashboard.')

    normalized_statuses = statuses or [
        VacationRequestStatusChoices.CLEARANCE_APPROVED,
        VacationRequestStatusChoices.COMPLETED,
    ]
    requests = selectors.get_room_vacation_requests_by_status(statuses=normalized_statuses)
    hall = _get_required_hall_for_super_admin(hall_id=hall_id)
    requests = requests.filter(hall_id=hall.id)
    return [_serialize_room_vacation_request(item) for item in requests]


@transaction.atomic
def finalizeRoomVacationService(*, user, request_id: int, confirm: bool, hall_id: str = None):
    """Super admin finalizes room vacation by deallocation and archival."""
    role, _ = resolve_hostel_rbac_role_service(user=user)
    if role != 'super_admin':
        raise UnauthorizedAccessError('Only super admin can finalize room vacation.')

    hall = _get_required_hall_for_super_admin(hall_id=hall_id)

    if not confirm:
        raise InvalidOperationError('Finalization confirmation is required.')

    try:
        request_obj = selectors.get_room_vacation_request_by_id(request_id=request_id)
    except RoomVacationRequest.DoesNotExist:
        raise RoomVacationRequestNotFoundError('Room vacation request not found.')

    if request_obj.hall_id != hall.id:
        raise UnauthorizedAccessError('Selected request does not belong to the specified hall.')

    if request_obj.status != VacationRequestStatusChoices.CLEARANCE_APPROVED:
        raise InvalidOperationError('Only clearance approved requests can be finalized.')

    allocation = request_obj.allocation or selectors.get_student_room_allocation_active(student=request_obj.student)
    if not allocation:
        raise InvalidOperationError('No active room allocation found for the student.')
    if allocation.status != RoomAllocationStatus.ACTIVE:
        raise InvalidOperationError('Student allocation is already vacated.')

    room = allocation.room
    if room and room.room_occupied > 0:
        room.room_occupied = room.room_occupied - 1
        room.save(update_fields=['room_occupied'])

    allocation.status = RoomAllocationStatus.VACATED
    allocation.vacated_at = timezone.now()
    allocation.save(update_fields=['status', 'vacated_at'])

    student = request_obj.student
    student.room_no = ''
    student.hall_no = 0
    student.save(update_fields=['room_no', 'hall_no'])

    student_details = selectors.get_student_details_by_id_or_none(student.id.user.username)
    if student_details:
        student_details.room_num = ''
        student_details.hall_id = ''
        student_details.hall_no = ''
        student_details.save(update_fields=['room_num', 'hall_id', 'hall_no'])

    active_allocations_count = StudentRoomAllocation.objects.filter(
        hall=request_obj.hall,
        status=RoomAllocationStatus.ACTIVE,
    ).count()
    request_obj.hall.number_students = active_allocations_count
    request_obj.hall.save(update_fields=['number_students'])

    request_obj.status = VacationRequestStatusChoices.COMPLETED
    request_obj.finalized_by = user
    request_obj.finalized_at = timezone.now()
    request_obj.completion_report = _build_room_vacation_completion_report(request_obj=request_obj)
    request_obj.save()

    HostelTransactionHistory.objects.create(
        hall=request_obj.hall,
        change_type='RoomVacationCompleted',
        previous_value='Clearance Approved',
        new_value=f"Completed for {student.id.user.username} by {user.username}",
    )

    _notify_room_vacation(
        sender=user,
        recipients=[request_obj.requested_by],
        notif_type='roomVacation_completed',
    )

    request_obj = selectors.get_room_vacation_request_by_id(request_id=request_obj.id)
    return _serialize_room_vacation_request(request_obj)


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


def _sync_attendance_for_approved_leave(*, leave, acting_user):
    """Upsert absence attendance records for the approved leave date range."""
    if not leave.student_id or not leave.hall_id:
        return

    marker_staff = Staff.objects.filter(id=acting_user.extrainfo).first()
    current_date = leave.start_date

    while current_date <= leave.end_date:
        HostelStudentAttendence.objects.update_or_create(
            student_id=leave.student,
            date=current_date,
            defaults={
                'hall': leave.hall,
                'status': AttendanceStatus.ABSENT,
                'present': False,
                'marked_by': marker_staff,
            },
        )
        current_date += timedelta(days=1)


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

    if normalized_status == 'approved':
        _sync_attendance_for_approved_leave(leave=leave, acting_user=user)

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
    """Return fines for caretaker/warden assigned hostel."""
    mapping = resolve_user_hall_mapping_service(user=user, strict=True)
    if mapping.role not in [UserHostelMapping.ROLE_CARETAKER, UserHostelMapping.ROLE_WARDEN]:
        raise UnauthorizedAccessError('Only caretaker or warden can view hostel fines.')

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
        quantity=quantity,
        condition_status=InventoryConditionStatus.GOOD,
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


def _ensure_inventory_role_access(*, user, allowed_roles):
    mapping = resolve_user_hall_mapping_service(user=user, strict=True)
    if mapping.role not in allowed_roles:
        raise UnauthorizedAccessError('You are not authorized for this inventory action.')
    if mapping.hall.operational_status != HostelOperationalStatus.ACTIVE:
        raise InvalidOperationError('Inventory workflow is available only for active hostels.')
    return mapping


def _serialize_inventory_item(item):
    return {
        'inventory_id': item.inventory_id,
        'hall_id': item.hall.hall_id if item.hall else '',
        'hall_name': item.hall.hall_name if item.hall else '',
        'inventory_name': item.inventory_name,
        'cost': float(item.cost),
        'quantity': item.quantity,
        'condition_status': item.condition_status,
    }


def getInventoryDashboardService(*, user, hall_id: str = None):
    """Return inventory list for authenticated hall (caretaker/warden) or all halls (superuser/admin)."""
    role, _ = resolve_hostel_rbac_role_service(user=user)
    if role == 'super_admin':
        hall = _get_required_hall_for_super_admin(hall_id=hall_id)
        inventory = [
            item for item in selectors.get_all_inventory()
            if item.hall and item.hall.id == hall.id and item.hall.operational_status == HostelOperationalStatus.ACTIVE
        ]
        return [_serialize_inventory_item(item) for item in inventory]

    mapping = _ensure_inventory_role_access(
        user=user,
        allowed_roles=[UserHostelMapping.ROLE_CARETAKER, UserHostelMapping.ROLE_WARDEN],
    )
    inventory = selectors.get_inventory_by_hall_instance(hall=mapping.hall)
    return [_serialize_inventory_item(item) for item in inventory]


@transaction.atomic
def submitInventoryInspectionService(*, user, items, remarks: str = ''):
    """UC-026: caretaker performs inspection and logs discrepancies."""
    mapping = _ensure_inventory_role_access(
        user=user,
        allowed_roles=[UserHostelMapping.ROLE_CARETAKER],
    )

    caretaker_staff = selectors.get_staff_by_extrainfo_id(user.extrainfo.id)
    inspection = HostelInventoryInspection.objects.create(
        hall=mapping.hall,
        caretaker=caretaker_staff,
        remarks=(remarks or '').strip(),
    )

    if not isinstance(items, list) or not items:
        raise InvalidOperationError('items list is required for inspection.')

    for row in items:
        inventory_id = row.get('inventory_id')
        if not inventory_id:
            raise InvalidOperationError('inventory_id is required in each inspection row.')

        try:
            inventory = selectors.get_inventory_by_id(int(inventory_id))
        except HostelInventory.DoesNotExist:
            raise InventoryNotFoundError(f'Inventory item with ID {inventory_id} not found.')

        if inventory.hall_id != mapping.hall_id:
            raise UnauthorizedAccessError('Inventory item does not belong to your hostel.')

        expected_qty = inventory.quantity
        observed_qty = int(row.get('observed_quantity', expected_qty))
        observed_condition = row.get('observed_condition', inventory.condition_status)
        if observed_condition not in InventoryConditionStatus.values:
            raise InvalidOperationError('Invalid observed_condition value.')

        discrepancy = bool(row.get('discrepancy', False))
        if observed_qty != expected_qty or observed_condition != inventory.condition_status:
            discrepancy = True

        HostelInventoryInspectionItem.objects.create(
            inspection=inspection,
            inventory=inventory,
            expected_quantity=expected_qty,
            observed_quantity=max(observed_qty, 0),
            observed_condition=observed_condition,
            discrepancy=discrepancy,
            discrepancy_remarks=(row.get('remarks') or '').strip(),
        )

    return {
        'inspection_id': inspection.id,
        'hall_id': mapping.hall.hall_id,
        'created_at': inspection.created_at.isoformat(),
        'remarks': inspection.remarks,
    }


def getInventoryInspectionsService(*, user, hall_id: str = None):
    """Get inspections for current hall (caretaker/warden) or all halls for superuser."""
    role, _ = resolve_hostel_rbac_role_service(user=user)
    if role == 'super_admin':
        hall = _get_required_hall_for_super_admin(hall_id=hall_id)
        inspections = selectors.get_inventory_inspections_by_hall(hall=hall)
        return [_serialize_inventory_inspection(inspection) for inspection in inspections]

    mapping = _ensure_inventory_role_access(
        user=user,
        allowed_roles=[UserHostelMapping.ROLE_CARETAKER, UserHostelMapping.ROLE_WARDEN],
    )
    inspections = selectors.get_inventory_inspections_by_hall(hall=mapping.hall)
    return [_serialize_inventory_inspection(inspection) for inspection in inspections]


def _serialize_inventory_inspection(inspection):
    return {
        'inspection_id': inspection.id,
        'hall_id': inspection.hall.hall_id if inspection.hall else '',
        'hall_name': inspection.hall.hall_name if inspection.hall else '',
        'caretaker_username': (
            inspection.caretaker.id.user.username
            if inspection.caretaker and inspection.caretaker.id and inspection.caretaker.id.user
            else ''
        ),
        'remarks': inspection.remarks,
        'created_at': inspection.created_at.isoformat() if inspection.created_at else None,
        'items': [
            {
                'inventory_id': row.inventory.inventory_id,
                'inventory_name': row.inventory.inventory_name,
                'expected_quantity': row.expected_quantity,
                'observed_quantity': row.observed_quantity,
                'observed_condition': row.observed_condition,
                'discrepancy': row.discrepancy,
                'discrepancy_remarks': row.discrepancy_remarks,
            }
            for row in inspection.items.all()
        ],
    }


@transaction.atomic
def submitResourceRequirementRequestService(*, user, request_type: str, items, justification: str = ''):
    """UC-027: caretaker submits replacement/new/additional resource request."""
    mapping = _ensure_inventory_role_access(
        user=user,
        allowed_roles=[UserHostelMapping.ROLE_CARETAKER],
    )

    normalized_type = (request_type or '').strip().capitalize()
    if normalized_type not in InventoryRequestType.values:
        raise InvalidOperationError('request_type must be Replacement, New, or Additional.')
    if not isinstance(items, list) or not items:
        raise InvalidOperationError('At least one resource request item is required.')

    caretaker_staff = selectors.get_staff_by_extrainfo_id(user.extrainfo.id)
    resource_request = HostelResourceRequest.objects.create(
        hall=mapping.hall,
        caretaker=caretaker_staff,
        request_type=normalized_type,
        justification=(justification or '').strip(),
        status=WorkflowStatus.PENDING,
    )

    for row in items:
        requested_qty = int(row.get('requested_quantity', 0))
        if requested_qty <= 0:
            raise InvalidOperationError('requested_quantity must be greater than 0.')

        inventory_id = row.get('inventory_id')
        inventory = None
        item_name = (row.get('item_name') or '').strip()

        if inventory_id:
            try:
                inventory = selectors.get_inventory_by_id(int(inventory_id))
            except HostelInventory.DoesNotExist:
                raise InventoryNotFoundError(f'Inventory item with ID {inventory_id} not found.')
            if inventory.hall_id != mapping.hall_id:
                raise UnauthorizedAccessError('Requested inventory item does not belong to your hostel.')
            if not item_name:
                item_name = inventory.inventory_name

        if not item_name:
            raise InvalidOperationError('item_name is required for each request row.')

        HostelResourceRequestItem.objects.create(
            request=resource_request,
            inventory=inventory,
            item_name=item_name,
            requested_quantity=requested_qty,
            remarks=(row.get('remarks') or '').strip(),
        )

    # Notify warden for first-level review.
    warden = selectors.get_warden_by_hall(mapping.hall)
    try:
        from notification.views import hostel_notifications
        if warden and warden.faculty and warden.faculty.id and warden.faculty.id.user:
            hostel_notifications(sender=user, recipient=warden.faculty.id.user, type='inventory_request')
        # Also notify caretaker that submission was registered successfully.
        hostel_notifications(sender=user, recipient=user, type='inventory_request_submitted')
    except Exception:
        pass

    return _serialize_resource_request(resource_request)


def _serialize_resource_request(resource_request):
    return {
        'id': resource_request.id,
        'hall_id': resource_request.hall.hall_id if resource_request.hall else '',
        'hall_name': resource_request.hall.hall_name if resource_request.hall else '',
        'request_type': resource_request.request_type,
        'justification': resource_request.justification,
        'status': resource_request.status,
        'review_remarks': resource_request.review_remarks,
        'reviewed_at': resource_request.reviewed_at.isoformat() if resource_request.reviewed_at else None,
        'created_at': resource_request.created_at.isoformat() if resource_request.created_at else None,
        'items': [
            {
                'item_id': item.id,
                'inventory_id': item.inventory_id,
                'item_name': item.item_name,
                'requested_quantity': item.requested_quantity,
                'remarks': item.remarks,
            }
            for item in resource_request.items.all()
        ],
    }


def getResourceRequestsService(*, user, hall_id: str = None):
    """Caretaker sees own-hall requests; warden sees hall requests; superuser sees all."""
    role, _ = resolve_hostel_rbac_role_service(user=user)
    if role == 'super_admin':
        hall = _get_required_hall_for_super_admin(hall_id=hall_id)
        return [_serialize_resource_request(req) for req in selectors.get_resource_requests_by_hall(hall=hall)]

    mapping = _ensure_inventory_role_access(
        user=user,
        allowed_roles=[UserHostelMapping.ROLE_CARETAKER, UserHostelMapping.ROLE_WARDEN],
    )
    requests = selectors.get_resource_requests_by_hall(hall=mapping.hall)
    return [_serialize_resource_request(req) for req in requests]


@transaction.atomic
def reviewResourceRequestService(*, user, request_id: int, decision: str, remarks: str = '', hall_id: str = None):
    """Warden/admin approves or rejects resource request."""
    try:
        resource_request = selectors.get_resource_request_by_id(request_id)
    except HostelResourceRequest.DoesNotExist:
        raise InventoryRequestNotFoundError('Resource request not found.')

    normalized_decision = (decision or '').strip().capitalize()
    if normalized_decision not in [WorkflowStatus.APPROVED, WorkflowStatus.REJECTED]:
        raise InvalidOperationError('decision must be Approved or Rejected.')
    if normalized_decision == WorkflowStatus.REJECTED and not (remarks or '').strip():
        raise InvalidOperationError('remarks are required when rejecting a request.')

    role, _ = resolve_hostel_rbac_role_service(user=user)
    if role == 'super_admin':
        hall = _get_required_hall_for_super_admin(hall_id=hall_id)
        if resource_request.hall_id != hall.id:
            raise UnauthorizedAccessError('Resource request does not belong to the specified hall.')
        resource_request.reviewed_by_admin = user
    else:
        mapping = _ensure_inventory_role_access(
            user=user,
            allowed_roles=[UserHostelMapping.ROLE_WARDEN],
        )
        if resource_request.hall_id != mapping.hall_id:
            raise UnauthorizedAccessError('Resource request does not belong to your hostel.')
        resource_request.reviewed_by_warden = selectors.get_faculty_by_extrainfo_id(user.extrainfo.id)

    resource_request.status = normalized_decision
    resource_request.review_remarks = (remarks or '').strip()
    resource_request.reviewed_at = timezone.now()
    resource_request.save(update_fields=[
        'status',
        'review_remarks',
        'reviewed_at',
        'reviewed_by_warden',
        'reviewed_by_admin',
        'updated_at',
    ])

    # Notify caretaker.
    try:
        from notification.views import hostel_notifications
        if resource_request.caretaker and resource_request.caretaker.id and resource_request.caretaker.id.user:
            notif_type = 'inventory_request_approved' if normalized_decision == WorkflowStatus.APPROVED else 'inventory_request_rejected'
            hostel_notifications(sender=user, recipient=resource_request.caretaker.id.user, type=notif_type)
    except Exception:
        pass

    return _serialize_resource_request(resource_request)


@transaction.atomic
def auditedInventoryUpdateService(*, user, inventory_id: int, quantity=None, condition_status: str = None, reason: str = ''):
    """UC-028: caretaker updates inventory and system records audit trail."""
    mapping = _ensure_inventory_role_access(
        user=user,
        allowed_roles=[UserHostelMapping.ROLE_CARETAKER],
    )
    try:
        inventory = selectors.get_inventory_by_id(inventory_id)
    except HostelInventory.DoesNotExist:
        raise InventoryNotFoundError(f'Inventory item with ID {inventory_id} not found.')

    if inventory.hall_id != mapping.hall_id:
        raise UnauthorizedAccessError('Inventory item does not belong to your hostel.')

    prev_qty = inventory.quantity
    prev_condition = inventory.condition_status

    if quantity is not None:
        quantity = int(quantity)
        if quantity < 0:
            raise InvalidOperationError('quantity cannot be negative.')
        inventory.quantity = quantity

    if condition_status is not None:
        normalized_condition = (condition_status or '').strip().capitalize()
        if normalized_condition not in InventoryConditionStatus.values:
            raise InvalidOperationError('Invalid condition_status value.')
        inventory.condition_status = normalized_condition

    inventory.save(update_fields=['quantity', 'condition_status'])

    HostelInventoryUpdateLog.objects.create(
        inventory=inventory,
        hall=inventory.hall,
        updated_by=user,
        previous_quantity=prev_qty,
        new_quantity=inventory.quantity,
        previous_condition=prev_condition,
        new_condition=inventory.condition_status,
        reason=(reason or '').strip(),
    )

    return _serialize_inventory_item(inventory)


def getInventoryUpdateLogsService(*, user, hall_id: str = None):
    """Return inventory update logs for hall scope or all (superuser)."""
    logs = []
    role, _ = resolve_hostel_rbac_role_service(user=user)
    if role == 'super_admin':
        hall = _get_required_hall_for_super_admin(hall_id=hall_id)
        logs = selectors.get_inventory_update_logs_by_hall(hall=hall)
    else:
        mapping = _ensure_inventory_role_access(
            user=user,
            allowed_roles=[UserHostelMapping.ROLE_CARETAKER, UserHostelMapping.ROLE_WARDEN],
        )
        logs = selectors.get_inventory_update_logs_by_hall(hall=mapping.hall)

    return [
        {
            'id': row.id,
            'inventory_id': row.inventory.inventory_id,
            'inventory_name': row.inventory.inventory_name,
            'hall_id': row.hall.hall_id,
            'hall_name': row.hall.hall_name,
            'previous_quantity': row.previous_quantity,
            'new_quantity': row.new_quantity,
            'previous_condition': row.previous_condition,
            'new_condition': row.new_condition,
            'reason': row.reason,
            'updated_by': row.updated_by.username if row.updated_by else '',
            'created_at': row.created_at.isoformat() if row.created_at else None,
        }
        for row in logs
    ]


@transaction.atomic
def createInventoryItemForCaretakerService(*, user, inventory_name: str, cost, quantity: int, condition_status: str = None):
    """Create initial inventory rows for caretaker's mapped hostel."""
    mapping = _ensure_inventory_role_access(
        user=user,
        allowed_roles=[UserHostelMapping.ROLE_CARETAKER],
    )

    name = (inventory_name or '').strip()
    if not name:
        raise InvalidOperationError('inventory_name is required.')

    quantity = int(quantity)
    if quantity < 0:
        raise InvalidOperationError('quantity cannot be negative.')

    parsed_cost = float(cost)
    if parsed_cost < 0:
        raise InvalidOperationError('cost cannot be negative.')

    normalized_condition = (condition_status or InventoryConditionStatus.GOOD).strip().capitalize()
    if normalized_condition not in InventoryConditionStatus.values:
        raise InvalidOperationError('Invalid condition_status value.')

    inventory = HostelInventory.objects.create(
        hall=mapping.hall,
        inventory_name=name,
        cost=parsed_cost,
        quantity=quantity,
        condition_status=normalized_condition,
    )
    return _serialize_inventory_item(inventory)


# ══════════════════════════════════════════════════════════════
# HOSTEL REPORT SERVICES (UC-034/UC-035)
# ══════════════════════════════════════════════════════════════

def _log_report_action(*, report, actor, action: str, metadata=None):
    HostelReportAuditLog.objects.create(
        report=report,
        actor=actor,
        action=action,
        metadata=metadata or {},
    )


def _resolve_report_scope(*, user, hall_id=None):
    role, mapping = resolve_hostel_rbac_role_service(user=user)
    if role not in ['caretaker', 'warden', 'super_admin']:
        raise UnauthorizedAccessError('Only caretaker, warden, or super admin can access report features.')

    if role == 'super_admin':
        if hall_id:
            hall = selectors.get_hall_by_hall_id_or_none(hall_id)
            if not hall:
                raise HallNotFoundError('Selected hostel does not exist.')
            return role, hall
        raise HostelReportValidationError('hall_id is required for super admin report generation.')

    if not mapping or not mapping.hall:
        raise UserHallMappingMissingError('You must be assigned to a hostel to generate reports.')

    if hall_id and mapping.hall.hall_id != hall_id:
        raise UnauthorizedAccessError('You can generate reports only for your assigned hostel.')

    return role, mapping.hall


def _normalize_report_filters(filters):
    normalized = filters or {}

    def _coerce_list(value):
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str):
            return [item.strip() for item in value.split(',') if item.strip()]
        return [str(value).strip()] if str(value).strip() else []

    return {
        'students': _coerce_list(normalized.get('students') or normalized.get('student_ids')),
        'room_blocks': _coerce_list(normalized.get('room_blocks') or normalized.get('blocks')),
        'room_numbers': _coerce_list(normalized.get('room_numbers') or normalized.get('rooms')),
        'statuses': _coerce_list(normalized.get('statuses') or normalized.get('status_filters')),
    }


def _ensure_report_params(*, report_type, start_date: date, end_date: date):
    valid_types = [choice.value for choice in HostelReportTypeChoices]
    if report_type not in valid_types:
        raise HostelReportValidationError('Invalid report_type selected.')
    if not start_date or not end_date:
        raise HostelReportValidationError('start_date and end_date are required.')
    if end_date < start_date:
        raise HostelReportValidationError('end_date cannot be earlier than start_date.')


def _serialize_hostel_report(report):
    attachments = [
        {
            'id': row.id,
            'file_name': row.file.name.split('/')[-1],
            'file_url': row.file.url if row.file else None,
            'uploaded_by': row.uploaded_by.username if row.uploaded_by else None,
            'uploaded_at': row.uploaded_at.isoformat() if row.uploaded_at else None,
        }
        for row in report.attachments.all()
    ]

    return {
        'id': report.id,
        'report_uid': report.report_uid,
        'hall_id': report.hall.hall_id if report.hall else None,
        'hall_name': report.hall.hall_name if report.hall else None,
        'created_by': report.created_by.username if report.created_by else None,
        'creator_role': report.creator_role,
        'report_type': report.report_type,
        'title': report.title,
        'start_date': report.start_date.isoformat() if report.start_date else None,
        'end_date': report.end_date.isoformat() if report.end_date else None,
        'filters': report.filters or {},
        'report_data': report.report_data or {},
        'status': report.status,
        'priority': report.priority,
        'submission_notes': report.submission_notes,
        'submitted_at': report.submitted_at.isoformat() if report.submitted_at else None,
        'reviewed_by': report.reviewed_by.username if report.reviewed_by else None,
        'reviewed_at': report.reviewed_at.isoformat() if report.reviewed_at else None,
        'review_feedback': report.review_feedback,
        'attachments': attachments,
        'created_at': report.created_at.isoformat() if report.created_at else None,
        'updated_at': report.updated_at.isoformat() if report.updated_at else None,
    }


def _filter_students_by_username(*, students_qs, usernames):
    if not usernames:
        return students_qs
    return students_qs.filter(id__user__username__in=usernames)


def _build_room_occupancy_section(*, hall, filters):
    rooms = selectors.get_rooms_by_hall(hall)
    blocks = filters.get('room_blocks') or []
    room_numbers = filters.get('room_numbers') or []
    if blocks:
        rooms = rooms.filter(block_no__in=blocks)
    if room_numbers:
        rooms = rooms.filter(room_no__in=room_numbers)

    rows = []
    total_capacity = 0
    total_occupied = 0
    for room in rooms:
        total_capacity += int(room.room_cap or 0)
        total_occupied += int(room.room_occupied or 0)
        rows.append(
            {
                'room': f"{room.block_no}-{room.room_no}",
                'capacity': int(room.room_cap or 0),
                'occupied': int(room.room_occupied or 0),
                'vacant': max(int(room.room_cap or 0) - int(room.room_occupied or 0), 0),
            }
        )

    occupancy_pct = round((total_occupied * 100.0 / total_capacity), 2) if total_capacity else 0
    return {
        'key': 'room_occupancy',
        'title': 'Room Occupancy Report',
        'summary': {
            'rooms': len(rows),
            'total_capacity': total_capacity,
            'total_occupied': total_occupied,
            'occupancy_percentage': occupancy_pct,
        },
        'chart': {
            'type': 'pie',
            'labels': ['Occupied', 'Vacant'],
            'values': [total_occupied, max(total_capacity - total_occupied, 0)],
        },
        'rows': rows,
    }


def _build_attendance_summary_section(*, hall, start_date, end_date, filters):
    attendance_qs = selectors.get_attendance_by_hall(hall).filter(date__range=[start_date, end_date])
    students_filter = filters.get('students') or []
    if students_filter:
        attendance_qs = attendance_qs.filter(student_id__id__user__username__in=students_filter)

    statuses = [item.lower() for item in (filters.get('statuses') or [])]
    if statuses:
        attendance_qs = attendance_qs.filter(status__in=statuses)

    total = attendance_qs.count()
    present = attendance_qs.filter(status=AttendanceStatus.PRESENT).count()
    absent = total - present

    return {
        'key': 'attendance_summary',
        'title': 'Attendance Summary Report',
        'summary': {
            'total_entries': total,
            'present_entries': present,
            'absent_entries': absent,
            'attendance_percentage': round((present * 100.0 / total), 2) if total else 0,
        },
        'chart': {
            'type': 'bar',
            'labels': ['Present', 'Absent'],
            'values': [present, absent],
        },
        'rows': [
            {
                'metric': 'Present',
                'value': present,
            },
            {
                'metric': 'Absent',
                'value': absent,
            },
        ],
    }


def _build_leave_analysis_section(*, hall, start_date, end_date, filters):
    leaves = selectors.get_leaves_by_hall(hall=hall).filter(start_date__gte=start_date, start_date__lte=end_date)
    students_filter = filters.get('students') or []
    if students_filter:
        leaves = leaves.filter(roll_num__in=students_filter)

    statuses = filters.get('statuses') or []
    if statuses:
        leaves = leaves.filter(status__in=statuses)

    total = leaves.count()
    approved = leaves.filter(status__iexact=LeaveStatus.APPROVED).count()
    rejected = leaves.filter(status__iexact=LeaveStatus.REJECTED).count()
    pending = leaves.filter(status__iexact=LeaveStatus.PENDING).count()

    return {
        'key': 'leave_analysis',
        'title': 'Leave Analysis Report',
        'summary': {
            'total_requests': total,
            'approved': approved,
            'rejected': rejected,
            'pending': pending,
        },
        'chart': {
            'type': 'pie',
            'labels': ['Approved', 'Rejected', 'Pending'],
            'values': [approved, rejected, pending],
        },
        'rows': [
            {
                'metric': 'Approved',
                'value': approved,
            },
            {
                'metric': 'Rejected',
                'value': rejected,
            },
            {
                'metric': 'Pending',
                'value': pending,
            },
        ],
    }


def _build_fine_disciplinary_section(*, hall, start_date, end_date, filters):
    fines = selectors.get_hostel_fines(hall=hall).filter(created_at__date__range=[start_date, end_date])
    students_filter = filters.get('students') or []
    if students_filter:
        fines = fines.filter(student__id__user__username__in=students_filter)

    statuses = filters.get('statuses') or []
    if statuses:
        fines = fines.filter(status__in=statuses)

    total_fines = fines.count()
    pending_fines = fines.filter(status=FineStatus.PENDING).count()
    paid_fines = fines.filter(status=FineStatus.PAID).count()
    total_amount = sum(Decimal(str(item.amount or 0)) for item in fines)

    complaints = selectors.get_complaints_by_hall(hall).filter(created_at__date__range=[start_date, end_date])
    open_complaints = complaints.filter(status__in=[ComplaintStatus.PENDING, ComplaintStatus.IN_PROGRESS, ComplaintStatus.ESCALATED]).count()

    return {
        'key': 'fine_disciplinary',
        'title': 'Fine and Disciplinary Report',
        'summary': {
            'total_fines': total_fines,
            'pending_fines': pending_fines,
            'paid_fines': paid_fines,
            'total_fine_amount': float(total_amount),
            'open_complaints': open_complaints,
        },
        'chart': {
            'type': 'bar',
            'labels': ['Pending Fines', 'Paid Fines', 'Open Complaints'],
            'values': [pending_fines, paid_fines, open_complaints],
        },
        'rows': [
            {
                'metric': 'Total Fine Amount',
                'value': float(total_amount),
            },
            {
                'metric': 'Pending Fine Count',
                'value': pending_fines,
            },
            {
                'metric': 'Open Complaint Count',
                'value': open_complaints,
            },
        ],
    }


def _build_complaint_resolution_section(*, hall, start_date, end_date, filters):
    complaints = selectors.get_complaints_by_hall(hall).filter(created_at__date__range=[start_date, end_date])
    students_filter = filters.get('students') or []
    if students_filter:
        complaints = complaints.filter(student__id__user__username__in=students_filter)

    statuses = filters.get('statuses') or []
    if statuses:
        complaints = complaints.filter(status__in=statuses)

    total = complaints.count()
    resolved = complaints.filter(status=ComplaintStatus.RESOLVED).count()
    escalated = complaints.filter(status=ComplaintStatus.ESCALATED).count()
    in_progress = complaints.filter(status=ComplaintStatus.IN_PROGRESS).count()

    return {
        'key': 'complaint_resolution',
        'title': 'Complaint Resolution Report',
        'summary': {
            'total_complaints': total,
            'resolved': resolved,
            'escalated': escalated,
            'in_progress': in_progress,
        },
        'chart': {
            'type': 'pie',
            'labels': ['Resolved', 'Escalated', 'In Progress'],
            'values': [resolved, escalated, in_progress],
        },
        'rows': [
            {
                'metric': 'Resolved Rate %',
                'value': round((resolved * 100.0 / total), 2) if total else 0,
            },
            {
                'metric': 'Escalated Count',
                'value': escalated,
            },
        ],
    }


def _build_guest_room_booking_section(*, hall, start_date, end_date, filters):
    bookings = selectors.get_bookings_by_hall(hall=hall).filter(booking_date__range=[start_date, end_date])
    students_filter = filters.get('students') or []
    if students_filter:
        bookings = bookings.filter(intender__username__in=students_filter)

    statuses = filters.get('statuses') or []
    if statuses:
        bookings = bookings.filter(status__in=statuses)

    total = bookings.count()
    approved = bookings.filter(status__in=[BookingStatus.APPROVED, BookingStatus.CONFIRMED]).count()
    rejected = bookings.filter(status=BookingStatus.REJECTED).count()
    pending = bookings.filter(status=BookingStatus.PENDING).count()

    return {
        'key': 'guest_room_booking',
        'title': 'Guest Room Booking Report',
        'summary': {
            'total_bookings': total,
            'approved_or_confirmed': approved,
            'rejected': rejected,
            'pending': pending,
        },
        'chart': {
            'type': 'bar',
            'labels': ['Approved/Confirmed', 'Rejected', 'Pending'],
            'values': [approved, rejected, pending],
        },
        'rows': [
            {
                'metric': 'Total Bookings',
                'value': total,
            },
            {
                'metric': 'Pending Bookings',
                'value': pending,
            },
        ],
    }


def _build_extended_stay_section(*, hall, start_date, end_date, filters):
    requests = selectors.get_extended_stay_requests_by_hall_and_status(hall=hall, statuses=None).filter(created_at__date__range=[start_date, end_date])
    students_filter = filters.get('students') or []
    if students_filter:
        requests = requests.filter(student__id__user__username__in=students_filter)

    statuses = filters.get('statuses') or []
    if statuses:
        requests = requests.filter(status__in=statuses)

    total = requests.count()
    approved = requests.filter(status=ExtendedStayStatusChoices.APPROVED).count()
    rejected = requests.filter(status=ExtendedStayStatusChoices.REJECTED).count()
    pending = requests.filter(status=ExtendedStayStatusChoices.PENDING).count()

    return {
        'key': 'extended_stay',
        'title': 'Extended Stay Report',
        'summary': {
            'total_requests': total,
            'approved': approved,
            'rejected': rejected,
            'pending': pending,
        },
        'chart': {
            'type': 'pie',
            'labels': ['Approved', 'Rejected', 'Pending'],
            'values': [approved, rejected, pending],
        },
        'rows': [
            {
                'metric': 'Total Requests',
                'value': total,
            },
            {
                'metric': 'Approval Rate %',
                'value': round((approved * 100.0 / total), 2) if total else 0,
            },
        ],
    }


def _generate_report_sections(*, report_type, hall, start_date, end_date, filters):
    builders = {
        HostelReportTypeChoices.ROOM_OCCUPANCY: lambda: [_build_room_occupancy_section(hall=hall, filters=filters)],
        HostelReportTypeChoices.ATTENDANCE_SUMMARY: lambda: [_build_attendance_summary_section(hall=hall, start_date=start_date, end_date=end_date, filters=filters)],
        HostelReportTypeChoices.LEAVE_ANALYSIS: lambda: [_build_leave_analysis_section(hall=hall, start_date=start_date, end_date=end_date, filters=filters)],
        HostelReportTypeChoices.FINE_DISCIPLINARY: lambda: [_build_fine_disciplinary_section(hall=hall, start_date=start_date, end_date=end_date, filters=filters)],
        HostelReportTypeChoices.COMPLAINT_RESOLUTION: lambda: [_build_complaint_resolution_section(hall=hall, start_date=start_date, end_date=end_date, filters=filters)],
        HostelReportTypeChoices.GUEST_ROOM_BOOKING: lambda: [_build_guest_room_booking_section(hall=hall, start_date=start_date, end_date=end_date, filters=filters)],
        HostelReportTypeChoices.EXTENDED_STAY: lambda: [_build_extended_stay_section(hall=hall, start_date=start_date, end_date=end_date, filters=filters)],
        HostelReportTypeChoices.COMPREHENSIVE: lambda: [
            _build_room_occupancy_section(hall=hall, filters=filters),
            _build_attendance_summary_section(hall=hall, start_date=start_date, end_date=end_date, filters=filters),
            _build_leave_analysis_section(hall=hall, start_date=start_date, end_date=end_date, filters=filters),
            _build_fine_disciplinary_section(hall=hall, start_date=start_date, end_date=end_date, filters=filters),
            _build_complaint_resolution_section(hall=hall, start_date=start_date, end_date=end_date, filters=filters),
            _build_guest_room_booking_section(hall=hall, start_date=start_date, end_date=end_date, filters=filters),
            _build_extended_stay_section(hall=hall, start_date=start_date, end_date=end_date, filters=filters),
        ],
    }

    sections = builders[report_type]()
    key_insights = []
    for section in sections:
        summary = section.get('summary') or {}
        if section['key'] == 'room_occupancy':
            key_insights.append(
                f"Hostel occupancy is {summary.get('occupancy_percentage', 0)}% for selected filters."
            )
        if section['key'] == 'attendance_summary':
            key_insights.append(
                f"Attendance percentage is {summary.get('attendance_percentage', 0)}% in selected period."
            )

    return {
        'generated_at': timezone.now().isoformat(),
        'sections': sections,
        'key_insights': key_insights,
    }


def generateHostelReportService(
    *,
    user,
    report_type: str,
    start_date: date,
    end_date: date,
    filters=None,
    title: str = '',
    hall_id: str = None,
    template_id=None,
):
    """Generate hostel report by type with date range and filters."""
    _ensure_report_params(report_type=report_type, start_date=start_date, end_date=end_date)
    creator_role, hall = _resolve_report_scope(user=user, hall_id=hall_id)

    normalized_filters = _normalize_report_filters(filters)
    if template_id:
        template = selectors.get_template_by_id_for_owner(template_id=int(template_id), owner=user)
        normalized_filters = _normalize_report_filters(template.template_filters)

    report_payload = _generate_report_sections(
        report_type=report_type,
        hall=hall,
        start_date=start_date,
        end_date=end_date,
        filters=normalized_filters,
    )

    report = HostelGeneratedReport.objects.create(
        hall=hall,
        created_by=user,
        creator_role=creator_role,
        report_type=report_type,
        title=(title or HostelReportTypeChoices(report_type).label).strip(),
        start_date=start_date,
        end_date=end_date,
        filters=normalized_filters,
        report_data=report_payload,
        status=HostelReportStatusChoices.DRAFT,
    )
    _log_report_action(
        report=report,
        actor=user,
        action='generated',
        metadata={
            'report_type': report_type,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
        },
    )

    report = selectors.get_report_by_id(report_id=report.id)
    return _serialize_hostel_report(report)


def listMyHostelReportsService(*, user):
    """List report history for the current user."""
    reports = selectors.get_reports_by_creator(user=user)
    return [_serialize_hostel_report(report) for report in reports]


@transaction.atomic
def saveReportFilterTemplateService(*, user, template_name: str, report_type: str, filters=None):
    """Save reusable filter template for report generation."""
    role, hall = _resolve_report_scope(user=user)
    if role not in ['caretaker', 'warden']:
        raise UnauthorizedAccessError('Only caretaker or warden can save report templates.')

    if report_type not in [choice.value for choice in HostelReportTypeChoices]:
        raise HostelReportValidationError('Invalid report_type for template.')

    name = (template_name or '').strip()
    if not name:
        raise HostelReportValidationError('template_name is required.')

    normalized_filters = _normalize_report_filters(filters)
    template, _ = HostelReportFilterTemplate.objects.update_or_create(
        owner=user,
        hall=hall,
        template_name=name,
        report_type=report_type,
        defaults={'template_filters': normalized_filters},
    )
    return {
        'id': template.id,
        'template_name': template.template_name,
        'report_type': template.report_type,
        'filters': template.template_filters,
        'updated_at': template.updated_at.isoformat() if template.updated_at else None,
    }


def listReportFilterTemplatesService(*, user, report_type=None):
    """List saved report filter templates."""
    role, hall = _resolve_report_scope(user=user)
    if role not in ['caretaker', 'warden']:
        raise UnauthorizedAccessError('Only caretaker or warden can load report templates.')

    templates = selectors.get_templates_by_owner_and_hall(owner=user, hall=hall, report_type=report_type)
    return [
        {
            'id': row.id,
            'template_name': row.template_name,
            'report_type': row.report_type,
            'filters': row.template_filters,
            'updated_at': row.updated_at.isoformat() if row.updated_at else None,
        }
        for row in templates
    ]


@transaction.atomic
def submitHostelReportToSuperAdminService(*, user, report_id: int, submission_notes: str = '', priority: str = 'Normal', supporting_documents=None):
    """Warden submits generated report to super admin for review."""
    role, _ = resolve_hostel_rbac_role_service(user=user)
    if role != 'warden':
        raise UnauthorizedAccessError('Only warden can submit reports to super admin.')

    try:
        report = selectors.get_report_by_id(report_id=report_id)
    except HostelGeneratedReport.DoesNotExist:
        raise HostelReportNotFoundError('Report not found.')

    if report.created_by_id != user.id:
        raise UnauthorizedAccessError('You can submit only reports you created.')

    if report.status not in [HostelReportStatusChoices.DRAFT, HostelReportStatusChoices.NEEDS_REVISION]:
        raise InvalidOperationError('Only draft/needs revision reports can be submitted.')

    if priority not in [choice.value for choice in HostelReportPriorityChoices]:
        raise HostelReportValidationError('Invalid priority selected.')

    report.submission_notes = (submission_notes or '').strip()
    report.priority = priority
    report.status = HostelReportStatusChoices.SUBMITTED
    report.submitted_at = timezone.now()
    report.save(update_fields=['submission_notes', 'priority', 'status', 'submitted_at', 'updated_at'])

    files = supporting_documents or []
    for file_obj in files:
        HostelReportAttachment.objects.create(
            report=report,
            uploaded_by=user,
            file=file_obj,
        )

    _log_report_action(
        report=report,
        actor=user,
        action='submitted',
        metadata={'priority': priority},
    )

    recipients = _get_super_admin_notification_recipients(exclude_user_id=user.id)
    _notify_room_vacation(sender=user, recipients=recipients, notif_type='report_submitted_superadmin')

    report = selectors.get_report_by_id(report_id=report.id)
    return _serialize_hostel_report(report)


def listSubmittedHostelReportsService(*, user, statuses=None, hall_id: str = None):
    """Super admin list of submitted/reviewed reports."""
    role, _ = resolve_hostel_rbac_role_service(user=user)
    if role != 'super_admin':
        raise UnauthorizedAccessError('Only super admin can review submitted reports.')

    hall = _get_required_hall_for_super_admin(hall_id=hall_id)
    reports = selectors.get_submitted_reports()
    reports = reports.filter(hall_id=hall.id)
    if statuses:
        reports = reports.filter(status__in=statuses)
    return [_serialize_hostel_report(report) for report in reports]


def getHostelReportDetailService(*, user, report_id: int, log_view=True, hall_id: str = None):
    """Get report detail if user is creator or super admin."""
    try:
        report = selectors.get_report_by_id(report_id=report_id)
    except HostelGeneratedReport.DoesNotExist:
        raise HostelReportNotFoundError('Report not found.')

    role, _ = resolve_hostel_rbac_role_service(user=user)
    if role != 'super_admin' and report.created_by_id != user.id:
        raise UnauthorizedAccessError('You are not authorized to view this report.')
    if role == 'super_admin':
        hall = _get_required_hall_for_super_admin(hall_id=hall_id)
        if report.hall_id != hall.id:
            raise UnauthorizedAccessError('Report does not belong to the specified hall.')

    if log_view:
        _log_report_action(
            report=report,
            actor=user,
            action='viewed',
            metadata={'status': report.status},
        )

    return _serialize_hostel_report(report)


@transaction.atomic
def reviewSubmittedHostelReportService(*, user, report_id: int, decision: str, feedback: str = '', hall_id: str = None):
    """Super admin reviews submitted report and provides feedback/decision."""
    role, _ = resolve_hostel_rbac_role_service(user=user)
    if role != 'super_admin':
        raise UnauthorizedAccessError('Only super admin can review submitted reports.')

    try:
        report = selectors.get_report_by_id(report_id=report_id)
    except HostelGeneratedReport.DoesNotExist:
        raise HostelReportNotFoundError('Report not found.')

    hall = _get_required_hall_for_super_admin(hall_id=hall_id)
    if report.hall_id != hall.id:
        raise UnauthorizedAccessError('Report does not belong to the specified hall.')

    if report.status not in [HostelReportStatusChoices.SUBMITTED, HostelReportStatusChoices.REVIEWED]:
        raise InvalidOperationError('Only submitted reports can be reviewed.')

    normalized_decision = (decision or '').strip().lower()
    if normalized_decision not in ['approved', 'needs_revision']:
        raise HostelReportValidationError('decision must be approved or needs_revision.')

    report.reviewed_by = user
    report.reviewed_at = timezone.now()
    report.review_feedback = (feedback or '').strip()
    report.status = (
        HostelReportStatusChoices.APPROVED
        if normalized_decision == 'approved'
        else HostelReportStatusChoices.NEEDS_REVISION
    )
    report.save(update_fields=['reviewed_by', 'reviewed_at', 'review_feedback', 'status', 'updated_at'])

    _log_report_action(
        report=report,
        actor=user,
        action='reviewed',
        metadata={'decision': normalized_decision},
    )

    feedback_notif_type = (
        'report_feedback_approved'
        if normalized_decision == 'approved'
        else 'report_feedback_revision_requested'
    )
    _notify_room_vacation(
        sender=user,
        recipients=[report.created_by],
        notif_type=feedback_notif_type,
    )

    report = selectors.get_report_by_id(report_id=report.id)
    return _serialize_hostel_report(report)


def logHostelReportDownloadService(*, user, report_id: int, download_format: str, hall_id: str = None):
    """Log report download activity for audit trail."""
    try:
        report = selectors.get_report_by_id(report_id=report_id)
    except HostelGeneratedReport.DoesNotExist:
        raise HostelReportNotFoundError('Report not found.')

    role, _ = resolve_hostel_rbac_role_service(user=user)
    if role != 'super_admin' and report.created_by_id != user.id:
        raise UnauthorizedAccessError('You are not authorized to download this report.')
    if role == 'super_admin':
        hall = _get_required_hall_for_super_admin(hall_id=hall_id)
        if report.hall_id != hall.id:
            raise UnauthorizedAccessError('Report does not belong to the specified hall.')

    _log_report_action(
        report=report,
        actor=user,
        action='downloaded',
        metadata={'format': download_format},
    )
    return _serialize_hostel_report(report)


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
