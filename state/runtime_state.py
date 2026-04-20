_state = {
    "current_role": None,
    "username": None,
    "login_timestamp": None,
    "patient_id": None,
    "samples": [],
    "tests": [],
    "balance": None,
    "approval_status": None,
}


def set_value(key, val):
    _state[key] = val


def get_value(key):
    return _state.get(key)


def clear():
    for key in _state:
        if isinstance(_state[key], list):
            _state[key] = []
        else:
            _state[key] = None


def add_sample(name, sub_department, id, index):
    _state["samples"].append({
        "name": name,
        "sub_department": sub_department,
        "id": id,
        "index": index,
    })


def get_samples():
    return _state["samples"]


def get_state_snapshot():
    return dict(_state)
