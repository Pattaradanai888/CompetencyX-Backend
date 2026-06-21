from rest_framework.exceptions import APIException


class AssessmentFlowError(APIException):
    status_code = 400
    default_detail = 'Assessment flow error.'
    default_code = 'assessment_flow_error'
