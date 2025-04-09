import json
from django.shortcuts import render, HttpResponse
from django.conf import settings

from .client import FSKXOAuth2Client


def fskx_run_test(request, model_type=0):
    client = FSKXOAuth2Client()
    if model_type == 0:
        model_id = settings.FSKX_SETTINGS['MODELS']['FSKX_SIMPLE_KOSEKI_ID']
        parameters = {
            "temp_celsius": 20,
            "y0": 4,
            "b": 0.033,
            "Tmin": 4.96,
            "alpha0": 0.097,
            "tmax": 72
        }
    elif model_type == 1:
        model_id = settings.FSKX_SETTINGS['MODELS']['SIMPLE_QMRA_ID']
        parameters = {
            "runs": 100,
            "meanTemp": 5.9,
            "sdTemp": 2.9,
            "Tmin": -1.18,
            "Input_prev": "prev_inputs3.csv",
            "Input_conc": "conc_inputs3.csv"
        }


    simulation_data = client.run_simulation(
        model_id,
        params=parameters
    )
    return HttpResponse(json.dumps(simulation_data))


def fskx_status_test(request, simulation_id):
    client = FSKXOAuth2Client()
    simulation_status = client.get_simulation_status(simulation_id)

    return HttpResponse(json.dumps(simulation_status))


def fskx_res_test(request, simulation_id):
    file_type = request.GET.get('file_type', 'json')
    client = FSKXOAuth2Client()
    simulation_res = client.get_simulation_result(simulation_id, file_type=file_type)

    if file_type != 'json':
        return HttpResponse(simulation_res.content, content_type=simulation_res.headers.get('Content-Type', 'image/png'))
    else:
        return HttpResponse(json.dumps(simulation_res))
