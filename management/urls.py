

from django.urls import path

from . import views

urlpatterns = [
    path('assigned-tasks/', views.assigned_tasks_view, name='assigned_tasks'),
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
    path('worksheet/', views.worksheet_view, name='worksheet'),
    path('worksheet/edit/<int:entry_id>/', views.worksheet_entry_edit_view, name='worksheet-edit'),
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

    # Admin print event logging endpoint
    path('admin/auditlog/print-event/', views.admin_print_event, name='admin_print_event'),
]

