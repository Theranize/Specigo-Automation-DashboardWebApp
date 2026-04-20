"""DDT data fixtures — load JSON test data files for all roles."""

import pytest
from utils.file_utils import load_json

LOGIN_DATA_PATH = "test_data/login/login_ddt.json"
FRONT_DESK_PATIENT_DATA_PATH = "test_data/front_desk/patient_data.json"
FRONT_DESK_TEST_PAYMENT_DATA_PATH = "test_data/front_desk/test_payment_data.json"
PHLEBOTOMIST_ACTIONS_PATH = "test_data/phlebotomist/phlebotomist_actions.json"
ACCESSION_ACTIONS_PATH = "test_data/accession/accession_actions.json"
LABTECH_SEARCH_PATH = "test_data/lab_technician/labtech_search.json"
LABTECH_TESTS_PATH = "test_data/lab_technician/labtech_tests.json"
DOCTOR_ACTIONS_PATH = "test_data/doctor/doctor_actions.json"
REASSIGNMENT_ACTIONS_PATH = "test_data/accession/reassignment_actions.json"
DOCTOR_RECTIFY_ACTIONS_PATH = "test_data/doctor/doctor_rectify_actions.json"


@pytest.fixture
def login_credentials():
    return load_json(LOGIN_DATA_PATH)


@pytest.fixture
def front_desk_patient_data():
    return load_json(FRONT_DESK_PATIENT_DATA_PATH)


@pytest.fixture
def front_desk_test_payment_data():
    return load_json(FRONT_DESK_TEST_PAYMENT_DATA_PATH)


@pytest.fixture
def phlebotomist_actions_data():
    return load_json(PHLEBOTOMIST_ACTIONS_PATH)


@pytest.fixture
def accession_actions_data():
    return load_json(ACCESSION_ACTIONS_PATH)


@pytest.fixture
def labtech_search_data():
    return load_json(LABTECH_SEARCH_PATH)


@pytest.fixture
def labtech_tests_data():
    return load_json(LABTECH_TESTS_PATH)


@pytest.fixture
def doctor_actions_data():
    return load_json(DOCTOR_ACTIONS_PATH)


@pytest.fixture
def reassignment_actions_data():
    return load_json(REASSIGNMENT_ACTIONS_PATH)


@pytest.fixture
def doctor_rectify_actions_data():
    return load_json(DOCTOR_RECTIFY_ACTIONS_PATH)
