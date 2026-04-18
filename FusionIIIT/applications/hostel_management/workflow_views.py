from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Hall
from . import lifecycle_services


def _require_super_admin(user):
    if lifecycle_services.is_super_admin(user):
        return None
    return Response({'error': 'Only Super Admin can perform this action.'}, status=status.HTTP_403_FORBIDDEN)


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def hostel_workflow_dashboard(request):
    permission_error = _require_super_admin(request.user)
    if permission_error:
        return permission_error

    dashboard = lifecycle_services.HostelService.get_workflow_dashboard()
    return Response({'workflow': dashboard}, status=status.HTTP_200_OK)


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def hostel_workflow_eligible_students(request, hall_id):
    permission_error = _require_super_admin(request.user)
    if permission_error:
        return permission_error

    source = (request.query_params.get('source') or 'batch').strip().lower()
    try:
        hall = Hall.objects.get(hall_id=hall_id)
    except Hall.DoesNotExist:
        return Response({'error': 'Hostel not found.'}, status=status.HTTP_404_NOT_FOUND)

    state = lifecycle_services.HostelService.sync_lifecycle_state(hall)
    if not state.batch_assigned:
        return Response({'error': 'Cannot fetch students before batch assignment.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        students = lifecycle_services.BatchService.get_eligible_students(hall=hall, source=source)
        lifecycle_services.HostelService.sync_lifecycle_state(
            hall,
            updated_by=request.user,
            note='Eligible students fetched',
            mark_students_fetched=True,
        )
    except lifecycle_services.WorkflowValidationError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    return Response(
        {
            'hall_id': hall.hall_id,
            'source': source,
            'eligible_students': students,
            'count': len(students),
        },
        status=status.HTTP_200_OK,
    )


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def hostel_workflow_bulk_allot(request, hall_id):
    permission_error = _require_super_admin(request.user)
    if permission_error:
        return permission_error

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

    return Response(
        {
            'message': 'Bulk room allotment completed.',
            'result': result,
        },
        status=status.HTTP_200_OK,
    )
