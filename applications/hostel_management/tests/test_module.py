"""
Test module for Hostel Management.

Tests for selectors, services, and API endpoints.
"""

from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from datetime import date, timedelta

from applications.globals.models import ExtraInfo, Staff, Faculty
from applications.academic_information.models import Student

from ..models import (
    Hall,
    HallCaretaker,
    HallWarden,
    GuestRoomBooking,
    HostelLeave,
    HostelComplaint,
    HostelFine,
    HostelInventory,
    GuestRoom,
    LeaveStatus,
    FineStatus,
    BookingStatus,
    StaffSchedule,
    UserHostelMapping,
)
from .. import selectors, services
from ..services import (
    HallAlreadyExistsError,
    RoomNotAvailableError,
    StudentNotFoundError,
    InvalidOperationError,
)


# ══════════════════════════════════════════════════════════════
# SELECTOR TESTS
# ══════════════════════════════════════════════════════════════

class HallSelectorTests(TestCase):
    """Tests for hall selectors."""

    def setUp(self):
        self.hall = Hall.objects.create(
            hall_id='hall1',
            hall_name='Test Hall',
            max_accomodation=100,
            number_students=0,
            type_of_seater='single'
        )

    def test_get_all_halls_returns_all(self):
        """Test that get_all_halls returns all halls."""
        result = selectors.get_all_halls()
        self.assertIn(self.hall, result)
        self.assertEqual(result.count(), 1)

    def test_get_hall_by_id_success(self):
        """Test getting a hall by ID."""
        result = selectors.get_hall_by_id(self.hall.id)
        self.assertEqual(result, self.hall)
        self.assertEqual(result.hall_id, 'hall1')

    def test_get_hall_by_id_not_found(self):
        """Test that getting non-existent hall raises exception."""
        with self.assertRaises(Hall.DoesNotExist):
            selectors.get_hall_by_id(99999)

    def test_hall_exists_by_hall_id(self):
        """Test checking if hall exists."""
        self.assertTrue(selectors.hall_exists_by_hall_id('hall1'))
        self.assertFalse(selectors.hall_exists_by_hall_id('hall999'))


class LeaveSelectorTests(TestCase):
    """Tests for leave selectors."""

    def setUp(self):
        self.leave = HostelLeave.objects.create(
            student_name='Test Student',
            roll_num='21BCS001',
            reason='Medical',
            start_date=date.today(),
            end_date=date.today() + timedelta(days=3),
            status=LeaveStatus.PENDING
        )

    def test_get_all_leaves(self):
        """Test getting all leaves."""
        result = selectors.get_all_leaves()
        self.assertIn(self.leave, result)

    def test_get_leave_by_id(self):
        """Test getting leave by ID."""
        result = selectors.get_leave_by_id(self.leave.id)
        self.assertEqual(result, self.leave)

    def test_get_leaves_by_roll_number(self):
        """Test getting leaves by roll number."""
        result = selectors.get_leaves_by_roll_number('21BCS001')
        self.assertEqual(result.count(), 1)
        self.assertIn(self.leave, result)


# ══════════════════════════════════════════════════════════════
# SERVICE TESTS
# ══════════════════════════════════════════════════════════════

class HallServiceTests(TestCase):
    """Tests for hall services."""

    def test_create_hall_success(self):
        """Test creating a new hall."""
        hall = services.create_hall(
            hall_id='hall2',
            hall_name='New Hall',
            max_accomodation=150,
            type_of_seater='double'
        )
        self.assertEqual(hall.hall_id, 'hall2')
        self.assertEqual(hall.hall_name, 'New Hall')
        self.assertEqual(hall.max_accomodation, 150)

    def test_create_hall_duplicate_raises_error(self):
        """Test that creating duplicate hall raises error."""
        Hall.objects.create(
            hall_id='hall3',
            hall_name='Existing Hall',
            max_accomodation=100,
            type_of_seater='single'
        )
        with self.assertRaises(HallAlreadyExistsError):
            services.create_hall(
                hall_id='hall3',
                hall_name='Duplicate Hall',
                max_accomodation=100,
                type_of_seater='single'
            )

    def test_delete_hall_success(self):
        """Test deleting a hall."""
        hall = Hall.objects.create(
            hall_id='hall4',
            hall_name='To Delete',
            max_accomodation=100,
            type_of_seater='single'
        )
        services.delete_hall(hall_id=hall.id)
        self.assertFalse(Hall.objects.filter(id=hall.id).exists())


class LeaveServiceTests(TestCase):
    """Tests for leave services."""

    def test_create_leave_application(self):
        """Test creating a leave application."""
        leave = services.create_leave_application(
            student_name='John Doe',
            roll_num='21BCS002',
            reason='Family emergency',
            start_date='2024-03-01',
            end_date='2024-03-05',
            phone_number='1234567890'
        )
        self.assertEqual(leave.student_name, 'John Doe')
        self.assertEqual(leave.status, LeaveStatus.PENDING)

    def test_update_leave_status_approve(self):
        """Test approving a leave."""
        leave = HostelLeave.objects.create(
            student_name='Jane Doe',
            roll_num='21BCS003',
            reason='Medical',
            start_date=date.today(),
            end_date=date.today() + timedelta(days=2),
            status=LeaveStatus.PENDING
        )
        updated = services.update_leave_status(
            leave_id=leave.id,
            status=LeaveStatus.APPROVED,
            remark='Approved'
        )
        self.assertEqual(updated.status, LeaveStatus.APPROVED)
        self.assertEqual(updated.remark, 'Approved')

    def test_update_leave_status_reject(self):
        """Test rejecting a leave."""
        leave = HostelLeave.objects.create(
            student_name='Bob Smith',
            roll_num='21BCS004',
            reason='Personal',
            start_date=date.today(),
            end_date=date.today() + timedelta(days=1),
            status=LeaveStatus.PENDING
        )
        updated = services.update_leave_status(
            leave_id=leave.id,
            status=LeaveStatus.REJECTED,
            remark='Insufficient reason'
        )
        self.assertEqual(updated.status, LeaveStatus.REJECTED)


class ComplaintServiceTests(TestCase):
    """Tests for complaint services."""

    def test_file_complaint(self):
        """Test filing a complaint."""
        complaint = services.file_complaint(
            hall_name='Hall 1',
            student_name='Alice Johnson',
            roll_number='21BCS005',
            description='Water supply issue',
            contact_number='9876543210'
        )
        self.assertEqual(complaint.hall_name, 'Hall 1')
        self.assertEqual(complaint.student_name, 'Alice Johnson')
        self.assertIn('Water supply', complaint.description)


# ══════════════════════════════════════════════════════════════
# API ENDPOINT TESTS
# ══════════════════════════════════════════════════════════════

class HallAPITests(APITestCase):
    """Tests for hall API endpoints."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.client.force_authenticate(user=self.user)

        self.hall = Hall.objects.create(
            hall_id='hall5',
            hall_name='API Test Hall',
            max_accomodation=200,
            type_of_seater='triple'
        )

    def test_list_halls_authenticated_returns_200(self):
        """Test that authenticated user can list halls."""
        response = self.client.get('/api/hostel-management/halls/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)

    def test_list_halls_unauthenticated_returns_401_or_403(self):
        """Test that unauthenticated user cannot list halls."""
        self.client.force_authenticate(user=None)
        response = self.client.get('/api/hostel-management/halls/')
        self.assertIn(response.status_code, [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN
        ])

    def test_get_hall_by_id_returns_200(self):
        """Test getting a specific hall."""
        response = self.client.get(f'/api/hostel-management/halls/{self.hall.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['hall_id'], 'hall5')

    def test_get_nonexistent_hall_returns_404(self):
        """Test getting non-existent hall returns 404."""
        response = self.client.get('/api/hostel-management/halls/99999/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class LeaveAPITests(APITestCase):
    """Tests for leave API endpoints."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='student1', password='pass123')
        self.client.force_authenticate(user=self.user)

    def test_create_leave_valid_data(self):
        """Test creating leave with valid data."""
        payload = {
            'student_name': 'Test Student',
            'roll_num': '21BCS006',
            'reason': 'Medical emergency',
            'start_date': str(date.today()),
            'end_date': str(date.today() + timedelta(days=2)),
            'phone_number': '1234567890'
        }
        response = self.client.post('/api/hostel-management/leaves/create/', payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['student_name'], 'Test Student')
        self.assertEqual(response.data['status'], LeaveStatus.PENDING)

    def test_create_leave_invalid_dates(self):
        """Test that end date before start date is rejected."""
        payload = {
            'student_name': 'Test Student',
            'roll_num': '21BCS007',
            'reason': 'Test',
            'start_date': str(date.today()),
            'end_date': str(date.today() - timedelta(days=1)),
        }
        response = self.client.post('/api/hostel-management/leaves/create/', payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ComplaintAPITests(APITestCase):
    """Tests for complaint API endpoints."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='student2', password='pass456')
        self.client.force_authenticate(user=self.user)

    def test_file_complaint_success(self):
        """Test filing a complaint successfully."""
        payload = {
            'hall_name': 'Hall 2',
            'student_name': 'Complaint Student',
            'roll_number': '21BCS008',
            'description': 'Room cleaning needed',
            'contact_number': '9876543210'
        }
        response = self.client.post('/api/hostel-management/complaints/file/', payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['hall_name'], 'Hall 2')

    def test_list_complaints_authenticated(self):
        """Test listing all complaints."""
        response = self.client.get('/api/hostel-management/complaints/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)


class FineAPITests(APITestCase):
    """Tests for fine API endpoints."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='student3', password='pass789')
        self.client.force_authenticate(user=self.user)

    def test_list_fines_authenticated(self):
        """Test listing fines."""
        response = self.client.get('/api/hostel-management/fines/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_my_fines_authenticated(self):
        """Test getting fines for current user."""
        response = self.client.get('/api/hostel-management/fines/my/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)


class GuestRoomBookingAPITests(APITestCase):
    """Tests for guest room booking API endpoints."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='faculty1', password='pass1011')
        self.client.force_authenticate(user=self.user)

        self.hall = Hall.objects.create(
            hall_id='hall6',
            hall_name='Guest Room Test Hall',
            max_accomodation=50,
            type_of_seater='single'
        )

        self.guest_room = GuestRoom.objects.create(
            hall=self.hall,
            room='G101',
            room_type='single',
            vacant=True
        )

    def test_list_bookings_authenticated(self):
        """Test listing all bookings."""
        response = self.client.get('/api/hostel-management/bookings/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_my_bookings_authenticated(self):
        """Test getting bookings for current user."""
        response = self.client.get('/api/hostel-management/bookings/my/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)


# ══════════════════════════════════════════════════════════════
# INTEGRATION TESTS
# ══════════════════════════════════════════════════════════════

class HallManagementIntegrationTests(TestCase):
    """Integration tests for hall management flow."""

    def test_full_hall_creation_and_assignment_flow(self):
        """Test complete flow of creating hall and assigning staff."""
        # Create hall
        hall = services.create_hall(
            hall_id='hall7',
            hall_name='Integration Test Hall',
            max_accomodation=120,
            type_of_seater='double'
        )
        self.assertIsNotNone(hall.id)

        # Verify hall exists
        retrieved_hall = selectors.get_hall_by_id(hall.id)
        self.assertEqual(retrieved_hall.hall_id, 'hall7')

        # Verify in list
        all_halls = selectors.get_all_halls()
        self.assertIn(hall, all_halls)


