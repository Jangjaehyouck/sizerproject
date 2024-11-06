from django.urls import path

from . import views

app_name = "sizer"

urlpatterns = [
    path('index', views.index, name='index'),
    path('upload/', views.upload_file, name='upload_file'),
    path("upload_list/", views.upload_list, name='upload_list'),
    path('upload_list/<int:uplist_id>/', views.excel_to_html),
    path('upload_list/upload_file_folder/<str:filename>/', views.download_file),
    path('sampledown/', views.sample_download_file, name='sampledown'),
    path('upload_list/delete_upload_list/', views.delete_upload_list, name='delete_upload_file'),
    path('save_html_table/', views.save_html_table, name='save_html_table'),
    path('request_sizer/', views.request_sizer, name='request_sizer'),
    path('add_workload/', views.add_workload, name='add_workload'),
    path('manual/', views.manual, name='manual'),
    path('add_workload/progress_status/', views.progress_status, name='progress_status'),
    path('tasklist/', views.tasklist, name='tasklist'),
    path('tasklist/<int:task_id>/', views.task_detail_list),
    path('tasklist/<int:task_id>/retasklist/', views.retasklist, name='retasklist'),
]