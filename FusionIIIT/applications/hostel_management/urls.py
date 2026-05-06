from django.urls import path
from . import views
from .api import views as api_views
from django.contrib.auth import views as auth_views
from django.urls import include
from django.contrib import admin
from django.conf.urls import url, include

app_name = 'hostelmanagement'

urlpatterns = [

    path('admin/', admin.site.urls),
    #Home 
    path('', views.hostel_view, name="hostel_view"),
    path('hello', views.hostel_view, name="hello"),

    #Notice Board
    path('notice_form/', views.notice_board, name="notice_board"),
    path('delete_notice/', views.delete_notice, name="delete_notice"),

    #Worker Schedule
    path('edit_schedule/', views.staff_edit_schedule, name='staff_edit_schedule'),
    path('delete_schedule/', views.staff_delete_schedule, name='staff_delete_schedule'),
    
    #Student Room
    path('edit_student/',views.edit_student_room,name="edit_student_room"),
    path('edit_student_rooms_sheet/', views.edit_student_rooms_sheet, name="edit_student_rooms_sheet"),

    #Attendance
    path('edit_attendance/', views.edit_attendance, name='edit_attendance'),

    #Attendance
    path('edit_attendance/', views.edit_attendance, name='edit_attendance'),

    #Worker Report
    path('worker_report/', views.generate_worker_report, name='workerreport'),
    path('pdf/', views.GeneratePDF.as_view(), name="pdf"),



    #for superUser

    path('hostel-notices/', views.getNoticesController, name='hostel_notices_board'),
    path('notices/', views.noticeBoardController, name='notice_board_api'),
    path('create_notice/', views.createNoticeController, name='create_notice_api'),
    path('student/notices/', views.student_notice_board, name='student_notice_board'),
    # Batch management APIs (HM-UC-NEW-017)
    path('get_batches/', views.get_batches, name='get_batches'),
    path('batch-assign/', api_views.assign_batch, name='batch_assign'),
    path('workflow/dashboard/', views.hostel_workflow_dashboard, name='hostel_workflow_dashboard'),
    path('workflow/<str:hall_id>/eligible-students/', views.hostel_workflow_eligible_students, name='hostel_workflow_eligible_students'),
    path('workflow/<str:hall_id>/bulk-allot/', views.hostel_workflow_bulk_allot, name='hostel_workflow_bulk_allot'),
    # Staffing management APIs (UC-021, UC-022)
    path('get_caretakers/', views.get_caretakers, name='get_caretakers'),
    path('assign_caretakers/', views.assign_caretakers, name='assign_caretakers'),
    path('get_wardens/', views.get_wardens, name='get_wardens'),
    path('assign_warden/', views.assign_warden, name='assign_warden'),
    path('get_guards/', views.get_guards, name='get_guards'),
    # Leave management APIs (new)
    path('leave/apply/', views.submitLeaveRequestController, name='submit_leave_request'),
    path('leave/my-requests/', views.getStudentLeavesController, name='get_student_leave_requests'),
    path('leave/pending/', views.getPendingLeavesController, name='get_pending_leave_requests'),
    path('leave/update-status/', views.updateLeaveStatusController, name='update_leave_status_controller'),
    # Student allotment APIs (new)
    path('students/search/', views.searchStudentsController, name='search_students_controller'),
    path('students/<str:student_id>/', views.getStudentController, name='get_student_controller'),
    path('rooms/assign/', views.assignRoomController, name='assign_room_controller'),
    path('rooms/my-room/', views.getStudentRoomController, name='get_student_room_controller'),
    # ERP modular aliases
    path('student/group/', views.createStudentGroupController, name='student_group_controller'),
    path('student/room-details/', views.getStudentRoomController, name='student_room_details_controller'),
    path('admin/bulk-allot/', views.adminBulkAllotRoomsController, name='admin_bulk_allot_controller'),
    # Room change request APIs (UC-013, UC-014, UC-015)
    path('room-change/requests/submit/', views.submitRoomChangeRequestController, name='submit_room_change_request'),
    path('room-change/requests/my/', views.myRoomChangeRequestsController, name='my_room_change_requests'),
    path('room-change/requests/review/', views.roomChangeRequestsForReviewController, name='room_change_requests_review'),
    path('room-change/requests/<int:request_id>/caretaker-decision/', views.caretakerRoomChangeDecisionController, name='caretaker_room_change_decision'),
    path('room-change/requests/<int:request_id>/warden-decision/', views.wardenRoomChangeDecisionController, name='warden_room_change_decision'),
    path('room-change/requests/<int:request_id>/allocate/', views.allocateRoomChangeRequestController, name='allocate_room_change_request'),
    path('room-change/approve/', views.approveRoomChangeRequestController, name='approve_room_change_request'),
    path('room-change/reject/', views.rejectRoomChangeRequestController, name='reject_room_change_request'),
    # Extended stay management APIs (UC-038, UC-039)
    path('extended-stay/requests/submit/', views.submitExtendedStayRequestController, name='submit_extended_stay_request'),
    path('extended-stay/requests/my/', views.myExtendedStayRequestsController, name='my_extended_stay_requests'),
    path('extended-stay/requests/<int:request_id>/modify/', views.modifyExtendedStayRequestController, name='modify_extended_stay_request'),
    path('extended-stay/requests/<int:request_id>/cancel/', views.cancelExtendedStayRequestController, name='cancel_extended_stay_request'),
    path('extended-stay/requests/review/', views.extendedStayRequestsForReviewController, name='extended_stay_requests_review'),
    path('extended-stay/requests/<int:request_id>/caretaker-decision/', views.caretakerExtendedStayDecisionController, name='caretaker_extended_stay_decision'),
    path('extended-stay/requests/<int:request_id>/warden-decision/', views.wardenExtendedStayDecisionController, name='warden_extended_stay_decision'),
    # Room vacation APIs (UC-029, UC-030, UC-031)
    path('room-vacation/checklist/generate/', views.generateRoomVacationChecklistController, name='generate_room_vacation_checklist'),
    path('room-vacation/requests/submit/', views.submitRoomVacationRequestController, name='submit_room_vacation_request'),
    path('room-vacation/requests/my/', views.myRoomVacationRequestsController, name='my_room_vacation_requests'),
    path('room-vacation/requests/clearance/', views.roomVacationRequestsForClearanceController, name='room_vacation_requests_clearance'),
    path('room-vacation/requests/<int:request_id>/clearance/verify/', views.caretakerVerifyRoomVacationController, name='caretaker_verify_room_vacation'),
    path('room-vacation/requests/finalization/', views.roomVacationRequestsForFinalizationController, name='room_vacation_requests_finalization'),
    path('room-vacation/requests/<int:request_id>/finalize/', views.finalizeRoomVacationController, name='finalize_room_vacation'),
    # Report generation/submission/review APIs (UC-034, UC-035)
    path('reports/generate/', views.generateHostelReportController, name='generate_hostel_report'),
    path('reports/my/', views.myHostelReportsController, name='my_hostel_reports'),
    path('reports/templates/', views.reportFilterTemplatesController, name='report_filter_templates'),
    path('reports/<int:report_id>/submit/', views.submitHostelReportController, name='submit_hostel_report'),
    path('reports/submitted/', views.submittedHostelReportsController, name='submitted_hostel_reports'),
    path('reports/<int:report_id>/', views.hostelReportDetailController, name='hostel_report_detail'),
    path('reports/<int:report_id>/review/', views.reviewHostelReportController, name='review_hostel_report'),
    path('reports/<int:report_id>/download/', views.downloadHostelReportController, name='download_hostel_report'),
    # Inventory management APIs (UC-026, UC-027, UC-028)
    path('inventory/dashboard/', views.inventoryDashboardController, name='inventory_dashboard'),
    path('inventory/inspections/submit/', views.submitInventoryInspectionController, name='inventory_inspection_submit'),
    path('inventory/inspections/', views.inventoryInspectionsController, name='inventory_inspections'),
    path('inventory/resource-requests/submit/', views.submitResourceRequirementRequestController, name='inventory_resource_request_submit'),
    path('inventory/resource-requests/', views.resourceRequirementRequestsController, name='inventory_resource_requests'),
    path('inventory/resource-requests/<int:request_id>/review/', views.reviewResourceRequirementRequestController, name='inventory_resource_request_review'),
    path('inventory/items/<int:inventory_id>/update/', views.updateInventoryRecordController, name='inventory_item_update'),
    path('inventory/update-logs/', views.inventoryUpdateLogsController, name='inventory_update_logs'),
    # Guard duty management APIs (UC-024, UC-025)
    path('guard-duties/schedules/', views.guardDutySchedulesController, name='guard_duty_schedules'),
    path('guard-duties/schedules/<int:schedule_id>/', views.guardDutyScheduleDetailController, name='guard_duty_schedule_detail'),
    path('guard-duties/concerns/', views.guardDutyConcernsController, name='guard_duty_concerns'),
    path('guard-duties/concerns/<int:concern_id>/resolve/', views.resolveGuardDutyConcernController, name='resolve_guard_duty_concern'),
    # Student allotment compatibility aliases for current frontend
    path('students_get_students_info/', views.searchStudentsController, name='students_get_students_info_alias'),
    path('caretaker_get_students_info/', views.searchStudentsController, name='caretaker_get_students_info_alias'),
    # Fine management APIs (new)
    path('fines/impose/', views.imposeFineController, name='impose_fine_controller'),
    path('fines/hostel/', views.getHostelFinesController, name='get_hostel_fines_controller'),
    path('fines/my-fines/', views.getStudentFinesController, name='get_student_fines_controller'),
    # Attendance submission APIs (new)
    path('attendance/students', views.getStudentsForAttendanceController, name='attendance_students'),
    path('attendance/students/', views.getStudentsForAttendanceController, name='attendance_students_slash'),
    path('attendance/submit', views.submitAttendanceController, name='attendance_submit'),
    path('attendance/submit/', views.submitAttendanceController, name='attendance_submit_slash'),
    path('attendance/my-attendance', views.getStudentAttendanceController, name='attendance_my_attendance'),
    path('attendance/my-attendance/', views.getStudentAttendanceController, name='attendance_my_attendance_slash'),
    # Complaint management APIs (new)
    path('complaints/submit', views.submitComplaintController, name='submit_complaint'),
    path('complaints/submit/', views.submitComplaintController, name='submit_complaint_slash'),
    path('complaints/my', views.getStudentComplaintsController, name='get_student_complaints'),
    path('complaints/my/', views.getStudentComplaintsController, name='get_student_complaints_slash'),
    path('complaints/hostel', views.getHostelComplaintsController, name='get_hostel_complaints'),
    path('complaints/hostel/', views.getHostelComplaintsController, name='get_hostel_complaints_slash'),
    path('complaints/update-status', views.updateComplaintStatusController, name='update_complaint_status'),
    path('complaints/update-status/', views.updateComplaintStatusController, name='update_complaint_status_slash'),
    path('complaints/escalate', views.escalateComplaintController, name='escalate_complaint'),
    path('complaints/escalate/', views.escalateComplaintController, name='escalate_complaint_slash'),
    # Warden complaint management APIs
    path('complaints/warden/escalated', views.getEscalatedComplaintsController, name='get_escalated_complaints'),
    path('complaints/warden/escalated/', views.getEscalatedComplaintsController, name='get_escalated_complaints_slash'),
    path('complaints/warden/all', views.getAllComplaintsForWardenController, name='get_all_complaints_for_warden'),
    path('complaints/warden/all/', views.getAllComplaintsForWardenController, name='get_all_complaints_for_warden_slash'),
    path('complaints/warden/resolve', views.resolveComplaintController, name='resolve_complaint'),
    path('complaints/warden/resolve/', views.resolveComplaintController, name='resolve_complaint_slash'),
    path('complaints/warden/reassign', views.reassignComplaintController, name='reassign_complaint'),
    path('complaints/warden/reassign/', views.reassignComplaintController, name='reassign_complaint_slash'),
    # Fine management APIs (frontend compatibility aliases)
    path('impose-fine/', views.imposeFineController, name='impose_fine_alias'),
    path('fetch-fine/', views.getHostelFinesController, name='fetch_fine_alias'),
    path('update-fine-status/<int:fine_id>/', views.updateFineStatusController, name='update_fine_status_alias'),
    # Caretaker student search API used by fine UI
    path('caretaker_get_students_info/', views.getCaretakerStudentsController, name='caretaker_get_students_info'),
    # Leave management APIs (legacy aliases kept for current frontend)
    path('all_leave_data/', views.all_leave_data, name='all_leave_data'),
    path('update_leave_status/', views.updateLeaveStatusController, name='update_leave_status'),
    path('create_hostel_leave/', views.create_hostel_leave, name='create_hostel_leave'),
    
    # caretaker and warden can get all complaints
    path('hostel_complaints/', views.hostel_complaint_list, name='hostel_complaint_list'),

    path('register_complaint/', views.PostComplaint.as_view(), name='PostComplaint'),

#  Student can view his leave status
    path('my_leaves/', views.getStudentLeavesController, name='my_leaves'),
    path('get_students/', views.get_students, name='get_students'),





    path('assign-batch/', views.AssignBatchView.as_view(),name='AssignBatchView'),
    path('hall-ids/', views.HallIdView.as_view(), name='hall'),
    path('assign-caretaker', views.AssignCaretakerView.as_view(), name='AssignCaretakerView'),
    path('assign-warden',views.AssignWardenView.as_view(), name='AssignWardenView'),
    path('add-hostel', views.AddHostelView.as_view(), name='add_hostel'),
    path('add-hostel/', views.AddHostelView.as_view(), name='add_hostel_slash'),
    path('admin-hostel-list', views.AdminHostelListView.as_view(), name='admin_hostel_list'),  # URL for displaying the list of hostels
    path('admin-hostel-list/', views.AdminHostelListView.as_view(), name='admin_hostel_list_slash'),
    path('hostel-status/manage/', views.ManageHostelStatusView.as_view(), name='manage_hostel_status'),
    path('delete-hostel/<str:hall_id>/', views.DeleteHostelView.as_view(), name='delete_hostel'),
  
    path('check-hall-exists/', views.CheckHallExistsView.as_view(), name='check_hall_exists'),
    path('accounts/', include('django.contrib.auth.urls')),
    path('logout/', views.logout_view, name='logout_view'),
    # path('logout/', auth_views.LogoutView.as_view(), name='logout'),
  
    # !! My Change
    path('allotted_rooms/<str:hall_id>/', views.alloted_rooms, name="alloted_rooms"),

    path('all_staff/<int:hall_id>/', views.all_staff, name='all_staff'),
    path('staff/<str:staff_id>/', views.StaffScheduleView.as_view(), name='staff_schedule'),
    
    # !!? Inventory
    path('inventory/', views.HostelInventoryView.as_view(), name='hostel_inventory_list'),
    path('inventory/<int:inventory_id>/modify/', views.HostelInventoryUpdateView.as_view(), name='hostel_inventory_update'),
    path('inventory/<int:inventory_id>/delete/', views.HostelInventoryView.as_view(), name='hostel_inventory_delete'),
    path('inventory/<int:hall_id>/', views.HostelInventoryView.as_view(), name='hostel_inventory_by_hall'),
    path('inventory/form/', views.get_inventory_form, name='get_inventory_form'),
    path('inventory/edit_inventory/<int:inventory_id>/', views.edit_inventory, name='edit_inventory'),
    path('allotted_rooms/', views.alloted_rooms_main, name="alloted_rooms"),
    path('all_staff/', views.all_staff, name='all_staff'),

    #guest room
    path('book_guest_room/', views.request_guest_room, name="book_guest_room"),
    path('update_guest_room/', views.update_guest_room, name="update_guest_room"),
    path('available_guest_rooms/', views.available_guestrooms_api, name='available_guestrooms_api'),
    # Guest room booking lifecycle APIs (UC-036, UC-037)
    path('guest-room/availability/', views.checkGuestRoomAvailabilityController, name='guest_room_availability'),
    path('guest-room/bookings/request/', views.submitGuestRoomBookingController, name='guest_room_booking_request'),
    path('guest-room/bookings/my/', views.myGuestRoomBookingsController, name='guest_room_booking_my'),
    path('guest-room/bookings/<int:booking_id>/', views.guestRoomBookingDetailController, name='guest_room_booking_detail'),
    path('guest-room/bookings/<int:booking_id>/modify/', views.modifyGuestRoomBookingController, name='guest_room_booking_modify'),
    path('guest-room/bookings/<int:booking_id>/cancel/', views.cancelGuestRoomBookingController, name='guest_room_booking_cancel'),
    path('guest-room/caretaker/pending/', views.caretakerPendingGuestBookingsController, name='guest_room_caretaker_pending'),
    path('guest-room/caretaker/<int:booking_id>/decision/', views.caretakerDecideGuestBookingController, name='guest_room_caretaker_decision'),
    path('guest-room/caretaker/<int:booking_id>/check-in/', views.caretakerCheckInGuestBookingController, name='guest_room_caretaker_checkin'),
    path('guest-room/caretaker/<int:booking_id>/check-out/', views.caretakerCheckOutGuestBookingController, name='guest_room_caretaker_checkout'),
    path('guest-room/caretaker/settings/', views.guestRoomPolicyController, name='guest_room_caretaker_settings'),
    path('guest-room/caretaker/report/', views.guestRoomBookingReportController, name='guest_room_caretaker_report'),


    # !!todo: Add Fine Functionality
    path('fine/', views.impose_fine_view, name='fine_form_show'),
    path('fine/impose/', views.HostelFineView.as_view(), name='fine_form_show'),
    path('fine/impose/list/', views.hostel_fine_list, name='fine_list_show'),
    path('fine/impose/edit/<int:fine_id>/', views.show_fine_edit_form, name='hostel_fine_edit'),
    path('fine/impose/update/<int:fine_id>/', views.update_student_fine, name='update_student_fine'),
    path('fine/impose/list/update/<int:fine_id>/', views.HostelFineUpdateView.as_view(), name='fine_update'),
    path('fine/delete/<int:fine_id>/', views.HostelFineUpdateView.as_view(), name='fine_delete'),
    path('fine/show/', views.student_fine_details, name='fine_show'),
    
    
    
    path('student/<str:username>/name/', views.get_student_name, name='find_name'),

    
    path('edit-student/<str:student_id>/', views.EditStudentView.as_view(), name='edit_student'),
    path('remove-student/<str:student_id>/', views.RemoveStudentView.as_view(), name='remove-student'),
    
     
]