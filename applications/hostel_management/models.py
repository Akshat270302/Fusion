import datetime
from django.db import models
from django.contrib.auth.models import User
from applications.globals.models import ExtraInfo, Staff, Faculty
from applications.academic_information.models import Student
from django.utils import timezone


# ══════════════════════════════════════════════════════════════
# CHOICES (TextChoices and IntegerChoices ONLY)
# ══════════════════════════════════════════════════════════════

class RoomStatus(models.TextChoices):
    BOOKED = 'Booked', 'Booked'
    CHECKED_IN = 'CheckedIn', 'Checked In'
    AVAILABLE = 'Available', 'Available'
    UNDER_MAINTENANCE = 'UnderMaintenance', 'Under Maintenance'


class DayOfWeek(models.TextChoices):
    MONDAY = 'Monday', 'Monday'
    TUESDAY = 'Tuesday', 'Tuesday'
    WEDNESDAY = 'Wednesday', 'Wednesday'
    THURSDAY = 'Thursday', 'Thursday'
    FRIDAY = 'Friday', 'Friday'
    SATURDAY = 'Saturday', 'Saturday'
    SUNDAY = 'Sunday', 'Sunday'


class BookingStatus(models.TextChoices):
    CONFIRMED = 'Confirmed', 'Confirmed'
    APPROVED = 'Approved', 'Approved'
    PENDING = 'Pending', 'Pending'
    REJECTED = 'Rejected', 'Rejected'
    CANCELED = 'Canceled', 'Canceled'
    CANCEL_REQUESTED = 'CancelRequested', 'Cancel Requested'
    CHECKED_IN = 'CheckedIn', 'Checked In'
    COMPLETE = 'Complete', 'Complete'
    COMPLETED = 'Completed', 'Completed'
    FORWARD = 'Forward', 'Forward'


class SeaterType(models.TextChoices):
    SINGLE = 'single', 'Single Seater'
    DOUBLE = 'double', 'Double Seater'
    TRIPLE = 'triple', 'Triple Seater'


class RoomType(models.TextChoices):
    SINGLE = 'single', 'Single'
    DOUBLE = 'double', 'Double'
    TRIPLE = 'triple', 'Triple'


class FineStatus(models.TextChoices):
    PENDING = 'Pending', 'Pending'
    PAID = 'Paid', 'Paid'


class FineCategory(models.TextChoices):
    RULE_VIOLATION = 'Rule Violation', 'Rule Violation'
    DAMAGE = 'Damage', 'Property Damage/Loss'
    ATTENDANCE = 'Attendance', 'Attendance Violation'
    ROOM_STANDARDS = 'Room Standards', 'Room Standards Violation'


class LeaveStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    APPROVED = 'Approved', 'Approved'
    REJECTED = 'Rejected', 'Rejected'


class AttendanceStatus(models.TextChoices):
    PRESENT = 'present', 'Present'
    ABSENT = 'absent', 'Absent'


class RoomAllocationStatus(models.TextChoices):
    ACTIVE = 'active', 'Active'
    VACATED = 'vacated', 'Vacated'


class ComplaintStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    IN_PROGRESS = 'in_progress', 'In Progress'
    ESCALATED = 'escalated', 'Escalated'
    RESOLVED = 'resolved', 'Resolved'


class InventoryConditionStatus(models.TextChoices):
    GOOD = 'Good', 'Good'
    DAMAGED = 'Damaged', 'Damaged'
    MISSING = 'Missing', 'Missing'
    DEPLETED = 'Depleted', 'Depleted'


class InventoryRequestType(models.TextChoices):
    REPLACEMENT = 'Replacement', 'Replacement'
    NEW = 'New', 'New'
    ADDITIONAL = 'Additional', 'Additional'


class WorkflowStatus(models.TextChoices):
    PENDING = 'Pending', 'Pending'
    APPROVED = 'Approved', 'Approved'
    REJECTED = 'Rejected', 'Rejected'
    FULFILLED = 'Fulfilled', 'Fulfilled'


class RoomChangeRequestStatus(models.TextChoices):
    PENDING = 'Pending', 'Pending'
    APPROVED = 'Approved', 'Approved'
    REJECTED = 'Rejected', 'Rejected'
    ALLOCATED = 'Allocated', 'Allocated'


class HostelOperationalStatus(models.TextChoices):
    ACTIVE = 'Active', 'Active'
    INACTIVE = 'Inactive', 'Inactive'
    UNDER_MAINTENANCE = 'UnderMaintenance', 'Under Maintenance'


class ReviewDecisionStatus(models.TextChoices):
    PENDING = 'Pending', 'Pending'
    APPROVED = 'Approved', 'Approved'
    REJECTED = 'Rejected', 'Rejected'


class ExtendedStayStatusChoices(models.TextChoices):
    PENDING = 'Pending', 'Pending'
    APPROVED = 'Approved', 'Approved'
    REJECTED = 'Rejected', 'Rejected'
    CANCELLED = 'Cancelled', 'Cancelled'


class VacationRequestStatusChoices(models.TextChoices):
    PENDING_CLEARANCE = 'Pending Clearance', 'Pending Clearance'
    CLEARANCE_APPROVED = 'Clearance Approved', 'Clearance Approved'
    CLEARANCE_PENDING_ACTION_REQUIRED = 'Clearance Pending - Action Required', 'Clearance Pending - Action Required'
    COMPLETED = 'Completed', 'Completed'


class ChecklistVerificationStatus(models.TextChoices):
    PENDING = 'Pending', 'Pending'
    VERIFIED = 'Verified', 'Verified'
    PENDING_ACTION = 'Pending Action', 'Pending Action'


class HostelReportTypeChoices(models.TextChoices):
    ROOM_OCCUPANCY = 'room_occupancy', 'Room Occupancy Report'
    ATTENDANCE_SUMMARY = 'attendance_summary', 'Attendance Summary Report'
    LEAVE_ANALYSIS = 'leave_analysis', 'Leave Analysis Report'
    FINE_DISCIPLINARY = 'fine_disciplinary', 'Fine and Disciplinary Report'
    COMPLAINT_RESOLUTION = 'complaint_resolution', 'Complaint Resolution Report'
    GUEST_ROOM_BOOKING = 'guest_room_booking', 'Guest Room Booking Report'
    EXTENDED_STAY = 'extended_stay', 'Extended Stay Report'
    COMPREHENSIVE = 'comprehensive', 'Comprehensive Hostel Report'


class HostelReportStatusChoices(models.TextChoices):
    DRAFT = 'Draft', 'Draft'
    SUBMITTED = 'Submitted', 'Submitted'
    REVIEWED = 'Reviewed', 'Reviewed'
    APPROVED = 'Approved', 'Approved'
    NEEDS_REVISION = 'Needs Revision', 'Needs Revision'


class HostelReportPriorityChoices(models.TextChoices):
    NORMAL = 'Normal', 'Normal'
    HIGH = 'High', 'High'
    URGENT = 'Urgent', 'Urgent'


# ══════════════════════════════════════════════════════════════
# MODELS
# ══════════════════════════════════════════════════════════════

class Hall(models.Model):
    """
    Records information related to various Hall of Residences.

    'hall_id' and 'hall_name' store id and name of a Hall of Residence.
    'max_accomodation' stores maximum accomodation limit of a Hall of Residence.
    'number_students' stores number of students currently residing in a Hall of Residence.
    """
    hall_id = models.CharField(max_length=10)
    hall_name = models.CharField(max_length=50)
    max_accomodation = models.IntegerField(default=0)
    number_students = models.PositiveIntegerField(default=0)
    assigned_batch = models.CharField(max_length=50, null=True, blank=True)
    type_of_seater = models.CharField(
        max_length=50,
        choices=SeaterType.choices,
        default=SeaterType.SINGLE
    )
    operational_status = models.CharField(
        max_length=20,
        choices=HostelOperationalStatus.choices,
        default=HostelOperationalStatus.INACTIVE,
    )

    class Meta:
        db_table = 'hostel_management_hall'
        ordering = ['hall_id']

    def __str__(self):
        return self.hall_id


class HostelBatch(models.Model):
    """
    Stores batch allocation configuration for hostels, including academic
    session and optional supporting document URL.
    """

    hall = models.ForeignKey(Hall, on_delete=models.CASCADE, related_name='hostel_batches')
    batch_name = models.CharField(max_length=80)
    academic_session = models.CharField(max_length=60)
    document_url = models.URLField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'hostel_management_hostelbatch'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['hall', 'batch_name', 'academic_session'],
                name='unique_hostel_batch_per_session',
            ),
        ]

    def __str__(self):
        return f"{self.hall.hall_id} - {self.batch_name} ({self.academic_session})"


class HostelLifecycleState(models.Model):
    """
    Tracks end-to-end hostel lifecycle progression for workflow orchestration.
    """

    hall = models.OneToOneField(Hall, on_delete=models.CASCADE, related_name='lifecycle_state')
    current_step = models.PositiveSmallIntegerField(default=1)
    staff_assigned = models.BooleanField(default=False)
    rooms_configured = models.BooleanField(default=False)
    hostel_activated = models.BooleanField(default=False)
    batch_assigned = models.BooleanField(default=False)
    eligible_students_fetched = models.BooleanField(default=False)
    bulk_allotment_completed = models.BooleanField(default=False)
    occupancy_updated = models.BooleanField(default=False)
    notifications_sent = models.BooleanField(default=False)
    operational = models.BooleanField(default=False)
    last_transition_note = models.CharField(max_length=255, blank=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hostel_management_hostellifecyclestate'
        ordering = ['hall__hall_id']

    def __str__(self):
        return f"{self.hall.hall_id} lifecycle (step {self.current_step})"


class UserHostelMapping(models.Model):
    """
    Stores a single hostel/hall association for each user in hostel module.

    This extends user profile data without changing the global auth schema.
    """
    ROLE_STUDENT = 'student'
    ROLE_WARDEN = 'warden'
    ROLE_CARETAKER = 'caretaker'
    ROLE_OTHER = 'other'

    ROLE_CHOICES = (
        (ROLE_STUDENT, 'Student'),
        (ROLE_WARDEN, 'Warden'),
        (ROLE_CARETAKER, 'Caretaker'),
        (ROLE_OTHER, 'Other'),
    )

    user = models.OneToOneField(
        ExtraInfo,
        on_delete=models.CASCADE,
        related_name='hostel_mapping',
    )
    hall = models.ForeignKey(
        Hall,
        on_delete=models.CASCADE,
        related_name='mapped_users',
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_OTHER)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hostel_management_userhostelmapping'
        ordering = ['user_id']

    def __str__(self):
        return f"{self.user_id} -> {self.hall.hall_id}"


class HallCaretaker(models.Model):
    """
    Records Caretakers of Hall of Residences.

    'hall' refers to related Hall of Residence.
    'staff' refers to related Staff details.
    """
    hall = models.ForeignKey(Hall, on_delete=models.CASCADE)
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE)
    start_date = models.DateField(default=timezone.now)
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'hostel_management_hallcaretaker'

    def __str__(self):
        return str(self.hall) + '  (' + str(self.staff.id.user.username) + ')'


class HallWarden(models.Model):
    """
    Records Wardens of Hall of Residences.

    'hall' refers to related Hall of Residence.
    'faculty' refers to related Faculty details.
    """
    class AssignmentRole(models.TextChoices):
        PRIMARY = 'primary', 'Primary'
        SECONDARY = 'secondary', 'Secondary'

    hall = models.ForeignKey(Hall, on_delete=models.CASCADE)
    faculty = models.ForeignKey(Faculty, on_delete=models.CASCADE)
    start_date = models.DateField(default=timezone.now)
    end_date = models.DateField(null=True, blank=True)
    assignment_role = models.CharField(
        max_length=20,
        choices=AssignmentRole.choices,
        default=AssignmentRole.PRIMARY,
    )
    is_active = models.BooleanField(default=True)
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'hostel_management_hallwarden'

    def __str__(self):
        return str(self.hall) + '  (' + str(self.faculty.id.user.username) + ')'


class GuestRoomBooking(models.Model):
    """
    Records information related to booking of guest rooms in various Hall of Residences.

    'hall' refers to related Hall of Residence.
    'intender' refers to the related User who has done the booking.
    'guest_name','guest_phone','guest_email','guest_address' stores details of guests.
    'rooms_required' stores the number of rooms booked.
    'guest_room_id' refers to related guest room.
    'total_guest' stores the number of guests.
    'purpose' stores the purpose of stay of guests.
    'arrival_date','arrival_time' stores the arrival date and time of the guests.
    'departure_date','departure_time' stores the departure date and time of the guests.
    'status' stores the status of booking from the available options in 'BookingStatus'.
    'booking_date' stores the date of booking.
    'nationality' stores the nationality of the guests.
    """
    hall = models.ForeignKey(Hall, on_delete=models.CASCADE)
    intender = models.ForeignKey(User, on_delete=models.CASCADE)
    guest_name = models.CharField(max_length=255)
    guest_phone = models.CharField(max_length=255)
    guest_email = models.CharField(max_length=255, blank=True)
    guest_address = models.TextField(blank=True)
    rooms_required = models.IntegerField(default=1, null=True, blank=True)
    guest_room_id = models.CharField(max_length=255, blank=True)
    total_guest = models.IntegerField(default=1)
    purpose = models.TextField()
    arrival_date = models.DateField(auto_now_add=False, auto_now=False)
    arrival_time = models.TimeField(auto_now_add=False, auto_now=False)
    departure_date = models.DateField(auto_now_add=False, auto_now=False)
    departure_time = models.TimeField(auto_now_add=False, auto_now=False)
    status = models.CharField(
        max_length=255,
        choices=BookingStatus.choices,
        default=BookingStatus.PENDING
    )
    rejection_reason = models.TextField(blank=True)
    decision_comment = models.TextField(blank=True)
    decision_by = models.ForeignKey(
        Staff,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='guestroom_booking_decisions',
    )
    decision_at = models.DateTimeField(null=True, blank=True)

    modified_count = models.PositiveIntegerField(default=0)
    last_modified_at = models.DateTimeField(null=True, blank=True)

    cancel_reason = models.TextField(blank=True)
    canceled_at = models.DateTimeField(null=True, blank=True)

    checked_in_at = models.DateTimeField(null=True, blank=True)
    checked_out_at = models.DateTimeField(null=True, blank=True)
    checked_in_by = models.ForeignKey(
        Staff,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='guestroom_booking_checkins',
    )
    checked_out_by = models.ForeignKey(
        Staff,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='guestroom_booking_checkouts',
    )
    id_proof_type = models.CharField(max_length=100, blank=True)
    id_proof_number = models.CharField(max_length=100, blank=True)
    checkin_notes = models.TextField(blank=True)

    inspection_notes = models.TextField(blank=True)
    damage_report = models.TextField(blank=True)
    damage_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    completed_with_damages = models.BooleanField(default=False)

    booking_charge_per_day = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    booking_date = models.DateField(auto_now_add=False, auto_now=False, default=timezone.now)
    nationality = models.CharField(max_length=255, blank=True)
    room_type = models.CharField(
        max_length=10,
        choices=RoomType.choices,
        default=RoomType.SINGLE
    )

    class Meta:
        db_table = 'hostel_management_guestroombooking'
        ordering = ['-booking_date']

    def __str__(self):
        return '%s ----> %s - %s' % (self.id, self.guest_name, self.status)


class StaffSchedule(models.Model):
    """
    Records schedule of staffs in various Hall of Residences.

    'hall' refers to the related Hall of Residence.
    'staff_id' refers to the related Staff.
    'staff_type' stores the type of staff, default is 'Caretaker'.
    'day' stores the assigned day of a schedule from the available choices in 'DayOfWeek'.
    'start_time' stores the start time of a schedule.
    'end_time' stores the end time of a schedule.
    """
    hall = models.ForeignKey(Hall, on_delete=models.CASCADE)
    staff_id = models.ForeignKey(Staff, on_delete=models.CASCADE)
    staff_type = models.CharField(max_length=100, default='Caretaker')
    day = models.CharField(max_length=15, choices=DayOfWeek.choices)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)

    class Meta:
        db_table = 'hostel_management_staffschedule'

    def __str__(self):
        return str(self.staff_id) + str(self.start_time) + '->' + str(self.end_time)


class HostelNoticeBoard(models.Model):
    """
    Records notices of various Hall of Residences.

    'hall' refers to the related Hall of Residence.
    'posted_by' refers to information related to the user who posted it.
    'head_line' stores the headline of the notice.
    'content' stores any file uploaded by the user as a part of notice.
    'description' stores description of a notice.
    """
    hall = models.ForeignKey(Hall, on_delete=models.CASCADE)
    posted_by = models.ForeignKey(ExtraInfo, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, blank=True, default='')
    head_line = models.CharField(max_length=100)
    content = models.FileField(upload_to='hostel_management/', blank=True, null=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'hostel_management_hostelnoticeboard'
        ordering = ['-id']

    def __str__(self):
        return self.head_line


class HostelStudentAttendence(models.Model):
    """
    Records attendance of students in various Hall of Residences.

    'hall' refers to the related Hall of Residence.
    'student_id' refers to the related Student.
    'date' stores the date for which attendance is being taken.
    'present' stores whether the student was present on a particular date.
    """
    hall = models.ForeignKey(Hall, on_delete=models.CASCADE)
    student_id = models.ForeignKey(Student, on_delete=models.CASCADE)
    date = models.DateField()
    present = models.BooleanField()
    status = models.CharField(
        max_length=10,
        choices=AttendanceStatus.choices,
        default=AttendanceStatus.PRESENT,
    )
    marked_by = models.ForeignKey(
        Staff,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='hostel_attendance_marked',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'hostel_management_hostelstudentattendence'
        constraints = [
            models.UniqueConstraint(fields=['student_id', 'date'], name='unique_hostel_attendance_student_date'),
        ]
        ordering = ['-date', 'student_id__id__user__username']

    def __str__(self):
        return str(self.student_id) + '->' + str(self.date) + '-' + str(self.status)


class HallRoom(models.Model):
    """
    Records information related to rooms in various Hall of Residences.

    'hall' refers to the related Hall of Residence.
    'room_no' stores the room number.
    'block_no' stores the block number a room belongs to.
    'room_cap' stores the maximum occupancy limit of a room.
    'room_occupied' stores the current number of occupants of a room.
    """
    hall = models.ForeignKey(Hall, on_delete=models.CASCADE)
    room_no = models.CharField(max_length=4)
    block_no = models.CharField(max_length=1)
    room_cap = models.IntegerField(default=3)
    room_occupied = models.IntegerField(default=0)

    class Meta:
        db_table = 'hostel_management_hallroom'

    def __str__(self):
        return str(self.hall) + str(self.block_no) + str(self.room_no) + str(self.room_cap) + str(self.room_occupied)


class WorkerReport(models.Model):
    """
    Records report of workers related to various Hall of Residences.

    'worker_id' stores the id of the worker.
    'hall' refers to the related Hall of Residence.
    'worker_name' stores the name of the worker.
    'year' and 'month' stores year and month respectively.
    'absent' stores the number of days a worker was absent in a month.
    'total_day' stores the number of days in a month.
    'remark' stores remarks for a worker.
    """
    worker_id = models.CharField(max_length=10)
    hall = models.ForeignKey(Hall, on_delete=models.CASCADE)
    worker_name = models.CharField(max_length=50)
    year = models.IntegerField(default=2020)
    month = models.IntegerField(default=1)
    absent = models.IntegerField(default=0)
    total_day = models.IntegerField(default=31)
    remark = models.CharField(max_length=100)

    class Meta:
        db_table = 'hostel_management_workerreport'

    def __str__(self):
        return str(self.worker_name) + '->' + str(self.month) + '-' + str(self.absent)


class HostelInventory(models.Model):
    """
    Model to store hostel inventory information.
    """
    inventory_id = models.AutoField(primary_key=True)
    hall = models.ForeignKey(Hall, on_delete=models.CASCADE)
    inventory_name = models.CharField(max_length=100)
    cost = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=0)
    condition_status = models.CharField(
        max_length=20,
        choices=InventoryConditionStatus.choices,
        default=InventoryConditionStatus.GOOD,
    )

    class Meta:
        db_table = 'hostel_management_hostelinventory'
        ordering = ['inventory_id']

    def __str__(self):
        return self.inventory_name


class HostelInventoryInspection(models.Model):
    """Inspection session initiated by caretaker for hostel inventory verification."""

    hall = models.ForeignKey(Hall, on_delete=models.CASCADE)
    caretaker = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True)
    remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'hostel_management_hostelinventoryinspection'
        ordering = ['-created_at']

    def __str__(self):
        return f"Inspection #{self.id} - {self.hall.hall_id}"


class HostelInventoryInspectionItem(models.Model):
    """Item-level observation captured in an inventory inspection."""

    inspection = models.ForeignKey(HostelInventoryInspection, on_delete=models.CASCADE, related_name='items')
    inventory = models.ForeignKey(HostelInventory, on_delete=models.CASCADE)
    expected_quantity = models.PositiveIntegerField(default=0)
    observed_quantity = models.PositiveIntegerField(default=0)
    observed_condition = models.CharField(
        max_length=20,
        choices=InventoryConditionStatus.choices,
        default=InventoryConditionStatus.GOOD,
    )
    discrepancy = models.BooleanField(default=False)
    discrepancy_remarks = models.TextField(blank=True)

    class Meta:
        db_table = 'hostel_management_hostelinventoryinspectionitem'
        ordering = ['id']

    def __str__(self):
        return f"InspectionItem #{self.id} ({self.inventory.inventory_name})"


class HostelResourceRequest(models.Model):
    """Caretaker request for replacement/new/additional resources."""

    hall = models.ForeignKey(Hall, on_delete=models.CASCADE)
    caretaker = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True)
    request_type = models.CharField(max_length=20, choices=InventoryRequestType.choices)
    justification = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=WorkflowStatus.choices, default=WorkflowStatus.PENDING)
    reviewed_by_warden = models.ForeignKey(
        Faculty,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='inventory_requests_reviewed_by_warden',
    )
    reviewed_by_admin = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='inventory_requests_reviewed_by_admin',
    )
    review_remarks = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hostel_management_hostelresourcerequest'
        ordering = ['-created_at']

    def __str__(self):
        return f"ResourceRequest #{self.id} ({self.request_type}) - {self.status}"


class HostelResourceRequestItem(models.Model):
    """Item lines for a resource request."""

    request = models.ForeignKey(HostelResourceRequest, on_delete=models.CASCADE, related_name='items')
    inventory = models.ForeignKey(HostelInventory, on_delete=models.SET_NULL, null=True, blank=True)
    item_name = models.CharField(max_length=120)
    requested_quantity = models.PositiveIntegerField(default=1)
    remarks = models.TextField(blank=True)

    class Meta:
        db_table = 'hostel_management_hostelresourcerequestitem'
        ordering = ['id']

    def __str__(self):
        return f"RequestItem #{self.id} ({self.item_name})"


class HostelInventoryUpdateLog(models.Model):
    """Audit trail for inventory quantity/condition changes."""

    inventory = models.ForeignKey(HostelInventory, on_delete=models.CASCADE)
    hall = models.ForeignKey(Hall, on_delete=models.CASCADE)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    previous_quantity = models.IntegerField(default=0)
    new_quantity = models.IntegerField(default=0)
    previous_condition = models.CharField(max_length=20, choices=InventoryConditionStatus.choices, default=InventoryConditionStatus.GOOD)
    new_condition = models.CharField(max_length=20, choices=InventoryConditionStatus.choices, default=InventoryConditionStatus.GOOD)
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'hostel_management_hostelinventoryupdatelog'
        ordering = ['-created_at']

    def __str__(self):
        return f"InventoryLog #{self.id} ({self.inventory.inventory_name})"


class HostelLeave(models.Model):
    """
    Records leave applications submitted by students.
    """
    student_name = models.CharField(max_length=100)
    roll_num = models.CharField(max_length=20)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, null=True, blank=True)
    hall = models.ForeignKey(Hall, on_delete=models.CASCADE, null=True, blank=True)
    reason = models.TextField()
    phone_number = models.CharField(max_length=20, null=True, blank=True)
    start_date = models.DateField(default=timezone.now)
    end_date = models.DateField()
    status = models.CharField(
        max_length=20,
        choices=LeaveStatus.choices,
        default=LeaveStatus.PENDING
    )
    remark = models.TextField(blank=True, null=True)
    file_upload = models.FileField(upload_to='hostel_management/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        db_table = 'hostel_management_hostelleave'
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.student_name}'s Leave"


class HostelComplaint(models.Model):
    """
    Records complaints filed by students with hostel-scoped filtering.
    
    - Student submits complaint (title + description)
    - Automatically linked to student's hostel
    - Caretaker can view and update status
    - Caretaker can escalate to warden with reason
    - Warden can resolve with resolution notes
    - Default status = pending
    """
    student = models.ForeignKey(Student, on_delete=models.CASCADE, null=True, blank=True)
    hall = models.ForeignKey(Hall, on_delete=models.CASCADE, null=True, blank=True)
    title = models.CharField(max_length=255, blank=True, default='')
    description = models.TextField(blank=True, default='')
    status = models.CharField(
        max_length=20,
        choices=ComplaintStatus.choices,
        default=ComplaintStatus.PENDING
    )
    # Escalation tracking fields
    escalation_reason = models.TextField(blank=True, default='', help_text='Reason for escalating to warden')
    escalated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='escalated_complaints', help_text='Caretaker who escalated the complaint')
    escalated_at = models.DateTimeField(null=True, blank=True, help_text='When the complaint was escalated')
    # Resolution tracking fields
    resolution_notes = models.TextField(blank=True, default='', help_text='Notes on how the complaint was resolved')
    resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='resolved_complaints', help_text='Warden who resolved the complaint')
    resolved_at = models.DateTimeField(null=True, blank=True, help_text='When the complaint was resolved')
    # Reassignment tracking
    reassigned_to = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name='reassigned_complaints', help_text='Caretaker complaint was reassigned to')
    reassignment_instructions = models.TextField(blank=True, default='', help_text='Instructions for caretaker on reassignment')
    reassigned_at = models.DateTimeField(null=True, blank=True, help_text='When the complaint was reassigned')
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        db_table = 'hostel_management_hostelcomplaint'
        ordering = ['-created_at']
        unique_together = [['student', 'title', 'created_at']]

    def __str__(self):
        return f"Complaint #{self.id} - {self.title} by {self.student.id.user.username if self.student else 'Unknown'}"


class HostelAllotment(models.Model):
    """
    Records hostel allotment information.
    """
    hall = models.ForeignKey(Hall, on_delete=models.CASCADE)
    assignedCaretaker = models.ForeignKey(Staff, on_delete=models.CASCADE, null=True)
    assignedWarden = models.ForeignKey(Faculty, on_delete=models.CASCADE, null=True)
    assignedBatch = models.CharField(max_length=50)

    class Meta:
        db_table = 'hostel_management_hostelallotment'

    def __str__(self):
        return str(self.hall) + str(self.assignedCaretaker) + str(self.assignedWarden) + str(self.assignedBatch)


class StudentDetails(models.Model):
    """
    Extended student information for hostel management.
    """
    id = models.CharField(primary_key=True, max_length=20)
    first_name = models.CharField(max_length=100, blank=True, null=True)
    last_name = models.CharField(max_length=100, blank=True, null=True)
    programme = models.CharField(max_length=100, blank=True, null=True)
    batch = models.CharField(max_length=100, blank=True, null=True)
    room_num = models.CharField(max_length=20, blank=True, null=True)
    hall_no = models.CharField(max_length=20, blank=True, null=True)
    hall_id = models.CharField(max_length=20, blank=True, null=True)
    specialization = models.CharField(max_length=100, blank=True, null=True)
    parent_contact = models.CharField(max_length=20, blank=True, null=True)
    address = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = 'hostel_management_studentdetails'

    def __str__(self):
        return self.first_name if self.first_name else self.id


class GuestRoom(models.Model):
    """
    Records guest room information.

    'hall' foreign key: the hostel to which the room belongs
    'room' guest room number
    'vacant' boolean value to determine if the room is vacant
    'occupied_till' date field that tells the next time the room will be vacant, null if 'vacant' == True
    """
    hall = models.ForeignKey(Hall, on_delete=models.CASCADE)
    room = models.CharField(max_length=255)
    occupied_till = models.DateField(null=True, blank=True)
    vacant = models.BooleanField(default=True)
    room_status = models.CharField(
        max_length=20,
        choices=RoomStatus.choices,
        default=RoomStatus.AVAILABLE,
    )
    room_type = models.CharField(
        max_length=10,
        choices=RoomType.choices,
        default=RoomType.SINGLE
    )

    class Meta:
        db_table = 'hostel_management_guestroom'

    @property
    def _vacant(self) -> bool:
        if self.occupied_till and self.occupied_till > timezone.now().date():
            self.vacant = False
        else:
            self.vacant = True
        return self.vacant

    def __str__(self):
        return f"{self.hall} - Room {self.room}"


class GuestRoomPolicy(models.Model):
    """
    Per-hall booking policy and pricing configuration for guest rooms.
    """
    hall = models.OneToOneField(Hall, on_delete=models.CASCADE, related_name='guest_room_policy')
    feature_enabled = models.BooleanField(default=True)
    charge_per_day = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    min_advance_days = models.PositiveIntegerField(default=0)
    max_advance_days = models.PositiveIntegerField(default=90)
    max_booking_duration_days = models.PositiveIntegerField(default=7)
    max_concurrent_bookings_per_student = models.PositiveIntegerField(default=1)
    eligibility_note = models.CharField(max_length=255, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hostel_management_guestroompolicy'

    def __str__(self):
        return f"Policy({self.hall.hall_id})"


class HostelFine(models.Model):
    """
    Records fines imposed on students.
    """
    fine_id = models.AutoField(primary_key=True)
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    caretaker = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True)
    hall = models.ForeignKey(Hall, on_delete=models.CASCADE)
    student_name = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.CharField(
        max_length=50,
        choices=FineCategory.choices,
        default=FineCategory.RULE_VIOLATION
    )
    status = models.CharField(
        max_length=50,
        choices=FineStatus.choices,
        default=FineStatus.PENDING
    )
    reason = models.TextField()
    evidence = models.FileField(upload_to='hostel/fines/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hostel_management_hostelfine'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.student_name}'s Fine - {self.amount} - {self.status}"


class StudentRoomAllocation(models.Model):
    """
    Tracks room assignments for students.
    """
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    room = models.ForeignKey(HallRoom, on_delete=models.CASCADE)
    hall = models.ForeignKey(Hall, on_delete=models.CASCADE)
    assigned_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True)
    assigned_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20,
        choices=RoomAllocationStatus.choices,
        default=RoomAllocationStatus.ACTIVE,
    )
    vacated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'hostel_management_studentroomallocation'
        ordering = ['-assigned_at']

    def __str__(self):
        return f"{self.student.id.user.username} -> {self.room.block_no}-{self.room.room_no} ({self.status})"


class HostelRoomGroup(models.Model):
    """Logical group of 3 students used for room allotment workflows."""

    hall = models.ForeignKey(Hall, on_delete=models.CASCADE, related_name='room_groups')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    is_auto_generated = models.BooleanField(default=False)
    member_signature = models.CharField(max_length=255)
    allotted_room = models.ForeignKey(HallRoom, on_delete=models.SET_NULL, null=True, blank=True, related_name='allotted_groups')
    allotted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'hostel_management_hostelroomgroup'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['hall', 'member_signature'],
                name='unique_hostel_group_signature_per_hall',
            ),
        ]

    def __str__(self):
        return f"Group#{self.id} ({self.hall.hall_id})"


class HostelRoomGroupMember(models.Model):
    """Member mapping to enforce single active group per student."""

    group = models.ForeignKey(HostelRoomGroup, on_delete=models.CASCADE, related_name='memberships')
    student = models.OneToOneField(Student, on_delete=models.CASCADE, related_name='hostel_group_membership')
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'hostel_management_hostelroomgroupmember'
        ordering = ['group_id', 'student_id']
        constraints = [
            models.UniqueConstraint(
                fields=['group', 'student'],
                name='unique_student_in_same_group',
            ),
        ]

    def __str__(self):
        return f"{self.student.id.user.username} -> Group#{self.group_id}"


class RoomChangeRequest(models.Model):
    """Tracks student room change requests and two-stage review decisions."""

    request_id = models.CharField(max_length=32, unique=True, blank=True)
    hall = models.ForeignKey(Hall, on_delete=models.CASCADE)
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    requested_by = models.ForeignKey(User, on_delete=models.CASCADE)

    current_room_no = models.CharField(max_length=30, blank=True)
    current_hall_id = models.CharField(max_length=20, blank=True)
    reason = models.TextField()
    preferred_room = models.CharField(max_length=30, blank=True)
    preferred_hall = models.CharField(max_length=20, blank=True)

    status = models.CharField(
        max_length=20,
        choices=RoomChangeRequestStatus.choices,
        default=RoomChangeRequestStatus.PENDING,
    )

    caretaker_decision = models.CharField(
        max_length=20,
        choices=ReviewDecisionStatus.choices,
        default=ReviewDecisionStatus.PENDING,
    )
    caretaker_remarks = models.TextField(blank=True)
    caretaker_decided_by = models.ForeignKey(
        Staff,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='room_change_caretaker_decisions',
    )
    caretaker_decided_at = models.DateTimeField(null=True, blank=True)

    warden_decision = models.CharField(
        max_length=20,
        choices=ReviewDecisionStatus.choices,
        default=ReviewDecisionStatus.PENDING,
    )
    warden_remarks = models.TextField(blank=True)
    warden_decided_by = models.ForeignKey(
        Faculty,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='room_change_warden_decisions',
    )
    warden_decided_at = models.DateTimeField(null=True, blank=True)

    allocated_room = models.ForeignKey(HallRoom, on_delete=models.SET_NULL, null=True, blank=True)
    allocation_notes = models.TextField(blank=True)
    allocated_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hostel_management_roomchangerequest'
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.request_id:
            self.request_id = f"RCR-{self.created_at.strftime('%Y%m%d')}-{self.id:05d}"
            super().save(update_fields=['request_id'])

    def __str__(self):
        return f"{self.request_id or self.id} - {self.student.id.user.username} - {self.status}"


class ExtendedStay(models.Model):
    """Student extended stay application and review workflow."""

    hall = models.ForeignKey(Hall, on_delete=models.CASCADE, related_name='extended_stays')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='extended_stays')
    requested_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='extended_stay_requests')

    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField()
    faculty_authorization = models.TextField()

    status = models.CharField(
        max_length=20,
        choices=ExtendedStayStatusChoices.choices,
        default=ExtendedStayStatusChoices.PENDING,
    )

    caretaker_decision = models.CharField(
        max_length=20,
        choices=ReviewDecisionStatus.choices,
        default=ReviewDecisionStatus.PENDING,
    )
    caretaker_remarks = models.TextField(blank=True)
    caretaker_decided_by = models.ForeignKey(
        Staff,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='extended_stay_caretaker_decisions',
    )
    caretaker_decided_at = models.DateTimeField(null=True, blank=True)

    warden_decision = models.CharField(
        max_length=20,
        choices=ReviewDecisionStatus.choices,
        default=ReviewDecisionStatus.PENDING,
    )
    warden_remarks = models.TextField(blank=True)
    warden_decided_by = models.ForeignKey(
        Faculty,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='extended_stay_warden_decisions',
    )
    warden_decided_at = models.DateTimeField(null=True, blank=True)

    cancel_reason = models.TextField(blank=True)
    canceled_at = models.DateTimeField(null=True, blank=True)

    modified_count = models.PositiveIntegerField(default=0)
    last_modified_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hostel_management_extendedstay'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.student.id.user.username} - {self.start_date} to {self.end_date} ({self.status})"


class RoomVacationRequest(models.Model):
    """Room vacation request raised by student and processed by caretaker/admin."""

    hall = models.ForeignKey(Hall, on_delete=models.CASCADE, related_name='room_vacation_requests')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='room_vacation_requests')
    requested_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='room_vacation_requests')
    allocation = models.ForeignKey(
        StudentRoomAllocation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='vacation_requests',
    )

    intended_vacation_date = models.DateField()
    reason = models.TextField()
    status = models.CharField(
        max_length=50,
        choices=VacationRequestStatusChoices.choices,
        default=VacationRequestStatusChoices.PENDING_CLEARANCE,
    )

    checklist_generated_at = models.DateTimeField(null=True, blank=True)
    checklist_acknowledged = models.BooleanField(default=False)
    checklist_acknowledged_at = models.DateTimeField(null=True, blank=True)

    room_inspection_notes = models.TextField(blank=True)
    room_damages_found = models.BooleanField(default=False)
    room_damage_description = models.TextField(blank=True)
    room_damage_fine_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    caretaker_review_comments = models.TextField(blank=True)
    borrowed_items_notes = models.TextField(blank=True)
    behavior_notes = models.TextField(blank=True)

    clearance_certificate_no = models.CharField(max_length=40, blank=True, unique=True, null=True)
    clearance_approved_by = models.ForeignKey(
        Staff,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_vacation_clearances',
    )
    clearance_approved_at = models.DateTimeField(null=True, blank=True)

    finalized_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='finalized_room_vacations',
    )
    finalized_at = models.DateTimeField(null=True, blank=True)
    completion_report = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hostel_management_roomvacationrequest'
        ordering = ['-created_at']

    def __str__(self):
        return f"VacationRequest#{self.id} - {self.student.id.user.username} ({self.status})"


class RoomVacationChecklistItem(models.Model):
    """Generated and caretaker-verified clearance checklist item for room vacation."""

    request = models.ForeignKey(
        RoomVacationRequest,
        on_delete=models.CASCADE,
        related_name='checklist_items',
    )
    code = models.CharField(max_length=50)
    title = models.CharField(max_length=120)
    details = models.TextField(blank=True)
    is_blocking = models.BooleanField(default=False)
    status = models.CharField(
        max_length=20,
        choices=ChecklistVerificationStatus.choices,
        default=ChecklistVerificationStatus.PENDING,
    )
    caretaker_comment = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hostel_management_roomvacationchecklistitem'
        ordering = ['id']
        constraints = [
            models.UniqueConstraint(
                fields=['request', 'code'],
                name='unique_vacation_checklist_code_per_request',
            ),
        ]

    def __str__(self):
        return f"VacationChecklist#{self.request_id}:{self.code} ({self.status})"


class HostelGeneratedReport(models.Model):
    """Generated hostel report with submission/review lifecycle."""

    report_uid = models.CharField(max_length=32, unique=True, blank=True)
    hall = models.ForeignKey(Hall, on_delete=models.CASCADE, related_name='generated_reports')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='hostel_reports_created')
    creator_role = models.CharField(max_length=20, default='other')

    report_type = models.CharField(
        max_length=40,
        choices=HostelReportTypeChoices.choices,
    )
    title = models.CharField(max_length=200)
    start_date = models.DateField()
    end_date = models.DateField()
    filters = models.JSONField(default=dict, blank=True)
    report_data = models.JSONField(default=dict, blank=True)

    status = models.CharField(
        max_length=20,
        choices=HostelReportStatusChoices.choices,
        default=HostelReportStatusChoices.DRAFT,
    )
    priority = models.CharField(
        max_length=10,
        choices=HostelReportPriorityChoices.choices,
        default=HostelReportPriorityChoices.NORMAL,
    )
    submission_notes = models.TextField(blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)

    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='hostel_reports_reviewed',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_feedback = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hostel_management_generatedreport'
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.report_uid:
            self.report_uid = f"HMR-{self.created_at.strftime('%Y%m%d')}-{self.id:06d}"
            super().save(update_fields=['report_uid'])

    def __str__(self):
        return f"{self.report_uid or self.id} - {self.report_type} - {self.status}"


class HostelReportFilterTemplate(models.Model):
    """Saved report filter template for quick reuse."""

    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='hostel_report_templates')
    hall = models.ForeignKey(Hall, on_delete=models.CASCADE, related_name='report_templates')
    template_name = models.CharField(max_length=100)
    report_type = models.CharField(max_length=40, choices=HostelReportTypeChoices.choices)
    template_filters = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hostel_management_reportfiltertemplate'
        ordering = ['-updated_at']
        constraints = [
            models.UniqueConstraint(
                fields=['owner', 'hall', 'template_name', 'report_type'],
                name='unique_report_template_per_owner_hall_and_type',
            ),
        ]

    def __str__(self):
        return f"{self.template_name} ({self.report_type})"


class HostelReportAttachment(models.Model):
    """Supporting documents attached during report submission."""

    report = models.ForeignKey(HostelGeneratedReport, on_delete=models.CASCADE, related_name='attachments')
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='hostel_report_attachments')
    file = models.FileField(upload_to='hostel/reports/supporting/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'hostel_management_reportattachment'
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"Attachment#{self.id} for Report#{self.report_id}"


class HostelReportAuditLog(models.Model):
    """Audit trail for report create/submit/view/review/download actions."""

    report = models.ForeignKey(HostelGeneratedReport, on_delete=models.CASCADE, related_name='audit_logs')
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='hostel_report_audit_actions')
    action = models.CharField(max_length=50)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'hostel_management_reportauditlog'
        ordering = ['-created_at']

    def __str__(self):
        return f"Report#{self.report_id} {self.action}"


class HostelTransactionHistory(models.Model):
    """
    Records transaction history of changes made to hostel data.
    """
    hall = models.ForeignKey(Hall, on_delete=models.CASCADE)
    change_type = models.CharField(max_length=100)  # Example: 'Caretaker', 'Warden', 'Batch'
    previous_value = models.CharField(max_length=255)
    new_value = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'hostel_management_hosteltransactionhistory'
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.change_type} change in {self.hall} at {self.timestamp}"


class HostelHistory(models.Model):
    """
    Records historical snapshots of hostel configuration.
    """
    hall = models.ForeignKey(Hall, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(default=timezone.now)
    caretaker = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, related_name='caretaker_history')
    batch = models.CharField(max_length=50, null=True)
    warden = models.ForeignKey(Faculty, on_delete=models.SET_NULL, null=True, related_name='warden_history')

    class Meta:
        db_table = 'hostel_management_hostelhistory'
        ordering = ['-timestamp']

    def __str__(self):
        return f"History for {self.hall.hall_name} - {self.timestamp}"
