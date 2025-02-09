import json
from fastapi import HTTPException, status
import pytest

from mock import AsyncMock, patch
from models.domain.airlock_request import AirlockRequest, AirlockRequestStatus, AirlockRequestType
from models.domain.airlock_resource import AirlockResourceType
from service_bus.airlock_request_status_update import receive_step_result_message_and_update_status
from db.errors import EntityDoesNotExist
from resources import strings

WORKSPACE_ID = "abc000d3-82da-4bfc-b6e9-9a7853ef753e"
AIRLOCK_REQUEST_ID = "5dbc15ae-40e1-49a5-834b-595f59d626b7"
EVENT_ID = "0000c8e7-5c42-4fcb-a7fd-294cfc27aa76"

pytestmark = pytest.mark.asyncio

test_data = [
    'bad',
    '{"good": "json", "bad": "message"}'
]


test_sb_step_result_message = {
    "id": EVENT_ID,
    "subject": "main",
    "data":
    {
        "completed_step": "submitted",
        "new_status": "in_review",
        "request_id": AIRLOCK_REQUEST_ID

    },
    "eventType": "bla",
    "eventTime": "test message",
    "topic": ""
}

test_sb_step_result_message_with_invalid_status = {
    "id": EVENT_ID,
    "subject": "main",
    "data":
    {
        "completed_step": "submitted",
        "new_status": "approved",
        "request_id": AIRLOCK_REQUEST_ID

    },
    "eventType": "bla",
    "eventTime": "test message",
    "topic": ""
}


def sample_airlock_request(status=AirlockRequestStatus.Submitted):
    airlock_request = AirlockRequest(
        id=AIRLOCK_REQUEST_ID,
        resourceType=AirlockResourceType.AirlockRequest,
        workspaceId=WORKSPACE_ID,
        requestType=AirlockRequestType.Import,
        files=[],
        businessJustification="some test reason",
        status=status
    )
    return airlock_request


class ServiceBusReceivedMessageMock:
    def __init__(self, message: dict):
        self.message = json.dumps(message)
        self.correlation_id = "test_correlation_id"

    def __str__(self):
        return self.message


@patch("event_grid.helpers.EventGridPublisherClient")
@patch('service_bus.airlock_request_status_update.AirlockRequestRepository')
@patch('logging.error')
@patch('service_bus.airlock_request_status_update.ServiceBusClient')
@patch('fastapi.FastAPI')
async def test_receiving_good_message(app, sb_client, logging_mock, airlock_request_repo, eg_client):
    service_bus_received_message_mock = ServiceBusReceivedMessageMock(test_sb_step_result_message)

    sb_client().get_queue_receiver().receive_messages = AsyncMock(return_value=[service_bus_received_message_mock])
    sb_client().get_queue_receiver().complete_message = AsyncMock()
    eg_client().send = AsyncMock()
    expected_airlock_request = sample_airlock_request()
    airlock_request_repo().get_airlock_request_by_id.return_value = expected_airlock_request
    airlock_request_repo().update_airlock_request_status.return_value = sample_airlock_request(status=AirlockRequestStatus.InReview)
    await receive_step_result_message_and_update_status(app)

    airlock_request_repo().get_airlock_request_by_id.assert_called_once_with(test_sb_step_result_message["data"]["request_id"])
    airlock_request_repo().update_airlock_request_status.assert_called_once_with(expected_airlock_request, test_sb_step_result_message["data"]["new_status"], expected_airlock_request.user)
    assert eg_client().send.call_count == 2
    logging_mock.assert_not_called()
    sb_client().get_queue_receiver().complete_message.assert_called_once_with(service_bus_received_message_mock)


@pytest.mark.parametrize("payload", test_data)
@patch('logging.error')
@patch('service_bus.airlock_request_status_update.ServiceBusClient')
@patch('fastapi.FastAPI')
async def test_receiving_bad_json_logs_error(app, sb_client, logging_mock, payload):
    service_bus_received_message_mock = ServiceBusReceivedMessageMock(payload)
    sb_client().get_queue_receiver().receive_messages = AsyncMock(return_value=[service_bus_received_message_mock])
    sb_client().get_queue_receiver().complete_message = AsyncMock()
    await receive_step_result_message_and_update_status(app)

    error_message = logging_mock.call_args.args[0]
    assert error_message.startswith(strings.STEP_RESULT_MESSAGE_FORMAT_INCORRECT)
    sb_client().get_queue_receiver().complete_message.assert_called_once_with(service_bus_received_message_mock)


@patch('service_bus.airlock_request_status_update.AirlockRequestRepository')
@patch('logging.error')
@patch('service_bus.airlock_request_status_update.ServiceBusClient')
@patch('fastapi.FastAPI')
async def test_updating_non_existent_airlock_request_error_is_logged(app, sb_client, logging_mock, airlock_request_repo):
    service_bus_received_message_mock = ServiceBusReceivedMessageMock(test_sb_step_result_message)

    sb_client().get_queue_receiver().receive_messages = AsyncMock(return_value=[service_bus_received_message_mock])
    sb_client().get_queue_receiver().complete_message = AsyncMock()
    airlock_request_repo().get_airlock_request_by_id.side_effect = EntityDoesNotExist
    await receive_step_result_message_and_update_status(app)

    expected_error_message = strings.STEP_RESULT_ID_NOT_FOUND.format(test_sb_step_result_message["data"]["request_id"])
    logging_mock.assert_called_once_with(expected_error_message)
    sb_client().get_queue_receiver().complete_message.assert_called_once_with(service_bus_received_message_mock)


@patch('service_bus.airlock_request_status_update.AirlockRequestRepository')
@patch('logging.error')
@patch('service_bus.airlock_request_status_update.ServiceBusClient')
@patch('fastapi.FastAPI')
async def test_when_updating_and_state_store_exception_error_is_logged(app, sb_client, logging_mock, airlock_request_repo):
    service_bus_received_message_mock = ServiceBusReceivedMessageMock(test_sb_step_result_message)

    sb_client().get_queue_receiver().receive_messages = AsyncMock(return_value=[service_bus_received_message_mock])
    sb_client().get_queue_receiver().complete_message = AsyncMock()
    airlock_request_repo().get_airlock_request_by_id.side_effect = Exception
    await receive_step_result_message_and_update_status(app)

    logging_mock.assert_called_once_with(strings.STATE_STORE_ENDPOINT_NOT_RESPONDING + " ")
    sb_client().get_queue_receiver().complete_message.assert_not_called()


@patch('service_bus.airlock_request_status_update.AirlockRequestRepository')
@patch('logging.error')
@patch('service_bus.airlock_request_status_update.ServiceBusClient')
@patch('fastapi.FastAPI')
async def test_when_updating_and_current_status_differs_from_status_in_state_store_error_is_logged(app, sb_client, logging_mock, airlock_request_repo):
    service_bus_received_message_mock = ServiceBusReceivedMessageMock(test_sb_step_result_message)

    sb_client().get_queue_receiver().receive_messages = AsyncMock(return_value=[service_bus_received_message_mock])
    sb_client().get_queue_receiver().complete_message = AsyncMock()
    expected_airlock_request = sample_airlock_request(AirlockRequestStatus.Draft)
    airlock_request_repo().get_airlock_request_by_id.return_value = expected_airlock_request
    await receive_step_result_message_and_update_status(app)

    expected_error_message = strings.STEP_RESULT_MESSAGE_STATUS_DOES_NOT_MATCH.format(test_sb_step_result_message["data"]["request_id"], test_sb_step_result_message["data"]["completed_step"], expected_airlock_request.status)
    logging_mock.assert_called_once_with(expected_error_message)
    sb_client().get_queue_receiver().complete_message.assert_not_called()


@patch('service_bus.airlock_request_status_update.AirlockRequestRepository')
@patch('logging.error')
@patch('service_bus.airlock_request_status_update.ServiceBusClient')
@patch('fastapi.FastAPI')
async def test_when_updating_and_status_update_is_illegal_error_is_logged(app, sb_client, logging_mock, airlock_request_repo):
    service_bus_received_message_mock = ServiceBusReceivedMessageMock(test_sb_step_result_message_with_invalid_status)

    sb_client().get_queue_receiver().receive_messages = AsyncMock(return_value=[service_bus_received_message_mock])
    sb_client().get_queue_receiver().complete_message = AsyncMock()
    airlock_request_repo().get_airlock_request_by_id.side_effect = HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
    await receive_step_result_message_and_update_status(app)

    expected_error_message = strings.STEP_RESULT_MESSAGE_INVALID_STATUS.format(test_sb_step_result_message_with_invalid_status["data"]["request_id"], test_sb_step_result_message_with_invalid_status["data"]["completed_step"], test_sb_step_result_message_with_invalid_status["data"]["new_status"])
    logging_mock.assert_called_once_with(expected_error_message)
    sb_client().get_queue_receiver().complete_message.assert_called_once_with(service_bus_received_message_mock)
