from django.db import transaction
from django.db.models import Count, Sum
from django.utils import timezone
import random

from applications.academic_information.models import Student
from applications.globals.models import HoldsDesignation

from .models import (
    Hall,
    HallCaretaker,
    HallWarden,
    HallRoom,
    HostelBatch,
    HostelLifecycleState,
    HostelTransactionHistory,
    RoomAllocationStatus,
    RoomChangeRequest,
    StudentDetails,
    StudentRoomAllocation,
    HostelRoomGroup,
    HostelRoomGroupMember,
)


class WorkflowValidationError(Exception):
    pass


def is_super_admin(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return HoldsDesignation.objects.filter(working=user).filter(
        designation__name__in=['super_admin', 'SuperAdmin'],
    ).exists()


def _hall_number_from_hall_id(hall_id):
    digits = ''.join(ch for ch in str(hall_id or '') if ch.isdigit())
    return int(digits) if digits else None


class HostelService:
    @staticmethod
    def sync_lifecycle_state(hall, updated_by=None, note='', mark_students_fetched=None, mark_notifications=None):
        state, _ = HostelLifecycleState.objects.get_or_create(hall=hall)

        has_active_warden = HallWarden.objects.filter(hall=hall, is_active=True).exists()
        has_active_caretaker = HallCaretaker.objects.filter(hall=hall, is_active=True).exists()
        state.staff_assigned = has_active_warden and has_active_caretaker

        rooms = HallRoom.objects.filter(hall=hall)
        total_capacity = rooms.aggregate(total=Sum('room_cap')).get('total') or 0
        # Treat any positive room capacity as configured so legacy hostels can proceed.
        state.rooms_configured = rooms.exists() and total_capacity > 0

        state.hostel_activated = hall.operational_status == 'Active'
        state.batch_assigned = bool(hall.assigned_batch) and HostelBatch.objects.filter(hall=hall).exists()

        if mark_students_fetched is not None:
            state.eligible_students_fetched = bool(mark_students_fetched)

        active_allocations = StudentRoomAllocation.objects.filter(
            hall=hall,
            status=RoomAllocationStatus.ACTIVE,
        )
        state.bulk_allotment_completed = active_allocations.exists()

        room_counts = dict(
            active_allocations.values('room_id').annotate(c=Count('id')).values_list('room_id', 'c')
        )
        occupancy_synced = True
        for room in rooms:
            if room.room_occupied != room_counts.get(room.id, 0):
                occupancy_synced = False
                break
        state.occupancy_updated = occupancy_synced

        if mark_notifications is not None:
            state.notifications_sent = bool(mark_notifications)

        state.operational = all(
            [
                state.staff_assigned,
                state.rooms_configured,
                state.hostel_activated,
                state.batch_assigned,
                state.bulk_allotment_completed,
                state.occupancy_updated,
                state.notifications_sent,
            ]
        )

        if state.operational:
            state.current_step = 10
        elif state.notifications_sent:
            state.current_step = 9
        elif state.occupancy_updated:
            state.current_step = 8
        elif state.bulk_allotment_completed:
            state.current_step = 7
        elif state.eligible_students_fetched:
            state.current_step = 6
        elif state.batch_assigned:
            state.current_step = 5
        elif state.hostel_activated:
            state.current_step = 4
        elif state.rooms_configured:
            state.current_step = 3
        elif state.staff_assigned:
            state.current_step = 2
        else:
            state.current_step = 1

        state.last_transition_note = (note or '').strip()[:255]
        state.updated_by = updated_by
        state.save()

        return state

    @staticmethod
    def get_workflow_dashboard():
        payload = []
        halls = Hall.objects.all().order_by('hall_id')
        for hall in halls:
            state = HostelService.sync_lifecycle_state(hall)
            payload.append(
                {
                    'hall_id': hall.hall_id,
                    'hall_name': hall.hall_name,
                    'operational_status': hall.operational_status,
                    'assigned_batch': hall.assigned_batch,
                    'max_accomodation': hall.max_accomodation,
                    'number_students': hall.number_students,
                    'current_step': state.current_step,
                    'step_flags': {
                        'staff_assigned': state.staff_assigned,
                        'rooms_configured': state.rooms_configured,
                        'hostel_activated': state.hostel_activated,
                        'batch_assigned': state.batch_assigned,
                        'eligible_students_fetched': state.eligible_students_fetched,
                        'bulk_allotment_completed': state.bulk_allotment_completed,
                        'occupancy_updated': state.occupancy_updated,
                        'notifications_sent': state.notifications_sent,
                        'operational': state.operational,
                    },
                }
            )
        return payload


class BatchService:
    @staticmethod
    def get_eligible_students(hall, source='batch'):
        source_normalized = (source or 'batch').strip().lower()
        students = []

        if source_normalized == 'requests':
            requests = RoomChangeRequest.objects.filter(
                hall=hall,
                status='Approved',
            ).select_related('student__id__user')
            students = [req.student for req in requests]
        else:
            if not hall.assigned_batch:
                raise WorkflowValidationError('Batch is not assigned to this hostel yet.')

            students = list(
                Student.objects.filter(batch=str(hall.assigned_batch)).select_related('id__user').order_by('id__user__username')
            )

        unique_students = {}
        for student in students:
            unique_students[student.id.user.username] = student

        payload = []
        for username, student in unique_students.items():
            active_alloc = StudentRoomAllocation.objects.filter(
                student=student,
                status=RoomAllocationStatus.ACTIVE,
            ).select_related('hall', 'room').first()

            payload.append(
                {
                    'student_id': username,
                    'full_name': (student.id.user.get_full_name() or username).strip(),
                    'batch': str(student.batch),
                    'current_hall_id': active_alloc.hall.hall_id if active_alloc else (f"hall{student.hall_no}" if student.hall_no else ''),
                    'current_room': f"{active_alloc.room.block_no}-{active_alloc.room.room_no}" if active_alloc else (student.room_no or ''),
                    'already_allocated': bool(active_alloc),
                }
            )

        return payload


class AllotmentService:
    @staticmethod
    @transaction.atomic
    def bulk_allot_students(*, hall, actor, source='batch', selected_student_ids=None, force_reassign=False):
        if hall.operational_status != 'Active':
            raise WorkflowValidationError('Cannot allot students. Hostel is not active.')

        state = HostelService.sync_lifecycle_state(hall)
        if not state.batch_assigned:
            raise WorkflowValidationError('Cannot allot students before batch assignment.')

        eligible = BatchService.get_eligible_students(hall=hall, source=source)
        eligible_map = {row['student_id']: row for row in eligible}
        if selected_student_ids:
            selected_ids = [str(value).strip() for value in selected_student_ids if str(value).strip()]
        else:
            selected_ids = list(eligible_map.keys())

        if not selected_ids:
            raise WorkflowValidationError('No eligible students found for allotment.')

        students = list(
            Student.objects.filter(id__user__username__in=selected_ids).select_related('id__user')
        )
        student_map = {student.id.user.username: student for student in students}
        missing_students = [student_id for student_id in selected_ids if student_id not in student_map]
        if missing_students:
            raise WorkflowValidationError(
                f"Student records not found for: {', '.join(missing_students)}"
            )

        selected_students = [student_map[student_id] for student_id in selected_ids]
        selected_students_by_pk = {student.pk: student for student in selected_students}

        memberships = list(
            HostelRoomGroupMember.objects.filter(
                group__hall=hall,
                student__in=selected_students,
            ).select_related('group', 'student__id__user')
        )

        existing_group_ids = sorted({membership.group_id for membership in memberships})
        existing_groups = list(
            HostelRoomGroup.objects.filter(id__in=existing_group_ids).prefetch_related('memberships__student__id__user')
        )

        # If selection contains any member of an existing group, include full group members automatically
        # to avoid partial-group failures during bulk room allotment.
        auto_included_student_ids = []
        for group in existing_groups:
            for membership in group.memberships.all():
                student = membership.student
                if student.pk not in selected_students_by_pk:
                    selected_students_by_pk[student.pk] = student
                    auto_included_student_ids.append(student.id.user.username)

        selected_students = list(selected_students_by_pk.values())
        selected_set = {student.pk for student in selected_students}

        grouped_student_ids = set()
        final_groups = []
        for group in existing_groups:
            group_memberships = list(group.memberships.all())
            if len(group_memberships) != 3:
                raise WorkflowValidationError(f'Group {group.id} is invalid. Each group must have exactly 3 members.')

            final_groups.append((group, [membership.student for membership in group_memberships]))
            grouped_student_ids.update(membership.student_id for membership in group_memberships)

        ungrouped_students = [student for student in selected_students if student.pk not in grouped_student_ids]
        if ungrouped_students and len(ungrouped_students) % 3 != 0:
            raise WorkflowValidationError(
                'Ungrouped students count must be divisible by 3 for automatic group creation.'
            )

        random.shuffle(ungrouped_students)
        for index in range(0, len(ungrouped_students), 3):
            chunk = ungrouped_students[index:index + 3]
            if len(chunk) != 3:
                raise WorkflowValidationError('Failed to create complete groups of 3 for ungrouped students.')

            signature = '|'.join(sorted(member.id.user.username.lower() for member in chunk))
            group = HostelRoomGroup.objects.create(
                hall=hall,
                created_by=actor,
                is_auto_generated=True,
                member_signature=signature,
            )
            HostelRoomGroupMember.objects.bulk_create(
                [HostelRoomGroupMember(group=group, student=member) for member in chunk]
            )
            final_groups.append((group, chunk))

            try:
                from notification.views import hostel_notifications

                for member in chunk:
                    hostel_notifications(sender=actor, recipient=member.id.user, type='group_created')
            except Exception:
                pass

        if not final_groups:
            raise WorkflowValidationError('No complete groups available for bulk allotment.')

        student_active_alloc_map = {}
        for _, group_members in final_groups:
            for student in group_members:
                active_alloc = StudentRoomAllocation.objects.filter(
                    student=student,
                    status=RoomAllocationStatus.ACTIVE,
                ).select_related('room').first()
                if active_alloc and not force_reassign:
                    raise WorkflowValidationError(
                        f"Student {student.id.user.username} already has active allocation."
                    )
                student_active_alloc_map[student.pk] = active_alloc

        available_rooms = list(
            HallRoom.objects.select_for_update().filter(
                hall=hall,
                room_occupied=0,
                room_cap__gte=3,
            )
        )
        random.shuffle(available_rooms)

        if len(final_groups) > len(available_rooms):
            raise WorkflowValidationError('Insufficient empty rooms for complete group allotment.')

        assigned = []
        for index, (group, group_members) in enumerate(final_groups):
            target_room = available_rooms[index]

            for student in group_members:
                active_alloc = student_active_alloc_map.get(student.pk)
                if active_alloc:
                    old_room = active_alloc.room
                    if old_room.room_occupied > 0:
                        old_room.room_occupied -= 1
                        old_room.save(update_fields=['room_occupied'])
                    active_alloc.status = RoomAllocationStatus.VACATED
                    active_alloc.vacated_at = timezone.now()
                    active_alloc.save(update_fields=['status', 'vacated_at'])

            target_room.room_occupied = len(group_members)
            target_room.save(update_fields=['room_occupied'])

            hall_no = _hall_number_from_hall_id(hall.hall_id)
            group_member_payload = []
            for student in group_members:
                student.room_no = f"{target_room.block_no}-{target_room.room_no}"
                if hall_no:
                    student.hall_no = hall_no
                student.save(update_fields=['room_no', 'hall_no'])

                StudentRoomAllocation.objects.create(
                    student=student,
                    room=target_room,
                    hall=hall,
                    assigned_by=None,
                    status=RoomAllocationStatus.ACTIVE,
                )

                StudentDetails.objects.update_or_create(
                    id=student.id.user.username,
                    defaults={
                        'first_name': student.id.user.first_name,
                        'last_name': student.id.user.last_name,
                        'programme': student.programme,
                        'batch': str(student.batch),
                        'room_num': student.room_no,
                        'hall_no': str(student.hall_no or ''),
                        'hall_id': hall.hall_id,
                        'specialization': student.specialization,
                    },
                )

                group_member_payload.append(student.id.user.username)

            group.allotted_room = target_room
            group.allotted_at = timezone.now()
            group.save(update_fields=['allotted_room', 'allotted_at'])

            assigned.append(
                {
                    'group_id': group.id,
                    'members': group_member_payload,
                    'room': f"{target_room.block_no}-{target_room.room_no}",
                }
            )

        active_allocations = StudentRoomAllocation.objects.filter(
            hall=hall,
            status=RoomAllocationStatus.ACTIVE,
        )
        hall.number_students = active_allocations.count()
        hall.save(update_fields=['number_students'])

        HostelTransactionHistory.objects.create(
            hall=hall,
            change_type='BulkAllotment',
            previous_value='N/A',
            new_value=f'Allotted {len(assigned)} groups by {actor.username}',
        )

        notifications_sent = False
        try:
            from notification.views import hostel_notifications

            for row in assigned:
                for student_id in row['members']:
                    student_user = Student.objects.get(id__user__username=student_id).id.user
                    hostel_notifications(sender=actor, recipient=student_user, type='room_allotted')

            caretaker = HallCaretaker.objects.filter(hall=hall, is_active=True).select_related('staff__id__user').first()
            if caretaker and caretaker.staff and caretaker.staff.id and caretaker.staff.id.user:
                hostel_notifications(sender=actor, recipient=caretaker.staff.id.user, type='caretaker_bulk_allotment')

            notifications_sent = True
        except Exception:
            notifications_sent = False

        state = HostelService.sync_lifecycle_state(
            hall,
            updated_by=actor,
            note='Bulk allotment completed',
            mark_students_fetched=True,
            mark_notifications=notifications_sent,
        )

        return {
            'hall_id': hall.hall_id,
            'assigned_groups_count': len(assigned),
            'assigned': assigned,
            'skipped': [],
            'auto_included_group_members': auto_included_student_ids,
            'current_step': state.current_step,
            'operational': state.operational,
        }


class InventoryService:
    @staticmethod
    def ensure_hall_is_active(hall):
        if hall.operational_status != 'Active':
            raise WorkflowValidationError('Inventory workflow is available only for active hostels.')


# Aliases retained for architecture readability in module-level usage.
hostelService = HostelService
batchService = BatchService
allotmentService = AllotmentService
inventoryService = InventoryService
