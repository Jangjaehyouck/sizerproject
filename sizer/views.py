from django.shortcuts import render, redirect
from django.http import JsonResponse
from .models import UploadedFile, excel_item, task_table
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseRedirect
from zipfile import BadZipFile
from django.core.paginator import Paginator
from time import sleep
from django.utils.http import urlquote

import aiohttp
import threading
import asyncio
import os
import pandas as pds
import json, requests

@login_required
def manual(request):
    return render(request, 'sizer/manual.html')

def index(request):
    return render(request, 'sizer/main.html')

def upload_file(request):
    if request.method == 'POST' and request.FILES['file']:
        uploaded_file = UploadedFile(
            file=request.FILES['file'],
            data_process=0,
            create_user=request.user
        )
        uploaded_file.save()
        return JsonResponse({'message': 'File uploaded successfully!'})
    return JsonResponse({'message': 'File upload failed.'}, status=400)

def upload_success(request):
    return render(request, 'success.html')

def upload_list(request):

    check_file = request.session.get('check_File_Error')

    if 'check_File_Error' not in request.session:
        check_file = ''
    request.session['check_File_Error'] = ''

    if not request.user.is_authenticated:
        return render(request, 'common/login.html')
    
    curuser = request.user
    uplist = UploadedFile.objects.filter(create_user=curuser).order_by('-uploaded_at')
    page = request.GET.get('page', '1')  # 페이지
    paginator = Paginator(uplist, 11)  # 페이지당 10개씩 보여주기
    page_obj = paginator.get_page(page)

    context = {'uplist':page_obj, 'cru_User':curuser, 'check': check_file}

    return render(request, 'sizer/sizerlist.html', context)

def delete_upload_list(request):
    if request.method == 'POST':
        del_ids = request.POST.get('ids')
        del_ids = json.loads(del_ids)
        
        for delid in del_ids:
            upfile = UploadedFile.objects.get(id=delid)
            del_file = upfile.file.path
            UploadedFile.objects.get(id=delid).delete()
            excel_item.objects.filter(upload_file_id=delid).delete()
            task_table.objects.filter(upload_file_id=delid).delete()
             
            if os.path.exists(del_file):
                os.remove(del_file)
            else:
                pass

        return JsonResponse({'message': 'Deletes successfully!'})

def detail(request, uplist_id):
    uplistid = UploadedFile.objects.get(id=uplist_id)
    context = {'uplist': uplistid}
    return render(request, 'sizer/sizerlist_detail.html', context)

def excel_to_html(request, uplist_id):

    check_api = request.session.get('check_api')
    request.session['check_api'] = ''

    uplistid = UploadedFile.objects.get(id=uplist_id)

    if uplistid.workstatus != '작업진행 중':
        context = {'uplist': uplistid}
        # Excel 파일 경로
        filepath = uplistid.file
        excel_file = filepath
        data_pro = uplistid.data_process
        uniqueid = uplistid.id
        # Excel 파일을 DataFrame으로 읽기
        try:
            request.session['check_File_Error'] = ''
            df = pds.read_excel(excel_file, engine='openpyxl', dtype={'SizerID': str,'VM Qty': str,'vCPU': str,'vCpu:pCore': str,'Memory': str,'Disk': str})

            columns_to_drop = [col for col in df.columns if 'Unnamed' in col]
            df = df.drop(columns=columns_to_drop)
            # DataFrame을 HTML 표로 변환

            checknull = df[df.isna().all(axis=1)]

            if not checknull.empty:
                nan_start_row_index = df[df.isna().all(axis=1)].index[0]
                df = df.iloc[:nan_start_row_index]

            total_cnt = df.shape[0]
            total_vm_count = df['VM Qty'].astype(int).sum()
            total_cpu_count = df['vCPU'].astype(int).sum()
            total_pcore_count = df['vCpu:pCore'].astype(int).mean()
            total_mem_count = df['Memory'].astype(int).sum()
            total_disk_count = df['Disk'].astype(int).sum()
            
            # 새로운 행을 추가할 데이터
            new_row_data = {
                'SizerID': 'Total',
                'Workload Name': '',
                'CLusterName': '',
                'VM Qty': total_vm_count,
                'vCPU': total_cpu_count,
                'vCpu:pCore': total_pcore_count,
                'Memory': total_mem_count,
                'Disk': total_disk_count
            }

            # DataFrame에 새로운 행 추가
            df = df.append(new_row_data, ignore_index=True)
            html_table = df.to_html(index=False, classes='table table-striped table-bordered table-hover')
            
            # 템플릿으로 전달할 context
            context = {'html_table': html_table, 'total_cnt': total_cnt, 'datapro': data_pro, 'uniqueid': uniqueid, 'check': check_api}
            
            # 템플릿 렌더링 및 반환
            return render(request, 'sizer/sizerlist_detail.html', context)

        except BadZipFile as e:
            errordata = UploadedFile.objects.get(id=uplist_id)
            if errordata.data_process != 2:
                errordata.data_process = 2
                errordata.save()

            request.session['check_File_Error'] = 'DRM'
            check_file = request.session.get('check_File_Error')
            return redirect('sizer:upload_list')
            #return JsonResponse({'error': 'The contents of the file are unreadable due to corporate DRM.','Message': 'Please disable DRM security on the document and try again.'}, status=500)

        except IndexError as e:
            errordata = UploadedFile.objects.get(id=uplist_id)
            if errordata.data_process != 2:
                errordata.data_process = 2
                errordata.save()

            request.session['check_File_Error'] = 'Empty'
            return redirect('sizer:upload_list')
            #return JsonResponse({'error': 'This is an empty file.','Message': 'Please enter data in the correct format.'}, status=500)
    else:
        return redirect('sizer:add_workload')

def save_html_table(request):
    if request.method == 'POST':
        html_table = request.POST.get('html_table', '')
        request_id = int(request.POST.get('uniqueid'))
        df = pds.read_html(html_table)[0]
        df = df[df['SizerID'] != 'Total']
        sizerid_dfrow = df['SizerID'][0]

        for index, row in df.iterrows():
            save_excel_item = excel_item(
                sizerID=row['SizerID'],
                workload_name=row['Workload Name'],
                cluster_name=row['CLusterName'],
                vm_qty=row['VM Qty'],
                vCpu=row['vCPU'],
                vcpu_pcore=row['vCpu:pCore'],
                memory=row['Memory'],
                disk=row['Disk'],
                upload_file_id=request_id
            )

            save_excel_item.save()

        uploadfile_update = UploadedFile.objects.get(id=request_id)
        uploadfile_update.data_process = 1
        uploadfile_update.sizer_id = sizerid_dfrow
        uploadfile_update.save()

        return redirect('sizer:upload_list')

def request_sizer(request):
    if request.method == 'POST':
        save_dataid = request.POST.get('uniqueid')
        cookies_value = request.POST.get('cookies_val')
        uploadfile_update = UploadedFile.objects.get(id=save_dataid)
        Cur_Sizer_ID = uploadfile_update.sizer_id

        url = "https://sizer.nutanix.com/v3/scenarios/"+ Cur_Sizer_ID

        headers = {
            'Accept': 'application/json;charset=UTF-8',
            'cookie': cookies_value,
            'Content-Type': 'application/json;charset=UTF-8'
        }

        response = requests.get(url, headers=headers, verify=False)
        
        task_status = task_table.objects.filter(upload_file_id=save_dataid, workstatus='R').count()
        print(task_status)

        if response.status_code == 200:

            request.session['seesion_uid'] = save_dataid
            request.session['sec_cook'] = cookies_value

            if task_status == 0:
                curuser = request.user
                task_table_item = task_table(
                    taskuser = curuser,
                    sizerID = Cur_Sizer_ID,
                    workload_name = '',
                    cluster_name = '',
                    workstatus = 'R',
                    progress = 0,
                    upload_file_id = save_dataid
                )

                task_table_item.save()

            return redirect('sizer:add_workload')
        else :
            return JsonResponse({'message': 'Error'}, status=400)

thread = ''
check_firsttask = 0

def add_workload(request):
    curuser = request.user
    unique_id = request.session.get('seesion_uid')
    cookies_value = request.session.get('sec_cook')
    uploadfile_update = UploadedFile.objects.get(id=unique_id)
    
    task_running_status = task_table.objects.filter(upload_file_id=unique_id, workstatus='R', taskuser=curuser).count()
    
    if task_running_status == 1:
        tast_update = task_table.objects.get(upload_file_id=unique_id, workstatus='R', taskuser=curuser)
        uploadfile_update.workstatus = '작업진행 중'
        uploadfile_update.save()
        thread = threading.Thread(target=ThreadsAPI_func, args=(unique_id, cookies_value))
        thread.start()
        tast_update.workstatus = 'I'
        tast_update.save()

        print("이거봐봐라",unique_id)

    context = {'uplist': '123'}
    return render(request, 'sizer/request_data.html', context)

def ThreadsAPI_func(unique_id, cookies_value):

    uploadfile_update = UploadedFile.objects.get(id=unique_id)
    Cur_Sizer_ID = uploadfile_update.sizer_id
    
    url = "https://sizer.nutanix.com/v1/design/"+ Cur_Sizer_ID +"/workloads"

    headers = {
        'Accept': 'application/json;charset=UTF-8',
        'cookie': cookies_value,
        'Content-Type': 'application/json;charset=UTF-8'
    }

    row_item = excel_item.objects.filter(upload_file_id=unique_id)
    all_cnt = row_item.count()
    task_progress = 0

    for itemname in row_item:
        task_progress += 1
        print(itemname.workload_name)

        sizerID = itemname.sizerID
        workload_name = itemname.workload_name
        cluster_name = itemname.cluster_name
        vm_qty = itemname.vm_qty
        vCpu = itemname.vCpu
        vcpu_pcore = itemname.vcpu_pcore
        memory = itemname.memory
        disk = itemname.disk
        cold_disk = round((90 / 100) * disk)
        hot_disk = round((10 / 100) * disk)

        create_Json = ''
        create_Json += '{"data":{"containerRF":2,"compression":{"enabledForAF":true,"enabledForHybrid":true,"containerCompression":30,"preCompressed":true},"erasureCoding":false,"targetCluster":"Yes","targetClusterName":"'
        create_Json += str(cluster_name)
        create_Json += '","encryptedStorage":{"hardwareEncryption":false,"softwareEncryption":false},"dedupe":0,"dedicatedWorkloadCluster":false,"workloadName":"'
        create_Json += str(workload_name)
        create_Json += '","type":"serverVirtualization","serverProfileType":"Large","numberOfVMs":'
        create_Json += str(vm_qty)
        create_Json += ',"sizeByMhz":false,"workloadId":0,"manageVMsUsingCalm":false,"disabled":false,"corePerVm":'
        create_Json += str(vCpu)
        create_Json += ',"vCPUsPerCore":'
        create_Json += str(vcpu_pcore)
        create_Json += ',"RAM":'
        create_Json += str(memory)
        create_Json += ',"coldData":'
        create_Json += str(cold_disk)
        create_Json += ',"hotData":'
        create_Json += str(hot_disk)
        create_Json += ',"vCPUsMinValue":1,"vCPUsMaxValue":64,"vCPUsPerCoreMinValue":1,"vCPUsPerCoreMaxValue":15,"ramMinValue":0.25,"ramMaxValue":1024,"coldDataMinValue":1,"coldDataMaxValue":62000,"hotDataMinValue":1,"hotDataMaxValue":62000,"mhz":1867,"processorName":"E5-2680 v2","processorFamily":"Ivy Bridge","frequencyMinValue":187,"frequencyMaxValue":179200,"isDefaultProcessorSelected":true},"designId":1'
        create_Json += str(sizerID)
        create_Json += '}'

        percents = round((task_progress / all_cnt) * 100)
        uploadfile_update.progress = percents
        uploadfile_update.save()

        response = requests.post(url, headers=headers, verify=False, data=create_Json)

    #Get Inserted Workload List
    check_url = "https://sizer.nutanix.com/v3/scenarios/"+ Cur_Sizer_ID +"/workloads"
    response = requests.get(check_url, headers=headers, verify=False)

    jsondata = json.loads(response.text)
    jsondata = json.loads(jsondata['data'])

    for ins_item in row_item:

        checkwname = ins_item.workload_name
        check_bool = 0
        excel_detail_id = ins_item.id

        for i in range(len(jsondata)):
            jsonworkload = jsondata[i]
            search_name = jsonworkload['workloadName']

            if checkwname == search_name:
                check_bool = 1
        
        if check_bool == 0:
            excel_update = excel_item.objects.get(upload_file_id=unique_id, id=excel_detail_id)
            excel_update.api_insert = '저장 실패'
            excel_update.save()
        else:
            excel_update = excel_item.objects.get(upload_file_id=unique_id, id=excel_detail_id)
            excel_update.api_insert = '저장 성공'
            excel_update.save()

def progress_status(request):
    global check_firsttask
    if request.method == 'GET':
        curuser = request.user
        unique_id = request.session.get('seesion_uid')
        
        uploadfile_update = UploadedFile.objects.get(id=unique_id)
        wok = uploadfile_update.progress
        
        current_progress = wok

        if current_progress == 100:
            task_running_status = task_table.objects.filter(upload_file_id=unique_id, workstatus='I', taskuser=curuser).count()

            if task_running_status == 1:
                uploadfile_update = UploadedFile.objects.get(id=unique_id)
                tast_update = task_table.objects.get(upload_file_id=unique_id, workstatus='I', taskuser=curuser)
                uploadfile_update.workstatus = '작업 완료'
                uploadfile_update.progress = 0
                uploadfile_update.save()
                tast_update.workstatus = 'C'
                tast_update.progress = 100
                tast_update.save()
            
        return JsonResponse({'progress': current_progress})

def tasklist(request):
    if not request.user.is_authenticated:
        return render(request, 'common/login.html')
    
    curuser = request.user
    tasklist_data = task_table.objects.filter(taskuser=curuser).order_by('-taskdate_at')
    page = request.GET.get('page', '1')  # 페이지
    paginator = Paginator(tasklist_data, 11)  # 페이지당 10개씩 보여주기
    page_obj = paginator.get_page(page)

    context = {'uplist':page_obj, 'cru_User':curuser}

    return render(request, 'sizer/tasklist.html', context)

def task_detail_list(request, task_id):
    if not request.user.is_authenticated:
        return render(request, 'common/login.html')
    
    curuser = request.user
    tasklist_data = task_table.objects.get(id=task_id)
    upload_file_id = tasklist_data.upload_file_id
    detail_excelitem = excel_item.objects.filter(upload_file_id=upload_file_id)
    page = request.GET.get('page', '1')  # 페이지
    paginator = Paginator(detail_excelitem, 50)  # 페이지당 10개씩 보여주기
    page_obj = paginator.get_page(page)

    context = {'tasklist':page_obj, 'cru_User':curuser}

    return render(request, 'sizer/task_detail.html', context)

def download_file(request,filename):

    path = os.path.join(settings.BASE_DIR, "upload_file_folder", filename)

    with open(path, 'rb') as file:
        response = HttpResponse(file.read(), content_type='application/octet-stream')
        response['Content-Disposition'] = 'attachment; filename="{}"'.format(urlquote(filename))
        return response

def sample_download_file(request):
    filename = "NutanixSizerExcel(Sample).xlsx"
    path = os.path.join(settings.BASE_DIR, "upload_file_folder", filename)
    with open(path, 'rb') as file:
        response = HttpResponse(file.read(), content_type='application/octet-stream')
        response['Content-Disposition'] = 'attachment; filename="{}"'.format(urlquote(filename))
        return response

def retasklist(request, task_id):
    if request.method == 'POST':
        del_ids = request.POST.get('ids')
        retask_cook = request.POST.get('cook')
        del_ids = json.loads(del_ids)

        for delid in del_ids:
            retaskid = excel_item.objects.get(id=delid)
            retask_sizerid = retaskid.sizerID
            
            url = "https://sizer.nutanix.com/v1/design/"+ retask_sizerid +"/workloads"

            headers = {
                'Accept': 'application/json;charset=UTF-8',
                'cookie': retask_cook,
                'Content-Type': 'application/json;charset=UTF-8'
            }

            sizerID = retaskid.sizerID
            workload_name = retaskid.workload_name
            cluster_name = retaskid.cluster_name
            vm_qty = retaskid.vm_qty
            vCpu = retaskid.vCpu
            vcpu_pcore = retaskid.vcpu_pcore
            memory = retaskid.memory
            disk = retaskid.disk
            cold_disk = round((90 / 100) * disk)
            hot_disk = round((10 / 100) * disk)

            create_Json = ''
            create_Json += '{"data":{"containerRF":2,"compression":{"enabledForAF":true,"enabledForHybrid":true,"containerCompression":30,"preCompressed":true},"erasureCoding":false,"targetCluster":"Yes","targetClusterName":"'
            create_Json += str(cluster_name)
            create_Json += '","encryptedStorage":{"hardwareEncryption":false,"softwareEncryption":false},"dedupe":0,"dedicatedWorkloadCluster":false,"workloadName":"'
            create_Json += str(workload_name)
            create_Json += '","type":"serverVirtualization","serverProfileType":"Large","numberOfVMs":'
            create_Json += str(vm_qty)
            create_Json += ',"sizeByMhz":false,"workloadId":0,"manageVMsUsingCalm":false,"disabled":false,"corePerVm":'
            create_Json += str(vCpu)
            create_Json += ',"vCPUsPerCore":'
            create_Json += str(vcpu_pcore)
            create_Json += ',"RAM":'
            create_Json += str(memory)
            create_Json += ',"coldData":'
            create_Json += str(cold_disk)
            create_Json += ',"hotData":'
            create_Json += str(hot_disk)
            create_Json += ',"vCPUsMinValue":1,"vCPUsMaxValue":64,"vCPUsPerCoreMinValue":1,"vCPUsPerCoreMaxValue":15,"ramMinValue":0.25,"ramMaxValue":1024,"coldDataMinValue":1,"coldDataMaxValue":62000,"hotDataMinValue":1,"hotDataMaxValue":62000,"mhz":1867,"processorName":"E5-2680 v2","processorFamily":"Ivy Bridge","frequencyMinValue":187,"frequencyMaxValue":179200,"isDefaultProcessorSelected":true},"designId":1'
            create_Json += str(sizerID)
            create_Json += '}'

            response = requests.post(url, headers=headers, verify=False, data=create_Json)

            #Get Inserted Workload List
            check_url = "https://sizer.nutanix.com/v3/scenarios/"+ retask_sizerid +"/workloads"
            response = requests.get(check_url, headers=headers, verify=False)

            jsondata = json.loads(response.text)
            jsondata = json.loads(jsondata['data'])
            check_bool = 0

            for i in range(len(jsondata)):
                jsonworkload = jsondata[i]
                search_name = jsonworkload['workloadName']

                if workload_name == search_name:
                    check_bool = 1

            if check_bool == 0:
                excel_update = excel_item.objects.get(id=delid)
                excel_update.api_insert = '저장 실패'
                excel_update.save()
            else:
                excel_update = excel_item.objects.get(id=delid)
                excel_update.api_insert = '저장 성공'
                excel_update.save()

        return JsonResponse({'message': 'Retask successfully!'})