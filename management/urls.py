from django.urls import path

from . import views

urlpatterns = [
    path('assigned-tasks/', views.assigned_tasks_view, name='assigned_tasks'),
        # Admin: Leave Management Report
        path('admin/leave-management/', views.admin_leave_management, name='admin_leave_management'),
    path('assigned-tasks/self/', views.assign_task_to_self, name='assign_task_to_self'),
    path('', views.employee_login, name='login'),
    path('employee/dashboard/', views.employee_dashboard, name='employee_dashboard'),
    path('employee/attendance/', views.attendance_view, name='attendance'),
    path('logout/', views.logout_view, name='logout'),
    path('create-invoice/', views.create_invoice, name='create_invoice'),
    path('invoice/<int:pk>/', views.invoice_detail, name='invoice_detail'),
    path('links/', views.assigned_links_view, name='assigned_links'),
    path('applications/', views.application_list_create_view, name='applications'),
    path('applications/<int:pk>/', views.application_detail_view, name='application-detail'),
    path('employee/attendance_ping/', views.attendance_ping, name='attendance_ping'),
    path('employee/refresh_session/', views.refresh_session, name='refresh_session'),
    path('employee/next-day-availability/', views.submit_next_day_availability, name='submit_next_day_availability'),
    path('employee/todays-absentees/', views.todays_absentees_view, name='todays_absentees'),
    path('employee/upi-qr/', views.employee_upi_qr_view, name='employee_upi_qr'),
    path('worksheet/', views.worksheet_view, name='worksheet'),
    path('worksheet/edit/<int:entry_id>/', views.worksheet_entry_edit_view, name='worksheet-edit'),
    path('admin/worksheet-management/', views.admin_worksheet_management, name='admin_worksheet_management'),
    path('admin/worksheet-management/print/<int:employee_id>/<str:time_range>/', views.admin_employee_daily_worksheet_pdf, name='admin_employee_daily_worksheet_pdf'),
    path('admin/worksheet-management/commission/<int:employee_id>/<str:period>/', views.admin_employee_commission_print, name='admin_employee_commission_print'),
    path('admin/targets/', views.admin_employee_targets, name='admin_employee_targets'),
    path('admin/worksheet-data/', views.admin_worksheet_data, name='admin_worksheet_data'),
    path('notifications/', views.notification_list_view, name='notification_list'),
    path('notifications/mark-as-read/<int:pk>/', views.mark_notification_as_read, name='mark_notification_as_read'),
    path('change-password/', views.change_password_request, name='change_password_request'),
    path('change-password/verify/', views.change_password_verify, name='change_password_verify'),
    path('upload-file/', views.upload_file_view, name='upload_file'),
    path('todos/', views.todo_page_view, name='todo_page'),
    path('api/todos/get/', views.get_employee_todos, name='todos_get'),
    path('api/todos/add/', views.add_employee_todo, name='todos_add'),
    path('api/todos/delete/<int:task_id>/', views.delete_employee_todo, name='todos_delete'),
    path('api/geofence_check/', views.geofence_check, name='geofence_check'),


    # Department Head: Top Up Page (renamed)
    path('employee/topup/', views.department_topup_view, name='department_topup'),

    # Admin Dashboard
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin-dashboard/ttd/', views.admin_ttd_view, name='admin_ttd_view'),
    path('admin-dashboard/ttd/group/<int:group_id>/print/', views.admin_ttd_group_print, name='admin_ttd_group_print'),
    path('admin-dashboard/ttd/individual/<int:darshan_id>/print/', views.admin_ttd_individual_print, name='admin_ttd_individual_print'),
    path('admin-dashboard/ttd/print-all/', views.admin_ttd_print_all, name='admin_ttd_print_all'),

    # Admin print event logging endpoint
    path('admin/auditlog/print-event/', views.admin_print_event, name='admin_print_event'),

    # TTD Section
    path('ttd/', views.ttd_main_view, name='ttd_main'),
    path('ttd/group-seva/new/', views.ttd_group_seva_step1, name='ttd_group_seva_step1'),
    path('ttd/group-seva/<int:group_id>/members/', views.ttd_group_seva_step2, name='ttd_group_seva_step2'),
    path('ttd/individual-darshan/new/', views.ttd_individual_darshan_create, name='ttd_individual_darshan_create'),
    path('ttd/group-seva/<int:group_id>/delete/', views.ttd_group_seva_delete, name='ttd_group_seva_delete'),
    path('ttd/individual-darshan/<int:darshan_id>/delete/', views.ttd_individual_darshan_delete, name='ttd_individual_darshan_delete'),
    path('ttd/group-seva/<int:group_id>/print/', views.ttd_group_seva_print, name='ttd_group_seva_print'),
    path('ttd/individual-darshan/<int:darshan_id>/print/', views.ttd_individual_darshan_print, name='ttd_individual_darshan_print'),
    path('ttd/print-all/', views.ttd_print_all, name='ttd_print_all'),

    # Admin: Employees Section
    path('admin-dashboard/employees/', views.admin_employees, name='admin_employees'),

    # Admin: Departments Section
    path('admin-dashboard/departments/', views.admin_departments, name='admin_departments'),
]

