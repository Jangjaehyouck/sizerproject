from django.contrib import admin
from .models import UploadedFile, excel_item, task_table
# Register your models here.

admin.site.register(UploadedFile)
admin.site.register(excel_item)
admin.site.register(task_table)