
from pathlib import Path
import pytest
from yaml_autogen.outputs import default_values


def cmd_yaml(num, type, hidden=False):
    return (f"""
TEST_RESID:
  dedicated_commands:
    - cmd: TEST_CMD
      number_of_values: {num}
      type: CMD_READ_WRITE
      help: Audio Mgr pre SHF microphone gain
      value_type: {type}
      value_ranges:
          value0: any
      hidden: {hidden}
  shared_commands:
  external_commands:
""")

def default_yaml(default: str):
    return (f"""
TEST_RESID:
  - cmd: TEST_CMD
    default_value: {default}
""")

PROJECTS = ["3800", "3820"]

def run_single(val_type, i, tmp_path):
    cmd_file = tmp_path / "cmd.yml"
    cmd_file.write_text(cmd_yaml(1, val_type))
    default_file = tmp_path / "def.yml"
    default_file.write_text(default_yaml(i))

    _, render_data = default_values.generate_commands_data(cmd_file, False, False, default_file)
    test_cmd = render_data[0]
    
    default_values.format_default_value(test_cmd)
    return test_cmd["default_value"]

@pytest.mark.parametrize("val_type", ("TYPE_FLOAT", "TYPE_RADIANS"))
@pytest.mark.parametrize("i,o", [
    ("3f","3.0"), 
    ("3","3.0"), 
    ("3.0","3.0"),
    ("1e3dB", "1000.0"),
    ("-1e3dB", "-1000.0"),
    ("-1e3", "-1000.0"),
    ("1e-8f", "1e-08"),
    ("3.0f","3.0"),
    ("-3", "-3.0"),
    ("-3.0", "-3.0"),
    ("5dB", "5.0"),
    ("5.0dB", "5.0"),
    ("disabled", "-1.0"),
    ("on125", "2.0"),
])
def test_float(val_type, i, o, tmp_path: Path):
    """test valid float conversions"""
    assert run_single(val_type, i, tmp_path) == o


# TYPE_CHAR, TYPE_UINT8, TYPE_INT32, TYPE_FLOAT, TYPE_UINT32, TYPE_RADIANS
@pytest.mark.parametrize("val_type", ("TYPE_CHAR", "TYPE_UINT8", "TYPE_INT32", "TYPE_UINT32"))
@pytest.mark.parametrize("i,o", [
    ("3","3"), 
    ("-3", "-3"),
    ("5dB", "5"),
    ("disabled", "-1"),
    ("on125", "2"),
    ("TRUE", "1"),
    ("FALSE", "0"),
    ("false", "0"),
    ("on125", "2"),
])
def test_int(val_type, i, o, tmp_path: Path):
    """test valid int conversions"""
    assert run_single(val_type, i, tmp_path) == o


@pytest.mark.parametrize("val_type", ("TYPE_FLOAT", "TYPE_RADIANS"))
@pytest.mark.parametrize("val", (
    "TRUE", "FALSE", "a", "5DB", "ON125", "DiSaBlEd", "FaLsE", "DISABLED"
))
def test_unsupported_floats(val, val_type, tmp_path):
    """test invalid float conversions"""
    try:
        run_single(val_type, val, tmp_path)
    except ValueError:
        pass
    else:
        assert False, f"{val} is not a valid {val_type} but no exception was raised"

@pytest.mark.parametrize("val_type", ("TYPE_CHAR", "TYPE_UINT8", "TYPE_INT32", "TYPE_UINT32"))
@pytest.mark.parametrize("val", (
    "5.0", "a", "ON125", "DiSaBlEd", "FaLsE", "DISABLED"
))
def test_unsupported_ints(val, val_type, tmp_path):
    """test invalid int conversions"""
    try:
        run_single(val_type, val, tmp_path)
    except ValueError:
        pass
    else:
        assert False, f"{val} is not a valid {val_type} but no exception was raised"

def test_multi_float(tmp_path: Path):
    """test multi param defaults"""

    test_str = "(5f, 5.0f, 5dB, disabled, on125)"
    n_vals = len(test_str.split(","))
    expected = "{5.0, 5.0, 5.0, -1.0, 2.0}"

    cmd_file = tmp_path / "cmd.yml"
    cmd_file.write_text(cmd_yaml(n_vals, "TYPE_FLOAT"))
    default_file = tmp_path / "def.yml"
    default_file.write_text(default_yaml(test_str))

    _, render_data = default_values.generate_commands_data(cmd_file, False, False, default_file)
    test_cmd = render_data[0]
    
    default_values.format_default_value(test_cmd)
    assert test_cmd["default_value"] == expected, "formated value doesn't match expected"

