from django.urls import path
from . import views
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
    path('admin-hostel-list', views.AdminHostelListView.as_view(), name='admin_hostel_list'),  # URL for displaying the list of hostels
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