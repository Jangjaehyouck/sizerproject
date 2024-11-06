from django.db import models
from django.contrib.auth.models import User

class UploadedFile(models.Model):
    file = models.FileField(upload_to='upload_file_folder/')
    data_process = models.IntegerField(default=0)
    create_user = models.CharField(max_length=100, default='admin')
    sizer_id = models.CharField(max_length=100, default='')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    workstatus = models.CharField(max_length=100, default='')
    progress = models.IntegerField(default=0)

class excel_item(models.Model):
    sizerID = models.CharField(max_length=100)
    workload_name = models.CharField(max_length=100)
    cluster_name = models.CharField(max_length=100)
    vm_qty = models.IntegerField()
    vCpu = models.IntegerField()
    vcpu_pcore = models.IntegerField()
    memory = models.IntegerField()
    disk = models.IntegerField()
    upload_file_id = models.IntegerField(default=3)
    api_insert = models.CharField(max_length=100, default='')

class task_table(models.Model):
    taskuser = models.CharField(max_length=100)
    sizerID = models.CharField(max_length=100)
    workload_name = models.CharField(max_length=100)
    cluster_name = models.CharField(max_length=100)
    workstatus = models.CharField(max_length=100, default='')
    progress = models.IntegerField(default=0)
    taskdate_at = models.DateTimeField(auto_now_add=True)
    upload_file_id = models.IntegerField(default=3)