from django.core.serializers import serialize
from django.http import HttpResponseBadRequest
from .models import HostelLeave, HallCaretaker
from applications.hostel_management.models import HallCaretaker, HallWarden
from django.http import JsonResponse, HttpResponse
from django.db import IntegrityError, models
from django.core.files.storage import default_storage
from rest_framework.exceptions import NotFound
from django.shortcuts import redirect
from django.template import loader
from django.shortcuts import get_object_or_404
from django.shortcuts import render
from django.http import HttpResponseRedirect
from django.shortcuts import render, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.permissions import IsAuthenticated
from .models import HallCaretaker, HallWarden
from django.urls import reverse
from .models import StudentDetails
from rest_framework.exceptions import APIException



from django.shortcuts import render, redirect

from .models import HostelLeave
from rest_framework.authentication import SessionAuthentication, BasicAuthentication
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.db.models import Q

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework import status



from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
# from .models import HostelStudentAttendance
from django.http import JsonResponse
from applications.globals.models import (Designation, ExtraInfo,
                                         HoldsDesignation, DepartmentInfo)
from applications.academic_information.models import Student
from applications.academic_information.models import *
from django.db.models import Q
import datetime
from datetime import time, datetime, date
from time import mktime, time, localtime
from .models import *
import xlrd
from .forms import GuestRoomBookingForm, HostelNoticeBoardForm
import re
from django.http import HttpResponse
from django.template.loader import get_template
from django.views.generic import View
from django.db.models import Q
from django.contrib import messages
from .utils import render_to_pdf, save_worker_report_sheet, get_caretaker_hall
from .utils import add_to_room, remove_from_room
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.authentication import TokenAuthentication
from django.http import JsonResponse
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
import json
import csv
import io
import zipfile

from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth import logout
from functools import wraps
from django.contrib.auth.decorators import login_required
from Fusion.settings.common import LOGIN_URL
from django.shortcuts import get_object_or_404, redirect, render
from django.db import transaction
from . import services
from . import selectors
from . import lifecycle_services
from .workflow_views import (
    hostel_workflow_bulk_allot,
    hostel_workflow_dashboard,
    hostel_workflow_eligible_students,
)
from .api.serializers import HostelComplaintSerializer
from .forms import HallForm
from notification.views import hostel_notifications
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction


def is_superuser(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return HoldsDesignation.objects.filter(
        working=user,
    ).filter(
        Q(designation__name__iexact='super_admin') | Q(designation__name__iexact='SuperAdmin')
    ).exists()


def _require_super_admin(user):
    if is_superuser(user):
        return None
    return Response({'error': 'Only Super Admin can perform this action.'}, status=status.HTTP_403_FORBIDDEN)


def _extract_hall_id(request):
    hall_id = (request.query_params.get('hall_id') or '').strip()
    if hall_id:
        return hall_id
    if hasattr(request, 'data'):
        return (request.data.get('hall_id') or '').strip()
    return ''


def _require_hall_for_super_admin(request):
    if not is_superuser(request.user):
        return None, None
    hall_id = _extract_hall_id(request)
    if not hall_id:
        return None, Response({'error': 'hall_id is required for super admin requests.'}, status=status.HTTP_400_BAD_REQUEST)
    return hall_id, None


def authorizeRoles(*allowed_roles):
    """ERP-style RBAC guard for hostel APIs.

    Supported roles: student, super_admin, warden, caretaker.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            role, _ = services.resolve_hostel_rbac_role_service(user=request.user)
            if role not in allowed_roles:
                return Response({'error': 'You are not authorized for this action.'}, status=status.HTTP_403_FORBIDDEN)
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator


def _parse_assignment_date(value, field_name):
    if not value:
        return None
    try:
        from datetime import datetime as dt

        return dt.strptime(value, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        raise ValueError(f'Invalid {field_name}. Use YYYY-MM-DD format.')


MAX_BATCH_DOC_SIZE = 5 * 1024 * 1024
ALLOWED_BATCH_DOC_EXTENSIONS = {'.pdf', '.docx', '.xlsx'}
REQUIRE_BATCH_DOCUMENT = False


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def get_batches(request):
    permission_error = _require_super_admin(request.user)
    if permission_error:
        return permission_error

    halls = [
        {
            'hall_id': hall.hall_id,
            'hall_name': hall.hall_name,
            'operational_status': hall.operational_status,
        }
        for hall in Hall.objects.all().order_by('hall_id')
    ]

    allocations = [
        {
            'id': allocation.id,
            'hall_id': allocation.hall.hall_id,
            'hall_name': allocation.hall.hall_name,
            'batch_name': allocation.batch_name,
            'academic_session': allocation.academic_session,
            'document_url': allocation.document_url,
            'created_by': allocation.created_by.username if allocation.created_by else None,
            'created_at': allocation.created_at,
        }
        for allocation in HostelBatch.objects.select_related('hall', 'created_by').all()
    ]

    available_batches = [
        {
            'value': str(row['batch']),
            'label': str(row['batch']),
            'student_count': row['student_count'],
        }
        for row in Student.objects.filter(batch__isnull=False)
        .values('batch')
        .annotate(student_count=models.Count('id'))
        .order_by('-batch')
    ]

    return Response(
        {
            'halls': halls,
            'allocations': allocations,
            'available_batches': available_batches,
        },
        status=status.HTTP_200_OK,
    )


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def get_guards(request):
    permission_error = _require_super_admin(request.user)
    if permission_error:
        return permission_error

    try:
        # Get staff with guard or security designation
        guard_user_ids = list(
            HoldsDesignation.objects.filter(
                designation__name__iregex=r'guard|security'
            ).values_list('working_id', flat=True)
        )

        guards_payload = []
        staff_qs = Staff.objects.select_related('id__user').all()
        
        if guard_user_ids:
            scoped = staff_qs.filter(id__user__id__in=guard_user_ids)
            if scoped.exists():
                staff_qs = scoped
        
        for staff in staff_qs.order_by('id__user__username'):
            try:
                if staff.id and staff.id.user:
                    guards_payload.append(
                        {
                            'staff_id': staff.id,
                            'username': staff.id.user.username,
                            'full_name': f"{staff.id.user.first_name} {staff.id.user.last_name}".strip() or staff.id.user.username,
                            'email': staff.id.user.email,
                        }
                    )
            except (AttributeError, Exception):
                # Skip staff with broken relationships
                continue

        return Response({'guard_staff': guards_payload}, status=status.HTTP_200_OK)
    except Exception as exc:
        return Response({'error': f'Failed to load guards: {str(exc)}'}, status=status.HTTP_400_BAD_REQUEST)
        batch_year = int(str(batch_name).strip())
    except (TypeError, ValueError):
        return Response(
            {'error': 'Batch must be a numeric year like 2023.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    document_url = None
    if document:
        filename = (document.name or '').lower()
        file_ext = f".{filename.split('.')[-1]}" if '.' in filename else ''
        if file_ext not in ALLOWED_BATCH_DOC_EXTENSIONS:
            return Response(
                {'error': 'Invalid file type. Allowed formats: pdf, docx, xlsx.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if document.size > MAX_BATCH_DOC_SIZE:
            return Response(
                {'error': 'File size exceeds 5 MB limit.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from datetime import datetime as dt

        safe_name = f"hostel_management/batch_documents/{hall_id}_{int(dt.now().timestamp())}_{document.name}"
        saved_path = default_storage.save(safe_name, document)
        document_url = default_storage.url(saved_path)

    with transaction.atomic():
        previous_batch = hall.assigned_batch
        hall.assigned_batch = batch_name
        hall.save(update_fields=['assigned_batch'])

        hall_number_digits = ''.join(ch for ch in hall.hall_id if ch.isdigit())
        hall_number = int(hall_number_digits) if hall_number_digits else None

        mapped_students = []
        if hall_number is not None:
            batch_students = Student.objects.filter(batch=batch_year).select_related('id__user')
            batch_students.update(hall_no=hall_number)

            for student in batch_students:
                mapped_students.append(student.id.user.username)
                UserHostelMapping.objects.update_or_create(
                    user=student.id,
                    defaults={
                        'hall': hall,
                        'role': UserHostelMapping.ROLE_STUDENT,
                    },
                )
                StudentDetails.objects.update_or_create(
                    id=student.id.user.username,
                    defaults={
                        'first_name': student.id.user.first_name,
                        'last_name': student.id.user.last_name,
                        'programme': student.programme,
                        'batch': str(student.batch),
                        'room_num': student.room_no or '',
                        'hall_no': str(hall_number),
                        'hall_id': hall.hall_id,
                        'specialization': student.specialization,
                    },
                )

        existing_allocation = HostelBatch.objects.filter(
            hall=hall,
            batch_name=batch_name,
            academic_session=academic_session,
        ).first()

        if not document_url and existing_allocation:
            document_url = existing_allocation.document_url

        allocation, created = HostelBatch.objects.update_or_create(
            hall=hall,
            batch_name=batch_name,
            academic_session=academic_session,
            defaults={
                'document_url': document_url,
                'created_by': request.user,
            },
        )

        for allotment in HostelAllotment.objects.filter(hall=hall):
            allotment.assignedBatch = batch_name
            allotment.save(update_fields=['assignedBatch'])

        HostelTransactionHistory.objects.create(
            hall=hall,
            change_type='BatchAllocation',
            previous_value=previous_batch or 'None',
            new_value=f'{batch_name} ({academic_session})',
        )

        lifecycle_services.HostelService.sync_lifecycle_state(
            hall,
            updated_by=request.user,
            note='Batch assigned',
        )

    return Response(
        {
            'message': 'Batch allocation saved successfully.',
            'students_mapped_to_hall': len(mapped_students),
            'allocation': {
                'id': allocation.id,
                'hall_id': hall.hall_id,
                'batch_name': allocation.batch_name,
                'academic_session': allocation.academic_session,
                'document_url': allocation.document_url,
                'created_by': request.user.username,
                'created_at': allocation.created_at,
                'created': created,
            },
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def get_caretakers(request):
    permission_error = _require_super_admin(request.user)
    if permission_error:
        return permission_error

    halls_payload = []
    for hall in Hall.objects.all().order_by('hall_id'):
        current_assignment = HallCaretaker.objects.filter(hall=hall, is_active=True).order_by('-assigned_at').first()
        halls_payload.append(
            {
                'hall_id': hall.hall_id,
                'hall_name': hall.hall_name,
                'current_caretaker': current_assignment.staff.id.user.username if current_assignment else None,
                'current_assignment': {
                    'start_date': current_assignment.start_date if current_assignment else None,
                    'end_date': current_assignment.end_date if current_assignment else None,
                } if current_assignment else None,
            }
        )

    caretakers_payload = []
    for staff in Staff.objects.select_related('id__user').all().order_by('id__user__username'):
        caretakers_payload.append(
            {
                'id_id': staff.id.user.username,
                'full_name': f"{staff.id.user.first_name} {staff.id.user.last_name}".strip(),
                'email': staff.id.user.email,
            }
        )

    return Response({'halls': halls_payload, 'caretaker_usernames': caretakers_payload}, status=status.HTTP_200_OK)


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def get_wardens(request):
    permission_error = _require_super_admin(request.user)
    if permission_error:
        return permission_error

    halls_payload = []
    for hall in Hall.objects.all().order_by('hall_id'):
        current_assignment = HallWarden.objects.filter(hall=hall, is_active=True).order_by('-assigned_at').first()
        halls_payload.append(
            {
                'hall_id': hall.hall_id,
                'hall_name': hall.hall_name,
                'current_warden': current_assignment.faculty.id.user.username if current_assignment else None,
                'current_assignment': {
                    'start_date': current_assignment.start_date if current_assignment else None,
                    'end_date': current_assignment.end_date if current_assignment else None,
                    'assignment_role': current_assignment.assignment_role if current_assignment else None,
                } if current_assignment else None,
            }
        )

    wardens_payload = []
    for faculty in Faculty.objects.select_related('id__user').all().order_by('id__user__username'):
        wardens_payload.append(
            {
                'id_id': faculty.id.user.username,
                'full_name': f"{faculty.id.user.first_name} {faculty.id.user.last_name}".strip(),
                'email': faculty.id.user.email,
            }
        )

    return Response({'halls': halls_payload, 'warden_usernames': wardens_payload}, status=status.HTTP_200_OK)


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def get_guards(request):
    permission_error = _require_super_admin(request.user)
    if permission_error:
        return permission_error

    try:
        # Get staff with guard or security designation
        guard_user_ids = list(
            HoldsDesignation.objects.filter(
                designation__name__iregex=r'guard|security'
            ).values_list('working_id', flat=True)
        )

        guards_payload = []
        staff_qs = Staff.objects.select_related('id__user').all()
        
        if guard_user_ids:
            scoped = staff_qs.filter(id__user__id__in=guard_user_ids)
            if scoped.exists():
                staff_qs = scoped
        
        for staff in staff_qs.order_by('id__user__username'):
            guards_payload.append(
                {
                    'staff_id': str(staff.pk),
                    'username': staff.id.user.username,
                    'full_name': f"{staff.id.user.first_name} {staff.id.user.last_name}".strip() or staff.id.user.username,
                    'email': staff.id.user.email,
                }
            )

        return Response({'guard_staff': guards_payload}, status=status.HTTP_200_OK)
    except Exception as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def assign_caretakers(request):
    permission_error = _require_super_admin(request.user)
    if permission_error:
        return permission_error

    hall_id = (request.data.get('hall_id') or '').strip()
    caretaker_username = (request.data.get('caretaker_username') or '').strip()
    force_reassign = bool(request.data.get('force_reassign', False))

    if not hall_id or not caretaker_username:
        return Response({'error': 'Please select both a hall and a caretaker.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        start_date = _parse_assignment_date(request.data.get('start_date'), 'start_date') or date.today()
        end_date = _parse_assignment_date(request.data.get('end_date'), 'end_date')
    except ValueError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    if end_date and end_date < start_date:
        return Response({'error': 'Invalid assignment dates.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        hall = Hall.objects.get(hall_id=hall_id)
    except Hall.DoesNotExist:
        return Response({'error': f'Hall with ID {hall_id} not found'}, status=status.HTTP_404_NOT_FOUND)

    try:
        caretaker_staff = Staff.objects.get(id__user__username=caretaker_username)
    except Staff.DoesNotExist:
        return Response({'error': f'Caretaker with username {caretaker_username} not found'}, status=status.HTTP_404_NOT_FOUND)

    concurrent_assignment = HallCaretaker.objects.filter(
        staff=caretaker_staff,
        is_active=True,
    ).exclude(hall=hall).first()

    if concurrent_assignment and not force_reassign:
        return Response(
            {
                'warning': f'{caretaker_username} is already assigned to {concurrent_assignment.hall.hall_name}. Confirm to reassign.',
                'requires_confirmation': True,
            },
            status=status.HTTP_409_CONFLICT,
        )

    with transaction.atomic():
        if concurrent_assignment:
            concurrent_assignment.is_active = False
            concurrent_assignment.end_date = start_date
            concurrent_assignment.save(update_fields=['is_active', 'end_date'])

        current_hall_assignment = HallCaretaker.objects.filter(hall=hall, is_active=True).first()
        if current_hall_assignment:
            current_hall_assignment.is_active = False
            current_hall_assignment.end_date = start_date
            current_hall_assignment.save(update_fields=['is_active', 'end_date'])

        new_assignment = HallCaretaker.objects.create(
            hall=hall,
            staff=caretaker_staff,
            start_date=start_date,
            end_date=end_date,
            is_active=True,
        )

        for hostel_allotment in HostelAllotment.objects.filter(hall=hall):
            hostel_allotment.assignedCaretaker = caretaker_staff
            hostel_allotment.save()

        current_warden = HallWarden.objects.filter(hall=hall, is_active=True).first()

        HostelTransactionHistory.objects.create(
            hall=hall,
            change_type='CaretakerAssignment',
            previous_value=current_hall_assignment.staff.id.user.username if current_hall_assignment else 'None',
            new_value=f"{caretaker_username} ({start_date} to {end_date or 'open'})",
        )

        HostelHistory.objects.create(
            hall=hall,
            caretaker=caretaker_staff,
            batch=hall.assigned_batch,
            warden=current_warden.faculty if current_warden else None,
        )

        extra_info = caretaker_staff.id
        UserHostelMapping.objects.update_or_create(
            user=extra_info,
            defaults={'hall': hall, 'role': UserHostelMapping.ROLE_CARETAKER},
        )

        hostel_notifications(request.user, caretaker_staff.id.user, 'caretaker_assignment')

        lifecycle_services.HostelService.sync_lifecycle_state(
            hall,
            updated_by=request.user,
            note='Caretaker assigned',
        )

    advisory = None
    active_caretaker_count = HallCaretaker.objects.filter(hall=hall, is_active=True).count()
    if active_caretaker_count < 2:
        advisory = 'Insufficient caretaker coverage advisory: consider assigning additional caretakers.'

    return Response(
        {
            'message': f'Caretaker {caretaker_username} assigned to Hall {hall_id} successfully',
            'assignment': {
                'start_date': new_assignment.start_date,
                'end_date': new_assignment.end_date,
                'is_active': new_assignment.is_active,
            },
            'advisory': advisory,
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def assign_warden(request):
    permission_error = _require_super_admin(request.user)
    if permission_error:
        return permission_error

    hall_id = (request.data.get('hall_id') or '').strip()
    warden_username = (request.data.get('warden_username') or request.data.get('warden_id') or '').strip()
    assignment_role = (request.data.get('assignment_role') or 'primary').strip().lower()
    force_reassign = bool(request.data.get('force_reassign', False))

    if not hall_id or not warden_username:
        return Response({'error': 'Please select both a hall and a warden.'}, status=status.HTTP_400_BAD_REQUEST)

    if assignment_role not in ['primary', 'secondary']:
        return Response({'error': 'Invalid warden designation.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        start_date = _parse_assignment_date(request.data.get('start_date'), 'start_date') or date.today()
        end_date = _parse_assignment_date(request.data.get('end_date'), 'end_date')
    except ValueError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    if end_date and end_date < start_date:
        return Response({'error': 'Invalid assignment dates.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        hall = Hall.objects.get(hall_id=hall_id)
    except Hall.DoesNotExist:
        return Response({'error': f'Hall with ID {hall_id} not found'}, status=status.HTTP_404_NOT_FOUND)

    try:
        warden = Faculty.objects.get(id__user__username=warden_username)
    except Faculty.DoesNotExist:
        return Response({'error': f'Warden with username {warden_username} not found'}, status=status.HTTP_404_NOT_FOUND)

    concurrent_assignment = HallWarden.objects.filter(
        faculty=warden,
        is_active=True,
    ).exclude(hall=hall).first()

    if concurrent_assignment and not force_reassign:
        return Response(
            {
                'warning': f'{warden_username} is already assigned to {concurrent_assignment.hall.hall_name}. Confirm to reassign.',
                'requires_confirmation': True,
            },
            status=status.HTTP_409_CONFLICT,
        )

    with transaction.atomic():
        if concurrent_assignment:
            concurrent_assignment.is_active = False
            concurrent_assignment.end_date = start_date
            concurrent_assignment.save(update_fields=['is_active', 'end_date'])

        current_hall_assignment = HallWarden.objects.filter(hall=hall, is_active=True).first()
        if current_hall_assignment:
            current_hall_assignment.is_active = False
            current_hall_assignment.end_date = start_date
            current_hall_assignment.save(update_fields=['is_active', 'end_date'])

        new_assignment = HallWarden.objects.create(
            hall=hall,
            faculty=warden,
            start_date=start_date,
            end_date=end_date,
            assignment_role=assignment_role,
            is_active=True,
        )

        current_caretaker = HallCaretaker.objects.filter(hall=hall, is_active=True).first()

        for hostel_allotment in HostelAllotment.objects.filter(hall=hall):
            hostel_allotment.assignedWarden = warden
            hostel_allotment.save()

        HostelTransactionHistory.objects.create(
            hall=hall,
            change_type='WardenAssignment',
            previous_value=current_hall_assignment.faculty.id.user.username if current_hall_assignment else 'None',
            new_value=f"{warden_username} ({assignment_role}, {start_date} to {end_date or 'open'})",
        )

        HostelHistory.objects.create(
            hall=hall,
            caretaker=current_caretaker.staff if current_caretaker else None,
            batch=hall.assigned_batch,
            warden=warden,
        )

        extra_info = warden.id
        UserHostelMapping.objects.update_or_create(
            user=extra_info,
            defaults={'hall': hall, 'role': UserHostelMapping.ROLE_WARDEN},
        )

        hostel_notifications(request.user, warden.id.user, 'warden_assignment')

        lifecycle_services.HostelService.sync_lifecycle_state(
            hall,
            updated_by=request.user,
            note='Warden assigned',
        )

    return Response(
        {
            'message': f'Warden {warden_username} assigned to Hall {hall_id} successfully',
            'assignment': {
                'start_date': new_assignment.start_date,
                'end_date': new_assignment.end_date,
                'assignment_role': new_assignment.assignment_role,
                'is_active': new_assignment.is_active,
            },
        },
        status=status.HTTP_201_CREATED,
    )


# //! My change


@login_required
def hostel_view(request, context={}):
    """
    This is a general function which is used for all the views functions.
    This function renders all the contexts required in templates.
    @param:
        request - HttpRequest object containing metadata about the user request.
        context - stores any data passed during request,by default is empty.

    @variables:
        hall_1_student - stores all hall 1 students
        hall_3_student - stores all hall 3 students
        hall_4_student - stores all hall 4 students
        all_hall - stores all the hall of residence
        all_notice - stores all notices of hostels (latest first)
    """
    # Check if the user is a superuser
    is_superuser = request.user.is_superuser

    all_hall = Hall.objects.all()
    halls_student = {}
    for hall in all_hall:
        halls_student[hall.hall_id] = Student.objects.filter(
            hall_no=int(hall.hall_id[4])).select_related('id__user')

    hall_staffs = {}
    for hall in all_hall:
        hall_staffs[hall.hall_id] = StaffSchedule.objects.filter(
            hall=hall).select_related('staff_id__id__user')

    all_notice = HostelNoticeBoard.objects.all().order_by("-id")
    hall_notices = {}
    for hall in all_hall:
        hall_notices[hall.hall_id] = HostelNoticeBoard.objects.filter(
            hall=hall).select_related('hall', 'posted_by__user')

    pending_guest_room_requests = {}
    for hall in all_hall:
        pending_guest_room_requests[hall.hall_id] = GuestRoomBooking.objects.filter(
            hall=hall, status='Pending').select_related('hall', 'intender')
        
       
    guest_rooms = {}
    for hall in all_hall:
        guest_rooms[hall.hall_id] = GuestRoom.objects.filter(
            hall=hall,vacant=True).select_related('hall')
    user_guest_room_requests = GuestRoomBooking.objects.filter(
        intender=request.user).order_by("-arrival_date")

    halls = Hall.objects.all()
    # Create a list to store additional details
    hostel_details = []

    # Loop through each hall and fetch assignedCaretaker and assignedWarden
    for hall in halls:
        try:
            caretaker = HallCaretaker.objects.filter(hall=hall).first()
            warden = HallWarden.objects.filter(hall=hall).first()
        except HostelAllotment.DoesNotExist:
            assigned_caretaker = None
            assigned_warden = None

        vacant_seat=(hall.max_accomodation-hall.number_students)
        hostel_detail = {
            'hall_id': hall.hall_id,
            'hall_name': hall.hall_name,
            'seater_type':hall.type_of_seater,
            'max_accomodation': hall.max_accomodation,
            'number_students': hall.number_students,
            'vacant_seat':vacant_seat,
            'assigned_batch': hall.assigned_batch,
            'assigned_caretaker': caretaker.staff.id.user.username if caretaker else None,
            'assigned_warden': warden.faculty.id.user.username if warden else None,
        }

        hostel_details.append(hostel_detail)

    Staff_obj = Staff.objects.all().select_related('id__user')
    hall1 = Hall.objects.get(hall_id='hall1')
    hall3 = Hall.objects.get(hall_id='hall3')
    hall4 = Hall.objects.get(hall_id='hall4')
    hall1_staff = StaffSchedule.objects.filter(hall=hall1)
    hall3_staff = StaffSchedule.objects.filter(hall=hall3)
    hall4_staff = StaffSchedule.objects.filter(hall=hall4)
    hall_caretakers = HallCaretaker.objects.all().select_related()
    hall_wardens = HallWarden.objects.all().select_related()
    all_students = Student.objects.all().select_related('id__user')
    all_students_id = []
    for student in all_students:
        all_students_id.append(student.id_id)
    # print(all_students)
    hall_student = ""
    current_hall = ""
    get_avail_room = []
    get_hall = get_caretaker_hall(hall_caretakers, request.user)
    if get_hall:
        get_hall_num = re.findall('[0-9]+', str(get_hall.hall_id))
        hall_student = Student.objects.filter(hall_no=int(
            str(get_hall_num[0]))).select_related('id__user')
        current_hall = 'hall'+str(get_hall_num[0])

    for hall in all_hall:
        total_rooms = HallRoom.objects.filter(hall=hall)
        for room in total_rooms:
            if (room.room_cap > room.room_occupied):
                get_avail_room.append(room)

    hall_caretaker_user = []
    for caretaker in hall_caretakers:
        hall_caretaker_user.append(caretaker.staff.id.user)

    hall_warden_user = []
    for warden in hall_wardens:
        hall_warden_user.append(warden.faculty.id.user)

    all_students = Student.objects.all().select_related('id__user')
    all_students_id = []
    for student in all_students:
        all_students_id.append(student.id_id)

    todays_date = date.today()
    current_year = todays_date.year
    current_month = todays_date.month

    if current_month != 1:
        worker_report = WorkerReport.objects.filter(Q(hall__hall_id=current_hall, year=current_year, month=current_month) | Q(
            hall__hall_id=current_hall, year=current_year, month=current_month-1))
    else:
        worker_report = WorkerReport.objects.filter(
            hall__hall_id=current_hall, year=current_year-1, month=12)

    attendance = HostelStudentAttendence.objects.all().select_related()
    halls_attendance = {}
    for hall in all_hall:
        halls_attendance[hall.hall_id] = HostelStudentAttendence.objects.filter(
            hall=hall).select_related()

    user_complaints = HostelComplaint.objects.filter(
        roll_number=request.user.username)
    user_leaves = HostelLeave.objects.filter(roll_num=request.user.username)
    my_leaves = []
    for leave in user_leaves:
        my_leaves.append(leave)
    my_complaints = []
    for complaint in user_complaints:
        my_complaints.append(complaint)

    all_leaves = HostelLeave.objects.all()
    all_complaints = HostelComplaint.objects.all()

    add_hostel_form = HallForm()
    warden_ids = Faculty.objects.all().select_related('id__user')

    # //! My change for imposing fines
    user_id = request.user
    staff_fine_caretaker = user_id.extrainfo.id
    students = Student.objects.all()

    fine_user = request.user

    if request.user.id in Staff.objects.values_list('id__user', flat=True):
        staff_fine_caretaker = request.user.extrainfo.id

        caretaker_fine_id = HallCaretaker.objects.filter(
            staff_id=staff_fine_caretaker).first()
        if caretaker_fine_id:
            hall_fine_id = caretaker_fine_id.hall_id
            hostel_fines = HostelFine.objects.filter(
                hall_id=hall_fine_id).order_by('fine_id')
            context['hostel_fines'] = hostel_fines

    # caretaker_fine_id = HallCaretaker.objects.get(staff_id=staff_fine_caretaker)
    # hall_fine_id = caretaker_fine_id.hall_id
    # hostel_fines = HostelFine.objects.filter(hall_id=hall_fine_id).order_by('fine_id')

    if request.user.id in Staff.objects.values_list('id__user', flat=True):
        staff_inventory_caretaker = request.user.extrainfo.id

        caretaker_inventory_id = HallCaretaker.objects.filter(
            staff_id=staff_inventory_caretaker).first()

        if caretaker_inventory_id:
            hall_inventory_id = caretaker_inventory_id.hall_id
            inventories = HostelInventory.objects.filter(
                hall_id=hall_inventory_id).order_by('inventory_id')

            # Serialize inventory data
            inventory_data = []
            for inventory in inventories:
                inventory_data.append({
                    'inventory_id': inventory.inventory_id,
                    'hall_id': inventory.hall_id,
                    'inventory_name': inventory.inventory_name,
                    # Convert DecimalField to string
                    'cost': str(inventory.cost),
                    'quantity': inventory.quantity,
                })

            inventory_data.sort(key=lambda x: x['inventory_id'])
            context['inventories'] = inventory_data

    # all students details for caretaker and warden
    if request.user.id in Staff.objects.values_list('id__user', flat=True):
        staff_student_info = request.user.extrainfo.id

        if HallCaretaker.objects.filter(staff_id=staff_student_info).exists():
            hall_caretaker_id = HallCaretaker.objects.get(
                staff_id=staff_student_info).hall_id

            hall_num = Hall.objects.get(id=hall_caretaker_id)
            hall_number = int(''.join(filter(str.isdigit,hall_num.hall_id)))

            
            # hostel_students_details = Student.objects.filter(hall_no=hall_number)
            # context['hostel_students_details']= hostel_students_details

            hostel_students_details = []
            students = Student.objects.filter(hall_no=hall_number)

            a_room=[]
            t_rooms = HallRoom.objects.filter(hall=hall_num)
            for room in t_rooms:
                if (room.room_cap > room.room_occupied):
                    a_room.append(room)

            # print(a_room)
            # Retrieve additional information for each student
            for student in students:
                student_info = {}
                student_info['student_id'] = student.id.id
                student_info['first_name'] = student.id.user.first_name
                student_info['programme'] = student.programme
                student_info['batch'] = student.batch
                student_info['hall_number'] = student.hall_no
                student_info['room_number'] = student.room_no
                student_info['specialization'] = student.specialization
                # student_info['parent_contact'] = student.parent_contact
                
                # Fetch address and phone number from ExtraInfo model
                extra_info = ExtraInfo.objects.get(user=student.id.user)
                student_info['address'] = extra_info.address
                student_info['phone_number'] = extra_info.phone_no
                
                hostel_students_details.append(student_info)

            # Sort the hostel_students_details list by roll number
            hostel_students_details = sorted(hostel_students_details, key=lambda x: x['student_id'])
            
            
            context['hostel_students_details'] = hostel_students_details
            context['av_room'] = a_room

    if request.user.id in Faculty.objects.values_list('id__user', flat=True):
        staff_student_info = request.user.extrainfo.id    
        if HallWarden.objects.filter(faculty_id=staff_student_info).exists():
            hall_warden_id = HallWarden.objects.get(
                faculty_id=staff_student_info).hall_id

            hall_num = Hall.objects.get(id=hall_warden_id)

            hall_number = int(''.join(filter(str.isdigit,hall_num.hall_id)))
            
            # hostel_students_details = Student.objects.filter(hall_no=hall_number)
            # context['hostel_students_details']= hostel_students_details

            hostel_students_details = []
            students = Student.objects.filter(hall_no=hall_number)

            # Retrieve additional information for each student
            for student in students:
                student_info = {}
                student_info['student_id'] = student.id.id
                student_info['first_name'] = student.id.user.first_name
                student_info['programme'] = student.programme
                student_info['batch'] = student.batch
                student_info['hall_number'] = student.hall_no
                student_info['room_number'] = student.room_no
                student_info['specialization'] = student.specialization
                # student_info['parent_contact'] = student.parent_contact
                
                # Fetch address and phone number from ExtraInfo model
                extra_info = ExtraInfo.objects.get(user=student.id.user)
                student_info['address'] = extra_info.address
                student_info['phone_number'] = extra_info.phone_no
                
                hostel_students_details.append(student_info)
                hostel_students_details = sorted(hostel_students_details, key=lambda x: x['student_id'])


            context['hostel_students_details'] = hostel_students_details

            


    # print(request.user.username);
    if Student.objects.filter(id_id=request.user.username).exists():
        user_id = request.user.username
        student_fines = HostelFine.objects.filter(student_id=user_id)
        # print(student_fines)
        context['student_fines'] = student_fines

    hostel_transactions = HostelTransactionHistory.objects.order_by('-timestamp')

    # Retrieve all hostel history entries
    hostel_history = HostelHistory.objects.order_by('-timestamp')
    context = {

        'all_hall': all_hall,
        'all_notice': all_notice,
        'staff': Staff_obj,
        'hall1_staff': hall1_staff,
        'hall3_staff': hall3_staff,
        'hall4_staff': hall4_staff,
        'hall_caretaker': hall_caretaker_user,
        'hall_warden': hall_warden_user,
        'room_avail': get_avail_room,
        'hall_student': hall_student,
        'worker_report': worker_report,
        'halls_student': halls_student,
        'current_hall': current_hall,
        'hall_staffs': hall_staffs,
        'hall_notices': hall_notices,
        'attendance': halls_attendance,
        'guest_rooms': guest_rooms,
        'pending_guest_room_requests': pending_guest_room_requests,
        'user_guest_room_requests': user_guest_room_requests,
        'all_students_id': all_students_id,
        'is_superuser': is_superuser,
        'warden_ids': warden_ids,
        'add_hostel_form': add_hostel_form,
        'hostel_details': hostel_details,
        'all_students_id': all_students_id,
        'my_complaints': my_complaints,
        'my_leaves': my_leaves,
        'all_leaves': all_leaves,
        'all_complaints': all_complaints,
        'staff_fine_caretaker': staff_fine_caretaker,
        'students': students,
        'hostel_transactions':hostel_transactions,
        'hostel_history':hostel_history,
        **context
    }

    return render(request, 'hostelmanagement/hostel.html', context)
    
def staff_edit_schedule(request):
    """
    This function is responsible for creating a new or updating an existing staff schedule.
    @param:
       request - HttpRequest object containing metadata about the user request.

    @variables:
       start_time - stores start time of the schedule.
       end_time - stores endtime of the schedule.
       staff_name - stores name of staff.
       staff_type - stores type of staff.
       day - stores assigned day of the schedule.
       staff - stores Staff instance related to staff_name.
       staff_schedule - stores StaffSchedule instance related to 'staff'.
       hall_caretakers - stores all hall caretakers.
    """
    if request.method == 'POST':
        start_time = datetime.datetime.strptime(
            request.POST["start_time"], '%H:%M').time()
        end_time = datetime.datetime.strptime(
            request.POST["end_time"], '%H:%M').time()
        staff_name = request.POST["Staff_name"]
        staff_type = request.POST["staff_type"]
        day = request.POST["day"]

        staff = Staff.objects.get(pk=staff_name)
        try:
            staff_schedule = StaffSchedule.objects.get(staff_id=staff)
            staff_schedule.day = day
            staff_schedule.start_time = start_time
            staff_schedule.end_time = end_time
            staff_schedule.staff_type = staff_type
            staff_schedule.save()
            messages.success(request, 'Staff schedule updated successfully.')
        except:
            hall_caretakers = HallCaretaker.objects.all()
            get_hall = ""
            get_hall = get_caretaker_hall(hall_caretakers, request.user)
            StaffSchedule(hall=get_hall, staff_id=staff, day=day,
                          staff_type=staff_type, start_time=start_time, end_time=end_time).save()
            messages.success(request, 'Staff schedule created successfully.')
    return HttpResponseRedirect(reverse("hostelmanagement:hostel_view"))


def staff_delete_schedule(request):
    """
    This function is responsible for deleting an existing staff schedule.
    @param:
      request - HttpRequest object containing metadata about the user request.

    @variables:
      staff_dlt_id - stores id of the staff whose schedule is to be deleted.
      staff - stores Staff object related to 'staff_name'
      staff_schedule - stores staff schedule related to 'staff'
    """
    if request.method == 'POST':
        staff_dlt_id = request.POST["dlt_schedule"]
        staff = Staff.objects.get(pk=staff_dlt_id)
        staff_schedule = StaffSchedule.objects.get(staff_id=staff)
        staff_schedule.delete()
    return HttpResponseRedirect(reverse("hostelmanagement:hostel_view"))


@login_required
def notice_board(request):
    """
    This function is used to create a form to show the notice on the Notice Board.
    @param:
      request - HttpRequest object containing metadata about the user request.

    @variables:
      hall - stores hall of residence related to the notice.
      head_line - stores headline of the notice. 
      content - stores content of the notice uploaded as file.
      description - stores description of the notice.
    """
    if request.method == "POST":
        form = HostelNoticeBoardForm(request.POST, request.FILES)

        if form.is_valid():
            hall = form.cleaned_data['hall']
            head_line = form.cleaned_data['head_line']
            content = form.cleaned_data['content']
            description = form.cleaned_data['description']

            new_notice = HostelNoticeBoard.objects.create(hall=hall, posted_by=request.user.extrainfo, head_line=head_line, content=content,
                                                          description=description)

            new_notice.save()
            messages.success(request, 'Notice created successfully.')
        return HttpResponseRedirect(reverse("hostelmanagement:hostel_view"))


@login_required
def delete_notice(request):
    """
    This function is responsible for deleting ana existing notice from the notice board.
    @param:
      request - HttpRequest object containing metadata about the user request.

    @variables:
      notice_id - stores id of the notice.
      notice - stores HostelNoticeBoard object related to 'notice_id'
    """
    if request.method != 'POST':
        return HttpResponseRedirect(reverse("hostelmanagement:hostel_view"))

    notice_id = request.POST.get("dlt_notice") or request.POST.get("id")
    if not notice_id and request.body:
        try:
            payload = json.loads(request.body.decode('utf-8'))
            notice_id = payload.get('id')
        except Exception:
            notice_id = None

    if not notice_id:
        if request.headers.get('Content-Type', '').startswith('application/json'):
            return JsonResponse({'error': 'Notice id is required.'}, status=400)
        return HttpResponseRedirect(reverse("hostelmanagement:hostel_view"))

    try:
        mapping = services.resolve_user_hall_mapping_service(user=request.user, strict=True)
    except services.UserHallMappingMissingError:
        mapping = None

    if not mapping or mapping.role not in ['warden', 'caretaker']:
        if request.headers.get('Content-Type', '').startswith('application/json'):
            return JsonResponse({'error': 'Only warden or caretaker can delete notices.'}, status=403)
        return HttpResponseRedirect(reverse("hostelmanagement:hostel_view"))

    try:
        notice = HostelNoticeBoard.objects.get(pk=notice_id)
    except HostelNoticeBoard.DoesNotExist:
        if request.headers.get('Content-Type', '').startswith('application/json'):
            return JsonResponse({'error': 'Notice not found.'}, status=404)
        return HttpResponseRedirect(reverse("hostelmanagement:hostel_view"))

    if notice.hall_id != mapping.hall_id:
        if request.headers.get('Content-Type', '').startswith('application/json'):
            return JsonResponse({'error': 'You can only delete notices from your hostel.'}, status=403)
        return HttpResponseRedirect(reverse("hostelmanagement:hostel_view"))

    notice.delete()

    if request.headers.get('Content-Type', '').startswith('application/json'):
        return JsonResponse({'message': 'Notice deleted successfully.'}, status=200)
    return HttpResponseRedirect(reverse("hostelmanagement:hostel_view"))


def edit_student_rooms_sheet(request):
    """
    This function is used to edit the room and hall of a multiple students.
    The user uploads a .xls file with Roll No, Hall No, and Room No to be updated.
    @param:
        request - HttpRequest object containing metadata about the user request.
    """
    if request.method == "POST":
        sheet = request.FILES["upload_rooms"]
        excel = xlrd.open_workbook(file_contents=sheet.read())
        all_rows = excel.sheets()[0]
        for row in all_rows:
            if row[0].value == "Roll No":
                continue
            roll_no = row[0].value
            hall_no = row[1].value
            if row[0].ctype == 2:
                roll_no = str(int(roll_no))
            if row[1].ctype == 2:
                hall_no = str(int(hall_no))

            room_no = row[2].value
            block = str(room_no[0])
            room = re.findall('[0-9]+', room_no)
            is_valid = True
            student = Student.objects.filter(id=roll_no.strip())
            hall = Hall.objects.filter(hall_id="hall"+hall_no[0])
            if student and hall.exists():
                Room = HallRoom.objects.filter(
                    hall=hall[0], block_no=block, room_no=str(room[0]))
                if Room.exists() and Room[0].room_occupied < Room[0].room_cap:
                    continue
                else:
                    is_valid = False
                    # print('Room  unavailable!')
                    messages.error(request, 'Room  unavailable!')
                    break
            else:
                is_valid = False
                # print("Wrong Credentials entered!")
                messages.error(request, 'Wrong credentials entered!')
                break

        if not is_valid:
            return HttpResponseRedirect(reverse("hostelmanagement:hostel_view"))

        for row in all_rows:
            if row[0].value == "Roll No":
                continue
            roll_no = row[0].value
            if row[0].ctype == 2:
                roll_no = str(int(roll_no))

            hall_no = str(int(row[1].value))
            room_no = row[2].value
            block = str(room_no[0])
            room = re.findall('[0-9]+', room_no)
            is_valid = True
            student = Student.objects.filter(id=roll_no.strip())
            remove_from_room(student[0])
            add_to_room(student[0], room_no, hall_no)
        messages.success(request, 'Hall Room change successfull !')

        return HttpResponseRedirect(reverse("hostelmanagement:hostel_view"))


def edit_student_room(request):
    """
    This function is used to edit the room number of a student.
    @param:
      request - HttpRequest object containing metadata about the user request.

    @varibles:
      roll_no - stores roll number of the student.
      room_no - stores new room number. 
      batch - stores batch number of the student generated from 'roll_no'
      students - stores students related to 'batch'.
    """
    if request.method == "POST":
        roll_no = request.POST["roll_no"]
        hall_room_no = request.POST["hall_room_no"]
        index = hall_room_no.find('-')
        room_no = hall_room_no[index+1:]
        hall_no = hall_room_no[:index]
        student = Student.objects.get(id=roll_no)
        remove_from_room(student)
        add_to_room(student, new_room=room_no, new_hall=hall_no)
        messages.success(request, 'Student room changed successfully.')
        return HttpResponseRedirect(reverse("hostelmanagement:hostel_view"))


def edit_attendance(request):
    """
    This function is used to edit the attendance of a student.
    @param:
      request - HttpRequest object containing metadata about the user request.

    @variables:
      student_id = The student whose attendance has to be updated.
      hall = The hall of the concerned student.
      date = The date on which attendance has to be marked.
    """
    if request.method == "POST":
        roll_no = request.POST["roll_no"]

        student = Student.objects.get(id=roll_no)
        hall = Hall.objects.get(hall_id='hall'+str(student.hall_no))
        date = datetime.datetime.today().strftime('%Y-%m-%d')

        if HostelStudentAttendence.objects.filter(student_id=student, date=date).exists() == True:
            messages.error(
                request, f'{student.id.id} is already marked present on {date}')
            return HttpResponseRedirect(reverse("hostelmanagement:hostel_view"))

        record = HostelStudentAttendence.objects.create(student_id=student,
                                                        hall=hall, date=date, present=True)
        record.save()

        messages.success(request, f'Attendance of {student.id.id} recorded.')

        return HttpResponseRedirect(reverse("hostelmanagement:hostel_view"))


# @login_required
# def generate_worker_report(request):
#     """
#     This function is used to read uploaded worker report spreadsheet(.xls) and generate WorkerReport instance and save it in the database.
#     @param:
#       request - HttpRequest object containing metadata about the user request.

#     @variables:
#       files - stores uploaded worker report file 
#       excel - stores the opened spreadsheet file raedy for data extraction.
#       user_id - stores user id of the current user.
#       sheet - stores a sheet from the uploaded spreadsheet.
#     """
#     if request.method == "POST":
#         try:
#             files = request.FILES['upload_report']
#             excel = xlrd.open_workbook(file_contents=files.read())
#             user_id = request.user.extrainfo.id
#             if str(excel.sheets()[0].cell(0, 0).value)[:5].lower() == str(HallCaretaker.objects.get(staff__id=user_id).hall):
#                 for sheet in excel.sheets():
#                     save_worker_report_sheet(excel, sheet, user_id)
#                     return HttpResponseRedirect(reverse("hostelmanagement:hostel_view"))

#             return HttpResponseRedirect(reverse("hostelmanagement:hostel_view"))
#         except:
#             messages.error(
#                 request, "Please upload a file in valid format before submitting")
#             return HttpResponseRedirect(reverse("hostelmanagement:hostel_view"))


# class GeneratePDF(View):
#     def get(self, request, *args, **kwargs):
#         """
#         This function is used to generate worker report in pdf format available for download.
#         @param:
#           request - HttpRequest object containing metadata about the user request.

#         @variables:
#           months - stores number of months for which the authorized user wants to generate worker report.
#           toadys_date - stores current date.
#           current_year - stores current year retrieved from 'todays_date'.
#           current_month - stores current month retrieved from 'todays_date'.
#           template - stores template returned by 'get_template' method.
#           hall_caretakers - stores all hall caretakers.
#           worker_report - stores 'WorkerReport' instances according to 'months'.

#         """
#         months = int(request.GET.get('months'))
#         todays_date = date.today()
#         current_year = todays_date.year
#         current_month = todays_date.month

#         template = get_template('hostelmanagement/view_report.html')

#         hall_caretakers = HallCaretaker.objects.all()
#         get_hall = ""
#         get_hall = get_caretaker_hall(hall_caretakers, request.user)
        
#         if months < current_month:
#             worker_report = WorkerReport.objects.filter(
#                 hall=get_hall, month__gte=current_month-months, year=current_year)
#         else:
#             worker_report = WorkerReport.objects.filter(Q(hall=get_hall, year=current_year, month__lte=current_month) | Q(
#                 hall=get_hall, year=current_year-1, month__gte=12-months+current_month))

#         worker = {
#             'worker_report': worker_report
#         }
#         html = template.render(worker)
#         pdf = render_to_pdf('hostelmanagement/view_report.html', worker)
#         if pdf:
#             response = HttpResponse(pdf, content_type='application/pdf')
#             filename = "Invoice_%s.pdf" % ("12341231")
#             content = "inline; filename='%s'" % (filename)
#             download = request.GET.get("download")
#             if download:
#                 content = "attachment; filename='%s'" % (filename)
#             response['Content-Disposition'] = content
#             return response
#         return HttpResponse("Not found")

@login_required
def generate_worker_report(request):
    if request.method == "POST":
        try:
            files = request.FILES.get('upload_report')
            if files:
                # Check if the file has a valid extension
                file_extension = files.name.split('.')[-1].lower()
                if file_extension not in ['xls', 'xlsx']:
                    messages.error(request, "Invalid file format. Please upload a .xls or .xlsx file.")
                    return HttpResponseRedirect(reverse("hostelmanagement:hostel_view"))
                
                excel = xlrd.open_workbook(file_contents=files.read())
                user_id = request.user.extrainfo.id
                for sheet in excel.sheets():
                    # print('111111111111111111111111111111111111',sheet[0])
                    save_worker_report_sheet(excel, sheet, user_id)
                return HttpResponseRedirect(reverse("hostelmanagement:hostel_view"))
            else:
                messages.error(request, "No file uploaded")
        except Exception as e:
            messages.error(request, f"Error processing file: {str(e)}")
    return HttpResponseRedirect(reverse("hostelmanagement:hostel_view"))


class GeneratePDF(View):
    def get(self, request, *args, **kwargs):
        """
        This function is used to generate worker report in pdf format available for download.
        @param:
          request - HttpRequest object containing metadata about the user request.

        @variables:
          months - stores number of months for which the authorized user wants to generate worker report.
          toadys_date - stores current date.
          current_year - stores current year retrieved from 'todays_date'.
          current_month - stores current month retrieved from 'todays_date'.
          template - stores template returned by 'get_template' method.
          hall_caretakers - stores all hall caretakers.
          worker_report - stores 'WorkerReport' instances according to 'months'.

        """
        months = int(request.GET.get('months'))
        # print('~~~~month',months)
        todays_date = date.today()
        current_year = todays_date.year
        current_month = todays_date.month

        template = get_template('hostelmanagement/view_report.html')

        hall_caretakers = HallCaretaker.objects.all()
        get_hall = ""
        get_hall = get_caretaker_hall(hall_caretakers, request.user)
        # print('~~~~~ get_hall' , get_hall)
        # print('month<curr_mn~~~~~~~',months,current_month)
        
        if months < current_month:
            worker_report = WorkerReport.objects.filter(
                hall=get_hall,)
        else:
            worker_report = WorkerReport.objects.filter(Q(hall=get_hall, year=current_year, month__lte=current_month) | Q(
                hall=get_hall, year=current_year-1, month__gte=12-months+current_month))

        worker = {
            'worker_report': worker_report
        }
        html = template.render(worker)
        pdf = render_to_pdf('hostelmanagement/view_report.html', worker)
        if pdf:
            response = HttpResponse(pdf, content_type='application/pdf')
            filename = "Invoice_%s.pdf" % ("12341231")
            content = "inline; filename='%s'" % (filename)
            download = request.GET.get("download")
            if download:
                content = "attachment; filename='%s'" % (filename)
            response['Content-Disposition'] = content
            return response
        return HttpResponse("Not found")


def hostel_notice_board(request):
    try:
        notices = services.getAllNoticesService(user=request.user)
    except services.UserHallMappingMissingError as exc:
        return JsonResponse({'error': str(exc)}, status=403)
    data = [
        {
            'id': notice.id,
            'title': notice.head_line,
            'hall_id': notice.hall.hall_id,
            'hall_name': notice.hall.hall_name,
            'head_line': notice.head_line,
            'content': notice.description,
            'description': notice.description,
            'content_url': notice.content.url if notice.content else None,
            'role': notice.role,
            'created_at': notice.created_at.isoformat() if notice.created_at else None,
            'posted_by': notice.posted_by.user.username,
        }
        for notice in notices
    ]
    return JsonResponse(data, safe=False)


def _get_notice_publisher_context(user):
    """Resolve whether user is warden/caretaker and fetch associated hall."""
    try:
        mapping = services.resolve_user_hall_mapping_service(user=user, strict=True)
    except services.UserHallMappingMissingError:
        return None, None, None
    return mapping.role, mapping.hall, user.extrainfo


@api_view(['POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def createNoticeController(request):
    """Create notice - only allowed for warden and caretaker."""
    return _create_notice_response(request)


def _create_notice_response(request):
    """Internal create-notice handler shared by notice endpoints."""
    title = (request.data.get('title') or request.data.get('headline') or request.data.get('head_line') or '').strip()
    content = (request.data.get('content') or request.data.get('description') or '').strip()

    if not title:
        return Response({'error': 'title is required.'}, status=status.HTTP_400_BAD_REQUEST)
    if not content:
        return Response({'error': 'content is required.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        notice = services.createNoticeService(
            user=request.user,
            title=title,
            content=content,
        )
    except services.UserHallMappingMissingError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_403_FORBIDDEN)
    except services.UnauthorizedAccessError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_403_FORBIDDEN)

    return Response({
        'id': notice.id,
        'title': notice.head_line,
        'content': notice.description,
        'created_by': notice.posted_by.user.username,
        'role': notice.role,
        'created_at': notice.created_at.isoformat() if notice.created_at else None,
        'hall_id': notice.hall.hall_id,
        'hall_name': notice.hall.hall_name,
    }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def getNoticesController(request):
    """Fetch notices for notice board consumers."""
    return _get_notices_response(request)


def _get_notices_response(request):
    """Internal notice-list handler shared by notice endpoints."""
    hall_id, hall_error = _require_hall_for_super_admin(request)
    if hall_error:
        return hall_error

    try:
        notices = services.getAllNoticesService(user=request.user, hall_id=hall_id)
    except services.UserHallMappingMissingError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_403_FORBIDDEN)
    except services.InvalidOperationError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    data = [
        {
            'id': notice.id,
            'title': notice.head_line,
            'content': notice.description,
            'created_by': notice.posted_by.user.username,
            'role': notice.role,
            'created_at': notice.created_at.isoformat() if notice.created_at else None,
            'hall_id': notice.hall.hall_id,
            'hall_name': notice.hall.hall_name,
            'content_url': notice.content.url if notice.content else None,
            # Keep legacy keys for compatibility with existing UI.
            'head_line': notice.head_line,
            'description': notice.description,
            'posted_by': notice.posted_by.user.username,
        }
        for notice in notices
    ]
    return Response(data, status=status.HTTP_200_OK)


@api_view(['GET', 'POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def noticeBoardController(request):
    """Single /notices endpoint supporting fetch and create operations."""
    if request.method == 'GET':
        return _get_notices_response(request)
    return _create_notice_response(request)


@api_view(['GET'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def student_notice_board(request):
    """Return notice board entries visible to the authenticated student."""
    try:
        notices = services.getAllNoticesService(user=request.user)
    except services.UserHallMappingMissingError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_403_FORBIDDEN)

    payload = [
        {
            'id': notice.id,
            'title': notice.head_line,
            'description': notice.description,
            'hall_id': notice.hall.hall_id,
            'hall_name': notice.hall.hall_name,
            'posted_by': notice.posted_by.user.username,
            'content_url': notice.content.url if notice.content else None,
        }
        for notice in notices
    ]
    return Response(payload, status=status.HTTP_200_OK)


@api_view(['POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def submitLeaveRequestController(request):
    """Student submits leave request for own hostel."""
    return _submit_leave_response(request)


def _submit_leave_response(request):
    """Internal submit-leave handler shared by new and legacy routes."""
    payload = request.data
    try:
        leave = services.submitLeaveRequestService(
            user=request.user,
            student_name=payload.get('student_name'),
            roll_num=payload.get('roll_num'),
            phone_number=payload.get('phone_number'),
            reason=payload.get('reason'),
            start_date=payload.get('start_date'),
            end_date=payload.get('end_date'),
        )
    except services.UserHallMappingMissingError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_403_FORBIDDEN)
    except (services.LeaveValidationError, services.StudentNotFoundError) as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except services.UnauthorizedAccessError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_403_FORBIDDEN)

    try:
        sender = request.user
        leave_type = 'leave_request'
        hostel_staff = HallCaretaker.objects.filter(hall=leave.hall)
        for caretaker in hostel_staff:
            hostel_notifications(sender, caretaker.staff.id.user, leave_type)
    except Exception:
        pass

    return Response(
        {
            'message': 'Leave request submitted successfully.',
            'leave': {
                'id': leave.id,
                'student_name': leave.student_name,
                'roll_num': leave.roll_num,
                'phone_number': leave.phone_number,
                'reason': leave.reason,
                'start_date': leave.start_date.isoformat(),
                'end_date': leave.end_date.isoformat(),
                'status': leave.status,
                'hall_id': leave.hall.hall_id if leave.hall else None,
            },
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(['GET'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def getStudentLeavesController(request):
    """Student gets own leave requests scoped by own hostel."""
    return _student_leaves_response(request)


def _student_leaves_response(request):
    """Internal student-leave-list handler shared by new and legacy routes."""
    try:
        leaves = services.getStudentLeaveRequestsService(user=request.user)
    except services.UserHallMappingMissingError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_403_FORBIDDEN)
    except services.UnauthorizedAccessError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_403_FORBIDDEN)

    payload = [
        {
            'id': leave.id,
            'student_name': leave.student_name,
            'roll_num': leave.roll_num,
            'reason': leave.reason,
            'phone_number': leave.phone_number,
            'start_date': leave.start_date.isoformat(),
            'end_date': leave.end_date.isoformat(),
            'status': leave.status.lower() if leave.status else 'pending',
            'remark': leave.remark,
            'hall_id': leave.hall.hall_id if leave.hall else None,
        }
        for leave in leaves
    ]
    return Response({'leaves': payload}, status=status.HTTP_200_OK)


@api_view(['GET'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def getPendingLeavesController(request):
    """Caretaker/warden gets all leave requests (pending + past) for own hostel."""
    return _pending_leaves_response(request)


def _pending_leaves_response(request):
    """Internal caretaker-leave-list handler shared by new and legacy routes."""
    try:
        leaves = services.getPendingLeaveRequestsService(user=request.user)
    except services.UserHallMappingMissingError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_403_FORBIDDEN)
    except services.UnauthorizedAccessError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_403_FORBIDDEN)

    payload = [
        {
            'id': leave.id,
            'student_name': leave.student_name,
            'roll_num': leave.roll_num,
            'reason': leave.reason,
            'phone_number': leave.phone_number,
            'start_date': leave.start_date.isoformat(),
            'end_date': leave.end_date.isoformat(),
            'status': leave.status.lower() if leave.status else 'pending',
            'remark': leave.remark,
            'hall_id': leave.hall.hall_id if leave.hall else None,
        }
        for leave in leaves
    ]
    return Response(payload, status=status.HTTP_200_OK)


@api_view(['POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def updateLeaveStatusController(request):
    """Caretaker/warden approves/rejects leave request for own hostel."""
    return _update_leave_status_response(request)


def _update_leave_status_response(request):
    """Internal leave-status-update handler shared by new and legacy routes."""
    leave_id = request.data.get('leave_id')
    status_value = request.data.get('status')
    remark = request.data.get('remark')

    if not leave_id:
        return Response({'error': 'leave_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
    if not status_value:
        return Response({'error': 'status is required.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        leave = services.updateLeaveStatusService(
            user=request.user,
            leave_id=int(leave_id),
            status=status_value,
            remark=remark,
        )
    except ValueError:
        return Response({'error': 'leave_id must be an integer.'}, status=status.HTTP_400_BAD_REQUEST)
    except services.LeaveNotFoundError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_404_NOT_FOUND)
    except (services.InvalidOperationError, services.UnauthorizedAccessError, services.UserHallMappingMissingError) as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    try:
        sender = request.user
        recipient = User.objects.get(username=leave.roll_num)
        notification_type = 'leave_accept' if leave.status.lower() == 'approved' else 'leave_reject'
        hostel_notifications(sender, recipient, notification_type)
    except Exception:
        pass

    return Response(
        {
            'status': 'success',
            'leave': {
                'id': leave.id,
                'status': leave.status.lower(),
                'remark': leave.remark,
            },
            'message': 'Leave status updated successfully.',
        },
        status=status.HTTP_200_OK,
    )


# Backward-compatible endpoint aliases used by current frontend.
@api_view(['POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def create_hostel_leave(request):
    return _submit_leave_response(request)


@api_view(['GET'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def all_leave_data(request):
    return _pending_leaves_response(request)

# hostel_complaints_list caretaker can see all hostel complaints

@login_required
def hostel_complaint_list(request):
    user_id = request.user.id

    try:
        # Assuming the user's profile is stored in extrainfo
        staff = request.user.extrainfo.id
    except AttributeError:
        staff = None

    if staff is not None and HallCaretaker.objects.filter(staff_id=staff).exists():
        complaints = HostelComplaint.objects.all()
        return render(request, 'hostelmanagement/hostel_complaint.html', {'complaints': complaints})
    else:
        return HttpResponse('<script>alert("You are not authorized to access this page"); window.location.href = "/hostelmanagement/"</script>')


@login_required
def get_students(request):
    try:
        staff = request.user.extrainfo.id
        print(staff)
    except AttributeError:
        staff = None

    if HallCaretaker.objects.filter(staff_id=staff).exists():
        hall_id = HallCaretaker.objects.get(staff_id=staff).hall_id
        print(hall_id)
        hall_no = Hall.objects.get(id=hall_id)
        print(hall_no)
        student_details = StudentDetails.objects.filter(hall_id=hall_no)

        return render(request, 'hostelmanagement/student_details.html', {'students': student_details})

    elif HallWarden.objects.filter(faculty_id=staff).exists():
        hall_id = HallWarden.objects.get(faculty_id=staff).hall_id
        student_details = StudentDetails.objects.filter(hall_id=hall_no)

        return render(request, 'hostelmanagement/student_details.html', {'students': student_details})
    else:
        return HttpResponse('<script>alert("You are not authorized to access this page"); window.location.href = "/hostelmanagement/"</script>')

# Student can post complaints


class PostComplaint(APIView):
    # Assuming you are using session authentication
    authentication_classes = [SessionAuthentication]
    # Allow only authenticated users to access the view
    permission_classes = [IsAuthenticated]

    def dispatch(self, request, *args, **kwargs):
        # print(request.user.username)
        if not request.user.is_authenticated:
            # Redirect to the login page if user is not authenticated
            return redirect('/hostelmanagement')
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        return render(request, 'hostelmanagement/post_complaint_form.html')

    def post(self, request):
        hall_name = request.data.get('hall_name')
        student_name = request.data.get('student_name')
        roll_number = request.data.get('roll_number')
        description = request.data.get('description')
        contact_number = request.data.get('contact_number')

        # Assuming the student's name is stored in the user object
        student_name = request.user.username

        complaint = HostelComplaint.objects.create(
            hall_name=hall_name,
            student_name=student_name,
            roll_number=roll_number,
            description=description,
            contact_number=contact_number
        )

        # Use JavaScript to display a pop-up message after submission
        return HttpResponse('<script>alert("Complaint submitted successfully"); window.location.href = "/hostelmanagement";</script>')


# // student can see his leave status

class my_leaves(View):
    @method_decorator(login_required, name='dispatch')
    def get(self, request, *args, **kwargs):
        try:
            # Get the user ID from the request's user
            user_id = str(request.user)

            # Retrieve leaves registered by the current student based on their roll number
            my_leaves = HostelLeave.objects.filter(roll_num__iexact=user_id)
            # Construct the context to pass to the template
            context = {
                'leaves': my_leaves
            }

            # Render the template with the context data
            return render(request, 'hostelmanagement/my_leaves.html', context)

        except User.DoesNotExist:
            # Handle the case where the user with the given ID doesn't exist
            return HttpResponse(f"User with ID {user_id} does not exist.")


class HallIdView(APIView):
    authentication_classes = []  # Allow public access for testing
    permission_classes = []  # Allow any user to access the view

    def get(self, request, *args, **kwargs):
        hall_id = HostelAllotment.objects.values('hall_id')
        return Response(hall_id, status=status.HTTP_200_OK)


@login_required(login_url=LOGIN_URL)
def logout_view(request):
    logout(request)
    return redirect("/")


@method_decorator(user_passes_test(is_superuser), name='dispatch')
class AssignCaretakerView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]
    template_name = 'hostelmanagement/assign_caretaker.html'

    def get(self, request, *args, **kwargs):
        hall = Hall.objects.all()
        caretaker_usernames = Staff.objects.all()
        return render(request, self.template_name, {'halls': hall, 'caretaker_usernames': caretaker_usernames})

    def post(self, request, *args, **kwargs):
        hall_id = request.data.get('hall_id')
        caretaker_username = request.data.get('caretaker_username')

        try:
            hall = Hall.objects.get(hall_id=hall_id)
            caretaker_staff = Staff.objects.get(
                id__user__username=caretaker_username)

            # Retrieve the previous caretaker for the hall, if any
            prev_hall_caretaker = HallCaretaker.objects.filter(hall=hall).first()
            # print(prev_hall_caretaker.staff.id)
            # Delete any previous assignments of the caretaker in HallCaretaker table
            HallCaretaker.objects.filter(staff=caretaker_staff).delete()

            # Delete any previous assignments of the caretaker in HostelAllotment table
            HostelAllotment.objects.filter(
                assignedCaretaker=caretaker_staff).delete()

            # Delete any previously assigned caretaker to the same hall
            HallCaretaker.objects.filter(hall=hall).delete()

            # Assign the new caretaker to the hall in HallCaretaker table
            hall_caretaker = HallCaretaker.objects.create(
                hall=hall, staff=caretaker_staff)

            # # Update the assigned caretaker in Hostelallottment table
            hostel_allotments = HostelAllotment.objects.filter(hall=hall)
            for hostel_allotment in hostel_allotments:
                hostel_allotment.assignedCaretaker = caretaker_staff
                hostel_allotment.save()

            # Retrieve the current warden for the hall
            current_warden = HallWarden.objects.filter(hall=hall).first()

            try:
                history_entry = HostelTransactionHistory.objects.create(
                    hall=hall,
                    change_type='Caretaker',
                    previous_value= prev_hall_caretaker.staff.id if (prev_hall_caretaker and prev_hall_caretaker.staff) else 'None',
                    new_value=caretaker_username
                )
            except Exception as e:
                print("Error creating HostelTransactionHistory:", e)

            
            # Create hostel history
            try:
                HostelHistory.objects.create(
                    hall=hall,
                    caretaker=caretaker_staff,
                    batch=hall.assigned_batch,
                    warden=current_warden.faculty if( current_warden and current_warden.faculty) else None
                )
            except Exception as e:
                print ("Error creating history",e)
            return Response({'message': f'Caretaker {caretaker_username} assigned to Hall {hall_id} successfully'}, status=status.HTTP_201_CREATED)

        except Hall.DoesNotExist:
            return Response({'error': f'Hall with ID {hall_id} not found'}, status=status.HTTP_404_NOT_FOUND)
        except Staff.DoesNotExist:
            return Response({'error': f'Caretaker with username {caretaker_username} not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return JsonResponse({'status': 'error', 'error': str(e)}, status=500)



@method_decorator(user_passes_test(is_superuser), name='dispatch')
class AssignBatchView(View):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]
    # Assuming the HTML file is directly in the 'templates' folder
    template_name = 'hostelmanagement/assign_batch.html'

    def get(self, request, *args, **kwargs):
        hall = Hall.objects.all()
        return render(request, self.template_name, {'halls': hall})

    def update_student_hall_allotment(self, hall, assigned_batch):
        hall_number = int(''.join(filter(str.isdigit, hall.hall_id)))
        students = Student.objects.filter(batch=int(assigned_batch))
       
        
        for student in students:
            student.hall_no = hall_number
            student.save()
            

    def post(self, request, *args, **kwargs):
        try:
            with transaction.atomic():  # Start a database transaction

                data = json.loads(request.body.decode('utf-8'))
                hall_id = data.get('hall_id')

                hall = Hall.objects.get(hall_id=hall_id)
                # previous_batch = hall.assigned_batch  # Get the previous batch
                previous_batch = hall.assigned_batch if hall.assigned_batch is not None else 0  # Get the previous batch
                hall.assigned_batch = data.get('batch')
                hall.save()

                

                
            
                # Update the assignedBatch field in HostelAllotment table for the corresponding hall
                room_allotments = HostelAllotment.objects.filter(hall=hall)
                for room_allotment in room_allotments:
                    room_allotment.assignedBatch = hall.assigned_batch
                    room_allotment.save()
                
                # retrieve the current caretaker and current warden for the hall
                current_caretaker =HallCaretaker.objects.filter(hall=hall).first()
                current_warden = HallWarden.objects.filter(hall=hall).first()

                # Record the transaction history
                HostelTransactionHistory.objects.create(
                    hall=hall,
                    change_type='Batch',
                    previous_value=previous_batch,
                    new_value=hall.assigned_batch
                )

                # Create hostel history
                try:
                    HostelHistory.objects.create(
                        hall=hall,
                        caretaker=current_caretaker.staff if (current_caretaker and current_caretaker.staff) else None,
                        
                        batch=hall.assigned_batch,
                        warden=current_warden.faculty if( current_warden and current_warden.faculty) else None

                    )
                except Exception as e:
                    print ("Error creating history",e)

                self.update_student_hall_allotment(hall, hall.assigned_batch)
                print("batch assigned successssssssssssssssssss")
                messages.success(request, 'batch assigned succesfully')
                
                return JsonResponse({'status': 'success', 'message': 'Batch assigned successfully'}, status=200)

        except Hall.DoesNotExist:
            return JsonResponse({'status': 'error', 'error': f'Hall with ID {hall_id} not found'}, status=404)

        except Exception as e:
            return JsonResponse({'status': 'error', 'error': str(e)}, status=500)

    def test_func(self):
        # Check if the user is a superuser
        return self.request.user.is_superuser


@method_decorator(user_passes_test(is_superuser), name='dispatch')
class AssignWardenView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]
    template_name = 'hostelmanagement/assign_warden.html'

    def post(self, request, *args, **kwargs):
        hall_id = request.data.get('hall_id')
        warden_id = request.data.get('warden_id')
        try:
            hall = Hall.objects.get(hall_id=hall_id)
            warden = Faculty.objects.get(id__user__username=warden_id)

            # Retrieve the previous caretaker for the hall, if any
            prev_hall_warden = HallWarden.objects.filter(hall=hall).first()
           
            # Delete any previous assignments of the warden in Hallwarden table
            HallWarden.objects.filter(faculty=warden).delete()

            # Delete any previous assignments of the warden in HostelAllotment table
            HostelAllotment.objects.filter(assignedWarden=warden).delete()

            # Delete any previously assigned warden to the same hall
            HallWarden.objects.filter(hall=hall).delete()

            # Assign the new warden to the hall in Hallwarden table
            hall_warden = HallWarden.objects.create(hall=hall, faculty=warden)

            #current caretker
            current_caretaker =HallCaretaker.objects.filter(hall=hall).first()
            print(current_caretaker)
            
            # Update the assigned warden in Hostelallottment table
            hostel_allotments = HostelAllotment.objects.filter(hall=hall)
            for hostel_allotment in hostel_allotments:
                hostel_allotment.assignedWarden = warden
                hostel_allotment.save()

            try:
                history_entry = HostelTransactionHistory.objects.create(
                    hall=hall,
                    change_type='Warden',
                    previous_value= prev_hall_warden.faculty.id if (prev_hall_warden and prev_hall_warden.faculty) else 'None',
                    new_value=warden
                )
            except Exception as e:
                print("Error creating HostelTransactionHistory:", e)


            # Create hostel history
            try:
                HostelHistory.objects.create(
                    hall=hall,
                    caretaker=current_caretaker.staff if (current_caretaker and current_caretaker.staff) else None,
                    
                    batch=hall.assigned_batch,
                    warden=warden
                )
            except Exception as e:
                print ("Error creating history",e)


            return Response({'message': f'Warden {warden_id} assigned to Hall {hall_id} successfully'}, status=status.HTTP_201_CREATED)

        except Hall.DoesNotExist:
            return Response({'error': f'Hall with ID {hall_id} not found'}, status=status.HTTP_404_NOT_FOUND)
        except Faculty.DoesNotExist:
            return Response({'error': f'Warden with username {warden_id} not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return JsonResponse({'status': 'error', 'error': str(e)}, status=500)


class AddHostelView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def _generate_hall_id(self):
        max_suffix = 0
        for existing_hall_id in Hall.objects.values_list('hall_id', flat=True):
            match = re.search(r'(\d+)$', str(existing_hall_id or ''))
            if match:
                max_suffix = max(max_suffix, int(match.group(1)))
        return f'hall{max_suffix + 1}'

    def post(self, request, *args, **kwargs):
        permission_error = _require_super_admin(request.user)
        if permission_error:
            return permission_error

        hall_name = (request.data.get('hall_name') or '').strip()
        hall_type = (request.data.get('type_of_seater') or '').strip().lower()
        assigned_batch = (request.data.get('assigned_batch') or '').strip()

        hall_id = (request.data.get('hall_id') or '').strip().lower()
        if not hall_id:
            hall_id = self._generate_hall_id()

        try:
            max_accomodation = int(request.data.get('max_accomodation'))
            room_count = int(request.data.get('room_count'))
        except (TypeError, ValueError):
            return Response(
                {'error': 'Please enter valid positive numbers.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not hall_name or not hall_type or not assigned_batch:
            return Response(
                {'error': 'Please fill all required fields.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if max_accomodation <= 0 or room_count <= 0:
            return Response(
                {'error': 'Please enter valid positive numbers.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if Hall.objects.filter(hall_name__iexact=hall_name).exists():
            return Response(
                {'error': 'A hostel with this name already exists.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if Hall.objects.filter(hall_id__iexact=hall_id).exists():
            return Response(
                {'error': 'A hostel with this ID already exists.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        room_capacity_default = {
            'single': 1,
            'double': 2,
            'triple': 3,
        }.get(hall_type)
        if room_capacity_default is None:
            return Response(
                {'error': 'Please fill all required fields.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        room_capacity = request.data.get('room_capacity', room_capacity_default)
        block_no = (request.data.get('block_no') or 'A').strip().upper()[:1] or 'A'

        try:
            room_capacity = int(room_capacity)
        except (TypeError, ValueError):
            return Response(
                {'error': 'Please enter valid positive numbers.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if room_capacity <= 0:
            return Response(
                {'error': 'Please enter valid positive numbers.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if room_count * room_capacity < max_accomodation:
            return Response(
                {'error': 'Room configuration is incomplete.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        room_start_number = request.data.get('room_start_number', 1)
        try:
            room_start_number = int(room_start_number)
        except (TypeError, ValueError):
            room_start_number = 1

        if room_start_number <= 0:
            room_start_number = 1

        with transaction.atomic():
            hall = Hall.objects.create(
                hall_id=hall_id,
                hall_name=hall_name,
                max_accomodation=max_accomodation,
                assigned_batch=assigned_batch,
                type_of_seater=hall_type,
            )

            for index in range(room_count):
                room_number = str(room_start_number + index).zfill(3)[:4]
                HallRoom.objects.create(
                    hall=hall,
                    room_no=room_number,
                    block_no=block_no,
                    room_cap=room_capacity,
                    room_occupied=0,
                )

            HostelTransactionHistory.objects.create(
                hall=hall,
                change_type='HostelCreate',
                previous_value='N/A',
                new_value=f"Created by {request.user.username}",
            )

            lifecycle_services.HostelService.sync_lifecycle_state(
                hall,
                updated_by=request.user,
                note='Hostel created',
            )

        return Response(
            {
                'message': 'Hostel added successfully!',
                'hostel': {
                    'hall_id': hall.hall_id,
                    'hall_name': hall.hall_name,
                    'operational_status': hall.operational_status,
                    'created_rooms': room_count,
                },
            },
            status=status.HTTP_201_CREATED,
        )


class CheckHallExistsView(View):

    def get(self, request, *args, **kwargs):

        hall_id = request.GET.get('hall_id')
        try:
            hall = Hall.objects.get(hall_id=hall_id)
            exists = True
        except Hall.DoesNotExist:
            exists = False
        messages.MessageFailure(request, f'Hall {hall_id} already exist.')
        return JsonResponse({'exists': exists})


class AdminHostelListView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        permission_error = _require_super_admin(request.user)
        if permission_error:
            return permission_error

        halls = Hall.objects.all()
        hostel_details = []

        for hall in halls:
            caretaker = HallCaretaker.objects.filter(hall=hall).first()
            warden = HallWarden.objects.filter(hall=hall).first()

            hostel_details.append(
                {
                    'hall_id': hall.hall_id,
                    'hall_name': hall.hall_name,
                    'max_accomodation': hall.max_accomodation,
                    'number_students': hall.number_students,
                    'assigned_batch': hall.assigned_batch,
                    'operational_status': hall.operational_status,
                    'room_count': HallRoom.objects.filter(hall=hall).count(),
                    'occupied_rooms': HallRoom.objects.filter(hall=hall, room_occupied__gt=0).count(),
                    'assigned_caretaker': caretaker.staff.id.user.username if caretaker else None,
                    'assigned_warden': warden.faculty.id.user.username if warden else None,
                }
            )

        return Response({'hostel_details': hostel_details}, status=status.HTTP_200_OK)


class ManageHostelStatusView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        permission_error = _require_super_admin(request.user)
        if permission_error:
            return permission_error

        hall_id = (request.data.get('hall_id') or '').strip()
        action = (request.data.get('action') or '').strip().lower()
        reason = (request.data.get('reason') or '').strip()

        if not hall_id or not action:
            return Response(
                {'error': 'Please fill all required fields.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            hall = Hall.objects.get(hall_id=hall_id)
        except Hall.DoesNotExist:
            return Response({'error': 'Hostel not found.'}, status=status.HTTP_404_NOT_FOUND)

        advisory = None

        if action == 'activate':
            has_warden = HallWarden.objects.filter(hall=hall).exists()
            has_caretaker = HallCaretaker.objects.filter(hall=hall).exists()
            if not has_warden or not has_caretaker:
                return Response(
                    {'error': 'Please assign at least one Warden and one Caretaker before activation.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            rooms = HallRoom.objects.filter(hall=hall)
            total_capacity = rooms.aggregate(total=models.Sum('room_cap')).get('total') or 0
            if not rooms.exists() or total_capacity <= 0:
                return Response(
                    {'error': 'Room configuration is incomplete. Add rooms with positive capacity before activation.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if total_capacity < hall.max_accomodation:
                advisory = (
                    f'Configured room capacity ({total_capacity}) is lower than max accommodation '
                    f'({hall.max_accomodation}). Activation is allowed, but allotment may fail once capacity is exhausted.'
                )
            target_status = 'Active'
        elif action == 'deactivate':
            occupied_count = HallRoom.objects.filter(hall=hall, room_occupied__gt=0).count()
            if occupied_count > 0:
                return Response(
                    {'error': f'Cannot deactivate hostel. {occupied_count} rooms are currently occupied.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            target_status = 'Inactive'
        elif action in ['maintenance', 'under_maintenance']:
            target_status = 'UnderMaintenance'
        else:
            return Response({'error': 'Invalid status action.'}, status=status.HTTP_400_BAD_REQUEST)

        previous_status = hall.operational_status
        if previous_status == target_status:
            return Response(
                {'message': f'Hostel is already {target_status}.', 'status': target_status},
                status=status.HTTP_200_OK,
            )

        hall.operational_status = target_status
        hall.save(update_fields=['operational_status'])

        HostelTransactionHistory.objects.create(
            hall=hall,
            change_type='HostelStatus',
            previous_value=previous_status,
            new_value=f'{target_status} by {request.user.username}. Reason: {reason or "N/A"}',
        )

        lifecycle_services.HostelService.sync_lifecycle_state(
            hall,
            updated_by=request.user,
            note=f'Hostel status set to {target_status}',
        )

        return Response(
            {
                'message': 'Hostel status updated successfully.',
                'hall_id': hall.hall_id,
                'status': hall.operational_status,
                'advisory': advisory,
            },
            status=status.HTTP_200_OK,
        )


@method_decorator(user_passes_test(is_superuser), name='dispatch')
class DeleteHostelView(View):
    def get(self, request, hall_id, *args, **kwargs):
        # Get the hall instance
        hall = get_object_or_404(Hall, hall_id=hall_id)

        # Delete related entries in other tables
        hostelallotments = HostelAllotment.objects.filter(hall=hall)
        hostelallotments.delete()

        # Delete the hall
        hall.delete()
        messages.success(request, f'Hall {hall_id} deleted successfully.')

        return HttpResponseRedirect(reverse("hostelmanagement:hostel_view"))


class HallIdView(APIView):
    authentication_classes = []  # Allow public access for testing
    permission_classes = []  # Allow any user to access the view

    def get(self, request, *args, **kwargs):
        hall_id = HostelAllotment.objects.values('hall_id')
        return Response(hall_id, status=status.HTTP_200_OK)


@login_required(login_url=LOGIN_URL)
def logout_view(request):
    logout(request)
    return redirect("/")


# //! alloted_rooms
def alloted_rooms(request, hall_id):
    """
    This function returns the allotted rooms in a particular hall.

    @param:
      request - HttpRequest object containing metadata about the user request.
      hall_id - Hall ID for which the allotted rooms need to be retrieved.

    @variables:
      allotted_rooms - stores all the rooms allotted in the given hall.
    """
    # Query the hall by hall_id
    hall = Hall.objects.get(hall_id=hall_id)
    # Query all rooms allotted in the given hall
    allotted_rooms = HallRoom.objects.filter(hall=hall, room_occupied__gt=0)
    # Prepare a list of room details to be returned
    room_details = []
    for room in allotted_rooms:
        room_details.append({
            'hall': room.hall.hall_id,
            'room_no': room.room_no,
            'block_no': room.block_no,
            'room_cap': room.room_cap,
            'room_occupied': room.room_occupied
        })
    return JsonResponse(room_details, safe=False)


def alloted_rooms_main(request):
    """
    This function returns the allotted rooms in all halls.

    @param:
      request - HttpRequest object containing metadata about the user request.

    @variables:
      all_halls - stores all the halls.
      all_rooms - stores all the rooms allotted in all halls.
    """
    # Query all halls
    all_halls = Hall.objects.all()

    # Query all rooms allotted in all halls
    all_rooms = []
    for hall in all_halls:
        all_rooms.append(HallRoom.objects.filter(
            hall=hall, room_occupied__gt=0))

    # Prepare a list of room details to be returned
    room_details = []
    for rooms in all_rooms:
        for room in rooms:
            room_details.append({
                'hall': room.hall.hall_name,
                'room_no': room.room_no,
                'block_no': room.block_no,
                'room_cap': room.room_cap,
                'room_occupied': room.room_occupied
            })

    # Return the room_details as JSON response
    return render(request, 'hostelmanagement/alloted_rooms_main.html', {'allotted_rooms': room_details, 'halls': all_halls})


# //! all_staff
def all_staff(request, hall_id):
    """
    This function returns all staff information for a specific hall.

    @param:
      request - HttpRequest object containing metadata about the user request.
      hall_id - The ID of the hall for which staff information is requested.


    @variables:
      all_staff - stores all staff information for the specified hall.
    """

    # Query all staff information for the specified hall
    all_staff = StaffSchedule.objects.filter(hall_id=hall_id)

    # Prepare a list of staff details to be returned
    staff_details = []
    for staff in all_staff:
        staff_details.append({
            'type': staff.staff_type,
            'staff_id': staff.staff_id_id,
            'hall_id': staff.hall_id,
            'day': staff.day,
            'start_time': staff.start_time,
            'end_time': staff.end_time
        })

    # Return the staff_details as JSON response
    return JsonResponse(staff_details, safe=False)


# //! Edit Stuff schedule
class StaffScheduleView(APIView):
    """
    API endpoint for creating or editing staff schedules.
    """

    authentication_classes = []  # Allow public access for testing
    permission_classes = []  # Allow any user to access the view

    def patch(self, request, staff_id):
        staff = get_object_or_404(Staff, pk=staff_id)
        staff_type = request.data.get('staff_type')
        start_time = request.data.get('start_time')
        end_time = request.data.get('end_time')
        day = request.data.get('day')


        if start_time and end_time and day and staff_type:
            # Check if staff schedule exists for the given day
            existing_schedule = StaffSchedule.objects.filter(
                staff_id=staff_id).first()
            if existing_schedule:
                existing_schedule.start_time = start_time
                existing_schedule.end_time = end_time
                existing_schedule.day = day
                existing_schedule.staff_type = staff_type
                existing_schedule.save()
                return Response({"message": "Staff schedule updated successfully."}, status=status.HTTP_200_OK)
            else:
                # If staff schedule doesn't exist for the given day, return 404
                return Response({"error": "Staff schedule does not exist for the given day."}, status=status.HTTP_404_NOT_FOUND)

        return Response({"error": "Please provide start_time, end_time, and day."}, status=status.HTTP_400_BAD_REQUEST)


# //! Hostel Inventory

@login_required
def get_inventory_form(request):
    user_id = request.user
    # print("user_id",user_id)
    staff = user_id.extrainfo.id
    # print("staff",staff)

    # Check if the user is present in the HallCaretaker table
    if HallCaretaker.objects.filter(staff_id=staff).exists():
        # If the user is a caretaker, allow access
        halls = Hall.objects.all()
        return render(request, 'hostelmanagement/inventory_form.html', {'halls': halls})
    else:
        # If the user is not a caretaker, redirect to the login page
        # return redirect('login')  # Adjust 'login' to your login URL name
        return HttpResponse(f'<script>alert("You are not authorized to access this page"); window.location.href = "/hostelmanagement/"</script>')


@login_required
def edit_inventory(request, inventory_id):
    # Retrieve hostel inventory object
    inventory = get_object_or_404(HostelInventory, pk=inventory_id)

    # Check if the user is a caretaker
    user_id = request.user
    staff_id = user_id.extrainfo.id

    if HallCaretaker.objects.filter(staff_id=staff_id).exists():
        halls = Hall.objects.all()

        # Prepare inventory data for rendering
        inventory_data = {
            'inventory_id': inventory.inventory_id,
            'hall_id': inventory.hall_id,
            'inventory_name': inventory.inventory_name,
            'cost': str(inventory.cost),  # Convert DecimalField to string
            'quantity': inventory.quantity,
        }

        # Render the inventory update form with inventory data
        return render(request, 'hostelmanagement/inventory_update_form.html', {'inventory': inventory_data, 'halls': halls})
    else:
        # If the user is not a caretaker, show a message and redirect
        return HttpResponse('<script>alert("You are not authorized to access this page"); window.location.href = "/hostelmanagement/"</script>')


class HostelInventoryUpdateView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(self, request, inventory_id):
        user_id = request.user
        staff_id = user_id.extrainfo.id

        if not HallCaretaker.objects.filter(staff_id=staff_id).exists():
            return Response({'error': 'You are not authorized to update this hostel inventory'}, status=status.HTTP_401_UNAUTHORIZED)

        hall_id = request.data.get('hall_id')
        inventory_name = request.data.get('inventory_name')
        cost = request.data.get('cost')
        quantity = request.data.get('quantity')

        # Validate required fields
        if not all([hall_id, inventory_name, cost, quantity]):
            return Response({'error': 'All fields are required'}, status=status.HTTP_400_BAD_REQUEST)

        # Retrieve hostel inventory object
        hostel_inventory = get_object_or_404(HostelInventory, pk=inventory_id)

        # Update hostel inventory object
        hostel_inventory.hall_id = hall_id
        hostel_inventory.inventory_name = inventory_name
        hostel_inventory.cost = cost
        hostel_inventory.quantity = quantity
        hostel_inventory.save()

        # Return success response
        return Response({'message': 'Hostel inventory updated successfully'}, status=status.HTTP_200_OK)


class HostelInventoryView(APIView):
    """
    API endpoint for CRUD operations on hostel inventory.
    """
    # permission_classes = [IsAuthenticated]

    # authentication_classes = []  # Allow public access for testing
    # permission_classes = []  # Allow any user to access the view

    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get(self, request, hall_id):
        user_id = request.user
        staff_id = user_id.extrainfo.id

        if not HallCaretaker.objects.filter(staff_id=staff_id).exists():
            return HttpResponse('<script>alert("You are not authorized to access this page"); window.location.href = "/hostelmanagement/"</script>')

        # Retrieve hostel inventory objects for the given hall ID
        inventories = HostelInventory.objects.filter(hall_id=hall_id)

        # Get all hall IDs
        halls = Hall.objects.all()

        # Serialize inventory data
        inventory_data = []
        for inventory in inventories:
            inventory_data.append({
                'inventory_id': inventory.inventory_id,
                'hall_id': inventory.hall_id,
                'inventory_name': inventory.inventory_name,
                'cost': str(inventory.cost),  # Convert DecimalField to string
                'quantity': inventory.quantity,
            })

        inventory_data.sort(key=lambda x: x['inventory_id'])

        # Return inventory data as JSON response
        return render(request, 'hostelmanagement/inventory_list.html', {'halls': halls, 'inventories': inventory_data})

    def post(self, request):
        user_id = request.user
        staff_id = user_id.extrainfo.id

        if not HallCaretaker.objects.filter(staff_id=staff_id).exists():
            return Response({'error': 'You are not authorized to create a new hostel inventory'}, status=status.HTTP_401_UNAUTHORIZED)

        # Extract data from request
        hall_id = request.data.get('hall_id')
        inventory_name = request.data.get('inventory_name')
        cost = request.data.get('cost')
        quantity = request.data.get('quantity')

        # Validate required fields
        if not all([hall_id, inventory_name, cost, quantity]):
            return Response({'error': 'All fields are required'}, status=status.HTTP_400_BAD_REQUEST)

        # Create hostel inventory object
        try:
            hostel_inventory = HostelInventory.objects.create(
                hall_id=hall_id,
                inventory_name=inventory_name,
                cost=cost,
                quantity=quantity
            )
            return Response({'message': 'Hostel inventory created successfully', 'hall_id': hall_id}, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request, inventory_id):
        user_id = request.user
        staff_id = user_id.extrainfo.id

        if not HallCaretaker.objects.filter(staff_id=staff_id).exists():
            return Response({'error': 'You are not authorized to delete this hostel inventory'}, status=status.HTTP_401_UNAUTHORIZED)

        inventory = get_object_or_404(HostelInventory, pk=inventory_id)
        inventory.delete()
        return Response({'message': 'Hostel inventory deleted successfully'}, status=status.HTTP_204_NO_CONTENT)


def update_allotment(request, pk):
    if request.method == 'POST':
        try:
            allotment = HostelAllottment.objects.get(pk=pk)
        except HostelAllottment.DoesNotExist:
            return JsonResponse({'error': 'HostelAllottment not found'}, status=404)

        try:
            allotment.assignedWarden = Faculty.objects.get(
                id=request.POST['warden_id'])
            allotment.assignedCaretaker = Staff.objects.get(
                id=request.POST['caretaker_id'])
            allotment.assignedBatch = request.POST.get(
                'student_batch', allotment.assignedBatch)
            allotment.save()
            return JsonResponse({'success': 'HostelAllottment updated successfully'})
        except (Faculty.DoesNotExist, Staff.DoesNotExist, IntegrityError):
            return JsonResponse({'error': 'Invalid data or integrity error'}, status=400)

    return JsonResponse({'error': 'Invalid request method'}, status=405)


@login_required
def request_guest_room(request):
    """
    This function is used by the student to book a guest room.
    @param:
      request - HttpRequest object containing metadata about the user request.
    """
    if request.method == "POST":
        form = GuestRoomBookingForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Invalid booking details. Please correct and retry.")
            return HttpResponseRedirect(reverse("hostelmanagement:hostel_view"))

        try:
            services.submitGuestRoomBookingService(
                user=request.user,
                guest_name=form.cleaned_data['guest_name'],
                guest_phone=form.cleaned_data['guest_phone'],
                guest_email=form.cleaned_data.get('guest_email', ''),
                guest_address=form.cleaned_data.get('guest_address', ''),
                rooms_required=form.cleaned_data['rooms_required'],
                total_guest=form.cleaned_data['total_guest'],
                purpose=form.cleaned_data['purpose'],
                arrival_date=form.cleaned_data['arrival_date'],
                arrival_time=form.cleaned_data['arrival_time'],
                departure_date=form.cleaned_data['departure_date'],
                departure_time=form.cleaned_data['departure_time'],
                nationality=form.cleaned_data.get('nationality', ''),
                room_type=form.cleaned_data['room_type'],
            )
            messages.success(request, "Guest room request submitted successfully.")
        except (services.InvalidOperationError, services.RoomNotAvailableError) as exc:
            messages.error(request, str(exc))
        except (services.UserHallMappingMissingError, services.UnauthorizedAccessError) as exc:
            messages.error(request, str(exc))
        return HttpResponseRedirect(reverse("hostelmanagement:hostel_view"))

    return HttpResponseRedirect(reverse("hostelmanagement:hostel_view"))


@login_required
def update_guest_room(request):
    if request.method == "POST":
        if 'accept_request' in request.POST:
            booking_id = request.POST.get('accept_request')
            room_label = request.POST.get('guest_room_id')
            try:
                booking = selectors.get_booking_by_id(int(booking_id))
                room = GuestRoom.objects.filter(hall=booking.hall, room=room_label).first()
                if not room:
                    messages.error(request, "Selected room is invalid.")
                    return HttpResponseRedirect(reverse("hostelmanagement:hostel_view"))

                services.decideGuestRoomBookingService(
                    user=request.user,
                    booking_id=int(booking_id),
                    decision='approved',
                    guest_room_id=room.id,
                    comment=request.POST.get('decision_comment', ''),
                )
                messages.success(request, "Request approved successfully.")
            except Exception as exc:
                messages.error(request, str(exc))

        elif 'reject_request' in request.POST:
            booking_id = request.POST.get('reject_request')
            rejection_reason = request.POST.get('decision_comment') or request.POST.get('rejection_reason') or 'Rejected by caretaker.'
            try:
                services.decideGuestRoomBookingService(
                    user=request.user,
                    booking_id=int(booking_id),
                    decision='rejected',
                    comment=rejection_reason,
                )
                messages.success(request, "Request rejected successfully.")
            except Exception as exc:
                messages.error(request, str(exc))

        else:
            messages.error(request, "Invalid request!")
    return HttpResponseRedirect(reverse("hostelmanagement:hostel_view"))


def available_guestrooms_api(request):
    if request.method == 'GET':
        hall_id = request.GET.get('hall_id')
        room_type = request.GET.get('room_type')
        arrival_date = request.GET.get('arrival_date')
        departure_date = request.GET.get('departure_date')
        rooms_required = request.GET.get('rooms_required', 1)

        if not room_type:
            return JsonResponse({'error': 'room_type is required.'}, status=400)

        if arrival_date and departure_date:
            try:
                availability = services.checkGuestRoomAvailabilityService(
                    user=request.user,
                    start_date=datetime.strptime(arrival_date, '%Y-%m-%d').date(),
                    end_date=datetime.strptime(departure_date, '%Y-%m-%d').date(),
                    room_type=room_type,
                    rooms_required=int(rooms_required),
                )
                return JsonResponse(availability, status=200)
            except Exception as exc:
                return JsonResponse({'error': str(exc)}, status=400)

        if hall_id and room_type:
            available_rooms_count = GuestRoom.objects.filter(hall_id=hall_id, room_type=room_type, vacant=True).count()
            return JsonResponse({'available_rooms_count': available_rooms_count})

    return JsonResponse({'error': 'Invalid request'}, status=400)


def _serialize_guest_booking(booking):
    """Serialize guest booking model for API responses."""
    def _safe_iso(value):
        if value is None:
            return None
        if hasattr(value, 'isoformat'):
            return value.isoformat()
        return str(value)

    return {
        'id': booking.id,
        'hall_id': booking.hall.hall_id if booking.hall else None,
        'hall_name': booking.hall.hall_name if booking.hall else None,
        'student_username': booking.intender.username if booking.intender else None,
        'guest_name': booking.guest_name,
        'guest_phone': booking.guest_phone,
        'guest_email': booking.guest_email,
        'guest_address': booking.guest_address,
        'rooms_required': booking.rooms_required,
        'guest_room_id': booking.guest_room_id,
        'total_guest': booking.total_guest,
        'purpose': booking.purpose,
        'arrival_date': _safe_iso(booking.arrival_date),
        'arrival_time': _safe_iso(booking.arrival_time),
        'departure_date': _safe_iso(booking.departure_date),
        'departure_time': _safe_iso(booking.departure_time),
        'status': booking.status,
        'booking_date': _safe_iso(booking.booking_date),
        'nationality': booking.nationality,
        'room_type': booking.room_type,
        'rejection_reason': booking.rejection_reason,
        'decision_comment': booking.decision_comment,
        'decision_at': _safe_iso(booking.decision_at),
        'checked_in_at': _safe_iso(booking.checked_in_at),
        'checked_out_at': _safe_iso(booking.checked_out_at),
        'id_proof_type': booking.id_proof_type,
        'id_proof_number': booking.id_proof_number,
        'inspection_notes': booking.inspection_notes,
        'damage_report': booking.damage_report,
        'damage_amount': float(booking.damage_amount or 0),
        'completed_with_damages': booking.completed_with_damages,
        'booking_charge_per_day': float(booking.booking_charge_per_day or 0),
        'total_charge': float(booking.total_charge or 0),
        'modified_count': booking.modified_count,
        'last_modified_at': _safe_iso(booking.last_modified_at),
    }


@api_view(['GET'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def checkGuestRoomAvailabilityController(request):
    """Student checks guest room availability for selected dates."""
    arrival_date = request.query_params.get('arrival_date')
    departure_date = request.query_params.get('departure_date')
    room_type = request.query_params.get('room_type')
    rooms_required = request.query_params.get('rooms_required', 1)

    if not arrival_date or not departure_date or not room_type:
        return Response(
            {'error': 'arrival_date, departure_date and room_type are required.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        payload = services.checkGuestRoomAvailabilityService(
            user=request.user,
            start_date=date.fromisoformat(arrival_date),
            end_date=date.fromisoformat(departure_date),
            room_type=room_type,
            rooms_required=int(rooms_required),
        )
        return Response(payload, status=status.HTTP_200_OK)
    except Exception as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def submitGuestRoomBookingController(request):
    """Student submits guest room booking request."""
    payload = request.data
    try:
        booking = services.submitGuestRoomBookingService(
            user=request.user,
            guest_name=payload.get('guest_name', ''),
            guest_phone=payload.get('guest_phone', ''),
            guest_email=payload.get('guest_email', ''),
            guest_address=payload.get('guest_address', ''),
            rooms_required=int(payload.get('rooms_required', 1)),
            total_guest=int(payload.get('total_guest', 1)),
            purpose=payload.get('purpose', ''),
            arrival_date=date.fromisoformat(payload.get('arrival_date', '')),
            arrival_time=payload.get('arrival_time'),
            departure_date=date.fromisoformat(payload.get('departure_date', '')),
            departure_time=payload.get('departure_time'),
            nationality=payload.get('nationality', ''),
            room_type=payload.get('room_type', RoomType.SINGLE),
        )
        return Response(
            {
                'message': 'Booking request submitted successfully.',
                'request_id': booking.id,
                'booking': _serialize_guest_booking(booking),
            },
            status=status.HTTP_201_CREATED,
        )
    except Exception as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def myGuestRoomBookingsController(request):
    """Student views own booking history."""
    try:
        bookings = services.getStudentGuestBookingsService(user=request.user)
        return Response([_serialize_guest_booking(booking) for booking in bookings], status=status.HTTP_200_OK)
    except Exception as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def guestRoomBookingDetailController(request, booking_id):
    """Student views one booking in detail."""
    try:
        booking = services.getStudentGuestBookingDetailService(user=request.user, booking_id=booking_id)
        return Response(_serialize_guest_booking(booking), status=status.HTTP_200_OK)
    except Exception as exc:
        return Response({'error': str(exc)}, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def modifyGuestRoomBookingController(request, booking_id):
    """Student modifies pending booking request."""
    payload = request.data
    try:
        booking = services.modifyGuestRoomBookingService(
            user=request.user,
            booking_id=booking_id,
            guest_name=payload.get('guest_name', ''),
            guest_phone=payload.get('guest_phone', ''),
            guest_email=payload.get('guest_email', ''),
            guest_address=payload.get('guest_address', ''),
            rooms_required=int(payload.get('rooms_required', 1)),
            total_guest=int(payload.get('total_guest', 1)),
            purpose=payload.get('purpose', ''),
            arrival_date=date.fromisoformat(payload.get('arrival_date', '')),
            arrival_time=payload.get('arrival_time'),
            departure_date=date.fromisoformat(payload.get('departure_date', '')),
            departure_time=payload.get('departure_time'),
            nationality=payload.get('nationality', ''),
            room_type=payload.get('room_type', RoomType.SINGLE),
        )
        return Response(
            {
                'message': 'Booking request modified and re-submitted as pending.',
                'booking': _serialize_guest_booking(booking),
            },
            status=status.HTTP_200_OK,
        )
    except Exception as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def cancelGuestRoomBookingController(request, booking_id):
    """Student cancels booking before check-in date."""
    try:
        booking = services.cancelGuestRoomBookingService(
            user=request.user,
            booking_id=booking_id,
            cancel_reason=request.data.get('cancel_reason', ''),
        )
        return Response(
            {
                'message': 'Booking cancelled successfully.',
                'booking': _serialize_guest_booking(booking),
            },
            status=status.HTTP_200_OK,
        )
    except Exception as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def caretakerPendingGuestBookingsController(request):
    """Caretaker dashboard: pending guest room requests."""
    try:
        bookings = services.getCaretakerPendingGuestBookingsService(user=request.user)
        return Response([_serialize_guest_booking(booking) for booking in bookings], status=status.HTTP_200_OK)
    except Exception as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def caretakerDecideGuestBookingController(request, booking_id):
    """Caretaker approves/rejects booking with reason and room assignment."""
    try:
        booking = services.decideGuestRoomBookingService(
            user=request.user,
            booking_id=booking_id,
            decision=request.data.get('decision', ''),
            guest_room_id=request.data.get('guest_room_id'),
            comment=request.data.get('comment', ''),
        )
        return Response(
            {
                'message': 'Booking decision recorded successfully.',
                'booking': _serialize_guest_booking(booking),
            },
            status=status.HTTP_200_OK,
        )
    except Exception as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def caretakerCheckInGuestBookingController(request, booking_id):
    """Caretaker performs guest check-in."""
    try:
        booking = services.checkInGuestBookingService(
            user=request.user,
            booking_id=booking_id,
            id_proof_type=request.data.get('id_proof_type', ''),
            id_proof_number=request.data.get('id_proof_number', ''),
            notes=request.data.get('checkin_notes', ''),
        )
        return Response(
            {
                'message': 'Guest check-in completed.',
                'booking': _serialize_guest_booking(booking),
            },
            status=status.HTTP_200_OK,
        )
    except Exception as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def caretakerCheckOutGuestBookingController(request, booking_id):
    """Caretaker performs guest check-out and optional damage processing."""
    try:
        booking = services.checkOutGuestBookingService(
            user=request.user,
            booking_id=booking_id,
            inspection_notes=request.data.get('inspection_notes', ''),
            damage_report=request.data.get('damage_report', ''),
            damage_amount=request.data.get('damage_amount', 0),
        )
        return Response(
            {
                'message': 'Guest check-out completed.',
                'booking': _serialize_guest_booking(booking),
            },
            status=status.HTTP_200_OK,
        )
    except Exception as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def guestRoomPolicyController(request):
    """Caretaker gets/updates guest room policy and charges."""
    if request.method == 'GET':
        try:
            policy = services.getGuestRoomPolicyService(user=request.user)
            return Response(
                {
                    'feature_enabled': policy.feature_enabled,
                    'charge_per_day': float(policy.charge_per_day),
                    'min_advance_days': policy.min_advance_days,
                    'max_advance_days': policy.max_advance_days,
                    'max_booking_duration_days': policy.max_booking_duration_days,
                    'max_concurrent_bookings_per_student': policy.max_concurrent_bookings_per_student,
                    'eligibility_note': policy.eligibility_note,
                },
                status=status.HTTP_200_OK,
            )
        except Exception as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    try:
        feature_enabled_raw = request.data.get('feature_enabled', True)
        if isinstance(feature_enabled_raw, str):
            feature_enabled = feature_enabled_raw.strip().lower() in ['1', 'true', 'yes', 'on']
        else:
            feature_enabled = bool(feature_enabled_raw)

        policy = services.upsertGuestRoomPolicyService(
            user=request.user,
            feature_enabled=feature_enabled,
            charge_per_day=request.data.get('charge_per_day', 0),
            min_advance_days=int(request.data.get('min_advance_days', 0)),
            max_advance_days=int(request.data.get('max_advance_days', 90)),
            max_booking_duration_days=int(request.data.get('max_booking_duration_days', 7)),
            max_concurrent_bookings_per_student=int(request.data.get('max_concurrent_bookings_per_student', 1)),
            eligibility_note=request.data.get('eligibility_note', ''),
        )
        return Response(
            {
                'message': 'Guest room policy updated successfully.',
                'policy': {
                    'feature_enabled': policy.feature_enabled,
                    'charge_per_day': float(policy.charge_per_day),
                    'min_advance_days': policy.min_advance_days,
                    'max_advance_days': policy.max_advance_days,
                    'max_booking_duration_days': policy.max_booking_duration_days,
                    'max_concurrent_bookings_per_student': policy.max_concurrent_bookings_per_student,
                    'eligibility_note': policy.eligibility_note,
                },
            },
            status=status.HTTP_200_OK,
        )
    except Exception as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def guestRoomBookingReportController(request):
    """Caretaker generates booking report for a date range."""
    start_date = request.query_params.get('start_date')
    end_date = request.query_params.get('end_date')

    if not start_date or not end_date:
        return Response({'error': 'start_date and end_date are required.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        report = services.getGuestRoomBookingReportService(
            user=request.user,
            start_date=date.fromisoformat(start_date),
            end_date=date.fromisoformat(end_date),
        )
        return Response(report, status=status.HTTP_200_OK)
    except Exception as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def submitRoomChangeRequestController(request):
    """Student submits room change request."""
    try:
        payload = services.submitRoomChangeRequestService(
            user=request.user,
            reason=request.data.get('reason', ''),
            preferred_room=request.data.get('preferred_room', ''),
            preferred_hall=request.data.get('preferred_hall', ''),
        )
        return Response(
            {
                'message': 'Room change request submitted successfully.',
                'request': payload,
            },
            status=status.HTTP_201_CREATED,
        )
    except Exception as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def myRoomChangeRequestsController(request):
    """Student views own room change request history."""
    try:
        requests_payload = services.getMyRoomChangeRequestsService(user=request.user)
        return Response(requests_payload, status=status.HTTP_200_OK)
    except Exception as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def roomChangeRequestsForReviewController(request):
    """Caretaker/Warden fetch requests in own hall for review and processing."""
    statuses = request.query_params.getlist('status')
    statuses = [value for value in statuses if value]
    try:
        requests_payload = services.getRoomChangeRequestsForReviewService(
            user=request.user,
            statuses=statuses or None,
        )
        return Response(requests_payload, status=status.HTTP_200_OK)
    except Exception as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def caretakerRoomChangeDecisionController(request, request_id):
    """Caretaker submits review decision on room change request."""
    try:
        payload = services.caretakerReviewRoomChangeRequestService(
            user=request.user,
            room_change_request_id=request_id,
            decision=request.data.get('decision', ''),
            remarks=request.data.get('remarks', ''),
        )
        return Response(
            {
                'message': 'Caretaker decision recorded successfully.',
                'request': payload,
            },
            status=status.HTTP_200_OK,
        )
    except Exception as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def wardenRoomChangeDecisionController(request, request_id):
    """Warden submits compliance decision on room change request."""
    try:
        payload = services.wardenReviewRoomChangeRequestService(
            user=request.user,
            room_change_request_id=request_id,
            decision=request.data.get('decision', ''),
            remarks=request.data.get('remarks', ''),
        )
        return Response(
            {
                'message': 'Warden decision recorded successfully.',
                'request': payload,
            },
            status=status.HTTP_200_OK,
        )
    except Exception as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def allocateRoomChangeRequestController(request, request_id):
    """Caretaker allocates new room for approved room change request."""
    try:
        payload = services.allocateApprovedRoomChangeRequestService(
            user=request.user,
            room_change_request_id=request_id,
            room_id=request.data.get('room_id'),
            room_label=request.data.get('room_no') or request.data.get('room_label'),
            notes=request.data.get('allocation_notes', ''),
        )
        return Response(
            {
                'message': 'Room allocation updated successfully.',
                'request': payload,
            },
            status=status.HTTP_200_OK,
        )
    except Exception as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def submitExtendedStayRequestController(request):
    """Student submits extended stay request."""
    try:
        payload = services.submitExtendedStayRequestService(
            user=request.user,
            start_date=date.fromisoformat(request.data.get('start_date', '')),
            end_date=date.fromisoformat(request.data.get('end_date', '')),
            reason=request.data.get('reason', ''),
            faculty_authorization=request.data.get('faculty_authorization', ''),
        )
        return Response(
            {
                'message': 'Extended stay request submitted successfully.',
                'request': payload,
            },
            status=status.HTTP_201_CREATED,
        )
    except Exception as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def myExtendedStayRequestsController(request):
    """Student views own extended stay request history."""
    try:
        payload = services.getMyExtendedStayRequestsService(user=request.user)
        return Response(payload, status=status.HTTP_200_OK)
    except Exception as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def modifyExtendedStayRequestController(request, request_id):
    """Student modifies pending extended stay request."""
    try:
        payload = services.modifyExtendedStayRequestService(
            user=request.user,
            request_id=request_id,
            start_date=date.fromisoformat(request.data.get('start_date', '')),
            end_date=date.fromisoformat(request.data.get('end_date', '')),
            reason=request.data.get('reason', ''),
            faculty_authorization=request.data.get('faculty_authorization', ''),
        )
        return Response(
            {
                'message': 'Extended stay request updated successfully.',
                'request': payload,
            },
            status=status.HTTP_200_OK,
        )
    except Exception as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def cancelExtendedStayRequestController(request, request_id):
    """Student cancels pending extended stay request."""
    try:
        payload = services.cancelExtendedStayRequestService(
            user=request.user,
            request_id=request_id,
            cancel_reason=request.data.get('cancel_reason', ''),
        )
        return Response(
            {
                'message': 'Extended stay request cancelled successfully.',
                'request': payload,
            },
            status=status.HTTP_200_OK,
        )
    except Exception as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def extendedStayRequestsForReviewController(request):
    """Caretaker/Warden fetch extended stay requests for review."""
    statuses = request.query_params.getlist('status')
    statuses = [value for value in statuses if value]
    try:
        payload = services.getExtendedStayRequestsForReviewService(
            user=request.user,
            statuses=statuses or None,
        )
        return Response(payload, status=status.HTTP_200_OK)
    except Exception as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def caretakerExtendedStayDecisionController(request, request_id):
    """Caretaker submits decision on extended stay request."""
    try:
        payload = services.caretakerReviewExtendedStayRequestService(
            user=request.user,
            extended_stay_request_id=request_id,
            decision=request.data.get('decision', ''),
            remarks=request.data.get('remarks', ''),
        )
        return Response(
            {
                'message': 'Caretaker decision recorded successfully.',
                'request': payload,
            },
            status=status.HTTP_200_OK,
        )
    except Exception as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def wardenExtendedStayDecisionController(request, request_id):
    """Warden submits decision on extended stay request."""
    try:
        payload = services.wardenReviewExtendedStayRequestService(
            user=request.user,
            extended_stay_request_id=request_id,
            decision=request.data.get('decision', ''),
            remarks=request.data.get('remarks', ''),
        )
        return Response(
            {
                'message': 'Warden decision recorded successfully.',
                'request': payload,
            },
            status=status.HTTP_200_OK,
        )
    except Exception as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def generateRoomVacationChecklistController(request):
    """Student generates clearance checklist preview before room vacation submission."""
    try:
        payload = services.generateRoomVacationChecklistService(
            user=request.user,
            intended_vacation_date=date.fromisoformat(request.data.get('intended_vacation_date', '')),
            reason=request.data.get('reason', ''),
        )
        return Response(payload, status=status.HTTP_200_OK)
    except Exception as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def submitRoomVacationRequestController(request):
    """Student submits room vacation request with acknowledged checklist."""
    try:
        payload = services.submitRoomVacationRequestService(
            user=request.user,
            intended_vacation_date=date.fromisoformat(request.data.get('intended_vacation_date', '')),
            reason=request.data.get('reason', ''),
            checklist_acknowledged=bool(request.data.get('checklist_acknowledged', False)),
        )
        return Response(
            {
                'message': 'Room vacation request submitted successfully.',
                'request': payload,
            },
            status=status.HTTP_201_CREATED,
        )
    except Exception as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def myRoomVacationRequestsController(request):
    """Student views own room vacation request history."""
    try:
        payload = services.getMyRoomVacationRequestsService(user=request.user)
        return Response(payload, status=status.HTTP_200_OK)
    except Exception as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def roomVacationRequestsForClearanceController(request):
    """Caretaker fetches room vacation requests for clearance verification."""
    statuses = request.query_params.getlist('status')
    statuses = [value for value in statuses if value]
    try:
        payload = services.getRoomVacationRequestsForClearanceService(
            user=request.user,
            statuses=statuses or None,
        )
        return Response(payload, status=status.HTTP_200_OK)
    except Exception as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def caretakerVerifyRoomVacationController(request, request_id):
    """Caretaker approves clearance or requests corrections after checklist verification."""
    try:
        payload = services.caretakerVerifyRoomVacationService(
            user=request.user,
            request_id=request_id,
            decision=request.data.get('decision', ''),
            caretaker_review_comments=request.data.get('caretaker_review_comments', ''),
            room_inspection_notes=request.data.get('room_inspection_notes', ''),
            room_damages_found=bool(request.data.get('room_damages_found', False)),
            room_damage_description=request.data.get('room_damage_description', ''),
            room_damage_fine_amount=request.data.get('room_damage_fine_amount', 0),
            borrowed_items_notes=request.data.get('borrowed_items_notes', ''),
            behavior_notes=request.data.get('behavior_notes', ''),
            checklist_updates=request.data.get('checklist_updates', []),
        )
        return Response(
            {
                'message': 'Vacation clearance review submitted successfully.',
                'request': payload,
            },
            status=status.HTTP_200_OK,
        )
    except Exception as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def roomVacationRequestsForFinalizationController(request):
    """Super admin fetches room vacation requests for finalization."""
    hall_id, hall_error = _require_hall_for_super_admin(request)
    if hall_error:
        return hall_error

    statuses = request.query_params.getlist('status')
    statuses = [value for value in statuses if value]
    try:
        payload = services.getRoomVacationRequestsForFinalizationService(
            user=request.user,
            statuses=statuses or None,
            hall_id=hall_id,
        )
        return Response(payload, status=status.HTTP_200_OK)
    except Exception as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def finalizeRoomVacationController(request, request_id):
    """Super admin finalizes room vacation after clearance approval."""
    hall_id, hall_error = _require_hall_for_super_admin(request)
    if hall_error:
        return hall_error

    try:
        payload = services.finalizeRoomVacationService(
            user=request.user,
            request_id=request_id,
            confirm=bool(request.data.get('confirm', False)),
            hall_id=hall_id,
        )
        return Response(
            {
                'message': 'Room vacation finalized successfully.',
                'request': payload,
            },
            status=status.HTTP_200_OK,
        )
    except Exception as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def generateHostelReportController(request):
    """Generate hostel report by report type/date/filters."""
    try:
        payload = services.generateHostelReportService(
            user=request.user,
            report_type=request.data.get('report_type', ''),
            start_date=date.fromisoformat(request.data.get('start_date', '')),
            end_date=date.fromisoformat(request.data.get('end_date', '')),
            filters=request.data.get('filters', {}),
            title=request.data.get('title', ''),
            hall_id=request.data.get('hall_id'),
            template_id=request.data.get('template_id'),
        )
        return Response(payload, status=status.HTTP_201_CREATED)
    except Exception as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def myHostelReportsController(request):
    """List report history for current user."""
    try:
        payload = services.listMyHostelReportsService(user=request.user)
        return Response(payload, status=status.HTTP_200_OK)
    except Exception as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def reportFilterTemplatesController(request):
    """List or save report filter templates for current user."""
    try:
        if request.method == 'GET':
            payload = services.listReportFilterTemplatesService(
                user=request.user,
                report_type=request.query_params.get('report_type'),
            )
            return Response(payload, status=status.HTTP_200_OK)

        payload = services.saveReportFilterTemplateService(
            user=request.user,
            template_name=request.data.get('template_name', ''),
            report_type=request.data.get('report_type', ''),
            filters=request.data.get('filters', {}),
        )
        return Response(payload, status=status.HTTP_201_CREATED)
    except Exception as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def submitHostelReportController(request, report_id):
    """Warden submits draft report to super admin."""
    try:
        payload = services.submitHostelReportToSuperAdminService(
            user=request.user,
            report_id=report_id,
            submission_notes=request.data.get('submission_notes', ''),
            priority=request.data.get('priority', 'Normal'),
            supporting_documents=request.FILES.getlist('supporting_documents'),
        )
        return Response(
            {
                'message': 'Report submitted to Super Admin successfully.',
                'report': payload,
            },
            status=status.HTTP_200_OK,
        )
    except Exception as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def submittedHostelReportsController(request):
    """Super admin list of submitted reports for review."""
    hall_id, hall_error = _require_hall_for_super_admin(request)
    if hall_error:
        return hall_error

    statuses = request.query_params.getlist('status')
    statuses = [value for value in statuses if value]
    try:
        payload = services.listSubmittedHostelReportsService(
            user=request.user,
            statuses=statuses or None,
            hall_id=hall_id,
        )
        return Response(payload, status=status.HTTP_200_OK)
    except Exception as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def hostelReportDetailController(request, report_id):
    """Detailed report payload for creator/super admin review."""
    hall_id, hall_error = _require_hall_for_super_admin(request)
    if hall_error:
        return hall_error

    try:
        payload = services.getHostelReportDetailService(
            user=request.user,
            report_id=report_id,
            log_view=True,
            hall_id=hall_id,
        )
        return Response(payload, status=status.HTTP_200_OK)
    except Exception as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def reviewHostelReportController(request, report_id):
    """Super admin approves report or requests revision with feedback."""
    hall_id, hall_error = _require_hall_for_super_admin(request)
    if hall_error:
        return hall_error

    try:
        payload = services.reviewSubmittedHostelReportService(
            user=request.user,
            report_id=report_id,
            decision=request.data.get('decision', ''),
            feedback=request.data.get('feedback', ''),
            hall_id=hall_id,
        )
        return Response(
            {
                'message': 'Report review submitted successfully.',
                'report': payload,
            },
            status=status.HTTP_200_OK,
        )
    except Exception as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


def _build_csv_for_report(report_payload):
    buffer = io.StringIO()
    writer = csv.writer(buffer)

    writer.writerow(['Report UID', report_payload.get('report_uid')])
    writer.writerow(['Title', report_payload.get('title')])
    writer.writerow(['Type', report_payload.get('report_type')])
    writer.writerow(['Hall', report_payload.get('hall_id')])
    writer.writerow(['Date Range', f"{report_payload.get('start_date')} to {report_payload.get('end_date')}"])
    writer.writerow([])

    report_data = report_payload.get('report_data') or {}
    sections = report_data.get('sections') or []
    for section in sections:
        writer.writerow([section.get('title', 'Section')])
        summary = section.get('summary') or {}
        for key, value in summary.items():
            writer.writerow([key, value])
        rows = section.get('rows') or []
        if rows:
            row_keys = sorted({key for row in rows for key in row.keys()})
            writer.writerow(row_keys)
            for row in rows:
                writer.writerow([row.get(key, '') for key in row_keys])
        writer.writerow([])

    return buffer.getvalue().encode('utf-8')


@api_view(['GET'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def downloadHostelReportController(request, report_id):
    """Download report in CSV/PDF/Both formats and log activity."""
    download_format = (request.query_params.get('format') or 'pdf').strip().lower()
    if download_format not in ['pdf', 'csv', 'both']:
        return Response({'error': 'format must be pdf, csv, or both.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        payload = services.getHostelReportDetailService(
            user=request.user,
            report_id=report_id,
            log_view=False,
            hall_id=_extract_hall_id(request),
        )
    except Exception as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    report_uid = payload.get('report_uid') or f'report-{report_id}'
    csv_bytes = _build_csv_for_report(payload)

    context = {
        'report': payload,
    }
    pdf_response = render_to_pdf('hostelmanagement/generated_report_pdf.html', context)
    if not pdf_response:
        return Response({'error': 'Unable to generate PDF for report.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    pdf_bytes = pdf_response.content

    services.logHostelReportDownloadService(
        user=request.user,
        report_id=report_id,
        download_format=download_format,
        hall_id=_extract_hall_id(request),
    )

    if download_format == 'csv':
        response = HttpResponse(csv_bytes, content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{report_uid}.csv"'
        return response

    if download_format == 'pdf':
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{report_uid}.pdf"'
        return response

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(f'{report_uid}.csv', csv_bytes)
        archive.writestr(f'{report_uid}.pdf', pdf_bytes)

    response = HttpResponse(zip_buffer.getvalue(), content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="{report_uid}.zip"'
    return response


@api_view(['GET'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def inventoryDashboardController(request):
    """UC-026/027/028 inventory dashboard list by role scope."""
    hall_id, hall_error = _require_hall_for_super_admin(request)
    if hall_error:
        return hall_error

    try:
        payload = services.getInventoryDashboardService(user=request.user, hall_id=hall_id)
        return Response(payload, status=status.HTTP_200_OK)
    except Exception as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def submitInventoryInspectionController(request):
    """UC-026 caretaker submits inventory inspection results."""
    try:
        payload = services.submitInventoryInspectionService(
            user=request.user,
            items=request.data.get('items', []),
            remarks=request.data.get('remarks', ''),
        )
        return Response(
            {
                'message': 'Inventory inspection saved successfully.',
                'inspection': payload,
            },
            status=status.HTTP_201_CREATED,
        )
    except Exception as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def inventoryInspectionsController(request):
    """List inventory inspection records."""
    hall_id, hall_error = _require_hall_for_super_admin(request)
    if hall_error:
        return hall_error

    try:
        payload = services.getInventoryInspectionsService(user=request.user, hall_id=hall_id)
        return Response(payload, status=status.HTTP_200_OK)
    except Exception as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def submitResourceRequirementRequestController(request):
    """UC-027 caretaker submits resource requirement request."""
    try:
        payload = services.submitResourceRequirementRequestService(
            user=request.user,
            request_type=request.data.get('request_type', ''),
            items=request.data.get('items', []),
            justification=request.data.get('justification', ''),
        )
        return Response(
            {
                'message': 'Resource requirement request submitted successfully.',
                'request': payload,
            },
            status=status.HTTP_201_CREATED,
        )
    except Exception as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def resourceRequirementRequestsController(request):
    """List resource requirement requests for review/track."""
    hall_id, hall_error = _require_hall_for_super_admin(request)
    if hall_error:
        return hall_error

    try:
        payload = services.getResourceRequestsService(user=request.user, hall_id=hall_id)
        return Response(payload, status=status.HTTP_200_OK)
    except Exception as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def reviewResourceRequirementRequestController(request, request_id):
    """Warden/admin reviews resource request."""
    hall_id, hall_error = _require_hall_for_super_admin(request)
    if hall_error:
        return hall_error

    try:
        payload = services.reviewResourceRequestService(
            user=request.user,
            request_id=request_id,
            decision=request.data.get('decision', ''),
            remarks=request.data.get('remarks', ''),
            hall_id=hall_id,
        )
        return Response(
            {
                'message': 'Resource request review submitted successfully.',
                'request': payload,
            },
            status=status.HTTP_200_OK,
        )
    except Exception as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def updateInventoryRecordController(request, inventory_id):
    """UC-028 caretaker updates inventory record with audit logging."""
    try:
        payload = services.auditedInventoryUpdateService(
            user=request.user,
            inventory_id=inventory_id,
            quantity=request.data.get('quantity'),
            condition_status=request.data.get('condition_status'),
            reason=request.data.get('reason', ''),
        )
        return Response(
            {
                'message': 'Inventory record updated successfully.',
                'inventory': payload,
            },
            status=status.HTTP_200_OK,
        )
    except Exception as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def inventoryUpdateLogsController(request):
    """List inventory update logs for audit."""
    hall_id, hall_error = _require_hall_for_super_admin(request)
    if hall_error:
        return hall_error

    try:
        payload = services.getInventoryUpdateLogsService(user=request.user, hall_id=hall_id)
        return Response(payload, status=status.HTTP_200_OK)
    except Exception as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


# ══════════════════════════════════════════════════════════════
# GUARD DUTY MANAGEMENT CONTROLLERS
# ══════════════════════════════════════════════════════════════


@api_view(['GET', 'POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
@authorizeRoles('super_admin', 'warden', 'caretaker')
def guardDutySchedulesController(request):
    """Super admin manages guard schedules; warden/caretaker can view schedules."""
    try:
        if request.method == 'GET':
            payload = services.getGuardDutySchedulesService(
                user=request.user,
                hall_id=_extract_hall_id(request),
                day=request.query_params.get('day', ''),
            )
            return Response(payload, status=status.HTTP_200_OK)

        override_policy = str(request.data.get('override_policy', 'false')).strip().lower() in {'1', 'true', 'yes'}
        payload = services.createGuardDutyScheduleService(
            user=request.user,
            hall_id=_extract_hall_id(request),
            staff_id=request.data.get('staff_id'),
            day=request.data.get('day'),
            start_time=request.data.get('start_time'),
            end_time=request.data.get('end_time'),
            override_policy=override_policy,
        )
        return Response({'message': 'Guard duty schedule saved successfully.', 'schedule': payload}, status=status.HTTP_201_CREATED)
    except Exception as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['PATCH', 'DELETE'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
@authorizeRoles('super_admin')
def guardDutyScheduleDetailController(request, schedule_id):
    """Update or delete a guard duty schedule entry by super admin."""
    try:
        hall_id = _extract_hall_id(request)
        if request.method == 'PATCH':
            override_policy = str(request.data.get('override_policy', 'false')).strip().lower() in {'1', 'true', 'yes'}
            payload = services.updateGuardDutyScheduleService(
                user=request.user,
                schedule_id=schedule_id,
                hall_id=hall_id,
                staff_id=request.data.get('staff_id'),
                day=request.data.get('day'),
                start_time=request.data.get('start_time'),
                end_time=request.data.get('end_time'),
                override_policy=override_policy,
            )
            return Response({'message': 'Guard duty schedule updated successfully.', 'schedule': payload}, status=status.HTTP_200_OK)

        services.deleteGuardDutyScheduleService(
            user=request.user,
            schedule_id=schedule_id,
            hall_id=hall_id,
        )
        return Response({'message': 'Guard duty schedule removed successfully.'}, status=status.HTTP_200_OK)
    except Exception as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
@authorizeRoles('super_admin', 'warden', 'caretaker')
def guardDutyConcernsController(request):
    """Warden/caretaker raise concerns; all authorized roles can view scoped concerns."""
    try:
        if request.method == 'GET':
            payload = services.listGuardDutyConcernsService(
                user=request.user,
                hall_id=_extract_hall_id(request),
            )
            return Response({'concerns': payload}, status=status.HTTP_200_OK)

        payload = services.raiseGuardDutyConcernService(
            user=request.user,
            subject=request.data.get('subject', ''),
            message=request.data.get('message', ''),
        )
        return Response({'message': 'Guard duty concern submitted to super admin.', 'concern': payload}, status=status.HTTP_201_CREATED)
    except Exception as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
@authorizeRoles('super_admin')
def resolveGuardDutyConcernController(request, concern_id):
    """Super admin resolves a guard duty concern."""
    try:
        payload = services.resolveGuardDutyConcernService(
            user=request.user,
            concern_id=concern_id,
            hall_id=_extract_hall_id(request),
            response_notes=request.data.get('response_notes', ''),
        )
        return Response({'message': 'Guard duty concern resolved successfully.', 'concern': payload}, status=status.HTTP_200_OK)
    except Exception as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


# //Caretaker can approve or reject leave applied by the student
@csrf_exempt
def update_leave_status(request):
    if request.method == 'POST':
        leave_id = request.POST.get('leave_id')
        status = request.POST.get('status')
        try:
            leave = HostelLeave.objects.get(id=leave_id)
            leave.status = status
            leave.remark = request.POST.get('remark')
            leave.save()

            # Send notification to the student
            sender = request.user  # Assuming request.user is the caretaker
            
            student_id = leave.roll_num  # Assuming student is a foreign key field in HostelLeave model
            recipient = User.objects.get(username=student_id)
            type = "leave_accept" if status == "Approved" else "leave_reject"
            hostel_notifications(sender, recipient, type)

            return JsonResponse({'status': status,'remarks':leave.remark,'message': 'Leave status updated successfully.'})
        except HostelLeave.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Leave not found.'}, status=404)
    else:
        return JsonResponse({'status': 'error', 'message': 'Only POST requests are allowed.'}, status=405)


# //! Manage Fine
# //! Add Fine Functionality


@login_required
def show_fine_edit_form(request,fine_id):
    user_id = request.user
    staff = user_id.extrainfo.id
    caretaker = HallCaretaker.objects.get(staff_id=staff)
    hall_id = caretaker.hall_id

    fine = HostelFine.objects.filter(fine_id=fine_id)



    return render(request, 'hostelmanagement/impose_fine_edit.html', {'fines': fine[0]})

@login_required
def update_student_fine(request,fine_id):
    if request.method == 'POST':
        fine = HostelFine.objects.get(fine_id=fine_id)
        print("------------------------------------------------")
        print(request.POST)
        fine.amount = request.POST.get('amount')
        fine.status = request.POST.get('status')
        fine.reason = request.POST.get('reason')
        fine.save()
        
        return HttpResponse({'message': 'Fine has edited successfully'}, status=status.HTTP_200_OK)


@login_required
def impose_fine_view(request):
    user_id = request.user
    staff = user_id.extrainfo.id
    students = Student.objects.all()

    if HallCaretaker.objects.filter(staff_id=staff).exists():
        return render(request, 'hostelmanagement/impose_fine.html', {'students': students})

    return HttpResponse(f'<script>alert("You are not authorized to access this page"); window.location.href = "/hostelmanagement/"</script>')


def _serialize_fine(fine, repeat_offender_student_ids=None, fine_count_by_student=None):
    caretaker_name = None
    if fine.caretaker and fine.caretaker.id and fine.caretaker.id.user:
        caretaker_name = fine.caretaker.id.user.username

    status_value = fine.status.value if hasattr(fine.status, 'value') else str(fine.status)
    category_value = fine.category.value if hasattr(fine.category, 'value') else str(fine.category)
    student_pk = fine.student_id
    repeat_offender = False
    student_fine_count = None

    if repeat_offender_student_ids is not None:
        repeat_offender = student_pk in repeat_offender_student_ids
    if fine_count_by_student is not None:
        student_fine_count = fine_count_by_student.get(student_pk, 0)

    return {
        'fine_id': fine.fine_id,
        'student_id': fine.student.id.user.username,
        'student_name': fine.student_name,
        'hall_id': fine.hall.hall_id,
        'hall_name': fine.hall.hall_name,
        'caretaker_name': caretaker_name,
        'amount': float(fine.amount),
        'category': category_value,
        'status': status_value,
        'reason': fine.reason,
        'evidence': fine.evidence.url if fine.evidence else None,
        'created_at': fine.created_at.isoformat() if fine.created_at else None,
        'repeat_offender': repeat_offender,
        'fine_count_for_student': student_fine_count,
    }


def _resolve_repeat_offender_threshold(request):
    """Resolve threshold from query param; defaults to 3 and must be >= 1."""
    raw_threshold = request.query_params.get('repeat_offender_threshold')
    if raw_threshold in (None, ''):
        return 3

    try:
        threshold = int(raw_threshold)
    except (TypeError, ValueError):
        raise ValueError('repeat_offender_threshold must be an integer >= 1.')

    if threshold < 1:
        raise ValueError('repeat_offender_threshold must be an integer >= 1.')
    return threshold


def _build_repeat_offender_metadata(fines, threshold):
    """Compute per-student fine counts and repeat-offender flags in-memory."""
    fine_count_by_student = {}
    for fine in fines:
        student_pk = fine.student_id
        fine_count_by_student[student_pk] = fine_count_by_student.get(student_pk, 0) + 1

    repeat_offender_student_ids = {
        student_pk
        for student_pk, count in fine_count_by_student.items()
        if count >= threshold
    }
    return repeat_offender_student_ids, fine_count_by_student


@api_view(['GET'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def getCaretakerStudentsController(request):
    """Return students in caretaker's hostel for fine search UI."""
    try:
        mapping = services.resolve_user_hall_mapping_service(user=request.user, strict=True)
    except services.UserHallMappingMissingError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_403_FORBIDDEN)

    if mapping.role != 'caretaker':
        return Response({'error': 'Only caretaker can access hostel student list.'}, status=status.HTTP_403_FORBIDDEN)

    payload = services.searchStudentsService(user=request.user, query=None)
    return Response(payload, status=status.HTTP_200_OK)


# ══════════════════════════════════════════════════════════════
# COMPLAINT MANAGEMENT CONTROLLERS
# ══════════════════════════════════════════════════════════════


@api_view(['POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def submitComplaintController(request):
    """Submit a new complaint by student."""
    try:
        title = request.data.get('title', '').strip()
        description = request.data.get('description', '').strip()
        
        if not title or not description:
            return Response(
                {'error': 'Both title and description are required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        complaint = services.submitComplaintService(
            user=request.user,
            title=title,
            description=description,
        )
        
        serializer = HostelComplaintSerializer(complaint)
        return Response(
            {
                'message': 'Complaint submitted successfully.',
                'complaint': serializer.data,
            },
            status=status.HTTP_201_CREATED
        )
    except services.UnauthorizedAccessError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_403_FORBIDDEN)
    except services.InvalidOperationError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except services.UserHallMappingMissingError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_403_FORBIDDEN)
    except services.StudentNotFoundError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def getStudentComplaintsController(request):
    """Get current student's own complaints only."""
    try:
        complaints = services.getStudentComplaintsService(user=request.user)
        serializer = HostelComplaintSerializer(complaints, many=True)
        return Response(
            {'complaints': serializer.data},
            status=status.HTTP_200_OK
        )
    except services.UnauthorizedAccessError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_403_FORBIDDEN)
    except services.UserHallMappingMissingError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_403_FORBIDDEN)
    except services.StudentNotFoundError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def getHostelComplaintsController(request):
    """Get all complaints for caretaker's hostel."""
    try:
        complaints = services.getHostelComplaintsService(user=request.user)
        serializer = HostelComplaintSerializer(complaints, many=True)
        return Response(
            {'complaints': serializer.data},
            status=status.HTTP_200_OK
        )
    except services.UnauthorizedAccessError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_403_FORBIDDEN)
    except services.UserHallMappingMissingError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_403_FORBIDDEN)
    except Exception as exc:
        return Response(
            {'error': f'Error fetching complaints: {str(exc)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def updateComplaintStatusController(request):
    """Update complaint status by caretaker."""
    try:
        complaint_id = request.data.get('complaint_id')
        new_status = request.data.get('status', '').strip().lower()
        
        if not complaint_id:
            return Response(
                {'error': 'Complaint ID is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not new_status:
            return Response(
                {'error': 'Status is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            complaint_id = int(complaint_id)
        except (ValueError, TypeError):
            return Response(
                {'error': 'Invalid complaint ID.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        complaint = services.updateComplaintStatusService(
            user=request.user,
            complaint_id=complaint_id,
            status=new_status,
        )
        
        serializer = HostelComplaintSerializer(complaint)
        return Response(
            {
                'message': f'Complaint status updated to {new_status}.',
                'complaint': serializer.data,
            },
            status=status.HTTP_200_OK
        )
    except services.UnauthorizedAccessError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_403_FORBIDDEN)
    except services.InvalidOperationError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except services.UserHallMappingMissingError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_403_FORBIDDEN)


@api_view(['POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def escalateComplaintController(request):
    """Escalate complaint to warden by caretaker."""
    try:
        complaint_id = request.data.get('complaint_id')
        escalation_reason = request.data.get('escalation_reason', '').strip()
        remarks = request.data.get('remarks', '').strip()
        
        if not complaint_id:
            return Response(
                {'error': 'Complaint ID is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not escalation_reason:
            return Response(
                {'error': 'Escalation reason is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            complaint_id = int(complaint_id)
        except (ValueError, TypeError):
            return Response(
                {'error': 'Invalid complaint ID.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        complaint = services.escalateComplaintService(
            user=request.user,
            complaint_id=complaint_id,
            escalation_reason=escalation_reason,
            remarks=remarks,
        )
        
        serializer = HostelComplaintSerializer(complaint)
        return Response(
            {
                'message': 'Complaint successfully escalated to warden.',
                'complaint': serializer.data,
            },
            status=status.HTTP_200_OK
        )
    except services.UnauthorizedAccessError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_403_FORBIDDEN)
    except services.InvalidOperationError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except services.UserHallMappingMissingError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_403_FORBIDDEN)


# ══════════════════════════════════════════════════════════════
# WARDEN COMPLAINT MANAGEMENT CONTROLLERS
# ══════════════════════════════════════════════════════════════

@api_view(['GET'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def getEscalatedComplaintsController(request):
    """Get all escalated complaints for warden."""
    try:
        complaints = services.getEscalatedComplaintsService(user=request.user)
        serializer = HostelComplaintSerializer(complaints, many=True)
        return Response(
            {
                'count': len(complaints),
                'complaints': serializer.data,
            },
            status=status.HTTP_200_OK
        )
    except services.UnauthorizedAccessError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_403_FORBIDDEN)
    except services.UserHallMappingMissingError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_403_FORBIDDEN)
    except Exception as exc:
        return Response(
            {'error': f'Error fetching complaints: {str(exc)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def getAllComplaintsForWardenController(request):
    """Get all complaints (all statuses) for warden complaint history."""
    try:
        complaints = services.getAllComplaintsForWardenService(user=request.user)
        serializer = HostelComplaintSerializer(complaints, many=True)
        return Response(
            {
                'count': len(complaints),
                'complaints': serializer.data,
            },
            status=status.HTTP_200_OK
        )
    except services.UnauthorizedAccessError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_403_FORBIDDEN)
    except services.UserHallMappingMissingError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_403_FORBIDDEN)
    except Exception as exc:
        return Response(
            {'error': f'Error fetching complaints: {str(exc)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def resolveComplaintController(request):
    """Warden resolves an escalated complaint."""
    try:
        complaint_id = request.data.get('complaint_id')
        resolution_notes = request.data.get('resolution_notes', '').strip()
        
        if not complaint_id:
            return Response(
                {'error': 'Complaint ID is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not resolution_notes:
            return Response(
                {'error': 'Resolution notes are required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            complaint_id = int(complaint_id)
        except (ValueError, TypeError):
            return Response(
                {'error': 'Invalid complaint ID.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        complaint = services.resolveComplaintService(
            user=request.user,
            complaint_id=complaint_id,
            resolution_notes=resolution_notes,
        )
        
        serializer = HostelComplaintSerializer(complaint)
        return Response(
            {
                'message': 'Complaint successfully resolved.',
                'complaint': serializer.data,
            },
            status=status.HTTP_200_OK
        )
    except services.UnauthorizedAccessError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_403_FORBIDDEN)
    except services.InvalidOperationError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except services.UserHallMappingMissingError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_403_FORBIDDEN)
    except Exception as exc:
        return Response(
            {'error': f'Error resolving complaint: {str(exc)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def reassignComplaintController(request):
    """Warden reassigns escalated complaint back to a caretaker."""
    try:
        complaint_id = request.data.get('complaint_id')
        caretaker_id = request.data.get('caretaker_id')
        instructions = request.data.get('instructions', '').strip()
        
        if not complaint_id:
            return Response(
                {'error': 'Complaint ID is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not caretaker_id:
            return Response(
                {'error': 'Caretaker ID is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            complaint_id = int(complaint_id)
            caretaker_id = int(caretaker_id)
        except (ValueError, TypeError):
            return Response(
                {'error': 'Invalid complaint ID or caretaker ID.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        complaint = services.reassignComplaintService(
            user=request.user,
            complaint_id=complaint_id,
            caretaker_id=caretaker_id,
            instructions=instructions,
        )
        
        serializer = HostelComplaintSerializer(complaint)
        return Response(
            {
                'message': 'Complaint successfully reassigned to caretaker.',
                'complaint': serializer.data,
            },
            status=status.HTTP_200_OK
        )
    except services.UnauthorizedAccessError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_403_FORBIDDEN)
    except services.InvalidOperationError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except services.UserHallMappingMissingError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_403_FORBIDDEN)
    except Exception as exc:
        return Response(
            {'error': f'Error reassigning complaint: {str(exc)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


def _impose_fine_response(request):
    student_id = request.data.get('student_id')
    amount = request.data.get('amount')
    reason = request.data.get('reason')
    category = request.data.get('category')
    evidence = request.FILES.get('evidence') if hasattr(request, 'FILES') else None

    if not student_id:
        return Response({'error': 'student_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
    if amount is None:
        return Response({'error': 'amount is required.'}, status=status.HTTP_400_BAD_REQUEST)
    if not reason:
        return Response({'error': 'reason is required.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        fine = services.imposeFineService(
            user=request.user,
            student_id=student_id,
            amount=amount,
            category=category,
            reason=reason,
            evidence=evidence,
        )
    except (services.InvalidOperationError, services.StudentNotFoundError) as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except (services.UserHallMappingMissingError, services.UnauthorizedAccessError) as exc:
        return Response({'error': str(exc)}, status=status.HTTP_403_FORBIDDEN)

    try:
        recipient = User.objects.get(username=student_id)
        hostel_notifications(request.user, recipient, 'fine_imposed')
    except Exception:
        pass

    return Response({'message': 'Fine imposed successfully.', 'fine': _serialize_fine(fine)}, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def imposeFineController(request):
    """Impose fine for student in caretaker's hostel."""
    return _impose_fine_response(request)


@api_view(['GET'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def getHostelFinesController(request):
    """Fetch fines for caretaker's hostel only."""
    try:
        threshold = _resolve_repeat_offender_threshold(request)
    except ValueError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    try:
        fines = services.getHostelFinesService(user=request.user)
    except (services.UserHallMappingMissingError, services.UnauthorizedAccessError) as exc:
        return Response({'error': str(exc)}, status=status.HTTP_403_FORBIDDEN)

    fines_list = list(fines)
    repeat_offender_student_ids, fine_count_by_student = _build_repeat_offender_metadata(fines_list, threshold)

    return Response(
        {
            'repeat_offender_threshold': threshold,
            'fines': [
                _serialize_fine(
                    fine,
                    repeat_offender_student_ids=repeat_offender_student_ids,
                    fine_count_by_student=fine_count_by_student,
                )
                for fine in fines_list
            ],
        },
        status=status.HTTP_200_OK,
    )


@api_view(['GET'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def getStudentFinesController(request):
    """Fetch fines visible to authenticated student only."""
    try:
        threshold = _resolve_repeat_offender_threshold(request)
    except ValueError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    try:
        fines = services.getStudentFinesService(user=request.user)
    except (services.UserHallMappingMissingError, services.UnauthorizedAccessError) as exc:
        return Response({'error': str(exc)}, status=status.HTTP_403_FORBIDDEN)
    except services.StudentNotFoundError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    fines_list = list(fines)
    repeat_offender_student_ids, fine_count_by_student = _build_repeat_offender_metadata(fines_list, threshold)

    return Response(
        [
            _serialize_fine(
                fine,
                repeat_offender_student_ids=repeat_offender_student_ids,
                fine_count_by_student=fine_count_by_student,
            )
            for fine in fines_list
        ],
        status=status.HTTP_200_OK,
    )


@api_view(['POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def updateFineStatusController(request, fine_id):
    """Caretaker updates fine status for own hostel."""
    status_value = request.data.get('status')
    if not status_value:
        return Response({'error': 'status is required.'}, status=status.HTTP_400_BAD_REQUEST)

    normalized = str(status_value).strip().lower()
    status_map = {
        'pending': FineStatus.PENDING,
        'paid': FineStatus.PAID,
    }
    mapped_status = status_map.get(normalized)
    if not mapped_status:
        return Response({'error': 'Invalid status. Use Pending or Paid.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        fine = services.update_fine_status_service(
            fine_id=fine_id,
            new_status=mapped_status,
            user=request.user,
        )
    except services.FineNotFoundError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_404_NOT_FOUND)
    except (services.UserHallMappingMissingError, services.UnauthorizedAccessError, services.InvalidOperationError) as exc:
        return Response({'error': str(exc)}, status=status.HTTP_403_FORBIDDEN)

    return Response({'message': 'Fine status updated successfully.', 'fine': _serialize_fine(fine)}, status=status.HTTP_200_OK)


@api_view(['GET'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def searchStudentsController(request):
    """Search students in authenticated user's hostel."""
    query = request.query_params.get('q') or request.query_params.get('search')
    try:
        students = services.searchStudentsService(user=request.user, query=query)
    except (services.UserHallMappingMissingError, services.UnauthorizedAccessError) as exc:
        return Response({'error': str(exc)}, status=status.HTTP_403_FORBIDDEN)
    return Response(students, status=status.HTTP_200_OK)


@api_view(['GET'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def getStudentController(request, student_id):
    """Get single student details for room allotment modal."""
    try:
        student_data = services.getStudentDetailsService(user=request.user, student_id=student_id)
    except services.StudentNotFoundError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_404_NOT_FOUND)
    except (services.UserHallMappingMissingError, services.UnauthorizedAccessError) as exc:
        return Response({'error': str(exc)}, status=status.HTTP_403_FORBIDDEN)
    return Response(student_data, status=status.HTTP_200_OK)


@api_view(['POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def assignRoomController(request):
    """Assign room to a student within caretaker's hostel."""
    student_id = request.data.get('student_id')
    room_id = request.data.get('room_id')
    room_label = request.data.get('room_no') or request.data.get('room_number')

    if not student_id:
        return Response({'error': 'student_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
    if not room_id and not room_label:
        return Response({'error': 'room_id or room_no is required.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        allocation = services.assignRoomService(
            user=request.user,
            student_id=student_id,
            room_id=room_id,
            room_label=room_label,
        )
    except (services.StudentNotFoundError, services.RoomNotFoundError) as exc:
        return Response({'error': str(exc)}, status=status.HTTP_404_NOT_FOUND)
    except (services.UserHallMappingMissingError, services.UnauthorizedAccessError) as exc:
        return Response({'error': str(exc)}, status=status.HTTP_403_FORBIDDEN)
    except (services.RoomNotAvailableError, services.RoomAssignmentError, ValueError) as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    return Response(
        {
            'message': 'Room assigned successfully.',
            'allocation': {
                'id': allocation.id,
                'student_id': allocation.student.id.user.username,
                'room_id': allocation.room.id,
                'room_number': f"{allocation.room.block_no}-{allocation.room.room_no}",
                'hostel_id': allocation.hall.hall_id,
                'assigned_at': allocation.assigned_at.isoformat(),
                'status': allocation.status,
            },
        },
        status=status.HTTP_200_OK,
    )


@api_view(['POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
@authorizeRoles('student')
def createStudentGroupController(request):
    """Student creates a room group (self + 2 members)."""
    payload = request.data or {}
    member_roll_numbers = payload.get('member_roll_numbers') or payload.get('roll_numbers') or []
    if not isinstance(member_roll_numbers, list):
        return Response({'error': 'member_roll_numbers must be a list.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        group = services.createStudentGroupService(
            user=request.user,
            member_roll_numbers=member_roll_numbers,
        )
    except (services.StudentNotFoundError, services.UserHallMappingMissingError) as exc:
        return Response({'error': str(exc)}, status=status.HTTP_404_NOT_FOUND)
    except (services.UnauthorizedAccessError, services.InvalidOperationError) as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    return Response({'message': 'Group created successfully.', 'group': group}, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def getStudentRoomController(request):
    """Get logged-in student's currently allotted room details."""
    try:
        room_data = services.getStudentRoomService(user=request.user)
    except services.StudentNotFoundError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_404_NOT_FOUND)
    except (services.UserHallMappingMissingError, services.UnauthorizedAccessError) as exc:
        return Response({'error': str(exc)}, status=status.HTTP_403_FORBIDDEN)
    return Response(room_data, status=status.HTTP_200_OK)


@api_view(['POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
@authorizeRoles('super_admin')
def adminBulkAllotRoomsController(request):
    """Admin alias endpoint for grouped bulk allotment workflow."""
    hall_id = (request.data.get('hall_id') or '').strip()
    if not hall_id:
        return Response({'error': 'hall_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        hall = Hall.objects.get(hall_id=hall_id)
    except Hall.DoesNotExist:
        return Response({'error': 'Hostel not found.'}, status=status.HTTP_404_NOT_FOUND)

    source = (request.data.get('source') or 'batch').strip().lower()
    selected_student_ids = request.data.get('student_ids') or []
    force_reassign = bool(request.data.get('force_reassign', False))

    try:
        result = lifecycle_services.AllotmentService.bulk_allot_students(
            hall=hall,
            actor=request.user,
            source=source,
            selected_student_ids=selected_student_ids,
            force_reassign=force_reassign,
        )
    except lifecycle_services.WorkflowValidationError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    return Response({'message': 'Bulk room allotment completed.', 'result': result}, status=status.HTTP_200_OK)


@api_view(['POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
@authorizeRoles('caretaker', 'warden')
def approveRoomChangeRequestController(request):
    """Unified approve endpoint for caretaker/warden room change review."""
    request_id = request.data.get('request_id')
    if not request_id:
        return Response({'error': 'request_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

    role, _ = services.resolve_hostel_rbac_role_service(user=request.user)
    try:
        if role == 'caretaker':
            payload = services.caretakerReviewRoomChangeRequestService(
                user=request.user,
                room_change_request_id=request_id,
                decision='Approved',
                remarks=request.data.get('remarks', ''),
            )
        else:
            payload = services.wardenReviewRoomChangeRequestService(
                user=request.user,
                room_change_request_id=request_id,
                decision='Approved',
                remarks=request.data.get('remarks', ''),
            )
    except Exception as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    return Response({'message': 'Room change request approved.', 'request': payload}, status=status.HTTP_200_OK)


@api_view(['POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
@authorizeRoles('caretaker', 'warden')
def rejectRoomChangeRequestController(request):
    """Unified reject endpoint for caretaker/warden room change review."""
    request_id = request.data.get('request_id')
    remarks = (request.data.get('remarks') or '').strip()
    if not request_id:
        return Response({'error': 'request_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
    if not remarks:
        return Response({'error': 'remarks are required for rejection.'}, status=status.HTTP_400_BAD_REQUEST)

    role, _ = services.resolve_hostel_rbac_role_service(user=request.user)
    try:
        if role == 'caretaker':
            payload = services.caretakerReviewRoomChangeRequestService(
                user=request.user,
                room_change_request_id=request_id,
                decision='Rejected',
                remarks=remarks,
            )
        else:
            payload = services.wardenReviewRoomChangeRequestService(
                user=request.user,
                room_change_request_id=request_id,
                decision='Rejected',
                remarks=remarks,
            )
    except Exception as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    return Response({'message': 'Room change request rejected.', 'request': payload}, status=status.HTTP_200_OK)


@api_view(['GET'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def getStudentsForAttendanceController(request):
    """Return all students from authenticated caretaker's hostel for attendance marking."""
    try:
        students = services.getStudentsForAttendanceService(user=request.user)
    except (services.UserHallMappingMissingError, services.UnauthorizedAccessError) as exc:
        return Response({'error': str(exc)}, status=status.HTTP_403_FORBIDDEN)

    return Response({'students': students}, status=status.HTTP_200_OK)


@api_view(['POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def submitAttendanceController(request):
    """Caretaker submits daily attendance for students in own hostel."""
    payload = request.data
    date_value = None

    if isinstance(payload, list):
        attendance_entries = payload
        date_value = request.query_params.get('date')
    elif isinstance(payload, dict):
        attendance_entries = payload.get('attendance') or payload.get('records') or []
        date_value = payload.get('date')
    else:
        return Response({'error': 'Invalid payload format.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        result = services.submitAttendanceService(
            user=request.user,
            attendance_entries=attendance_entries,
            date_value=date_value,
        )
    except services.StudentNotFoundError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_404_NOT_FOUND)
    except (services.UserHallMappingMissingError, services.UnauthorizedAccessError) as exc:
        return Response({'error': str(exc)}, status=status.HTTP_403_FORBIDDEN)
    except services.InvalidOperationError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    return Response(
        {
            'message': 'Attendance submitted successfully.',
            'summary': result,
        },
        status=status.HTTP_200_OK,
    )


@api_view(['GET'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def getStudentAttendanceController(request):
    """Student views own attendance history only."""
    try:
        records = services.getStudentAttendanceService(user=request.user)
    except services.StudentNotFoundError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_404_NOT_FOUND)
    except (services.UserHallMappingMissingError, services.UnauthorizedAccessError) as exc:
        return Response({'error': str(exc)}, status=status.HTTP_403_FORBIDDEN)

    return Response({'attendance': records}, status=status.HTTP_200_OK)


class HostelFineView(APIView):
    """
    API endpoint for imposing fines on students.
    """
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(self, request):
        # Check if the user is a caretaker
        user_id = request.user
        staff = user_id.extrainfo.id

        try:
            caretaker = HallCaretaker.objects.get(staff_id=staff)
        except HallCaretaker.DoesNotExist:
            return HttpResponse(f'<script>alert("You are not authorized to access this page"); window.location.href = "/hostelmanagement/"</script>')

        hall_id = caretaker.hall_id

        # Extract data from the request
        student_id = request.data.get('student_id')
        student_name = request.data.get('student_fine_name')
        amount = request.data.get('amount')
        reason = request.data.get('reason')

        # Validate the data
        if not all([student_id, student_name, amount, reason]):
            return HttpResponse({'error': 'Incomplete data provided.'}, status=status.HTTP_400_BAD_REQUEST)

        # Create the HostelFine object
        try:
            fine = HostelFine.objects.create(
                student_id=student_id,
                student_name=student_name,
                amount=amount,
                reason=reason,
                hall_id=hall_id
            )
            # Sending notification to the student about the imposed fine
           
            
            
            recipient = User.objects.get(username=student_id)
            
            sender = request.user
            
            type = "fine_imposed"
            hostel_notifications(sender, recipient, type)

            return HttpResponse({'message': 'Fine imposed successfully.'}, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@login_required
def get_student_name(request, username):
    try:
        user = User.objects.get(username=username)
        full_name = f"{user.first_name} {user.last_name}" if user.first_name or user.last_name else ""
        return JsonResponse({"name": full_name})
    except User.DoesNotExist:
        return JsonResponse({"error": "User not found"}, status=404)


@login_required
def hostel_fine_list(request):
    user_id = request.user
    staff = user_id.extrainfo.id
    caretaker = HallCaretaker.objects.get(staff_id=staff)
    hall_id = caretaker.hall_id
    hostel_fines = HostelFine.objects.filter(
        hall_id=hall_id).order_by('fine_id')

    if HallCaretaker.objects.filter(staff_id=staff).exists():
        return render(request, 'hostelmanagement/hostel_fine_list.html', {'hostel_fines': hostel_fines})

    return HttpResponse(f'<script>alert("You are not authorized to access this page"); window.location.href = "/hostelmanagement/"</script>')


@login_required
def student_fine_details(request):
    user_id = request.user.username
    # print(user_id)
    # staff=user_id.extrainfo.id

    # Check if the user_id exists in the Student table
    # if HallCaretaker.objects.filter(staff_id=staff).exists():
    #     return HttpResponse('<script>alert("You are not authorized to access this page"); window.location.href = "/hostelmanagement/";</script>')

    if not Student.objects.filter(id_id=user_id).exists():
        return HttpResponse('<script>alert("You are not authorized to access this page"); window.location.href = "/hostelmanagement/";</script>')

    # # Check if the user_id exists in the HostelFine table
    if not HostelFine.objects.filter(student_id=user_id).exists():
        return HttpResponse('<script>alert("You have no fines recorded"); window.location.href = "/hostelmanagement/";</script>')

    # # Retrieve the fines associated with the current student
    student_fines = HostelFine.objects.filter(student_id=user_id)

    return render(request, 'hostelmanagement/student_fine_details.html', {'student_fines': student_fines})

    # return JsonResponse({'message': 'Nice'}, status=status.HTTP_200_OK)


class HostelFineUpdateView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(self, request, fine_id):
        user_id = request.user
        staff = user_id.extrainfo.id

        data = request.data
        fine_idd = data.get('fine_id')
        status_ = data.get('status')
        # print("fine_idd",fine_idd)
        # print("status_",status_)

        try:
            caretaker = HallCaretaker.objects.get(staff_id=staff)
        except HallCaretaker.DoesNotExist:
            return Response({'error': 'You are not authorized to access this page'}, status=status.HTTP_403_FORBIDDEN)

        hall_id = caretaker.hall_id

        # Convert fine_id to integer
        fine_id = int(fine_id)

        # Get hostel fine object
        try:
            hostel_fine = HostelFine.objects.get(
                hall_id=hall_id, fine_id=fine_id)
        except HostelFine.DoesNotExist:
            raise NotFound(detail="Hostel fine not found")

        # Validate required fields
        if status_ not in ['Pending', 'Paid']:
            return Response({'error': 'Invalid status value'}, status=status.HTTP_400_BAD_REQUEST)

        # # Update status of the hostel fine
        hostel_fine.status = status_
        hostel_fine.save()

        # Return success response
        return Response({'message': 'Hostel fine status updated successfully!'}, status=status.HTTP_200_OK)

    def delete(self, request, fine_id):
        user_id = request.user
        staff = user_id.extrainfo.id

        try:
            caretaker = HallCaretaker.objects.get(staff_id=staff)
        except HallCaretaker.DoesNotExist:
            return Response({'error': 'You are not authorized to access this page'}, status=status.HTTP_403_FORBIDDEN)

        hall_id = caretaker.hall_id

        # Convert fine_id to integer
        fine_id = int(fine_id)

        # Get hostel fine object
        try:
            hostel_fine = HostelFine.objects.get(
                hall_id=hall_id, fine_id=fine_id)
            hostel_fine.delete()
        except HostelFine.DoesNotExist:
            raise NotFound(detail="Hostel fine not found")

        return Response({'message': 'Fine deleted successfully.'}, status=status.HTTP_204_NO_CONTENT)




class EditStudentView(View):
    template_name = 'hostelmanagement/edit_student.html'
    
    def get(self, request, student_id):
        student = Student.objects.get(id=student_id)
        
        context = {'student': student}
        return render(request, self.template_name, context)

    def post(self, request, student_id):
        student = Student.objects.get(id=student_id)
       
        # Update student details
        student.id.user.first_name = request.POST.get('first_name')
        student.id.user.last_name = request.POST.get('last_name')
        student.programme = request.POST.get('programme')
        student.batch = request.POST.get('batch')
        student.hall_no = request.POST.get('hall_number')
        student.room_no = request.POST.get('room_number')
        student.specialization = request.POST.get('specialization')
        
        student.save()

        # Update phone number and address from ExtraInfo model
        student.id.phone_no = request.POST.get('phone_number')
        student.id.address = request.POST.get('address')
        student.id.save()
        student.save()
        messages.success(request, 'Student details updated successfully.')
        return redirect("hostelmanagement:hostel_view")
    
class RemoveStudentView(View):
    def post(self, request, student_id):
        try:
            student = Student.objects.get(id=student_id)
            student.hall_no = 0
            student.save()
            messages.success(request, 'Student removed successfully.')
            return redirect("hostelmanagement:hostel_view")
            return JsonResponse({'status': 'success', 'message': 'Student removed successfully'})
        except Student.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Student not found'}, status=404)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

    def dispatch(self, request, *args, **kwargs):
        if request.method != 'POST':
            return JsonResponse({'status': 'error', 'message': 'Method Not Allowed'}, status=405)
        return super().dispatch(request, *args, **kwargs)
    

