from rest_framework import status
from rest_framework.exceptions import APIException


class AssessmentFlowError(APIException):
    status_code = 400
    default_detail = 'Assessment flow error.'
    default_code = 'assessment_flow_error'


class AssessmentNotCompleted(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = 'Assessment results are only available after completion.'
    default_code = 'assessment_not_completed'
